"""
╔═══════════════════════════════════════════════════════════════╗
║         GADGET PREMIUM HOST - Configuration Module            ║
║              Next-Gen Telegram Hosting Bot                    ║
║                   By: @shuvohassan00                          ║
╚═══════════════════════════════════════════════════════════════╝
"""

import os
from typing import List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════════
# 🔐 BOT CONFIGURATION
# ═══════════════════════════════════════════════════════════════

BOT_TOKEN = os.getenv("BOT_TOKEN", "8581813381:AAFZdh0f5u_BnFTE62jPGX5-GQPccnv54Jo")

# Owner Configuration
OWNER_ID = 7857957075  # @shuvohassan00
OWNER_USERNAME = "@shuvohassan00"

# Admin IDs (can be expanded)
ADMIN_IDS: List[int] = [7857957075]

# ═══════════════════════════════════════════════════════════════
# 📢 FORCE SUBSCRIBE CHANNELS
# ═══════════════════════════════════════════════════════════════

class ChannelType(Enum):
    PUBLIC = "public"
    PRIVATE = "private"


@dataclass
class ForceSubscribeChannel:
    """Represents a force subscribe channel"""
    chat_id: str
    invite_link: str
    name: str
    channel_type: ChannelType
    required: bool = True


# Required Channels for Force Subscribe
FORCE_SUBSCRIBE_CHANNELS: List[ForceSubscribeChannel] = [
    ForceSubscribeChannel(
        chat_id="@gadgetpremiumzone",
        invite_link="https://t.me/gadgetpremiumzone",
        name="📢 GADGET PREMIUM ZONE",
        channel_type=ChannelType.PUBLIC,
        required=True
    ),
    ForceSubscribeChannel(
        chat_id="-1002429023073",  # Replace with actual private channel ID
        invite_link="https://t.me/+HSqmdVuHFr84MzRl",
        name="💎 PREMIUM VIP ZONE",
        channel_type=ChannelType.PRIVATE,
        required=True
    ),
]

# ═══════════════════════════════════════════════════════════════
# 🎨 BRAND IDENTITY & UI STRINGS
# ═══════════════════════════════════════════════════════════════

BRAND_NAME = "GADGET PREMIUM HOST"
BRAND_TAGLINE = "⚡ Next-Gen Python Hosting Platform"
BRAND_VERSION = "3.0.0 CYBER"
BRAND_LOGO = "🛡️"
BRAND_FOOTER = f"""
╔══════════════════════════════════════╗
║  {BRAND_LOGO} {BRAND_NAME} v{BRAND_VERSION}
║  👑 Owner: {OWNER_USERNAME}
║  ⚡ Powered by GADGET TECH
╚══════════════════════════════════════╝
"""

# Cyberpunk Color Codes (for reference - Telegram uses HTML)
CYBERPUNK_COLORS = {
    "neon_pink": "#FF00FF",
    "neon_blue": "#00FFFF",
    "neon_green": "#00FF00",
    "neon_yellow": "#FFFF00",
    "dark_bg": "#0D0D0D",
    "glass_bg": "#1A1A2E",
    "accent": "#7B2CBF"
}

# ═══════════════════════════════════════════════════════════════
# 💎 PLAN CONFIGURATIONS
# ═══════════════════════════════════════════════════════════════

@dataclass
class HostingPlan:
    """Represents a hosting plan"""
    name: str
    slots: int  # -1 for unlimited
    max_file_size_mb: int
    max_processes: int
    cpu_limit: int  # percentage
    memory_limit_mb: int
    features: List[str]
    price: str
    duration_days: int  # -1 for lifetime


PLANS: Dict[str, HostingPlan] = {
    "free": HostingPlan(
        name="🆓 FREE PLAN",
        slots=1,
        max_file_size_mb=10,
        max_processes=1,
        cpu_limit=25,
        memory_limit_mb=256,
        features=[
            "1 Bot Slot",
            "10MB Max File Size",
            "Basic Support",
            "24/7 Uptime"
        ],
        price="FREE",
        duration_days=-1
    ),
    "premium": HostingPlan(
        name="💎 PREMIUM PLAN",
        slots=-1,  # Unlimited
        max_file_size_mb=100,
        max_processes=10,
        cpu_limit=100,
        memory_limit_mb=1024,
        features=[
            "♾️ Unlimited Bot Slots",
            "100MB Max File Size",
            "Priority Support",
            "24/7 Uptime",
            "Custom Process Names",
            "Advanced Logs",
            "Git Clone Support",
            "Module Installer"
        ],
        price="৳500 BDT / $5 USD",
        duration_days=30
    ),
    "ultimate": HostingPlan(
        name="🚀 ULTIMATE PLAN",
        slots=-1,
        max_file_size_mb=500,
        max_processes=20,
        cpu_limit=100,
        memory_limit_mb=2048,
        features=[
            "♾️ Unlimited Bot Slots",
            "500MB Max File Size",
            "VIP Support",
            "99.9% Uptime SLA",
            "Custom Process Names",
            "Advanced Logs",
            "Git Clone Support",
            "Module Installer",
            "Auto-Restart on Crash",
            "Custom Environment Variables",
            "Priority Server Resources"
        ],
        price="৳1000 BDT / $10 USD",
        duration_days=30
    ),
}

# ═══════════════════════════════════════════════════════════════
# 📊 SERVER CONFIGURATION
# ═══════════════════════════════════════════════════════════════

# Server Limits
MAX_TOTAL_PROCESSES = 100
MAX_TOTAL_USERS = 1000
MAX_FILE_SIZE_MB = 500

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
USER_FILES_DIR = os.path.join(BASE_DIR, "user_files")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
DATABASE_PATH = os.path.join(DATA_DIR, "gadget_host.db")

# Ensure directories exist
for directory in [DATA_DIR, USER_FILES_DIR, LOGS_DIR]:
    os.makedirs(directory, exist_ok=True)

# ═══════════════════════════════════════════════════════════════
# 🔄 PROCESS MANAGEMENT
# ═══════════════════════════════════════════════════════════════

PYTHON_EXECUTABLE = "python3"
PIP_EXECUTABLE = "pip3"

# Process Status
class ProcessStatus(Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    CRASHED = "crashed"
    RESTARTING = "restarting"
    UNKNOWN = "unknown"

# ═══════════════════════════════════════════════════════════════
# 🎁 REFERRAL SYSTEM
# ═══════════════════════════════════════════════════════════════

REFERRAL_BONUS_SLOTS = 1
REFERRAL_BONUS_CREDITS = 10
MIN_WITHDRAWAL_CREDITS = 100

# ═══════════════════════════════════════════════════════════════
# 🛡️ SECURITY SETTINGS
# ═══════════════════════════════════════════════════════════════

# Banned file extensions
BANNED_EXTENSIONS = [".exe", ".bat", ".cmd", ".sh", ".msi", ".dll", ".so"]

# Dangerous Python modules (will be flagged in syntax check)
DANGEROUS_MODULES = [
    "os.system", "subprocess.call", "subprocess.run", 
    "eval", "exec", "compile", "__import__",
    "socket.socket", "ctypes", "multiprocessing"
]

# Rate limiting
MAX_COMMANDS_PER_MINUTE = 30
MAX_UPLOADS_PER_HOUR = 10

# ═══════════════════════════════════════════════════════════════
# 📱 UI MESSAGES
# ═══════════════════════════════════════════════════════════════

MESSAGES = {
    "welcome": """
🛡️ <b>Welcome to {brand_name}!</b>
⚡ <i>{tagline}</i>

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ <b>🚀 HOST YOUR PYTHON BOTS</b>
┃ <b>💎 24/7 UPTIME GUARANTEED</b>
┃ <b>⚡ LIGHTNING FAST SERVERS</b>
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

👤 <b>User:</b> {user_name}
🆔 <b>ID:</b> <code>{user_id}</code>
💎 <b>Plan:</b> {plan_name}
📊 <b>Slots:</b> {slots_used}/{slots_max}

{force_sub_warning}
<b>⚡ Click a button below to get started!</b>
""",
    "force_subscribe": """
⚠️ <b>ACCESS DENIED!</b>

🔒 <b>You must join our channels to use this bot!</b>

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 📢 <b>Required Channels:</b>
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

{channel_list}

<i>💎 Join all channels and click "🔄 Verify Status"</i>
""",
    "maintenance": """
⚠️ <b>MAINTENANCE BREAK!</b>

🔧 <i>We are currently updating our systems...</i>

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 🛠️ <b>What's happening:</b>
┃ • Server Optimization
┃ • New Features Added
┃ • Security Updates
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

⏰ <b>Estimated Time:</b> {eta}

<i>💎 Please check back later!</i>
""",
    "server_stats": """
📊 <b>LIVE SERVER STATISTICS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🖥️ <b>CPU USAGE:</b>
{cpu_bar} <b>{cpu_percent}%</b>

💾 <b>RAM USAGE:</b>
{ram_bar} <b>{ram_used:.1f}GB / {ram_total:.1f}GB</b>

💿 <b>DISK USAGE:</b>
{disk_bar} <b>{disk_percent}%</b>

⏱️ <b>UPTIME:</b> <code>{uptime}</code>

📡 <b>Active Processes:</b> {active_processes}
👥 <b>Total Users:</b> {total_users}
🤖 <b>Running Bots:</b> {running_bots}

━━━━━━━━━━━━━━━━━━━━━━━━━━
<i>📈 Updated in real-time</i>
""",
    "user_info": """
👤 <b>USER INTELLIGENCE REPORT</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🆔 <b>User ID:</b> <code>{user_id}</code>
👤 <b>Name:</b> {user_name}
👤 <b>Username:</b> @{username}
💎 <b>Plan:</b> {plan_name}
📅 <b>Joined:</b> {join_date}

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 💰 <b>WALLET STATUS</b>
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ 💵 Credits: {credits}
┃ 🎁 Referrals: {referrals}
┃ 📊 Slots: {slots_used}/{slots_max}
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 🤖 <b>ACTIVE PROCESSES</b>
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
{processes_list}
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

<b>Status:</b> {status_emoji} {status_text}
""",
    "syntax_error": """
⚠️ <b>CODE ERROR DETECTED!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 <b>Syntax Analysis Failed!</b>

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 📍 <b>Line:</b> <code>{line}</code>
┃ ❌ <b>Error:</b> {error_msg}
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

<i>🛡️ Please fix the error and try again!</i>
""",
    "file_uploaded": """
✅ <b>FILE UPLOADED SUCCESSFULLY!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

📄 <b>File:</b> <code>{filename}</code>
📏 <b>Size:</b> {file_size}
🔍 <b>Syntax:</b> ✅ Valid Python

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ⚡ <b>READY TO DEPLOY!</b>
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

<i>🚀 Click "Start" to run your bot!</i>
""",
    "process_started": """
🚀 <b>BOT DEPLOYED SUCCESSFULLY!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🤖 <b>Bot:</b> <code>{bot_name}</code>
🔢 <b>PID:</b> <code>{pid}</code>
⏰ <b>Started:</b> {start_time}

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ✅ <b>STATUS: RUNNING</b>
┃ 💻 <b>Process Active</b>
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

<i>⚡ Your bot is now online 24/7!</i>
""",
    "broadcast_sent": """
📢 <b>BROADCAST COMPLETED!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ <b>Successfully Sent:</b> {success_count}
❌ <b>Failed:</b> {failed_count}
📊 <b>Total Users:</b> {total_count}

<i>💎 Message delivered to all users!</i>
"""
}

# ═══════════════════════════════════════════════════════════════
# ⚙️ FEATURE FLAGS
# ═══════════════════════════════════════════════════════════════

FEATURES = {
    "git_clone": True,
    "module_installer": True,
    "auto_restart": True,
    "syntax_check": True,
    "referral_system": True,
    "maintenance_mode": False,
    "broadcast_system": True,
    "terminal_access": True,  # Owner only
    "server_monitoring": True,
    "user_spy_mode": True,
}

# ═══════════════════════════════════════════════════════════════
# 📝 LOGGING CONFIGURATION
# ═══════════════════════════════════════════════════════════════

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "cyberpunk": {
            "format": "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "cyberpunk",
            "level": "INFO"
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOGS_DIR, "bot.log"),
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "formatter": "cyberpunk",
            "level": "DEBUG"
        }
    },
    "loggers": {
        "aiogram": {"level": "INFO"},
        "gadget_host": {"level": "DEBUG"}
    },
    "root": {
        "level": "INFO",
        "handlers": ["console", "file"]
    }
}
