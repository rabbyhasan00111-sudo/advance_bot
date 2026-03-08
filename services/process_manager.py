"""
╔═══════════════════════════════════════════════════════════════╗
║         GADGET PREMIUM HOST - Process Manager                 ║
║              Advanced Bot Hosting Engine                      ║
╚═══════════════════════════════════════════════════════════════╝
"""

import asyncio
import os
import sys
import signal
import logging
import shutil
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from pathlib import Path
import json

from config import (
    USER_FILES_DIR, PYTHON_EXECUTABLE, PIP_EXECUTABLE,
    ProcessStatus, PLANS, MAX_FILE_SIZE_MB
)
from database import db
from utils.helpers import validate_python_code, get_user_directory

logger = logging.getLogger("gadget_host.process_manager")


class ProcessManager:
    """
    Advanced Process Manager for hosting Python bots.
    Handles bot lifecycle: start, stop, restart, logs, cleanup.
    """
    
    def __init__(self):
        self.active_processes: Dict[int, asyncio.subprocess.Process] = {}
        self.process_logs: Dict[int, List[str]] = {}
        self.max_log_lines = 100
        
    async def initialize(self):
        """Initialize the process manager"""
        await self._restore_processes()
        logger.info("✅ Process Manager initialized")
    
    async def _restore_processes(self):
        """Restore previously running processes on startup"""
        try:
            running_processes = await db.get_running_processes()
            
            for proc in running_processes:
                # Check if PID is still alive
                try:
                    import psutil
                    if psutil.pid_exists(proc['pid']):
                        # Process still running, track it
                        logger.info(f"Restoring process: {proc['id']} (PID: {proc['pid']})")
                        # We can't restore the actual subprocess object, so mark as unknown
                        await db.update_process(proc['id'], status=ProcessStatus.RUNNING.value)
                    else:
                        # Process died, mark as crashed
                        await db.crash_process(proc['id'], "Process died during server restart")
                except Exception as e:
                    logger.error(f"Error checking process {proc['id']}: {e}")
                    
        except Exception as e:
            logger.error(f"Error restoring processes: {e}")
    
    async def start_bot(self, process_id: int) -> Tuple[bool, str]:
        """
        Start a bot process.
        Returns (success, message)
        """
        try:
            # Get process info
            process = await db.get_process(process_id)
            if not process:
                return False, "Process not found"
            
            if process['status'] == ProcessStatus.RUNNING.value:
                return False, "Bot is already running"
            
            # Check if file exists
            if not os.path.exists(process['file_path']):
                return False, "Bot file not found"
            
            # Get user info to check plan limits
            user = await db.get_user(process['user_id'])
            if not user:
                return False, "User not found"
            
            # Check slot limit
            plan = PLANS.get(user['plan'], PLANS['free'])
            if plan.slots != -1 and user['slots_used'] > plan.slots:
                return False, "Slot limit reached. Upgrade to premium for unlimited slots."
            
            # Start the process
            env = os.environ.copy()
            if process.get('environment_vars'):
                try:
                    env.update(json.loads(process['environment_vars']))
                except:
                    pass
            
            proc = await asyncio.create_subprocess_exec(
                PYTHON_EXECUTABLE,
                process['file_path'],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.path.dirname(process['file_path']),
                env=env
            )
            
            # Track the process
            self.active_processes[process_id] = proc
            self.process_logs[process_id] = []
            
            # Update database
            await db.start_process(process_id, proc.pid)
            
            # Start log collector
            asyncio.create_task(self._collect_logs(process_id, proc))
            
            logger.info(f"Started bot {process_id} (PID: {proc.pid})")
            return True, f"Bot started successfully! PID: {proc.pid}"
            
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            return False, f"Failed to start bot: {str(e)}"
    
    async def stop_bot(self, process_id: int) -> Tuple[bool, str]:
        """
        Stop a bot process.
        Returns (success, message)
        """
        try:
            process = await db.get_process(process_id)
            if not process:
                return False, "Process not found"
            
            if process['status'] != ProcessStatus.RUNNING.value:
                return False, "Bot is not running"
            
            # Try to stop via tracked process
            if process_id in self.active_processes:
                proc = self.active_processes[process_id]
                
                try:
                    proc.terminate()
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                except Exception as e:
                    logger.error(f"Error terminating process: {e}")
            
            # If we have a PID, try to kill via OS
            if process.get('pid'):
                try:
                    import psutil
                    if psutil.pid_exists(process['pid']):
                        p = psutil.Process(process['pid'])
                        p.terminate()
                        try:
                            p.wait(timeout=5)
                        except psutil.TimeoutExpired:
                            p.kill()
                except Exception as e:
                    logger.error(f"Error killing process via PID: {e}")
            
            # Clean up
            if process_id in self.active_processes:
                del self.active_processes[process_id]
            
            # Update database
            await db.stop_process(process_id)
            
            logger.info(f"Stopped bot {process_id}")
            return True, "Bot stopped successfully"
            
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")
            return False, f"Failed to stop bot: {str(e)}"
    
    async def restart_bot(self, process_id: int) -> Tuple[bool, str]:
        """
        Restart a bot process.
        Returns (success, message)
        """
        # Stop the bot first
        success, msg = await self.stop_bot(process_id)
        
        # Wait a moment
        await asyncio.sleep(2)
        
        # Start again
        success, msg = await self.start_bot(process_id)
        
        if success:
            # Update restart count
            process = await db.get_process(process_id)
            if process:
                await db.update_process(
                    process_id,
                    restart_count=process['restart_count'] + 1
                )
        
        return success, msg
    
    async def delete_bot(self, process_id: int) -> Tuple[bool, str]:
        """
        Delete a bot process and its files.
        Returns (success, message)
        """
        try:
            # Stop if running
            process = await db.get_process(process_id)
            if process and process['status'] == ProcessStatus.RUNNING.value:
                await self.stop_bot(process_id)
            
            # Delete files
            if process and process.get('file_path'):
                try:
                    file_dir = os.path.dirname(process['file_path'])
                    if os.path.exists(file_dir):
                        shutil.rmtree(file_dir)
                except Exception as e:
                    logger.error(f"Error deleting files: {e}")
            
            # Clean up memory
            if process_id in self.active_processes:
                del self.active_processes[process_id]
            if process_id in self.process_logs:
                del self.process_logs[process_id]
            
            # Delete from database
            await db.delete_process(process_id)
            
            logger.info(f"Deleted bot {process_id}")
            return True, "Bot deleted successfully"
            
        except Exception as e:
            logger.error(f"Error deleting bot: {e}")
            return False, f"Failed to delete bot: {str(e)}"
    
    async def _collect_logs(self, process_id: int, 
                           proc: asyncio.subprocess.Process):
        """Collect logs from a running process"""
        try:
            while True:
                # Read stdout
                try:
                    line = await asyncio.wait_for(
                        proc.stdout.readline(),
                        timeout=1.0
                    )
                    if line:
                        log_line = line.decode('utf-8', errors='replace').strip()
                        self._add_log(process_id, f"[OUT] {log_line}")
                except asyncio.TimeoutError:
                    pass
                except Exception as e:
                    logger.error(f"Error reading stdout: {e}")
                
                # Check if process is still running
                if proc.returncode is not None:
                    # Read remaining stderr
                    stderr = await proc.stderr.read()
                    if stderr:
                        error_text = stderr.decode('utf-8', errors='replace')
                        for line in error_text.splitlines():
                            self._add_log(process_id, f"[ERR] {line}")
                    
                    # Mark as crashed or stopped
                    if proc.returncode != 0:
                        self._add_log(process_id, f"[SYS] Process exited with code {proc.returncode}")
                        await db.crash_process(process_id, f"Exit code: {proc.returncode}")
                    else:
                        await db.stop_process(process_id)
                    
                    # Clean up
                    if process_id in self.active_processes:
                        del self.active_processes[process_id]
                    
                    # Auto-restart if enabled
                    process = await db.get_process(process_id)
                    if process and process.get('auto_restart'):
                        self._add_log(process_id, "[SYS] Auto-restarting...")
                        await asyncio.sleep(5)
                        await self.start_bot(process_id)
                    
                    break
                
                # Read stderr
                try:
                    line = await asyncio.wait_for(
                        proc.stderr.readline(),
                        timeout=0.1
                    )
                    if line:
                        log_line = line.decode('utf-8', errors='replace').strip()
                        self._add_log(process_id, f"[ERR] {log_line}")
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Error collecting logs for {process_id}: {e}")
    
    def _add_log(self, process_id: int, line: str):
        """Add a log line"""
        if process_id not in self.process_logs:
            self.process_logs[process_id] = []
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.process_logs[process_id].append(f"[{timestamp}] {line}")
        
        # Keep only last N lines
        if len(self.process_logs[process_id]) > self.max_log_lines:
            self.process_logs[process_id] = self.process_logs[process_id][-self.max_log_lines:]
    
    def get_logs(self, process_id: int, lines: int = 50) -> str:
        """Get logs for a process"""
        if process_id not in self.process_logs:
            return "No logs available"
        
        logs = self.process_logs[process_id][-lines:]
        return "\n".join(logs) if logs else "No logs available"
    
    def clear_logs(self, process_id: int):
        """Clear logs for a process"""
        if process_id in self.process_logs:
            self.process_logs[process_id] = []
    
    async def kill_all_user_processes(self, user_id: int) -> Tuple[int, int]:
        """
        Kill all processes for a user.
        Returns (killed_count, failed_count)
        """
        processes = await db.get_user_processes(user_id)
        killed = 0
        failed = 0
        
        for proc in processes:
            if proc['status'] == ProcessStatus.RUNNING.value:
                success, _ = await self.stop_bot(proc['id'])
                if success:
                    killed += 1
                else:
                    failed += 1
        
        return killed, failed
    
    async def get_process_status(self, process_id: int) -> Optional[Dict]:
        """Get detailed process status"""
        process = await db.get_process(process_id)
        if not process:
            return None
        
        status = {
            'id': process['id'],
            'name': process['process_name'],
            'status': process['status'],
            'pid': process.get('pid'),
            'created': process['created_at'],
            'started': process.get('started_at'),
            'restarts': process['restart_count'],
            'auto_restart': bool(process.get('auto_restart')),
        }
        
        # Add live info if running
        if process['status'] == ProcessStatus.RUNNING.value and process.get('pid'):
            try:
                import psutil
                if psutil.pid_exists(process['pid']):
                    p = psutil.Process(process['pid'])
                    status['cpu_percent'] = p.cpu_percent()
                    status['memory_mb'] = p.memory_info().rss / (1024 * 1024)
                    status['threads'] = p.num_threads()
                else:
                    status['status'] = 'dead'
            except:
                pass
        
        return status


class GitManager:
    """
    Git repository manager for cloning and managing repos.
    """
    
    def __init__(self):
        self.git_available = self._check_git()
    
    def _check_git(self) -> bool:
        """Check if git is available"""
        try:
            import shutil
            return shutil.which('git') is not None
        except:
            return False
    
    async def clone_repo(self, repo_url: str, user_id: int,
                        branch: str = None) -> Tuple[bool, str, Optional[str]]:
        """
        Clone a git repository.
        Returns (success, message, cloned_dir_path)
        """
        if not self.git_available:
            return False, "Git is not installed on the server", None
        
        try:
            # Create user directory
            user_dir = get_user_directory(user_id)
            
            # Generate unique directory name
            repo_name = repo_url.split('/')[-1].replace('.git', '')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            clone_dir = os.path.join(user_dir, f"{repo_name}_{timestamp}")
            
            # Build git command
            cmd = ['git', 'clone']
            if branch:
                cmd.extend(['-b', branch])
            cmd.extend([repo_url, clone_dir])
            
            # Run git clone
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='replace')
                return False, f"Git clone failed: {error_msg}", None
            
            # Find main Python file
            main_file = self._find_main_file(clone_dir)
            
            return True, f"Repository cloned successfully!", clone_dir
            
        except Exception as e:
            logger.error(f"Error cloning repo: {e}")
            return False, f"Failed to clone repository: {str(e)}", None
    
    def _find_main_file(self, directory: str) -> Optional[str]:
        """Find the main Python file in a directory"""
        # Common main file names
        main_names = ['main.py', 'bot.py', 'app.py', 'run.py', 'start.py']
        
        for name in main_names:
            path = os.path.join(directory, name)
            if os.path.exists(path):
                return path
        
        # Find any Python file
        for file in os.listdir(directory):
            if file.endswith('.py'):
                return os.path.join(directory, file)
        
        return None
    
    async def get_repo_info(self, repo_url: str) -> Optional[Dict]:
        """Get repository information"""
        # This would require GitHub API or similar
        # For now, return basic info
        return {
            'url': repo_url,
            'name': repo_url.split('/')[-1].replace('.git', '')
        }


class ModuleInstaller:
    """
    Python module installer for installing packages.
    """
    
    def __init__(self):
        self.pip_available = self._check_pip()
    
    def _check_pip(self) -> bool:
        """Check if pip is available"""
        try:
            import shutil
            return shutil.which(PIP_EXECUTABLE) is not None
        except:
            return False
    
    async def install_module(self, module_name: str,
                            user_id: int = None) -> Tuple[bool, str]:
        """
        Install a Python module.
        Returns (success, output)
        """
        if not self.pip_available:
            return False, "pip is not installed on the server"
        
        try:
            # Sanitize module name
            module_name = module_name.strip().split()[0]  # Take first word only
            
            # Build pip command
            cmd = [PIP_EXECUTABLE, 'install', module_name]
            
            # Run pip install
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            output = stdout.decode('utf-8', errors='replace')
            error = stderr.decode('utf-8', errors='replace')
            
            if process.returncode != 0:
                return False, f"Installation failed:\n{error or output}"
            
            return True, f"Successfully installed {module_name}\n\n{output}"
            
        except Exception as e:
            logger.error(f"Error installing module: {e}")
            return False, f"Failed to install module: {str(e)}"
    
    async def uninstall_module(self, module_name: str) -> Tuple[bool, str]:
        """Uninstall a Python module"""
        if not self.pip_available:
            return False, "pip is not installed on the server"
        
        try:
            cmd = [PIP_EXECUTABLE, 'uninstall', '-y', module_name]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                return False, f"Uninstall failed"
            
            return True, f"Successfully uninstalled {module_name}"
            
        except Exception as e:
            return False, f"Failed to uninstall: {str(e)}"
    
    async def list_installed(self) -> List[str]:
        """List installed packages"""
        try:
            cmd = [PIP_EXECUTABLE, 'list', '--format=freeze']
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await process.communicate()
            
            output = stdout.decode('utf-8', errors='replace')
            packages = [line.split('==')[0] for line in output.splitlines() if '==' in line]
            
            return packages
            
        except Exception as e:
            logger.error(f"Error listing packages: {e}")
            return []


class FileHandler:
    """
    File handler for uploading and managing bot files.
    """
    
    @staticmethod
    async def save_user_file(file_data: bytes, filename: str,
                            user_id: int) -> Tuple[bool, str, Optional[str]]:
        """
        Save uploaded file for user.
        Returns (success, message, file_path)
        """
        try:
            # Check file size
            if len(file_data) > MAX_FILE_SIZE_MB * 1024 * 1024:
                return False, f"File too large. Max size: {MAX_FILE_SIZE_MB}MB", None
            
            # Validate Python file
            if filename.endswith('.py'):
                code = file_data.decode('utf-8', errors='replace')
                is_valid, result = validate_python_code(code)
                
                if not is_valid:
                    error = result['errors'][0] if result['errors'] else {}
                    return False, f"Syntax Error on line {error.get('line', '?')}: {error.get('message', 'Unknown error')}", None
                
                if result.get('warnings'):
                    # Log warnings but allow file
                    logger.warning(f"Code warnings for {filename}: {result['warnings']}")
            
            # Create user directory
            user_dir = get_user_directory(user_id)
            
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = "".join(c for c in filename if c.isalnum() or c in '._-')
            unique_name = f"{timestamp}_{safe_name}"
            
            file_path = os.path.join(user_dir, unique_name)
            
            # Save file
            with open(file_path, 'wb') as f:
                f.write(file_data)
            
            return True, f"File saved successfully", file_path
            
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            return False, f"Failed to save file: {str(e)}", None
    
    @staticmethod
    def delete_user_files(user_id: int) -> Tuple[bool, str]:
        """Delete all files for a user"""
        try:
            user_dir = get_user_directory(user_id)
            
            if os.path.exists(user_dir):
                shutil.rmtree(user_dir)
                return True, "All files deleted"
            
            return True, "No files to delete"
            
        except Exception as e:
            return False, f"Failed to delete files: {str(e)}"


# Global instances
process_manager = ProcessManager()
git_manager = GitManager()
module_installer = ModuleInstaller()
file_handler = FileHandler()
