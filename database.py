"""
╔═══════════════════════════════════════════════════════════════╗
║         GADGET PREMIUM HOST - Database Module                 ║
║              Advanced SQLite Database Manager                 ║
╚═══════════════════════════════════════════════════════════════╝
"""

import sqlite3
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
import json
import os

from config import (
    DATABASE_PATH, OWNER_ID, PLANS, REFERRAL_BONUS_SLOTS,
    REFERRAL_BONUS_CREDITS, ProcessStatus
)

logger = logging.getLogger("gadget_host.database")


class DatabaseManager:
    """
    Advanced SQLite Database Manager with async support.
    Handles all database operations for the hosting bot.
    """
    
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self._lock = asyncio.Lock()
        self._connection: Optional[sqlite3.Connection] = None
        
    async def initialize(self):
        """Initialize database and create all tables"""
        async with self._lock:
            self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
            self._create_tables()
            logger.info("✅ Database initialized successfully")
            
    def _create_tables(self):
        """Create all necessary tables"""
        cursor = self._connection.cursor()
        
        # ═════════════════════════════════════════════════════════
        # 👥 USERS TABLE
        # ═════════════════════════════════════════════════════════
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                plan TEXT DEFAULT 'free',
                slots INTEGER DEFAULT 1,
                slots_used INTEGER DEFAULT 0,
                credits INTEGER DEFAULT 0,
                referrals INTEGER DEFAULT 0,
                referred_by INTEGER,
                is_banned INTEGER DEFAULT 0,
                ban_reason TEXT,
                is_verified INTEGER DEFAULT 0,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                premium_expiry TIMESTAMP,
                total_uploads INTEGER DEFAULT 0,
                total_processes INTEGER DEFAULT 0,
                settings TEXT DEFAULT '{}',
                notes TEXT
            )
        """)
        
        # ═════════════════════════════════════════════════════════
        # 🤖 BOT PROCESSES TABLE
        # ═════════════════════════════════════════════════════════
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_processes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                process_name TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                pid INTEGER,
                status TEXT DEFAULT 'stopped',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                stopped_at TIMESTAMP,
                restart_count INTEGER DEFAULT 0,
                auto_restart INTEGER DEFAULT 0,
                environment_vars TEXT DEFAULT '{}',
                logs TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        # ═════════════════════════════════════════════════════════
        # 💳 TRANSACTIONS TABLE
        # ═════════════════════════════════════════════════════════
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                amount INTEGER DEFAULT 0,
                description TEXT,
                status TEXT DEFAULT 'completed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        # ═════════════════════════════════════════════════════════
        # 📢 BROADCASTS TABLE
        # ═════════════════════════════════════════════════════════
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                message_text TEXT,
                message_id INTEGER,
                sent_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                pinned INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # ═════════════════════════════════════════════════════════
        # 🔗 REFERRALS TABLE
        # ═════════════════════════════════════════════════════════
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL,
                bonus_given INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (referrer_id) REFERENCES users (user_id),
                FOREIGN KEY (referred_id) REFERENCES users (user_id)
            )
        """)
        
        # ═════════════════════════════════════════════════════════
        # ⚙️ SETTINGS TABLE
        # ═════════════════════════════════════════════════════════
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # ═════════════════════════════════════════════════════════
        # 📝 ACTIVITY LOGS TABLE
        # ═════════════════════════════════════════════════════════
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                details TEXT,
                ip_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # ═════════════════════════════════════════════════════════
        # 🛡️ BANNED FILES TABLE
        # ═════════════════════════════════════════════════════════
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS banned_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                filename TEXT,
                file_hash TEXT,
                reason TEXT,
                banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # ═════════════════════════════════════════════════════════
        # 🔔 NOTIFICATIONS TABLE
        # ═════════════════════════════════════════════════════════
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT,
                message TEXT,
                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for better performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_plan ON users(plan)",
            "CREATE INDEX IF NOT EXISTS idx_users_banned ON users(is_banned)",
            "CREATE INDEX IF NOT EXISTS idx_processes_user ON bot_processes(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_processes_status ON bot_processes(status)",
            "CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id)",
            "CREATE INDEX IF NOT EXISTS idx_logs_user ON activity_logs(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id)"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        
        self._connection.commit()
        logger.info("✅ All database tables created")
        
    # ═══════════════════════════════════════════════════════════════
    # 👤 USER OPERATIONS
    # ═══════════════════════════════════════════════════════════════
    
    async def add_user(self, user_id: int, username: str = None, 
                       first_name: str = None, last_name: str = None,
                       referred_by: int = None) -> bool:
        """Add a new user to the database"""
        async with self._lock:
            cursor = self._connection.cursor()
            
            try:
                # Check if user already exists
                cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
                if cursor.fetchone():
                    # Update user info
                    cursor.execute("""
                        UPDATE users SET 
                        username = ?, first_name = ?, last_name = ?,
                        last_active = CURRENT_TIMESTAMP
                        WHERE user_id = ?
                    """, (username, first_name, last_name, user_id))
                    self._connection.commit()
                    return False
                
                # Determine initial slots based on plan
                initial_slots = PLANS['free'].slots
                
                # Insert new user
                cursor.execute("""
                    INSERT INTO users (user_id, username, first_name, last_name, 
                                      slots, referred_by)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (user_id, username, first_name, last_name, initial_slots, referred_by))
                
                # Handle referral bonus
                if referred_by:
                    await self._process_referral_bonus(referred_by, user_id)
                
                self._connection.commit()
                logger.info(f"✅ New user added: {user_id} ({first_name})")
                return True
                
            except Exception as e:
                logger.error(f"❌ Error adding user: {e}")
                return False
    
    async def _process_referral_bonus(self, referrer_id: int, referred_id: int):
        """Process referral bonus for referrer"""
        cursor = self._connection.cursor()
        
        # Record the referral
        cursor.execute("""
            INSERT INTO referrals (referrer_id, referred_id, bonus_given)
            VALUES (?, ?, 1)
        """, (referrer_id, referred_id))
        
        # Update referrer's stats
        cursor.execute("""
            UPDATE users SET 
            referrals = referrals + 1,
            slots = slots + ?,
            credits = credits + ?
            WHERE user_id = ?
        """, (REFERRAL_BONUS_SLOTS, REFERRAL_BONUS_CREDITS, referrer_id))
        
        # Log the transaction
        cursor.execute("""
            INSERT INTO transactions (user_id, type, amount, description)
            VALUES (?, 'referral_bonus', ?, ?)
        """, (referrer_id, REFERRAL_BONUS_CREDITS, 
              f"Referral bonus for user {referred_id}"))
        
        logger.info(f"🎁 Referral bonus given to {referrer_id}")
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user information"""
        async with self._lock:
            cursor = self._connection.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    async def update_user(self, user_id: int, **kwargs) -> bool:
        """Update user information"""
        if not kwargs:
            return False
            
        async with self._lock:
            cursor = self._connection.cursor()
            
            set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
            values = list(kwargs.values()) + [user_id]
            
            try:
                cursor.execute(f"UPDATE users SET {set_clause} WHERE user_id = ?", values)
                self._connection.commit()
                return True
            except Exception as e:
                logger.error(f"❌ Error updating user: {e}")
                return False
    
    async def ban_user(self, user_id: int, reason: str = None) -> bool:
        """Ban a user"""
        return await self.update_user(user_id, is_banned=1, ban_reason=reason)
    
    async def unban_user(self, user_id: int) -> bool:
        """Unban a user"""
        return await self.update_user(user_id, is_banned=0, ban_reason=None)
    
    async def is_banned(self, user_id: int) -> bool:
        """Check if user is banned"""
        user = await self.get_user(user_id)
        return user['is_banned'] == 1 if user else False
    
    async def set_premium(self, user_id: int, plan: str = 'premium', 
                          days: int = 30) -> bool:
        """Set user premium status"""
        expiry = datetime.now() + timedelta(days=days) if days > 0 else None
        plan_data = PLANS.get(plan, PLANS['premium'])
        
        return await self.update_user(
            user_id, 
            plan=plan,
            slots=plan_data.slots,
            premium_expiry=expiry.isoformat() if expiry else None
        )
    
    async def remove_premium(self, user_id: int) -> bool:
        """Remove user premium status"""
        return await self.update_user(
            user_id,
            plan='free',
            slots=PLANS['free'].slots
        )
    
    async def get_all_users(self, limit: int = None, offset: int = 0) -> List[Dict]:
        """Get all users"""
        async with self._lock:
            cursor = self._connection.cursor()
            sql = "SELECT * FROM users ORDER BY join_date DESC"
            if limit:
                sql += f" LIMIT {limit} OFFSET {offset}"
            cursor.execute(sql)
            return [dict(row) for row in cursor.fetchall()]
    
    async def get_users_count(self) -> int:
        """Get total users count"""
        async with self._lock:
            cursor = self._connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            return cursor.fetchone()[0]
    
    async def get_premium_users(self) -> List[Dict]:
        """Get all premium users"""
        async with self._lock:
            cursor = self._connection.cursor()
            cursor.execute("""
                SELECT * FROM users 
                WHERE plan != 'free' 
                ORDER BY join_date DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
    
    async def verify_user(self, user_id: int) -> bool:
        """Mark user as verified (passed force subscribe)"""
        return await self.update_user(user_id, is_verified=1)
    
    async def is_verified(self, user_id: int) -> bool:
        """Check if user is verified"""
        user = await self.get_user(user_id)
        return user['is_verified'] == 1 if user else False
    
    # ═══════════════════════════════════════════════════════════════
    # 🤖 PROCESS OPERATIONS
    # ═══════════════════════════════════════════════════════════════
    
    async def add_process(self, user_id: int, process_name: str, 
                          filename: str, file_path: str,
                          environment_vars: Dict = None) -> int:
        """Add a new process record"""
        async with self._lock:
            cursor = self._connection.cursor()
            
            try:
                cursor.execute("""
                    INSERT INTO bot_processes 
                    (user_id, process_name, filename, file_path, environment_vars, status)
                    VALUES (?, ?, ?, ?, ?, 'stopped')
                """, (user_id, process_name, filename, file_path,
                      json.dumps(environment_vars or {})))
                
                process_id = cursor.lastrowid
                
                # Update user's used slots
                cursor.execute("""
                    UPDATE users SET slots_used = slots_used + 1,
                    total_processes = total_processes + 1
                    WHERE user_id = ?
                """, (user_id,))
                
                self._connection.commit()
                return process_id
                
            except Exception as e:
                logger.error(f"❌ Error adding process: {e}")
                return -1
    
    async def get_process(self, process_id: int) -> Optional[Dict]:
        """Get process by ID"""
        async with self._lock:
            cursor = self._connection.cursor()
            cursor.execute("SELECT * FROM bot_processes WHERE id = ?", (process_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    async def get_user_processes(self, user_id: int) -> List[Dict]:
        """Get all processes for a user"""
        async with self._lock:
            cursor = self._connection.cursor()
            cursor.execute("""
                SELECT * FROM bot_processes 
                WHERE user_id = ? 
                ORDER BY created_at DESC
            """, (user_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    async def update_process(self, process_id: int, **kwargs) -> bool:
        """Update process information"""
        if not kwargs:
            return False
            
        async with self._lock:
            cursor = self._connection.cursor()
            
            set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
            values = list(kwargs.values()) + [process_id]
            
            try:
                cursor.execute(f"UPDATE bot_processes SET {set_clause} WHERE id = ?", values)
                self._connection.commit()
                return True
            except Exception as e:
                logger.error(f"❌ Error updating process: {e}")
                return False
    
    async def start_process(self, process_id: int, pid: int) -> bool:
        """Mark process as started"""
        return await self.update_process(
            process_id,
            pid=pid,
            status=ProcessStatus.RUNNING.value,
            started_at=datetime.now().isoformat()
        )
    
    async def stop_process(self, process_id: int) -> bool:
        """Mark process as stopped"""
        return await self.update_process(
            process_id,
            status=ProcessStatus.STOPPED.value,
            stopped_at=datetime.now().isoformat()
        )
    
    async def crash_process(self, process_id: int, logs: str = None) -> bool:
        """Mark process as crashed"""
        return await self.update_process(
            process_id,
            status=ProcessStatus.CRASHED.value,
            stopped_at=datetime.now().isoformat(),
            logs=logs
        )
    
    async def delete_process(self, process_id: int) -> bool:
        """Delete a process record"""
        async with self._lock:
            cursor = self._connection.cursor()
            
            try:
                # Get process info first
                cursor.execute("SELECT user_id FROM bot_processes WHERE id = ?", (process_id,))
                row = cursor.fetchone()
                if not row:
                    return False
                
                user_id = row['user_id']
                
                # Delete process
                cursor.execute("DELETE FROM bot_processes WHERE id = ?", (process_id,))
                
                # Update user's used slots
                cursor.execute("""
                    UPDATE users SET slots_used = slots_used - 1
                    WHERE user_id = ? AND slots_used > 0
                """, (user_id,))
                
                self._connection.commit()
                return True
                
            except Exception as e:
                logger.error(f"❌ Error deleting process: {e}")
                return False
    
    async def get_running_processes(self) -> List[Dict]:
        """Get all running processes"""
        async with self._lock:
            cursor = self._connection.cursor()
            cursor.execute("""
                SELECT * FROM bot_processes 
                WHERE status = 'running'
            """)
            return [dict(row) for row in cursor.fetchall()]
    
    async def get_active_pids(self) -> List[Tuple[int, int]]:
        """Get all active PIDs with their process IDs"""
        async with self._lock:
            cursor = self._connection.cursor()
            cursor.execute("""
                SELECT id, pid FROM bot_processes 
                WHERE status = 'running' AND pid IS NOT NULL
            """)
            return [(row['id'], row['pid']) for row in cursor.fetchall()]
    
    # ═══════════════════════════════════════════════════════════════
    # 💳 TRANSACTION OPERATIONS
    # ═══════════════════════════════════════════════════════════════
    
    async def add_transaction(self, user_id: int, trans_type: str,
                              amount: int, description: str = None) -> int:
        """Add a new transaction"""
        async with self._lock:
            cursor = self._connection.cursor()
            
            try:
                cursor.execute("""
                    INSERT INTO transactions 
                    (user_id, type, amount, description)
                    VALUES (?, ?, ?, ?)
                """, (user_id, trans_type, amount, description))
                
                self._connection.commit()
                return cursor.lastrowid
                
            except Exception as e:
                logger.error(f"❌ Error adding transaction: {e}")
                return -1
    
    async def get_user_transactions(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get user's transactions"""
        async with self._lock:
            cursor = self._connection.cursor()
            cursor.execute("""
                SELECT * FROM transactions 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    async def add_credits(self, user_id: int, amount: int, 
                          description: str = None) -> bool:
        """Add credits to user"""
        async with self._lock:
            cursor = self._connection.cursor()
            
            try:
                cursor.execute("""
                    UPDATE users SET credits = credits + ?
                    WHERE user_id = ?
                """, (amount, user_id))
                
                await self.add_transaction(user_id, 'credit_add', amount, description)
                return True
                
            except Exception as e:
                logger.error(f"❌ Error adding credits: {e}")
                return False
    
    async def deduct_credits(self, user_id: int, amount: int,
                             description: str = None) -> bool:
        """Deduct credits from user"""
        async with self._lock:
            cursor = self._connection.cursor()
            
            try:
                # Check if user has enough credits
                cursor.execute("SELECT credits FROM users WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                if not row or row['credits'] < amount:
                    return False
                
                cursor.execute("""
                    UPDATE users SET credits = credits - ?
                    WHERE user_id = ?
                """, (amount, user_id))
                
                await self.add_transaction(user_id, 'credit_deduct', amount, description)
                return True
                
            except Exception as e:
                logger.error(f"❌ Error deducting credits: {e}")
                return False
    
    # ═══════════════════════════════════════════════════════════════
    # 📢 BROADCAST OPERATIONS
    # ═══════════════════════════════════════════════════════════════
    
    async def log_broadcast(self, admin_id: int, message_text: str,
                           sent_count: int, failed_count: int,
                           pinned: bool = False) -> int:
        """Log a broadcast"""
        async with self._lock:
            cursor = self._connection.cursor()
            
            try:
                cursor.execute("""
                    INSERT INTO broadcasts 
                    (admin_id, message_text, sent_count, failed_count, pinned)
                    VALUES (?, ?, ?, ?, ?)
                """, (admin_id, message_text, sent_count, failed_count, int(pinned)))
                
                self._connection.commit()
                return cursor.lastrowid
                
            except Exception as e:
                logger.error(f"❌ Error logging broadcast: {e}")
                return -1
    
    # ═══════════════════════════════════════════════════════════════
    # ⚙️ SETTINGS OPERATIONS
    # ═══════════════════════════════════════════════════════════════
    
    async def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value"""
        async with self._lock:
            cursor = self._connection.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            
            if row:
                try:
                    return json.loads(row['value'])
                except:
                    return row['value']
            return default
    
    async def set_setting(self, key: str, value: Any) -> bool:
        """Set a setting value"""
        async with self._lock:
            cursor = self._connection.cursor()
            
            try:
                value_json = json.dumps(value) if not isinstance(value, str) else value
                cursor.execute("""
                    INSERT OR REPLACE INTO settings (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (key, value_json))
                
                self._connection.commit()
                return True
                
            except Exception as e:
                logger.error(f"❌ Error setting setting: {e}")
                return False
    
    async def is_maintenance_mode(self) -> bool:
        """Check if maintenance mode is on"""
        return await self.get_setting('maintenance_mode', False)
    
    async def set_maintenance_mode(self, status: bool) -> bool:
        """Set maintenance mode"""
        return await self.set_setting('maintenance_mode', status)
    
    # ═══════════════════════════════════════════════════════════════
    # 📝 ACTIVITY LOG OPERATIONS
    # ═══════════════════════════════════════════════════════════════
    
    async def log_activity(self, user_id: int, action: str, 
                          details: str = None) -> bool:
        """Log user activity"""
        async with self._lock:
            cursor = self._connection.cursor()
            
            try:
                cursor.execute("""
                    INSERT INTO activity_logs (user_id, action, details)
                    VALUES (?, ?, ?)
                """, (user_id, action, details))
                
                self._connection.commit()
                return True
                
            except Exception as e:
                logger.error(f"❌ Error logging activity: {e}")
                return False
    
    async def get_user_activity(self, user_id: int, limit: int = 20) -> List[Dict]:
        """Get user's activity log"""
        async with self._lock:
            cursor = self._connection.cursor()
            cursor.execute("""
                SELECT * FROM activity_logs 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    # ═══════════════════════════════════════════════════════════════
    # 🔔 NOTIFICATION OPERATIONS
    # ═══════════════════════════════════════════════════════════════
    
    async def add_notification(self, user_id: int, title: str, 
                               message: str) -> int:
        """Add a notification for user"""
        async with self._lock:
            cursor = self._connection.cursor()
            
            try:
                cursor.execute("""
                    INSERT INTO notifications (user_id, title, message)
                    VALUES (?, ?, ?)
                """, (user_id, title, message))
                
                self._connection.commit()
                return cursor.lastrowid
                
            except Exception as e:
                logger.error(f"❌ Error adding notification: {e}")
                return -1
    
    async def get_unread_notifications(self, user_id: int) -> List[Dict]:
        """Get unread notifications for user"""
        async with self._lock:
            cursor = self._connection.cursor()
            cursor.execute("""
                SELECT * FROM notifications 
                WHERE user_id = ? AND is_read = 0
                ORDER BY created_at DESC
            """, (user_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    async def mark_notification_read(self, notification_id: int) -> bool:
        """Mark notification as read"""
        async with self._lock:
            cursor = self._connection.cursor()
            
            try:
                cursor.execute("""
                    UPDATE notifications SET is_read = 1
                    WHERE id = ?
                """, (notification_id,))
                
                self._connection.commit()
                return True
                
            except Exception as e:
                logger.error(f"❌ Error marking notification read: {e}")
                return False
    
    # ═══════════════════════════════════════════════════════════════
    # 📊 STATISTICS
    # ═══════════════════════════════════════════════════════════════
    
    async def get_stats(self) -> Dict:
        """Get overall statistics"""
        async with self._lock:
            cursor = self._connection.cursor()
            
            stats = {}
            
            # Total users
            cursor.execute("SELECT COUNT(*) FROM users")
            stats['total_users'] = cursor.fetchone()[0]
            
            # Premium users
            cursor.execute("SELECT COUNT(*) FROM users WHERE plan != 'free'")
            stats['premium_users'] = cursor.fetchone()[0]
            
            # Banned users
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1")
            stats['banned_users'] = cursor.fetchone()[0]
            
            # Total processes
            cursor.execute("SELECT COUNT(*) FROM bot_processes")
            stats['total_processes'] = cursor.fetchone()[0]
            
            # Running processes
            cursor.execute("SELECT COUNT(*) FROM bot_processes WHERE status = 'running'")
            stats['running_processes'] = cursor.fetchone()[0]
            
            # Today's new users
            cursor.execute("""
                SELECT COUNT(*) FROM users 
                WHERE date(join_date) = date('now')
            """)
            stats['today_users'] = cursor.fetchone()[0]
            
            # Total credits in system
            cursor.execute("SELECT SUM(credits) FROM users")
            stats['total_credits'] = cursor.fetchone()[0] or 0
            
            return stats
    
    # ═══════════════════════════════════════════════════════════════
    # 🔌 CONNECTION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════
    
    async def close(self):
        """Close database connection"""
        if self._connection:
            self._connection.close()
            logger.info("🔌 Database connection closed")
    
    def __del__(self):
        """Cleanup on deletion"""
        if self._connection:
            self._connection.close()


# Global database instance
db = DatabaseManager()
