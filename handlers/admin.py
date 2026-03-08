"""
╔═══════════════════════════════════════════════════════════════╗
║         GADGET PREMIUM HOST - Admin Handlers                  ║
║              God Mode Control Panel                           ║
╚═══════════════════════════════════════════════════════════════╝
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from io import BytesIO

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from config import OWNER_ID, ADMIN_IDS, MESSAGES, BRAND_NAME, BRAND_FOOTER
from database import db
from keyboards import (
    get_admin_panel_keyboard, get_admin_user_keyboard,
    get_admin_users_list_keyboard, get_admin_maintenance_keyboard,
    get_admin_broadcast_keyboard, get_back_keyboard
)
from utils.helpers import (
    is_owner, is_admin, owner_only, admin_only,
    ServerMonitor, format_server_stats, run_shell_command,
    truncate_text, escape_html
)
from services.process_manager import process_manager

logger = logging.getLogger("gadget_host.admin")

# Create router
admin_router = Router()


# ═══════════════════════════════════════════════════════════════
# 📋 FSM STATES
# ═══════════════════════════════════════════════════════════════

class AdminStates(StatesGroup):
    user_lookup = State()
    broadcast = State()
    terminal = State()
    add_credits = State()
    ban_user = State()
    set_premium = State()


# ═══════════════════════════════════════════════════════════════
# 👑 ADMIN COMMANDS
# ═══════════════════════════════════════════════════════════════

@admin_router.message(Command("admin"))
@admin_only
async def cmd_admin_panel(message: Message):
    """Open admin panel"""
    text = f"""
👑 <b>ADMIN CONTROL PANEL</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🔐 <b>Access Level:</b> {'👑 Owner' if is_owner(message.from_user.id) else '🛡️ Admin'}
👤 <b>Admin:</b> {message.from_user.full_name}
🆔 <b>ID:</b> <code>{message.from_user.id}</code>

<b>⚡ Select an option below:</b>
"""
    await message.answer(text, reply_markup=get_admin_panel_keyboard(), parse_mode="HTML")


@admin_router.message(Command("server"))
@admin_only
async def cmd_server_stats(message: Message):
    """Show server statistics"""
    stats = ServerMonitor.get_full_stats()
    db_stats = await db.get_stats()
    
    text = format_server_stats(
        stats,
        active_processes=stats['process_count'],
        total_users=db_stats['total_users'],
        running_bots=db_stats['running_processes']
    )
    
    await message.answer(text, parse_mode="HTML")


@admin_router.message(Command("user"))
@admin_only
async def cmd_user_lookup(message: Message, command):
    """Look up user information"""
    args = message.text.split()
    
    if len(args) < 2:
        await message.answer(
            "⚠️ <b>Usage:</b> <code>/user &lt;user_id&gt;</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        user_id = int(args[1])
    except ValueError:
        await message.answer("❌ Invalid user ID")
        return
    
    await show_user_info(message, user_id)


async def show_user_info(message_or_callback, user_id: int, edit: bool = False):
    """Show detailed user information"""
    user = await db.get_user(user_id)
    
    if not user:
        text = f"❌ User <code>{user_id}</code> not found in database"
        if hasattr(message_or_callback, 'answer'):
            await message_or_callback.answer(text, parse_mode="HTML")
        else:
            await message_or_callback.message.edit_text(text, parse_mode="HTML")
        return
    
    # Get user's processes
    processes = await db.get_user_processes(user_id)
    
    # Format processes list
    if processes:
        proc_list = ""
        for proc in processes[:5]:
            status_emoji = "🟢" if proc['status'] == 'running' else "🔴"
            proc_list += f"┃ {status_emoji} <code>{proc['process_name'][:20]}</code>\n"
            proc_list += f"┃    PID: {proc.get('pid', 'N/A')} | Status: {proc['status']}\n"
        if len(processes) > 5:
            proc_list += f"┃ ... and {len(processes) - 5} more\n"
    else:
        proc_list = "┃ <i>No active processes</i>\n"
    
    # Determine status
    if user['is_banned']:
        status_emoji = "🚫"
        status_text = "BANNED"
    elif user['plan'] != 'free':
        status_emoji = "💎"
        status_text = "PREMIUM"
    else:
        status_emoji = "🆓"
        status_text = "FREE"
    
    # Get plan info
    from config import PLANS
    plan = PLANS.get(user['plan'], PLANS['free'])
    
    # Format slots
    slots_max = "∞" if plan.slots == -1 else str(plan.slots)
    
    text = MESSAGES['user_info'].format(
        user_id=user['user_id'],
        user_name=escape_html(user.get('first_name', 'Unknown')),
        username=user.get('username') or 'N/A',
        plan_name=plan.name,
        join_date=user['join_date'][:19] if user.get('join_date') else 'N/A',
        credits=user.get('credits', 0),
        referrals=user.get('referrals', 0),
        slots_used=user.get('slots_used', 0),
        slots_max=slots_max,
        processes_list=proc_list,
        status_emoji=status_emoji,
        status_text=status_text
    )
    
    keyboard = get_admin_user_keyboard(
        user_id,
        is_banned=user['is_banned'],
        is_premium=user['plan'] != 'free'
    )
    
    if hasattr(message_or_callback, 'answer'):
        await message_or_callback.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message_or_callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@admin_router.message(Command("exec"))
@owner_only
async def cmd_exec(message: Message, state: FSMContext):
    """Execute shell command (Owner Only)"""
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer(
            "💻 <b>Terminal Access</b>\n\n"
            "<b>Usage:</b> <code>/exec &lt;command&gt;</code>\n\n"
            "<b>Examples:</b>\n"
            "• <code>/exec ls -la</code>\n"
            "• <code>/exec pip list</code>\n"
            "• <code>/exec cat /etc/os-release</code>",
            parse_mode="HTML"
        )
        return
    
    command = args[1]
    
    # Security warning for dangerous commands
    dangerous_commands = ['rm -rf', 'mkfs', 'dd if=', ':(){ :|:& };:', 'shutdown', 'reboot', 'init 0']
    for dangerous in dangerous_commands:
        if dangerous in command:
            await message.answer(
                "⚠️ <b>DANGEROUS COMMAND DETECTED!</b>\n\n"
                "🛡️ This command has been blocked for security reasons.\n"
                "If you really need to run this, do it directly on the server.",
                parse_mode="HTML"
            )
            return
    
    # Log the command
    logger.warning(f"Owner {message.from_user.id} executing: {command}")
    
    # Execute command
    await message.answer(f"💻 <code>{escape_html(command)}</code>\n\n⏳ Executing...", parse_mode="HTML")
    
    return_code, stdout, stderr = await run_shell_command(command, timeout=60)
    
    # Format output
    output = stdout if stdout else stderr
    output = truncate_text(output, 3800)
    
    result_text = f"""
💻 <b>Command:</b> <code>{escape_html(command)}</code>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>Return Code:</b> {return_code}

<b>Output:</b>
<pre>{escape_html(output) if output else '(no output)'}</pre>
"""
    
    await message.answer(result_text, parse_mode="HTML")


@admin_router.message(Command("broadcast"))
@admin_only
async def cmd_broadcast(message: Message, state: FSMContext):
    """Start broadcast process"""
    text = """
📢 <b>BROADCAST SYSTEM</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>To send a broadcast:</b>
1️⃣ Reply to a message with <code>/broadcast</code>
2️⃣ Or use the buttons below for options

<b>Features:</b>
• ✅ Markdown & HTML support
• ✅ Pin to channels
• ✅ Add inline buttons
• ✅ Progress tracking
"""
    await message.answer(text, parse_mode="HTML", reply_markup=get_admin_broadcast_keyboard())


@admin_router.message(Command("maintenance"))
@admin_only
async def cmd_maintenance(message: Message):
    """Toggle maintenance mode"""
    is_active = await db.is_maintenance_mode()
    
    text = f"""
🔧 <b>MAINTENANCE MODE</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>Current Status:</b> {'🟢 ACTIVE' if is_active else '🔴 INACTIVE'}

<i>When active, normal users will see a maintenance message.</i>
"""
    await message.answer(text, parse_mode="HTML", reply_markup=get_admin_maintenance_keyboard(is_active))


# ═══════════════════════════════════════════════════════════════
# 🎛️ ADMIN CALLBACK HANDLERS
# ═══════════════════════════════════════════════════════════════

@admin_router.callback_query(F.data == "admin_panel")
@admin_only
async def cb_admin_panel(callback: CallbackQuery):
    """Open admin panel"""
    text = f"""
👑 <b>ADMIN CONTROL PANEL</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🔐 <b>Access Level:</b> {'👑 Owner' if is_owner(callback.from_user.id) else '🛡️ Admin'}
👤 <b>Admin:</b> {callback.from_user.full_name}

<b>⚡ Select an option below:</b>
"""
    await callback.message.edit_text(text, reply_markup=get_admin_panel_keyboard(), parse_mode="HTML")


@admin_router.callback_query(F.data == "admin_server")
@admin_only
async def cb_admin_server(callback: CallbackQuery):
    """Show server stats"""
    stats = ServerMonitor.get_full_stats()
    db_stats = await db.get_stats()
    
    text = format_server_stats(
        stats,
        active_processes=stats['process_count'],
        total_users=db_stats['total_users'],
        running_bots=db_stats['running_processes']
    )
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard("admin_panel"))


@admin_router.callback_query(F.data == "admin_users")
@admin_only
async def cb_admin_users(callback: CallbackQuery, page: int = 0):
    """Show users list"""
    users = await db.get_all_users(limit=100)
    
    if not users:
        text = "👥 <b>No users found</b>"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard("admin_panel"))
        return
    
    text = f"""
👥 <b>USER MANAGEMENT</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 <b>Total Users:</b> {len(users)}
💎 <b>Premium:</b> {sum(1 for u in users if u['plan'] != 'free')}
🚫 <b>Banned:</b> {sum(1 for u in users if u['is_banned'])}

<i>Click a user to view details:</i>
"""
    await callback.message.edit_text(
        text, 
        parse_mode="HTML", 
        reply_markup=get_admin_users_list_keyboard(users, page)
    )


@admin_router.callback_query(F.data.startswith("users_page_"))
@admin_only
async def cb_users_page(callback: CallbackQuery):
    """Handle users pagination"""
    page = int(callback.data.split("_")[-1])
    await cb_admin_users(callback, page)


@admin_router.callback_query(F.data.startswith("admin_user_"))
@admin_only
async def cb_admin_user(callback: CallbackQuery):
    """Show user info"""
    user_id = int(callback.data.split("_")[-1])
    await show_user_info(callback, user_id, edit=True)


@admin_router.callback_query(F.data.startswith("admin_ban_"))
@admin_only
async def cb_admin_ban(callback: CallbackQuery):
    """Ban user"""
    user_id = int(callback.data.split("_")[-1])
    
    if user_id == OWNER_ID:
        await callback.answer("⚠️ Cannot ban the owner!", show_alert=True)
        return
    
    success = await db.ban_user(user_id, "Banned by admin")
    
    if success:
        # Kill all their processes
        killed, failed = await process_manager.kill_all_user_processes(user_id)
        await callback.answer(f"✅ User banned! {killed} processes killed.", show_alert=True)
        await show_user_info(callback, user_id, edit=True)
    else:
        await callback.answer("❌ Failed to ban user", show_alert=True)


@admin_router.callback_query(F.data.startswith("admin_unban_"))
@admin_only
async def cb_admin_unban(callback: CallbackQuery):
    """Unban user"""
    user_id = int(callback.data.split("_")[-1])
    
    success = await db.unban_user(user_id)
    
    if success:
        await callback.answer("✅ User unbanned!", show_alert=True)
        await show_user_info(callback, user_id, edit=True)
    else:
        await callback.answer("❌ Failed to unban user", show_alert=True)


@admin_router.callback_query(F.data.startswith("admin_premium_"))
@admin_only
async def cb_admin_premium(callback: CallbackQuery):
    """Give premium to user"""
    user_id = int(callback.data.split("_")[-1])
    
    success = await db.set_premium(user_id, 'premium', 30)
    
    if success:
        await callback.answer("💎 Premium granted for 30 days!", show_alert=True)
        await show_user_info(callback, user_id, edit=True)
    else:
        await callback.answer("❌ Failed to grant premium", show_alert=True)


@admin_router.callback_query(F.data.startswith("admin_unpremium_"))
@admin_only
async def cb_admin_unpremium(callback: CallbackQuery):
    """Remove premium from user"""
    user_id = int(callback.data.split("_")[-1])
    
    success = await db.remove_premium(user_id)
    
    if success:
        await callback.answer("🔻 Premium removed!", show_alert=True)
        await show_user_info(callback, user_id, edit=True)
    else:
        await callback.answer("❌ Failed to remove premium", show_alert=True)


@admin_router.callback_query(F.data.startswith("admin_kill_"))
@admin_only
async def cb_admin_kill_processes(callback: CallbackQuery):
    """Kill all user processes"""
    user_id = int(callback.data.split("_")[-1])
    
    killed, failed = await process_manager.kill_all_user_processes(user_id)
    
    await callback.answer(f"🛑 Killed {killed} processes. Failed: {failed}", show_alert=True)


@admin_router.callback_query(F.data.startswith("admin_delete_"))
@admin_only
async def cb_admin_delete_files(callback: CallbackQuery):
    """Delete user files"""
    user_id = int(callback.data.split("_")[-1])
    
    from services.process_manager import file_handler
    success, msg = file_handler.delete_user_files(user_id)
    
    if success:
        await callback.answer("🗑 All files deleted!", show_alert=True)
    else:
        await callback.answer(f"❌ {msg}", show_alert=True)


@admin_router.callback_query(F.data.startswith("admin_addcreds_"))
@admin_only
async def cb_admin_add_credits(callback: CallbackQuery, state: FSMContext):
    """Add credits to user"""
    user_id = int(callback.data.split("_")[-1])
    
    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminStates.add_credits)
    
    await callback.message.edit_text(
        f"💰 <b>Add Credits to User {user_id}</b>\n\n"
        "Send the amount of credits to add:",
        parse_mode="HTML",
        reply_markup=get_back_keyboard(f"admin_user_{user_id}")
    )


@admin_router.message(AdminStates.add_credits)
@admin_only
async def process_add_credits(message: Message, state: FSMContext):
    """Process credit addition"""
    data = await state.get_data()
    user_id = data.get('target_user_id')
    
    try:
        amount = int(message.text)
        if amount <= 0:
            raise ValueError("Amount must be positive")
    except ValueError:
        await message.answer("❌ Please enter a valid positive number")
        return
    
    success = await db.add_credits(user_id, amount, f"Added by admin {message.from_user.id}")
    
    await state.clear()
    
    if success:
        await message.answer(f"✅ Added {amount} credits to user {user_id}")
    else:
        await message.answer("❌ Failed to add credits")


@admin_router.callback_query(F.data == "admin_maintenance")
@admin_only
async def cb_admin_maintenance(callback: CallbackQuery):
    """Show maintenance options"""
    is_active = await db.is_maintenance_mode()
    
    text = f"""
🔧 <b>MAINTENANCE MODE</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>Current Status:</b> {'🟢 ACTIVE' if is_active else '🔴 INACTIVE'}

<i>When active, normal users will see a maintenance message.</i>
"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_maintenance_keyboard(is_active))


@admin_router.callback_query(F.data == "maintenance_on")
@admin_only
async def cb_maintenance_on(callback: CallbackQuery):
    """Turn on maintenance mode"""
    await db.set_maintenance_mode(True)
    await callback.answer("🔧 Maintenance mode activated!")
    await cb_admin_maintenance(callback)


@admin_router.callback_query(F.data == "maintenance_off")
@admin_only
async def cb_maintenance_off(callback: CallbackQuery):
    """Turn off maintenance mode"""
    await db.set_maintenance_mode(False)
    await callback.answer("✅ Maintenance mode deactivated!")
    await cb_admin_maintenance(callback)


@admin_router.callback_query(F.data == "admin_stats")
@admin_only
async def cb_admin_stats(callback: CallbackQuery):
    """Show detailed statistics"""
    stats = await db.get_stats()
    server_stats = ServerMonitor.get_full_stats()
    
    text = f"""
📈 <b>DETAILED STATISTICS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

👥 <b>USERS</b>
┃ Total: {stats['total_users']}
┃ Premium: {stats['premium_users']}
┃ Banned: {stats['banned_users']}
┃ Today: {stats['today_users']}

🤖 <b>PROCESSES</b>
┃ Total: {stats['total_processes']}
┃ Running: {stats['running_processes']}

💰 <b>ECONOMY</b>
┃ Total Credits: {stats['total_credits']}

🖥️ <b>SERVER</b>
┃ CPU: {server_stats['cpu_percent']:.1f}%
┃ RAM: {server_stats['ram_percent']:.1f}%
┃ Disk: {server_stats['disk_percent']:.1f}%
┃ Uptime: {server_stats['uptime']}
"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard("admin_panel"))


@admin_router.callback_query(F.data == "admin_terminal")
@owner_only
async def cb_admin_terminal(callback: CallbackQuery, state: FSMContext):
    """Open terminal access"""
    text = """
💻 <b>TERMINAL ACCESS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ <b>WARNING:</b> This is a powerful feature!

<b>Usage:</b> Send a command to execute

<b>Examples:</b>
• <code>ls -la</code>
• <code>pip list</code>
• <code>systemctl status</code>

<i>⚠️ Dangerous commands are blocked for safety.</i>
"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard("admin_panel"))
    await state.set_state(AdminStates.terminal)


@admin_router.message(AdminStates.terminal)
@owner_only
async def process_terminal_command(message: Message, state: FSMContext):
    """Process terminal command"""
    command = message.text
    
    # Security check
    dangerous_commands = ['rm -rf', 'mkfs', 'dd if=', ':(){ :|:& };:', 'shutdown', 'reboot', 'init 0']
    for dangerous in dangerous_commands:
        if dangerous in command:
            await message.answer("⚠️ Dangerous command blocked!")
            return
    
    logger.warning(f"Owner executing via terminal: {command}")
    
    return_code, stdout, stderr = await run_shell_command(command, timeout=60)
    
    output = truncate_text(stdout or stderr or "(no output)", 3800)
    
    await message.answer(
        f"💻 <code>{escape_html(command)}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Exit Code:</b> {return_code}\n\n"
        f"<pre>{escape_html(output)}</pre>",
        parse_mode="HTML"
    )


@admin_router.callback_query(F.data == "admin_broadcast")
@admin_only
async def cb_admin_broadcast(callback: CallbackQuery):
    """Show broadcast options"""
    text = """
📢 <b>BROADCAST SYSTEM</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>To send a broadcast:</b>
Reply to any message with <code>/broadcast</code>

<b>Features:</b>
• HTML/Markdown support
• Pin option
• Progress tracking
"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_broadcast_keyboard())


@admin_router.callback_query(F.data == "broadcast_stats")
@admin_only
async def cb_broadcast_stats(callback: CallbackQuery):
    """Show broadcast statistics"""
    # This would show broadcast history
    text = """
📊 <b>BROADCAST STATISTICS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<i>Recent broadcasts will appear here.</i>
"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard("admin_broadcast"))


@admin_router.callback_query(F.data == "admin_processes")
@admin_only
async def cb_admin_processes(callback: CallbackQuery):
    """Show all running processes"""
    processes = await db.get_running_processes()
    
    if not processes:
        text = "🤖 <b>No running processes</b>"
    else:
        text = f"🤖 <b>RUNNING PROCESSES</b> ({len(processes)})\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for proc in processes[:20]:
            user = await db.get_user(proc['user_id'])
            name = user.get('first_name', 'Unknown') if user else 'Unknown'
            text += f"🟢 <code>{proc['process_name'][:20]}</code>\n"
            text += f"   👤 {name} | PID: {proc.get('pid', 'N/A')}\n\n"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard("admin_panel"))


@admin_router.callback_query(F.data == "admin_banned")
@admin_only
async def cb_admin_banned(callback: CallbackQuery):
    """Show banned users"""
    users = await db.get_all_users()
    banned = [u for u in users if u['is_banned']]
    
    if not banned:
        text = "✅ <b>No banned users</b>"
    else:
        text = f"🚫 <b>BANNED USERS</b> ({len(banned)})\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for user in banned:
            text += f"👤 {user.get('first_name', 'Unknown')}\n"
            text += f"   🆔 <code>{user['user_id']}</code>\n"
            text += f"   📝 {user.get('ban_reason', 'No reason')}\n\n"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard("admin_panel"))


@admin_router.callback_query(F.data == "admin_credits")
@admin_only
async def cb_admin_credits(callback: CallbackQuery):
    """Show credits management"""
    stats = await db.get_stats()
    
    text = f"""
💰 <b>CREDITS MANAGEMENT</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 <b>System Stats:</b>
┃ Total Credits: {stats['total_credits']}
┃ Premium Users: {stats['premium_users']}

<i>Use /user &lt;id&gt; to add/deduct credits for specific users.</i>
"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard("admin_panel"))


@admin_router.callback_query(F.data == "admin_settings")
@admin_only
async def cb_admin_settings(callback: CallbackQuery):
    """Show admin settings"""
    maintenance = await db.is_maintenance_mode()
    
    text = f"""
⚙️ <b>ADMIN SETTINGS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🔧 <b>Maintenance Mode:</b> {'🟢 ON' if maintenance else '🔴 OFF'}

<i>Configure bot settings here.</i>
"""
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard("admin_panel"))
