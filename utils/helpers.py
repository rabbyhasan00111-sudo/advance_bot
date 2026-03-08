"""
╔═══════════════════════════════════════════════════════════════╗
║         GADGET PREMIUM HOST - Utilities Module                ║
║              Helper Functions & Decorators                    ║
╚═══════════════════════════════════════════════════════════════╝
"""

import ast
import sys
import os
import psutil
import hashlib
import asyncio
import logging
import time
import traceback
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict, Any, Callable
from functools import wraps
from io import BytesIO

from aiogram import Bot
from aiogram.types import User, Message, CallbackQuery
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from config import (
    OWNER_ID, ADMIN_IDS, DANGEROUS_MODULES, BANNED_EXTENSIONS,
    MESSAGES, FORCE_SUBSCRIBE_CHANNELS, BRAND_NAME, BRAND_TAGLINE,
    USER_FILES_DIR, MAX_FILE_SIZE_MB, MAX_COMMANDS_PER_MINUTE
)

logger = logging.getLogger("gadget_host.utils")


# ═══════════════════════════════════════════════════════════════
# 🛡️ SYNTAX GUARD - AST Analyzer
# ═══════════════════════════════════════════════════════════════

class SyntaxGuard:
    """
    Advanced Python Syntax Analyzer and Security Checker.
    Validates Python code before execution.
    """
    
    DANGEROUS_FUNCTIONS = {
        'eval', 'exec', 'compile', '__import__',
        'globals', 'locals', 'vars', 'dir'
    }
    
    DANGEROUS_IMPORTS = {
        'subprocess', 'os.system', 'ctypes', 'multiprocessing',
        'socket', 'pickle', 'marshal', 'shelve'
    }
    
    def __init__(self, code: str):
        self.code = code
        self.errors: List[Dict] = []
        self.warnings: List[Dict] = []
        self.imports: List[str] = []
        self.functions: List[str] = []
        self.classes: List[str] = []
        
    def analyze(self) -> Tuple[bool, Dict]:
        """
        Analyze the Python code for syntax errors and security issues.
        Returns (is_valid, analysis_result)
        """
        result = {
            'valid': False,
            'errors': [],
            'warnings': [],
            'imports': [],
            'functions': [],
            'classes': [],
            'stats': {}
        }
        
        # Step 1: Parse AST
        try:
            tree = ast.parse(self.code)
            result['valid'] = True
        except SyntaxError as e:
            result['errors'].append({
                'type': 'syntax',
                'line': e.lineno or 0,
                'col': e.offset or 0,
                'message': str(e.msg),
                'full_message': str(e)
            })
            result['valid'] = False
            return result['valid'], result
        except Exception as e:
            result['errors'].append({
                'type': 'parse',
                'line': 0,
                'col': 0,
                'message': f"Failed to parse code: {str(e)}",
                'full_message': str(e)
            })
            result['valid'] = False
            return result['valid'], result
        
        # Step 2: Walk the AST
        for node in ast.walk(tree):
            # Track imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.imports.append(alias.name)
                    self._check_dangerous_import(alias.name, node.lineno, result)
                    
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                self.imports.append(module)
                self._check_dangerous_import(module, node.lineno, result)
                
                for alias in node.names:
                    full_name = f"{module}.{alias.name}"
                    self._check_dangerous_import(full_name, node.lineno, result)
            
            # Track function definitions
            elif isinstance(node, ast.FunctionDef):
                self.functions.append(node.name)
                
            # Track class definitions
            elif isinstance(node, ast.ClassDef):
                self.classes.append(node.name)
            
            # Check for dangerous function calls
            elif isinstance(node, ast.Call):
                self._check_dangerous_call(node, result)
        
        # Step 3: Compile to bytecode (final check)
        try:
            compile(self.code, '<string>', 'exec')
        except Exception as e:
            result['errors'].append({
                'type': 'compile',
                'line': getattr(e, 'lineno', 0),
                'col': getattr(e, 'offset', 0),
                'message': str(e),
                'full_message': str(e)
            })
            result['valid'] = False
        
        result['imports'] = self.imports
        result['functions'] = self.functions
        result['classes'] = self.classes
        result['stats'] = {
            'lines': len(self.code.splitlines()),
            'imports': len(self.imports),
            'functions': len(self.functions),
            'classes': len(self.classes)
        }
        
        return result['valid'], result
    
    def _check_dangerous_import(self, module: str, line: int, result: Dict):
        """Check if import is potentially dangerous"""
        for dangerous in self.DANGEROUS_IMPORTS:
            if dangerous in module:
                result['warnings'].append({
                    'type': 'dangerous_import',
                    'line': line,
                    'message': f"Potentially dangerous import: {module}",
                    'severity': 'high'
                })
    
    def _check_dangerous_call(self, node: ast.Call, result: Dict):
        """Check for dangerous function calls"""
        if isinstance(node.func, ast.Name):
            if node.func.id in self.DANGEROUS_FUNCTIONS:
                result['warnings'].append({
                    'type': 'dangerous_call',
                    'line': node.lineno,
                    'message': f"Potentially dangerous function: {node.func.id}()",
                    'severity': 'high'
                })
        
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in ['system', 'popen', 'spawn', 'call', 'run']:
                result['warnings'].append({
                    'type': 'dangerous_call',
                    'line': node.lineno,
                    'message': f"Potentially dangerous method: {attr_name}()",
                    'severity': 'medium'
                })


def validate_python_code(code: str) -> Tuple[bool, Dict]:
    """
    Validate Python code for syntax errors.
    Returns (is_valid, result_dict)
    """
    guard = SyntaxGuard(code)
    return guard.analyze()


def format_syntax_error(error: Dict) -> str:
    """Format a syntax error for display"""
    return MESSAGES['syntax_error'].format(
        line=error.get('line', '?'),
        error_msg=error.get('message', 'Unknown error')
    )


# ═══════════════════════════════════════════════════════════════
# 📊 SERVER MONITOR
# ═══════════════════════════════════════════════════════════════

class ServerMonitor:
    """
    Real-time server monitoring using psutil.
    Provides CPU, RAM, Disk, and Network statistics.
    """
    
    @staticmethod
    def get_uptime() -> str:
        """Get system uptime as formatted string"""
        boot_time = psutil.boot_time()
        uptime = datetime.now() - datetime.fromtimestamp(boot_time)
        
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days} Day{'s' if days > 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} Hour{'s' if hours > 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} Min{'s' if minutes > 1 else ''}")
        
        return ", ".join(parts) if parts else "Just Started"
    
    @staticmethod
    def get_cpu_usage() -> float:
        """Get CPU usage percentage"""
        return psutil.cpu_percent(interval=1)
    
    @staticmethod
    def get_cpu_cores() -> int:
        """Get number of CPU cores"""
        return psutil.cpu_count(logical=True)
    
    @staticmethod
    def get_ram_usage() -> Tuple[float, float, float]:
        """
        Get RAM usage.
        Returns (used_gb, total_gb, percent)
        """
        mem = psutil.virtual_memory()
        used_gb = mem.used / (1024 ** 3)
        total_gb = mem.total / (1024 ** 3)
        percent = mem.percent
        return used_gb, total_gb, percent
    
    @staticmethod
    def get_disk_usage() -> Tuple[float, float, float]:
        """
        Get Disk usage.
        Returns (used_gb, total_gb, percent)
        """
        disk = psutil.disk_usage('/')
        used_gb = disk.used / (1024 ** 3)
        total_gb = disk.total / (1024 ** 3)
        percent = disk.percent
        return used_gb, total_gb, percent
    
    @staticmethod
    def get_network_stats() -> Dict:
        """Get network statistics"""
        net = psutil.net_io_counters()
        return {
            'bytes_sent': net.bytes_sent / (1024 ** 2),  # MB
            'bytes_recv': net.bytes_recv / (1024 ** 2),  # MB
            'packets_sent': net.packets_sent,
            'packets_recv': net.packets_recv
        }
    
    @staticmethod
    def get_process_count() -> int:
        """Get total process count"""
        return len(psutil.pids())
    
    @staticmethod
    def get_load_average() -> Tuple[float, float, float]:
        """Get system load average (1, 5, 15 minutes)"""
        try:
            return os.getloadavg()
        except:
            return (0.0, 0.0, 0.0)
    
    @classmethod
    def get_full_stats(cls) -> Dict:
        """Get all server statistics"""
        ram_used, ram_total, ram_percent = cls.get_ram_usage()
        disk_used, disk_total, disk_percent = cls.get_disk_usage()
        
        return {
            'cpu_percent': cls.get_cpu_usage(),
            'cpu_cores': cls.get_cpu_cores(),
            'ram_used': ram_used,
            'ram_total': ram_total,
            'ram_percent': ram_percent,
            'disk_used': disk_used,
            'disk_total': disk_total,
            'disk_percent': disk_percent,
            'uptime': cls.get_uptime(),
            'network': cls.get_network_stats(),
            'process_count': cls.get_process_count(),
            'load_average': cls.get_load_average()
        }


def create_progress_bar(percent: float, length: int = 10) -> str:
    """
    Create a visual progress bar.
    Returns: [██████░░░░] 60%
    """
    filled = int(length * percent / 100)
    empty = length - filled
    
    bar = "█" * filled + "░" * empty
    return f"[{bar}]"


def format_server_stats(stats: Dict, active_processes: int = 0,
                        total_users: int = 0, running_bots: int = 0) -> str:
    """Format server stats for display"""
    return MESSAGES['server_stats'].format(
        cpu_bar=create_progress_bar(stats['cpu_percent']),
        cpu_percent=stats['cpu_percent'],
        ram_bar=create_progress_bar(stats['ram_percent']),
        ram_used=stats['ram_used'],
        ram_total=stats['ram_total'],
        disk_bar=create_progress_bar(stats['disk_percent']),
        disk_percent=stats['disk_percent'],
        uptime=stats['uptime'],
        active_processes=stats['process_count'],
        total_users=total_users,
        running_bots=running_bots
    )


# ═══════════════════════════════════════════════════════════════
# 🔐 PERMISSION DECORATORS
# ═══════════════════════════════════════════════════════════════

def is_owner(user_id: int) -> bool:
    """Check if user is the bot owner"""
    return user_id == OWNER_ID


def is_admin(user_id: int) -> bool:
    """Check if user is an admin"""
    return user_id in ADMIN_IDS or user_id == OWNER_ID


def owner_only(func: Callable) -> Callable:
    """Decorator to restrict function to owner only"""
    @wraps(func)
    async def wrapper(event, *args, **kwargs):
        user_id = None
        
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            
        if user_id != OWNER_ID:
            if isinstance(event, Message):
                await event.answer(
                    "⛔ <b>ACCESS DENIED!</b>\n\n"
                    "🛡️ This command is restricted to the <b>Bot Owner</b> only.\n"
                    f"👑 Owner: @{OWNER_ID}",
                    parse_mode="HTML"
                )
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔ Owner Only!", show_alert=True)
            return
            
        return await func(event, *args, **kwargs)
    return wrapper


def admin_only(func: Callable) -> Callable:
    """Decorator to restrict function to admins only"""
    @wraps(func)
    async def wrapper(event, *args, **kwargs):
        user_id = None
        
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            
        if not is_admin(user_id):
            if isinstance(event, Message):
                await event.answer(
                    "⛔ <b>ACCESS DENIED!</b>\n\n"
                    "🛡️ This command is restricted to <b>Administrators</b> only.",
                    parse_mode="HTML"
                )
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔ Admin Only!", show_alert=True)
            return
            
        return await func(event, *args, **kwargs)
    return wrapper


# ═══════════════════════════════════════════════════════════════
# 📢 FORCE SUBSCRIBE CHECKER
# ═══════════════════════════════════════════════════════════════

async def check_force_subscribe(bot: Bot, user_id: int) -> Tuple[bool, List[Dict]]:
    """
    Check if user has joined all required channels.
    Returns (all_joined, missing_channels)
    """
    missing_channels = []
    
    for channel in FORCE_SUBSCRIBE_CHANNELS:
        try:
            chat_id = channel.chat_id
            
            # Handle private channels with invite links
            if channel.channel_type.value == "private":
                # For private channels, we check via invite link
                # Note: This requires the bot to be admin in the channel
                chat_id = channel.chat_id
            
            member = await bot.get_chat_member(chat_id, user_id)
            
            # Check if user is actually a member
            if member.status in ['left', 'kicked', 'restricted']:
                missing_channels.append({
                    'name': channel.name,
                    'link': channel.invite_link,
                    'joined': False
                })
            else:
                missing_channels.append({
                    'name': channel.name,
                    'link': channel.invite_link,
                    'joined': True
                })
                
        except TelegramBadRequest:
            # Channel not found or bot not admin
            missing_channels.append({
                'name': channel.name,
                'link': channel.invite_link,
                'joined': False
            })
        except Exception as e:
            logger.error(f"Error checking channel subscription: {e}")
            missing_channels.append({
                'name': channel.name,
                'link': channel.invite_link,
                'joined': False
            })
    
    all_joined = all(ch['joined'] for ch in missing_channels)
    return all_joined, missing_channels


def format_force_subscribe_message(channels: List[Dict]) -> str:
    """Format the force subscribe message"""
    channel_list = ""
    for ch in channels:
        status = "✅" if ch['joined'] else "❌"
        channel_list += f"\n{status} <a href=\"{ch['link']}\">{ch['name']}</a>"
    
    return MESSAGES['force_subscribe'].format(channel_list=channel_list)


# ═══════════════════════════════════════════════════════════════
# 📁 FILE UTILITIES
# ═══════════════════════════════════════════════════════════════

def get_file_hash(file_data: bytes) -> str:
    """Get MD5 hash of file data"""
    return hashlib.md5(file_data).hexdigest()


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def is_valid_file_extension(filename: str) -> bool:
    """Check if file extension is allowed"""
    ext = os.path.splitext(filename)[1].lower()
    return ext not in BANNED_EXTENSIONS


def get_user_directory(user_id: int) -> str:
    """Get or create user's file directory"""
    user_dir = os.path.join(USER_FILES_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    return user_dir


def cleanup_old_files(directory: str, max_age_days: int = 30):
    """Clean up files older than max_age_days"""
    now = datetime.now()
    
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        
        if os.path.isfile(filepath):
            file_mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
            age = now - file_mtime
            
            if age.days > max_age_days:
                try:
                    os.remove(filepath)
                    logger.info(f"Cleaned up old file: {filename}")
                except Exception as e:
                    logger.error(f"Error cleaning up file: {e}")


# ═══════════════════════════════════════════════════════════════
# 🔄 RATE LIMITER
# ═══════════════════════════════════════════════════════════════

class RateLimiter:
    """
    Simple in-memory rate limiter.
    Tracks user commands per minute.
    """
    
    def __init__(self):
        self._requests: Dict[int, List[float]] = {}
    
    def is_allowed(self, user_id: int, max_requests: int = MAX_COMMANDS_PER_MINUTE,
                   window_seconds: int = 60) -> Tuple[bool, int]:
        """
        Check if request is allowed.
        Returns (is_allowed, remaining_requests)
        """
        now = time.time()
        
        if user_id not in self._requests:
            self._requests[user_id] = []
        
        # Clean old requests
        self._requests[user_id] = [
            t for t in self._requests[user_id]
            if now - t < window_seconds
        ]
        
        # Check limit
        if len(self._requests[user_id]) >= max_requests:
            return False, 0
        
        # Add new request
        self._requests[user_id].append(now)
        remaining = max_requests - len(self._requests[user_id])
        
        return True, remaining
    
    def get_retry_after(self, user_id: int, window_seconds: int = 60) -> int:
        """Get seconds until rate limit resets"""
        if user_id not in self._requests or not self._requests[user_id]:
            return 0
        
        oldest = min(self._requests[user_id])
        retry_after = int(window_seconds - (time.time() - oldest))
        
        return max(0, retry_after)


# Global rate limiter instance
rate_limiter = RateLimiter()


def rate_limit(func: Callable) -> Callable:
    """Decorator for rate limiting commands"""
    @wraps(func)
    async def wrapper(event, *args, **kwargs):
        user_id = None
        
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        
        # Skip rate limit for owner
        if user_id == OWNER_ID:
            return await func(event, *args, **kwargs)
        
        allowed, remaining = rate_limiter.is_allowed(user_id)
        
        if not allowed:
            retry_after = rate_limiter.get_retry_after(user_id)
            msg = (
                f"⚠️ <b>Rate Limit Exceeded!</b>\n\n"
                f"🕐 Please wait <b>{retry_after} seconds</b> before trying again."
            )
            
            if isinstance(event, Message):
                await event.answer(msg, parse_mode="HTML")
            elif isinstance(event, CallbackQuery):
                await event.answer(f"Rate limit! Wait {retry_after}s", show_alert=True)
            return
        
        return await func(event, *args, **kwargs)
    
    return wrapper


# ═══════════════════════════════════════════════════════════════
# 🛠️ GENERAL UTILITIES
# ═══════════════════════════════════════════════════════════════

def escape_html(text: str) -> str:
    """Escape HTML special characters"""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def truncate_text(text: str, max_length: int = 4000) -> str:
    """Truncate text to fit Telegram message limit"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def get_user_display_name(user: User) -> str:
    """Get user's display name"""
    if user.first_name:
        name = user.first_name
        if user.last_name:
            name += f" {user.last_name}"
        return name
    return user.username or f"User {user.id}"


def parse_time_string(time_str: str) -> Optional[timedelta]:
    """
    Parse time string like '1d', '2h', '30m' into timedelta.
    Examples: '1d2h', '30m', '1w', '2h30m'
    """
    import re
    
    pattern = r'(\d+)([dhmws])'
    matches = re.findall(time_str.lower())
    
    if not matches:
        return None
    
    kwargs = {}
    for value, unit in matches:
        value = int(value)
        if unit == 's':
            kwargs['seconds'] = value
        elif unit == 'm':
            kwargs['minutes'] = value
        elif unit == 'h':
            kwargs['hours'] = value
        elif unit == 'd':
            kwargs['days'] = value
        elif unit == 'w':
            kwargs['weeks'] = value
    
    return timedelta(**kwargs) if kwargs else None


async def run_shell_command(command: str, timeout: int = 60) -> Tuple[int, str, str]:
    """
    Run a shell command asynchronously.
    Returns (return_code, stdout, stderr)
    """
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout
        )
        
        return (
            process.returncode,
            stdout.decode('utf-8', errors='replace'),
            stderr.decode('utf-8', errors='replace')
        )
        
    except asyncio.TimeoutError:
        return (-1, "", "Command timed out")
    except Exception as e:
        return (-1, "", str(e))


def split_list(lst: List, chunk_size: int) -> List[List]:
    """Split list into chunks"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def generate_referral_code(user_id: int) -> str:
    """Generate a unique referral code for user"""
    import base64
    data = f"REF_{user_id}_{int(time.time())}"
    return base64.urlsafe_b64encode(data.encode()).decode()[:12].upper()


def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime object to string"""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except:
            return dt
    return dt.strftime(format_str)


def get_plan_display(plan: str) -> str:
    """Get plan display name"""
    from config import PLANS
    return PLANS.get(plan, PLANS['free']).name
