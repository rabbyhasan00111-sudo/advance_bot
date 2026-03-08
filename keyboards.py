"""
╔═══════════════════════════════════════════════════════════════╗
║         GADGET PREMIUM HOST - Keyboards Module                ║
║              Cyberpunk Glassmorphism UI Keyboards             ║
╚═══════════════════════════════════════════════════════════════╝
"""

from typing import List, Dict, Optional
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


# ═══════════════════════════════════════════════════════════════
# 🎨 KEYBOARD BUILDERS
# ═══════════════════════════════════════════════════════════════

def create_inline_keyboard(
    buttons: List[Dict],
    row_width: int = 2
) -> InlineKeyboardMarkup:
    """
    Create an inline keyboard from button list.
    Each button dict: {'text': str, 'callback_data': str} or
                       {'text': str, 'url': str}
    """
    builder = InlineKeyboardBuilder()
    
    for btn in buttons:
        if 'url' in btn:
            builder.button(text=btn['text'], url=btn['url'])
        elif 'callback_data' in btn:
            builder.button(text=btn['text'], callback_data=btn['callback_data'])
        elif 'switch_inline_query' in btn:
            builder.button(text=btn['text'], switch_inline_query=btn['switch_inline_query'])
    
    builder.adjust(row_width)
    return builder.as_markup()


def create_reply_keyboard(
    buttons: List[List[str]],
    resize: bool = True,
    one_time: bool = False,
    placeholder: str = None
) -> ReplyKeyboardMarkup:
    """Create a reply keyboard from 2D button list"""
    builder = ReplyKeyboardBuilder()
    
    for row in buttons:
        for btn_text in row:
            builder.button(text=KeyboardButton(text=btn_text))
    
    return builder.as_markup(
        resize_keyboard=resize,
        one_time_keyboard=one_time,
        input_field_placeholder=placeholder
    )


# ═══════════════════════════════════════════════════════════════
# 🏠 MAIN MENU KEYBOARD
# ═══════════════════════════════════════════════════════════════

def get_main_menu_keyboard(is_premium: bool = False) -> InlineKeyboardMarkup:
    """Get the main menu keyboard"""
    buttons = [
        {'text': '🚀 My Bots', 'callback_data': 'my_bots'},
        {'text': '📤 Upload Bot', 'callback_data': 'upload_bot'},
        {'text': '🔗 Git Clone', 'callback_data': 'git_clone'},
        {'text': '📦 Install Module', 'callback_data': 'install_module'},
        {'text': '💎 Premium', 'callback_data': 'premium_info'},
        {'text': '💰 Wallet', 'callback_data': 'wallet'},
        {'text': '🎁 Referral', 'callback_data': 'referral'},
        {'text': '❓ Help', 'callback_data': 'help'},
    ]
    
    if is_premium:
        buttons.insert(6, {'text': '⚙️ Settings', 'callback_data': 'settings'})
    
    return create_inline_keyboard(buttons, row_width=2)


# ═══════════════════════════════════════════════════════════════
# 🔐 FORCE SUBSCRIBE KEYBOARD
# ═══════════════════════════════════════════════════════════════

def get_force_subscribe_keyboard(channels: List[Dict]) -> InlineKeyboardMarkup:
    """Get force subscribe keyboard with channel buttons"""
    builder = InlineKeyboardBuilder()
    
    # Add channel join buttons
    for channel in channels:
        if not channel['joined']:
            builder.button(
                text=f"🔔 Join {channel['name'][:20]}",
                url=channel['link']
            )
    
    # Add verify button
    builder.button(text="🔄 Verify Status", callback_data="verify_subscription")
    
    builder.adjust(1)
    return builder.as_markup()


# ═══════════════════════════════════════════════════════════════
# 🤖 BOT MANAGEMENT KEYBOARDS
# ═══════════════════════════════════════════════════════════════

def get_my_bots_keyboard(bots: List[Dict]) -> InlineKeyboardMarkup:
    """Get keyboard for user's bots list"""
    builder = InlineKeyboardBuilder()
    
    if not bots:
        builder.button(text="📤 Upload Your First Bot", callback_data="upload_bot")
    else:
        for bot in bots:
            status_emoji = "🟢" if bot['status'] == 'running' else "🔴"
            name = bot['process_name'][:20]
            builder.button(
                text=f"{status_emoji} {name}",
                callback_data=f"bot_{bot['id']}"
            )
        
        builder.button(text="📤 Upload New Bot", callback_data="upload_bot")
    
    builder.button(text="🔙 Back to Menu", callback_data="main_menu")
    
    builder.adjust(1)
    return builder.as_markup()


def get_bot_control_keyboard(bot_id: int, status: str) -> InlineKeyboardMarkup:
    """Get bot control keyboard"""
    builder = InlineKeyboardBuilder()
    
    if status == 'running':
        builder.button(text="⏹ Stop", callback_data=f"stop_{bot_id}")
        builder.button(text="🔄 Restart", callback_data=f"restart_{bot_id}")
    else:
        builder.button(text="▶ Start", callback_data=f"start_{bot_id}")
    
    builder.button(text="📜 Logs", callback_data=f"logs_{bot_id}")
    builder.button(text="📝 Rename", callback_data=f"rename_{bot_id}")
    builder.button(text="⚙️ Config", callback_data=f"config_{bot_id}")
    builder.button(text="🗑 Delete", callback_data=f"delete_{bot_id}")
    builder.button(text="🔙 Back", callback_data="my_bots")
    
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def get_bot_delete_confirm_keyboard(bot_id: int) -> InlineKeyboardMarkup:
    """Get delete confirmation keyboard"""
    return create_inline_keyboard([
        {'text': '✅ Yes, Delete', 'callback_data': f"confirm_delete_{bot_id}"},
        {'text': '❌ Cancel', 'callback_data': f"bot_{bot_id}"}
    ], row_width=2)


# ═══════════════════════════════════════════════════════════════
# 💎 PREMIUM KEYBOARDS
# ═══════════════════════════════════════════════════════════════

def get_premium_keyboard() -> InlineKeyboardMarkup:
    """Get premium plans keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="💎 Premium - $5/mo", callback_data="buy_premium")
    builder.button(text="🚀 Ultimate - $10/mo", callback_data="buy_ultimate")
    builder.button(text="📋 Compare Plans", callback_data="compare_plans")
    builder.button(text="🔙 Back", callback_data="main_menu")
    
    builder.adjust(1)
    return builder.as_markup()


def get_plan_comparison_keyboard() -> InlineKeyboardMarkup:
    """Get plan comparison keyboard"""
    return create_inline_keyboard([
        {'text': '💎 Get Premium', 'callback_data': 'buy_premium'},
        {'text': '🚀 Get Ultimate', 'callback_data': 'buy_ultimate'},
        {'text': '🔙 Back', 'callback_data': 'premium_info'}
    ], row_width=1)


# ═══════════════════════════════════════════════════════════════
# 💰 WALLET KEYBOARDS
# ═══════════════════════════════════════════════════════════════

def get_wallet_keyboard(credits: int = 0) -> InlineKeyboardMarkup:
    """Get wallet keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="💰 Add Credits", callback_data="add_credits")
    
    if credits >= 100:
        builder.button(text="💸 Withdraw", callback_data="withdraw_credits")
    
    builder.button(text="📊 Transaction History", callback_data="transaction_history")
    builder.button(text="🔙 Back", callback_data="main_menu")
    
    builder.adjust(1)
    return builder.as_markup()


# ═══════════════════════════════════════════════════════════════
# 🎁 REFERRAL KEYBOARDS
# ═══════════════════════════════════════════════════════════════

def get_referral_keyboard(referral_code: str, referral_link: str) -> InlineKeyboardMarkup:
    """Get referral keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="📤 Share Link", url=f"https://t.me/share/url?url={referral_link}")
    builder.button(text="📋 Copy Code", callback_data=f"copy_referral_{referral_code}")
    builder.button(text="👥 My Referrals", callback_data="my_referrals")
    builder.button(text="🔙 Back", callback_data="main_menu")
    
    builder.adjust(1)
    return builder.as_markup()


# ═══════════════════════════════════════════════════════════════
# 👑 ADMIN PANEL KEYBOARDS
# ═══════════════════════════════════════════════════════════════

def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Get admin panel main keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="📊 Server Stats", callback_data="admin_server")
    builder.button(text="👥 Users", callback_data="admin_users")
    builder.button(text="🤖 Processes", callback_data="admin_processes")
    builder.button(text="📢 Broadcast", callback_data="admin_broadcast")
    builder.button(text="⚙️ Settings", callback_data="admin_settings")
    builder.button(text="🔧 Maintenance", callback_data="admin_maintenance")
    builder.button(text="👤 User Lookup", callback_data="admin_user_lookup")
    builder.button(text="💰 Credits Manager", callback_data="admin_credits")
    builder.button(text="🔒 Banned Users", callback_data="admin_banned")
    builder.button(text="📈 Statistics", callback_data="admin_stats")
    builder.button(text="💻 Terminal", callback_data="admin_terminal")
    builder.button(text="🔙 Exit Admin", callback_data="main_menu")
    
    builder.adjust(2, 2, 2, 2, 2, 2)
    return builder.as_markup()


def get_admin_user_keyboard(user_id: int, is_banned: bool = False,
                            is_premium: bool = False) -> InlineKeyboardMarkup:
    """Get admin user management keyboard"""
    builder = InlineKeyboardBuilder()
    
    if is_banned:
        builder.button(text="✅ Unban User", callback_data=f"admin_unban_{user_id}")
    else:
        builder.button(text="❌ Ban User", callback_data=f"admin_ban_{user_id}")
    
    if is_premium:
        builder.button(text="🔻 Remove Premium", callback_data=f"admin_unpremium_{user_id}")
    else:
        builder.button(text="💎 Give Premium", callback_data=f"admin_premium_{user_id}")
    
    builder.button(text="💰 Add Credits", callback_data=f"admin_addcreds_{user_id}")
    builder.button(text="🛑 Kill Processes", callback_data=f"admin_kill_{user_id}")
    builder.button(text="🗑 Delete Files", callback_data=f"admin_delete_{user_id}")
    builder.button(text="📝 View Activity", callback_data=f"admin_activity_{user_id}")
    builder.button(text="🔙 Back", callback_data="admin_users")
    
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def get_admin_broadcast_keyboard() -> InlineKeyboardMarkup:
    """Get broadcast options keyboard"""
    return create_inline_keyboard([
        {'text': '📝 With Buttons', 'callback_data': 'broadcast_buttons'},
        {'text': '📌 Pin Message', 'callback_data': 'broadcast_pin'},
        {'text': '📊 Stats', 'callback_data': 'broadcast_stats'},
        {'text': '🔙 Back', 'callback_data': 'admin_panel'}
    ], row_width=1)


def get_admin_maintenance_keyboard(is_active: bool) -> InlineKeyboardMarkup:
    """Get maintenance mode keyboard"""
    builder = InlineKeyboardBuilder()
    
    if is_active:
        builder.button(text="🟢 Turn OFF Maintenance", callback_data="maintenance_off")
    else:
        builder.button(text="🔴 Turn ON Maintenance", callback_data="maintenance_on")
    
    builder.button(text="🔙 Back", callback_data="admin_panel")
    
    builder.adjust(1)
    return builder.as_markup()


def get_admin_users_list_keyboard(users: List[Dict], page: int = 0,
                                  per_page: int = 10) -> InlineKeyboardMarkup:
    """Get paginated users list keyboard"""
    builder = InlineKeyboardBuilder()
    
    start = page * per_page
    end = start + per_page
    page_users = users[start:end]
    
    for user in page_users:
        status_emoji = "🔴" if user['is_banned'] else "🟢"
        plan_emoji = "💎" if user['plan'] != 'free' else "🆓"
        name = user.get('first_name', 'Unknown')[:15]
        builder.button(
            text=f"{status_emoji}{plan_emoji} {name} ({user['user_id']})",
            callback_data=f"admin_user_{user['user_id']}"
        )
    
    # Navigation buttons
    total_pages = (len(users) + per_page - 1) // per_page
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append({'text': '⬅️ Previous', 'callback_data': f'users_page_{page-1}'})
    
    nav_buttons.append({'text': f'📄 {page+1}/{total_pages}', 'callback_data': 'noop'})
    
    if page < total_pages - 1:
        nav_buttons.append({'text': '➡️ Next', 'callback_data': f'users_page_{page+1}'})
    
    for btn in nav_buttons:
        builder.button(**btn)
    
    builder.button(text="🔙 Back", callback_data="admin_panel")
    
    builder.adjust(1, 3, 1)
    return builder.as_markup()


# ═══════════════════════════════════════════════════════════════
# ⚙️ SETTINGS KEYBOARDS
# ═══════════════════════════════════════════════════════════════

def get_settings_keyboard(auto_restart: bool = False) -> InlineKeyboardMarkup:
    """Get settings keyboard"""
    builder = InlineKeyboardBuilder()
    
    auto_text = "✅ Auto-Restart: ON" if auto_restart else "❌ Auto-Restart: OFF"
    builder.button(text=auto_text, callback_data="toggle_autorestart")
    
    builder.button(text="🌍 Environment Variables", callback_data="env_vars")
    builder.button(text="📝 Edit Config", callback_data="edit_config")
    builder.button(text="🔙 Back", callback_data="main_menu")
    
    builder.adjust(1)
    return builder.as_markup()


# ═══════════════════════════════════════════════════════════════
# 📜 LOGS KEYBOARDS
# ═══════════════════════════════════════════════════════════════

def get_logs_keyboard(bot_id: int) -> InlineKeyboardMarkup:
    """Get logs viewer keyboard"""
    return create_inline_keyboard([
        {'text': '🔄 Refresh', 'callback_data': f'logs_{bot_id}'},
        {'text': '📥 Download', 'callback_data': f'download_logs_{bot_id}'},
        {'text': '🗑 Clear Logs', 'callback_data': f'clear_logs_{bot_id}'},
        {'text': '🔙 Back', 'callback_data': f'bot_{bot_id}'}
    ], row_width=2)


# ═══════════════════════════════════════════════════════════════
# ❓ HELP & INFO KEYBOARDS
# ═══════════════════════════════════════════════════════════════

def get_help_keyboard() -> InlineKeyboardMarkup:
    """Get help keyboard"""
    return create_inline_keyboard([
        {'text': '📤 Uploading Bots', 'callback_data': 'help_upload'},
        {'text': '🔗 Git Clone', 'callback_data': 'help_git'},
        {'text': '📦 Modules', 'callback_data': 'help_modules'},
        {'text': '💎 Premium', 'callback_data': 'help_premium'},
        {'text': '🎁 Referral System', 'callback_data': 'help_referral'},
        {'text': '📞 Contact Support', 'callback_data': 'contact_support'},
        {'text': '🔙 Back', 'callback_data': 'main_menu'}
    ], row_width=2)


def get_back_keyboard(callback_data: str = "main_menu") -> InlineKeyboardMarkup:
    """Get simple back button keyboard"""
    return create_inline_keyboard([
        {'text': '🔙 Back', 'callback_data': callback_data}
    ], row_width=1)


def get_confirmation_keyboard(confirm_callback: str,
                              cancel_callback: str = "main_menu") -> InlineKeyboardMarkup:
    """Get confirmation keyboard"""
    return create_inline_keyboard([
        {'text': '✅ Confirm', 'callback_data': confirm_callback},
        {'text': '❌ Cancel', 'callback_data': cancel_callback}
    ], row_width=2)


# ═══════════════════════════════════════════════════════════════
# 📱 PAGINATION KEYBOARD
# ═══════════════════════════════════════════════════════════════

def get_pagination_keyboard(
    current_page: int,
    total_pages: int,
    callback_prefix: str,
    extra_buttons: List[Dict] = None
) -> InlineKeyboardMarkup:
    """Get pagination keyboard"""
    builder = InlineKeyboardBuilder()
    
    # Add extra buttons first
    if extra_buttons:
        for btn in extra_buttons:
            builder.button(**btn)
    
    # Navigation row
    if current_page > 0:
        builder.button(text="⬅️", callback_data=f"{callback_prefix}_{current_page-1}")
    
    builder.button(text=f"📄 {current_page+1}/{total_pages}", callback_data="noop")
    
    if current_page < total_pages - 1:
        builder.button(text="➡️", callback_data=f"{callback_prefix}_{current_page+1}")
    
    builder.button(text="🔙 Back", callback_data="main_menu")
    
    if extra_buttons:
        builder.adjust(len(extra_buttons), 3, 1)
    else:
        builder.adjust(3, 1)
    
    return builder.as_markup()


# ═══════════════════════════════════════════════════════════════
# 🎯 QUICK ACTION KEYBOARDS
# ═══════════════════════════════════════════════════════════════

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Get cancel action keyboard"""
    return create_inline_keyboard([
        {'text': '❌ Cancel', 'callback_data': 'cancel_action'}
    ], row_width=1)


def get_git_clone_keyboard() -> InlineKeyboardMarkup:
    """Get git clone options keyboard"""
    return create_inline_keyboard([
        {'text': '📥 Clone Public Repo', 'callback_data': 'git_public'},
        {'text': '🔐 Clone Private Repo', 'callback_data': 'git_private'},
        {'text': '📋 Recent Repos', 'callback_data': 'git_recent'},
        {'text': '🔙 Back', 'callback_data': 'main_menu'}
    ], row_width=1)


def get_module_install_keyboard() -> InlineKeyboardMarkup:
    """Get module installation keyboard"""
    popular_modules = [
        ('aiogram', 'aiogram'),
        ('discord.py', 'discord.py'),
        ('pyTelegramBotAPI', 'telebot'),
        ('Flask', 'flask'),
        ('FastAPI', 'fastapi'),
        ('Requests', 'requests'),
    ]
    
    buttons = []
    for name, pkg in popular_modules:
        buttons.append({'text': f'📦 {name}', 'callback_data': f'install_{pkg}'})
    
    buttons.append({'text': '✏️ Custom Module', 'callback_data': 'install_custom'})
    buttons.append({'text': '🔙 Back', 'callback_data': 'main_menu'})
    
    return create_inline_keyboard(buttons, row_width=2)
