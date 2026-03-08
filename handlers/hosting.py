"""
╔═══════════════════════════════════════════════════════════════╗
║         GADGET PREMIUM HOST - Hosting Handlers                ║
║              Bot Process Management Handlers                  ║
╚═══════════════════════════════════════════════════════════════╝
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional
from io import BytesIO

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, Document
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from config import MESSAGES, PLANS, ProcessStatus
from database import db
from keyboards import (
    get_my_bots_keyboard, get_bot_control_keyboard,
    get_bot_delete_confirm_keyboard, get_logs_keyboard,
    get_back_keyboard
)
from utils.helpers import truncate_text, escape_html
from services.process_manager import process_manager

logger = logging.getLogger("gadget_host.hosting")

# Create router
hosting_router = Router()


# ═══════════════════════════════════════════════════════════════
# 📋 FSM STATES
# ═══════════════════════════════════════════════════════════════

class HostingStates(StatesGroup):
    waiting_for_rename = State()
    waiting_for_env_var = State()


# ═══════════════════════════════════════════════════════════════
# 🤖 MY BOTS
# ═══════════════════════════════════════════════════════════════

@hosting_router.callback_query(F.data == "my_bots")
async def cb_my_bots(callback: CallbackQuery):
    """Show user's bots"""
    user_id = callback.from_user.id
    processes = await db.get_user_processes(user_id)
    
    if not processes:
        text = """
🤖 <b>MY BOTS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<i>You haven't uploaded any bots yet.</i>

<b>📤 Upload your first bot to get started!</b>
"""
    else:
        running = sum(1 for p in processes if p['status'] == 'running')
        text = f"""
🤖 <b>MY BOTS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 <b>Total:</b> {len(processes)} | 🟢 Running: {running} | 🔴 Stopped: {len(processes) - running}

<i>Click a bot to manage it:</i>
"""
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_my_bots_keyboard(processes)
    )


# ═══════════════════════════════════════════════════════════════
# 🤖 BOT CONTROL
# ═══════════════════════════════════════════════════════════════

@hosting_router.callback_query(F.data.startswith("bot_"))
async def cb_bot_info(callback: CallbackQuery):
    """Show bot info and controls"""
    process_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    # Get process
    process = await db.get_process(process_id)
    
    if not process:
        await callback.answer("❌ Bot not found!", show_alert=True)
        return
    
    # Verify ownership
    if process['user_id'] != user_id:
        await callback.answer("⛔ Access denied!", show_alert=True)
        return
    
    # Get live status
    status = await process_manager.get_process_status(process_id)
    
    status_emoji = {
        'running': '🟢',
        'stopped': '🔴',
        'crashed': '💀',
        'restarting': '🔄'
    }.get(process['status'], '❓')
    
    # Get user plan for slot display
    user = await db.get_user(user_id)
    plan = PLANS.get(user['plan'], PLANS['free'])
    
    text = f"""
🤖 <b>BOT CONTROL PANEL</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📋 Bot Info:</b>
┃ 🏷️ Name: <code>{process['process_name']}</code>
┃ 📄 File: <code>{process['filename']}</code>
┃ 🆔 ID: <code>{process_id}</code>

<b>📊 Status:</b>
┃ {status_emoji} <b>{process['status'].upper()}</b>
┃ 🔢 PID: {process.get('pid') or 'N/A'}
┃ 🔄 Restarts: {process.get('restart_count', 0)}

<b>📅 Timeline:</b>
┃ Created: {str(process['created_at'])[:16]}
┃ Started: {str(process.get('started_at', 'N/A'))[:16] if process.get('started_at') else 'N/A'}
"""

    if status and process['status'] == 'running':
        text += f"""
<b>💻 Live Stats:</b>
┃ CPU: {status.get('cpu_percent', 0):.1f}%
┃ RAM: {status.get('memory_mb', 0):.1f} MB
┃ Threads: {status.get('threads', 'N/A')}
"""

    text += "\n<b>⚡ Select an action:</b>"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_bot_control_keyboard(process_id, process['status'])
    )


# ═══════════════════════════════════════════════════════════════
# ▶ START BOT
# ═══════════════════════════════════════════════════════════════

@hosting_router.callback_query(F.data.startswith("start_"))
async def cb_start_bot(callback: CallbackQuery):
    """Start a bot"""
    process_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    # Verify ownership
    process = await db.get_process(process_id)
    if not process or process['user_id'] != user_id:
        await callback.answer("⛔ Access denied!", show_alert=True)
        return
    
    await callback.answer("⏳ Starting bot...")
    
    success, msg = await process_manager.start_bot(process_id)
    
    if success:
        await callback.answer(f"✅ {msg}", show_alert=True)
        # Refresh bot info
        await cb_bot_info(callback)
    else:
        await callback.answer(f"❌ {msg}", show_alert=True)


# ═══════════════════════════════════════════════════════════════
# ⏹ STOP BOT
# ═══════════════════════════════════════════════════════════════

@hosting_router.callback_query(F.data.startswith("stop_"))
async def cb_stop_bot(callback: CallbackQuery):
    """Stop a bot"""
    process_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    # Verify ownership
    process = await db.get_process(process_id)
    if not process or process['user_id'] != user_id:
        await callback.answer("⛔ Access denied!", show_alert=True)
        return
    
    await callback.answer("⏳ Stopping bot...")
    
    success, msg = await process_manager.stop_bot(process_id)
    
    if success:
        await callback.answer(f"✅ {msg}", show_alert=True)
        # Refresh bot info
        await cb_bot_info(callback)
    else:
        await callback.answer(f"❌ {msg}", show_alert=True)


# ═══════════════════════════════════════════════════════════════
# 🔄 RESTART BOT
# ═══════════════════════════════════════════════════════════════

@hosting_router.callback_query(F.data.startswith("restart_"))
async def cb_restart_bot(callback: CallbackQuery):
    """Restart a bot"""
    process_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    # Verify ownership
    process = await db.get_process(process_id)
    if not process or process['user_id'] != user_id:
        await callback.answer("⛔ Access denied!", show_alert=True)
        return
    
    await callback.answer("🔄 Restarting bot...")
    
    success, msg = await process_manager.restart_bot(process_id)
    
    if success:
        await callback.answer(f"✅ {msg}", show_alert=True)
        # Refresh bot info
        await cb_bot_info(callback)
    else:
        await callback.answer(f"❌ {msg}", show_alert=True)


# ═══════════════════════════════════════════════════════════════
# 📜 LOGS
# ═══════════════════════════════════════════════════════════════

@hosting_router.callback_query(F.data.startswith("logs_"))
async def cb_bot_logs(callback: CallbackQuery):
    """Show bot logs"""
    process_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    # Verify ownership
    process = await db.get_process(process_id)
    if not process or process['user_id'] != user_id:
        await callback.answer("⛔ Access denied!", show_alert=True)
        return
    
    # Get logs
    logs = process_manager.get_logs(process_id, lines=50)
    logs = truncate_text(logs, 3500)
    
    text = f"""
📜 <b>BOT LOGS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🤖 <b>Bot:</b> <code>{process['process_name']}</code>

<pre>{escape_html(logs)}</pre>
"""
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_logs_keyboard(process_id)
    )


@hosting_router.callback_query(F.data.startswith("clear_logs_"))
async def cb_clear_logs(callback: CallbackQuery):
    """Clear bot logs"""
    process_id = int(callback.data.split("_")[-1])
    
    process_manager.clear_logs(process_id)
    
    await callback.answer("🗑 Logs cleared!")
    await cb_bot_logs(callback)


@hosting_router.callback_query(F.data.startswith("download_logs_"))
async def cb_download_logs(callback: CallbackQuery, bot: Bot):
    """Download logs as file"""
    process_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    # Verify ownership
    process = await db.get_process(process_id)
    if not process or process['user_id'] != user_id:
        await callback.answer("⛔ Access denied!", show_alert=True)
        return
    
    # Get logs
    logs = process_manager.get_logs(process_id, lines=500)
    
    # Create file
    log_file = BytesIO(logs.encode('utf-8'))
    log_file.name = f"{process['process_name']}_logs.txt"
    
    await callback.message.answer_document(
        document=log_file,
        caption=f"📜 Logs for <code>{process['process_name']}</code>",
        parse_mode="HTML"
    )
    
    await callback.answer("📥 Downloading logs...")


# ═══════════════════════════════════════════════════════════════
# 🗑 DELETE BOT
# ═══════════════════════════════════════════════════════════════

@hosting_router.callback_query(F.data.startswith("delete_"))
async def cb_delete_bot(callback: CallbackQuery):
    """Show delete confirmation"""
    process_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    # Verify ownership
    process = await db.get_process(process_id)
    if not process or process['user_id'] != user_id:
        await callback.answer("⛔ Access denied!", show_alert=True)
        return
    
    text = f"""
⚠️ <b>DELETE BOT?</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🤖 <b>Bot:</b> <code>{process['process_name']}</code>

<i>This action cannot be undone!</i>

<b>All data will be permanently deleted:</b>
• Source code
• Configuration
• Logs
"""
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_bot_delete_confirm_keyboard(process_id)
    )


@hosting_router.callback_query(F.data.startswith("confirm_delete_"))
async def cb_confirm_delete(callback: CallbackQuery):
    """Confirm and delete bot"""
    process_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    # Verify ownership
    process = await db.get_process(process_id)
    if not process or process['user_id'] != user_id:
        await callback.answer("⛔ Access denied!", show_alert=True)
        return
    
    bot_name = process['process_name']
    
    success, msg = await process_manager.delete_bot(process_id)
    
    if success:
        await callback.message.edit_text(
            f"""
✅ <b>BOT DELETED!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🤖 <b>Bot:</b> <code>{bot_name}</code>

<i>All files have been removed.</i>
""",
            parse_mode="HTML",
            reply_markup=get_back_keyboard("my_bots")
        )
    else:
        await callback.answer(f"❌ {msg}", show_alert=True)


# ═══════════════════════════════════════════════════════════════
# ✏️ RENAME BOT
# ═══════════════════════════════════════════════════════════════

@hosting_router.callback_query(F.data.startswith("rename_"))
async def cb_rename_bot(callback: CallbackQuery, state: FSMContext):
    """Start rename process"""
    process_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    # Verify ownership
    process = await db.get_process(process_id)
    if not process or process['user_id'] != user_id:
        await callback.answer("⛔ Access denied!", show_alert=True)
        return
    
    await state.update_data(process_id=process_id)
    await state.set_state(HostingStates.waiting_for_rename)
    
    await callback.message.edit_text(
        f"""
✏️ <b>RENAME BOT</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🤖 <b>Current Name:</b> <code>{process['process_name']}</code>

<b>Send the new name:</b>
<i>(Max 30 characters)</i>
""",
        parse_mode="HTML",
        reply_markup=get_back_keyboard(f"bot_{process_id}")
    )


@hosting_router.message(HostingStates.waiting_for_rename)
async def process_rename(message: Message, state: FSMContext):
    """Process rename"""
    data = await state.get_data()
    process_id = data.get('process_id')
    
    new_name = message.text.strip()[:30]
    
    success = await db.update_process(process_id, process_name=new_name)
    
    await state.clear()
    
    if success:
        await message.answer(f"✅ Bot renamed to <code>{new_name}</code>", parse_mode="HTML")
    else:
        await message.answer("❌ Failed to rename bot")


# ═══════════════════════════════════════════════════════════════
# ⚙️ CONFIG
# ═══════════════════════════════════════════════════════════════

@hosting_router.callback_query(F.data.startswith("config_"))
async def cb_bot_config(callback: CallbackQuery):
    """Show bot config"""
    process_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    # Verify ownership
    process = await db.get_process(process_id)
    if not process or process['user_id'] != user_id:
        await callback.answer("⛔ Access denied!", show_alert=True)
        return
    
    # Check if premium
    user = await db.get_user(user_id)
    is_premium = user['plan'] != 'free'
    
    auto_restart = "✅ ON" if process.get('auto_restart') else "❌ OFF"
    
    text = f"""
⚙️ <b>BOT CONFIGURATION</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🤖 <b>Bot:</b> <code>{process['process_name']}</code>

<b>Settings:</b>
┃ 🔄 Auto-Restart: {auto_restart}
"""
    
    if is_premium:
        text += """
┃ 🌍 Environment Variables: Available

<b>Available Actions:</b>
• Toggle auto-restart
• Set environment variables
"""
    else:
        text += """
<i>💎 Upgrade to Premium for advanced config options!</i>
"""
    
    # Build config keyboard
    from keyboards import create_inline_keyboard
    
    buttons = [
        {'text': f"🔄 Auto-Restart: {'ON' if process.get('auto_restart') else 'OFF'}", 
         'callback_data': f"toggle_autorestart_{process_id}"}
    ]
    
    if is_premium:
        buttons.append({'text': '🌍 Set Env Variables', 'callback_data': f"env_vars_{process_id}"})
    
    buttons.append({'text': '🔙 Back', 'callback_data': f"bot_{process_id}"})
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=create_inline_keyboard(buttons, row_width=1)
    )


@hosting_router.callback_query(F.data.startswith("toggle_autorestart_"))
async def cb_toggle_autorestart(callback: CallbackQuery):
    """Toggle auto-restart"""
    process_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    # Verify ownership
    process = await db.get_process(process_id)
    if not process or process['user_id'] != user_id:
        await callback.answer("⛔ Access denied!", show_alert=True)
        return
    
    # Check premium
    user = await db.get_user(user_id)
    if user['plan'] == 'free':
        await callback.answer("💎 Auto-restart is a Premium feature!", show_alert=True)
        return
    
    new_value = 0 if process.get('auto_restart') else 1
    await db.update_process(process_id, auto_restart=new_value)
    
    await callback.answer(f"🔄 Auto-restart {'enabled' if new_value else 'disabled'}!")
    await cb_bot_config(callback)


@hosting_router.callback_query(F.data.startswith("env_vars_"))
async def cb_env_vars(callback: CallbackQuery, state: FSMContext):
    """Set environment variables"""
    process_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    # Verify ownership
    process = await db.get_process(process_id)
    if not process or process['user_id'] != user_id:
        await callback.answer("⛔ Access denied!", show_alert=True)
        return
    
    await state.update_data(process_id=process_id)
    await state.set_state(HostingStates.waiting_for_env_var)
    
    await callback.message.edit_text(
        """
🌍 <b>ENVIRONMENT VARIABLES</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>Format:</b>
<code>KEY=VALUE</code>
<code>API_KEY=abc123</code>

<b>Send each variable on a new line:</b>

<i>Example:</i>
<code>BOT_TOKEN=your_token
API_ID=12345
API_HASH=abc123</code>
""",
        parse_mode="HTML",
        reply_markup=get_back_keyboard(f"config_{process_id}")
    )


@hosting_router.message(HostingStates.waiting_for_env_var)
async def process_env_var(message: Message, state: FSMContext):
    """Process environment variables"""
    data = await state.get_data()
    process_id = data.get('process_id')
    
    import json
    
    env_vars = {}
    for line in message.text.strip().split('\n'):
        if '=' in line:
            key, value = line.split('=', 1)
            env_vars[key.strip()] = value.strip()
    
    success = await db.update_process(process_id, environment_vars=json.dumps(env_vars))
    
    await state.clear()
    
    if success:
        await message.answer(
            f"✅ <b>Environment variables set!</b>\n\n"
            f"📊 <b>Variables:</b> {len(env_vars)}",
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Failed to set environment variables")


# ═══════════════════════════════════════════════════════════════
# 📊 SETTINGS
# ═══════════════════════════════════════════════════════════════

@hosting_router.callback_query(F.data == "settings")
async def cb_settings(callback: CallbackQuery):
    """Show settings menu"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    from keyboards import get_settings_keyboard
    
    text = f"""
⚙️ <b>SETTINGS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 <b>User:</b> {user.get('first_name', 'Unknown')}
💎 <b>Plan:</b> {PLANS.get(user['plan'], PLANS['free']).name}

<b>Configure your preferences here.</b>
"""
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_settings_keyboard()
    )


@hosting_router.callback_query(F.data == "toggle_autorestart")
async def cb_global_autorestart(callback: CallbackQuery):
    """Toggle global auto-restart preference"""
    # This would toggle a user preference
    await callback.answer("⚙️ Setting updated!")


# ═══════════════════════════════════════════════════════════════
# 🚫 NOOP HANDLER
# ═══════════════════════════════════════════════════════════════

@hosting_router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    """Do nothing (for non-clickable buttons)"""
    pass
