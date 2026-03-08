"""
╔═══════════════════════════════════════════════════════════════╗
║         GADGET PREMIUM HOST - User Handlers                   ║
║              Main User Interface Handlers                     ║
╚═══════════════════════════════════════════════════════════════╝
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from io import BytesIO

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, Document
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from config import (
    OWNER_ID, MESSAGES, BRAND_NAME, BRAND_TAGLINE, BRAND_FOOTER,
    PLANS, FORCE_SUBSCRIBE_CHANNELS, MAX_FILE_SIZE_MB
)
from database import db
from keyboards import (
    get_main_menu_keyboard, get_force_subscribe_keyboard,
    get_premium_keyboard, get_wallet_keyboard,
    get_referral_keyboard, get_help_keyboard,
    get_back_keyboard, get_confirmation_keyboard,
    get_git_clone_keyboard, get_module_install_keyboard
)
from utils.helpers import (
    is_owner, is_admin, rate_limit,
    check_force_subscribe, format_force_subscribe_message,
    get_user_display_name, format_file_size,
    get_plan_display, generate_referral_code
)

logger = logging.getLogger("gadget_host.user")

# Create router
user_router = Router()


# ═══════════════════════════════════════════════════════════════
# 📋 FSM STATES
# ═══════════════════════════════════════════════════════════════

class UserStates(StatesGroup):
    waiting_for_file = State()
    waiting_for_git_url = State()
    waiting_for_module = State()
    waiting_for_bot_name = State()
    waiting_for_rename = State()


# ═══════════════════════════════════════════════════════════════
# 🚀 START COMMAND
# ═══════════════════════════════════════════════════════════════

@user_router.message(CommandStart())
@rate_limit
async def cmd_start(message: Message, bot: Bot, ref_param: str = None):
    """Handle /start command"""
    user_id = message.from_user.id
    user_name = get_user_display_name(message.from_user)
    
    # Add user to database
    referred_by = None
    if ref_param:
        try:
            # Decode referral code
            referred_by = int(ref_param) if ref_param.isdigit() else None
        except:
            pass
    
    is_new = await db.add_user(
        user_id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name,
        referred_by
    )
    
    # Check if user is banned
    if await db.is_banned(user_id):
        await message.answer(
            "🚫 <b>ACCESS DENIED!</b>\n\n"
            "You have been banned from using this bot.\n"
            f"Contact {OWNER_ID} for appeal.",
            parse_mode="HTML"
        )
        return
    
    # Check maintenance mode
    if await db.is_maintenance_mode() and not is_admin(user_id):
        await message.answer(
            MESSAGES['maintenance'].format(eta="30 minutes"),
            parse_mode="HTML"
        )
        return
    
    # Check force subscribe
    all_joined, channels = await check_force_subscribe(bot, user_id)
    
    if not all_joined:
        await db.update_user(user_id, is_verified=0)
        await message.answer(
            format_force_subscribe_message(channels),
            parse_mode="HTML",
            reply_markup=get_force_subscribe_keyboard(channels),
            disable_web_page_preview=True
        )
        return
    
    # Mark as verified
    await db.verify_user(user_id)
    
    # Get user info
    user = await db.get_user(user_id)
    plan = PLANS.get(user['plan'], PLANS['free'])
    
    # Format slots display
    slots_max = "∞" if plan.slots == -1 else str(plan.slots)
    
    text = MESSAGES['welcome'].format(
        brand_name=BRAND_NAME,
        tagline=BRAND_TAGLINE,
        user_name=user_name,
        user_id=user_id,
        plan_name=plan.name,
        slots_used=user['slots_used'],
        slots_max=slots_max,
        force_sub_warning=""
    )
    
    if is_new:
        text += "\n\n🎉 <b>Welcome aboard! You received 1 free bot slot!</b>"
    
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(user['plan'] != 'free')
    )


# ═══════════════════════════════════════════════════════════════
# 🔄 VERIFY SUBSCRIPTION
# ═══════════════════════════════════════════════════════════════

@user_router.callback_query(F.data == "verify_subscription")
async def cb_verify_subscription(callback: CallbackQuery, bot: Bot):
    """Verify user subscription status"""
    user_id = callback.from_user.id
    
    all_joined, channels = await check_force_subscribe(bot, user_id)
    
    if all_joined:
        await db.verify_user(user_id)
        await callback.answer("✅ Verification successful!", show_alert=True)
        
        # Show main menu
        user = await db.get_user(user_id)
        plan = PLANS.get(user['plan'], PLANS['free'])
        
        text = f"""
🛡️ <b>Welcome to {BRAND_NAME}!</b>
⚡ <i>{BRAND_TAGLINE}</i>

✅ <b>Verification Complete!</b>

👤 <b>User:</b> {get_user_display_name(callback.from_user)}
💎 <b>Plan:</b> {plan.name}
📊 <b>Slots:</b> {user['slots_used']}/{"∞" if plan.slots == -1 else plan.slots}

<b>⚡ Select an option below to get started!</b>
"""
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(user['plan'] != 'free')
        )
    else:
        await callback.answer("❌ Please join all channels first!", show_alert=True)
        await callback.message.edit_text(
            format_force_subscribe_message(channels),
            parse_mode="HTML",
            reply_markup=get_force_subscribe_keyboard(channels),
            disable_web_page_preview=True
        )


# ═══════════════════════════════════════════════════════════════
# 🏠 MAIN MENU
# ═══════════════════════════════════════════════════════════════

@user_router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery):
    """Show main menu"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ User not found. Please /start again.", show_alert=True)
        return
    
    plan = PLANS.get(user['plan'], PLANS['free'])
    slots_max = "∞" if plan.slots == -1 else str(plan.slots)
    
    text = f"""
🛡️ <b>{BRAND_NAME}</b>
⚡ <i>{BRAND_TAGLINE}</i>

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ <b>👤 User Dashboard</b>
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ 👤 Name: {get_user_display_name(callback.from_user)}
┃ 🆔 ID: <code>{user_id}</code>
┃ 💎 Plan: {plan.name}
┃ 📊 Slots: {user['slots_used']}/{slots_max}
┃ 💰 Credits: {user['credits']}
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

<b>⚡ What would you like to do?</b>
"""
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(user['plan'] != 'free')
    )


# ═══════════════════════════════════════════════════════════════
# 💎 PREMIUM
# ═══════════════════════════════════════════════════════════════

@user_router.callback_query(F.data == "premium_info")
async def cb_premium_info(callback: CallbackQuery):
    """Show premium information"""
    text = f"""
💎 <b>PREMIUM PLANS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🆓 FREE PLAN</b>
┃ 1 Bot Slot
┃ 10MB Max File Size
┃ Basic Support
┃ <b>Price: FREE</b>

<b>💎 PREMIUM PLAN</b>
┃ ♾️ Unlimited Slots
┃ 100MB Max File Size
┃ Priority Support
┃ Git Clone Support
┃ Module Installer
┃ <b>Price: $5/month</b>

<b>🚀 ULTIMATE PLAN</b>
┃ ♾️ Unlimited Slots
┃ 500MB Max File Size
┃ VIP Support + SLA
┃ All Premium Features
┃ Auto-Restart on Crash
┃ Custom Environment
┃ <b>Price: $10/month</b>

<i>💰 Contact @{OWNER_ID} to purchase!</i>
"""
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_premium_keyboard()
    )


@user_router.callback_query(F.data == "compare_plans")
async def cb_compare_plans(callback: CallbackQuery):
    """Show plan comparison"""
    text = """
📊 <b>PLAN COMPARISON</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────┬───────┬─────────┬─────────┐
│ <b>Feature</b>     │ <b>Free</b>  │ <b>Premium</b> │ <b>Ultimate</b> │
├─────────────┼───────┼─────────┼─────────┤
│ Bot Slots   │ 1     │ ∞       │ ∞       │
│ File Size   │ 10MB  │ 100MB   │ 500MB   │
│ Git Clone   │ ❌    │ ✅      │ ✅      │
│ Auto-Restart│ ❌    │ ❌      │ ✅      │
│ Modules     │ ❌    │ ✅      │ ✅      │
│ Support     │ Basic │ Priority│ VIP     │
│ Price       │ Free  │ $5/mo   │ $10/mo  │
└─────────────┴───────┴─────────┴─────────┘
"""
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("premium_info")
    )


@user_router.callback_query(F.data == "buy_premium")
async def cb_buy_premium(callback: CallbackQuery):
    """Handle buy premium"""
    await callback.answer("💎 Contact the owner to purchase Premium!", show_alert=True)


@user_router.callback_query(F.data == "buy_ultimate")
async def cb_buy_ultimate(callback: CallbackQuery):
    """Handle buy ultimate"""
    await callback.answer("🚀 Contact the owner to purchase Ultimate!", show_alert=True)


# ═══════════════════════════════════════════════════════════════
# 💰 WALLET
# ═══════════════════════════════════════════════════════════════

@user_router.callback_query(F.data == "wallet")
async def cb_wallet(callback: CallbackQuery):
    """Show wallet"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    text = f"""
💰 <b>YOUR WALLET</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

💵 <b>Balance:</b> {user['credits']} Credits

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ <b>💳 How to get credits:</b>
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ 🎁 Invite friends (+10 each)
┃ 💎 Purchase from admin
┃ 🏆 Participate in events
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

<i>💡 1 Credit = $0.01 USD</i>
"""
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_wallet_keyboard(user['credits'])
    )


@user_router.callback_query(F.data == "transaction_history")
async def cb_transaction_history(callback: CallbackQuery):
    """Show transaction history"""
    user_id = callback.from_user.id
    transactions = await db.get_user_transactions(user_id, limit=10)
    
    if not transactions:
        text = "📜 <b>No transactions yet</b>"
    else:
        text = f"📜 <b>TRANSACTION HISTORY</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for tx in transactions:
            emoji = "💰" if tx['type'] in ['credit_add', 'referral_bonus'] else "💸"
            text += f"{emoji} {tx['type']}\n"
            text += f"   💵 {tx['amount']} credits\n"
            text += f"   📅 {tx['created_at'][:10]}\n\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("wallet")
    )


# ═══════════════════════════════════════════════════════════════
# 🎁 REFERRAL
# ═══════════════════════════════════════════════════════════════

@user_router.callback_query(F.data == "referral")
async def cb_referral(callback: CallbackQuery, bot: Bot):
    """Show referral info"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    # Generate referral link
    bot_info = await bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    text = f"""
🎁 <b>REFERRAL PROGRAM</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ <b>📊 Your Stats</b>
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ 👥 Referrals: {user['referrals']}
┃ 💰 Earned: {user['referrals'] * 10} credits
┃ 🎫 Bonus: +{user['referrals']} slots
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

<b>🎁 Rewards per referral:</b>
• +1 Bot Slot
• +10 Credits
• Friend gets +1 Slot too!

<b>🔗 Your Referral Link:</b>
<code>{referral_link}</code>

<i>Share this link and earn rewards!</i>
"""
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_referral_keyboard(str(user_id), referral_link)
    )


@user_router.callback_query(F.data == "my_referrals")
async def cb_my_referrals(callback: CallbackQuery):
    """Show user's referrals"""
    user_id = callback.from_user.id
    
    # This would query referrals table
    text = f"""
👥 <b>YOUR REFERRALS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<i>Users who joined using your link will appear here.</i>

<b>Total Referrals:</b> Check your stats above.
"""
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("referral")
    )


# ═══════════════════════════════════════════════════════════════
# ❓ HELP
# ═══════════════════════════════════════════════════════════════

@user_router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery):
    """Show help menu"""
    text = f"""
❓ <b>HELP CENTER</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📚 Quick Guide:</b>

<b>🤖 Hosting a Bot:</b>
1. Click "📤 Upload Bot"
2. Send your .py file
3. Name your bot
4. Click Start to run!

<b>🔗 Git Clone:</b>
1. Click "🔗 Git Clone"
2. Send your repo URL
3. Bot auto-hosts main.py

<b>📦 Modules:</b>
Premium users can install Python packages.

<b>💎 Premium:</b>
Get unlimited slots and features!

<i>📞 Support: @{OWNER_ID}</i>
"""
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_help_keyboard()
    )


@user_router.callback_query(F.data.startswith("help_"))
async def cb_help_topic(callback: CallbackQuery):
    """Show specific help topic"""
    topic = callback.data.split("_")[-1]
    
    topics = {
        "upload": """
📤 <b>UPLOADING BOTS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>Step-by-step:</b>
1️⃣ Click "📤 Upload Bot" from menu
2️⃣ Send your Python file (.py)
3️⃣ Bot will scan for syntax errors
4️⃣ Name your bot when prompted
5️⃣ Use control panel to start!

<b>Tips:</b>
• Make sure your code has no errors
• Use relative imports
• Include requirements in comments
""",
        "git": """
🔗 <b>GIT CLONE</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>How to use:</b>
1️⃣ Click "🔗 Git Clone"
2️⃣ Send public GitHub URL
3️⃣ Bot clones the repository
4️⃣ Finds and hosts main.py

<b>Supported:</b>
• GitHub public repos
• GitLab public repos

<i>💡 Premium feature!</i>
""",
        "modules": """
📦 <b>MODULE INSTALLER</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>How to install:</b>
1️⃣ Click "📦 Install Module"
2️⃣ Select popular package OR
3️⃣ Enter custom package name
4️⃣ Wait for installation

<b>Popular packages:</b>
• aiogram
• discord.py
• Flask
• FastAPI

<i>💡 Premium feature!</i>
""",
        "premium": """
💎 <b>PREMIUM FEATURES</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>Why upgrade?</b>
✅ Unlimited bot slots
✅ Larger file uploads
✅ Git clone support
✅ Module installer
✅ Priority support
✅ Auto-restart on crash

<b>How to buy:</b>
Contact @{OWNER_ID}
""",
        "referral": """
🎁 <b>REFERRAL SYSTEM</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>How it works:</b>
1️⃣ Share your referral link
2️⃣ Friend joins via link
3️⃣ You get +1 slot & +10 credits
4️⃣ Friend gets +1 slot too!

<b>Tips:</b>
• Share in groups
• Post on social media
• Invite programmer friends
"""
    }
    
    text = topics.get(topic, "Help topic not found")
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("help")
    )


# ═══════════════════════════════════════════════════════════════
# 📤 UPLOAD BOT
# ═══════════════════════════════════════════════════════════════

@user_router.callback_query(F.data == "upload_bot")
async def cb_upload_bot(callback: CallbackQuery, state: FSMContext):
    """Start upload process"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    plan = PLANS.get(user['plan'], PLANS['free'])
    
    # Check slot limit
    if plan.slots != -1 and user['slots_used'] >= plan.slots:
        await callback.answer(
            "❌ No slots available! Upgrade to Premium for unlimited slots.",
            show_alert=True
        )
        return
    
    text = """
📤 <b>UPLOAD YOUR BOT</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>Send your Python file (.py)</b>

<i>⚡ Your code will be scanned for errors before hosting.</i>

<b>Requirements:</b>
• File must be .py extension
• No syntax errors
• Max size: {size}MB

<b>⚠️ Security Note:</b>
Dangerous code patterns will be flagged.
""".format(size=MAX_FILE_SIZE_MB)
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("main_menu")
    )
    
    await state.set_state(UserStates.waiting_for_file)


@user_router.message(UserStates.waiting_for_file)
async def process_file_upload(message: Message, state: FSMContext, bot: Bot):
    """Process uploaded file"""
    user_id = message.from_user.id
    
    # Check if document
    if not message.document:
        await message.answer("❌ Please send a Python file (.py)")
        return
    
    document = message.document
    
    # Check extension
    if not document.file_name.endswith('.py'):
        await message.answer("❌ Only Python files (.py) are allowed!")
        return
    
    # Check file size
    if document.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        await message.answer(f"❌ File too large! Max: {MAX_FILE_SIZE_MB}MB")
        return
    
    # Download file
    await message.answer("⏳ <i>Downloading and analyzing...</i>", parse_mode="HTML")
    
    try:
        file = await bot.get_file(document.file_id)
        file_data = await bot.download_file(file.file_path)
        file_content = file_data.read()
    except Exception as e:
        await message.answer(f"❌ Failed to download file: {e}")
        return
    
    # Validate code
    from utils.helpers import validate_python_code
    
    try:
        code = file_content.decode('utf-8')
    except UnicodeDecodeError:
        await message.answer("❌ Invalid file encoding. Use UTF-8.")
        return
    
    is_valid, result = validate_python_code(code)
    
    if not is_valid:
        error = result['errors'][0] if result['errors'] else {}
        await message.answer(
            MESSAGES['syntax_error'].format(
                line=error.get('line', '?'),
                error_msg=error.get('message', 'Unknown error')
            ),
            parse_mode="HTML"
        )
        return
    
    # Show warnings if any
    if result.get('warnings'):
        warnings_text = "\n".join([f"⚠️ {w['message']}" for w in result['warnings'][:3]])
        await message.answer(
            f"⚠️ <b>Warnings detected:</b>\n{warnings_text}\n\n<i>Proceeding with upload...</i>",
            parse_mode="HTML"
        )
    
    # Save file
    from services.process_manager import file_handler
    
    success, msg, file_path = await file_handler.save_user_file(
        file_content,
        document.file_name,
        user_id
    )
    
    if not success:
        await message.answer(f"❌ {msg}")
        await state.clear()
        return
    
    # Store file info in state
    await state.update_data(
        file_path=file_path,
        filename=document.file_name,
        code_stats=result.get('stats', {})
    )
    
    # Ask for bot name
    await message.answer(
        f"""
✅ <b>FILE UPLOADED SUCCESSFULLY!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

📄 <b>File:</b> <code>{document.file_name}</code>
📏 <b>Size:</b> {format_file_size(document.file_size)}
🔍 <b>Lines:</b> {result['stats'].get('lines', 'N/A')}

<b>Please enter a name for your bot:</b>
<i>(This helps you identify it later)</i>
""",
        parse_mode="HTML"
    )
    
    await state.set_state(UserStates.waiting_for_bot_name)


@user_router.message(UserStates.waiting_for_bot_name)
async def process_bot_name(message: Message, state: FSMContext):
    """Process bot name and create process"""
    user_id = message.from_user.id
    bot_name = message.text.strip()[:30]  # Limit name length
    
    # Get stored file info
    data = await state.get_data()
    file_path = data.get('file_path')
    filename = data.get('filename')
    
    if not file_path:
        await message.answer("❌ Session expired. Please upload again.")
        await state.clear()
        return
    
    # Create process in database
    process_id = await db.add_process(
        user_id=user_id,
        process_name=bot_name,
        filename=filename,
        file_path=file_path
    )
    
    if process_id == -1:
        await message.answer("❌ Failed to create bot. Try again.")
        await state.clear()
        return
    
    # Log activity
    await db.log_activity(user_id, 'bot_upload', f'Bot: {bot_name}')
    
    # Update user upload count
    await db.update_user(user_id, total_uploads=await db.get_user(user_id) + 1)
    
    # Notify owner
    try:
        from config import OWNER_ID
        user = await db.get_user(user_id)
        await message.bot.send_message(
            OWNER_ID,
            f"""
📤 <b>NEW BOT UPLOADED!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 <b>User:</b> {message.from_user.full_name}
🆔 <b>ID:</b> <code>{user_id}</code>
💎 <b>Plan:</b> {user['plan']}

🤖 <b>Bot Name:</b> {bot_name}
📄 <b>File:</b> <code>{filename}</code>

<b>Stats:</b>
• Lines: {data.get('code_stats', {}).get('lines', 'N/A')}
• Functions: {data.get('code_stats', {}).get('functions', 'N/A')}
""",
            parse_mode="HTML"
        )
    except:
        pass
    
    await state.clear()
    
    # Show success and control panel
    from keyboards import get_bot_control_keyboard
    
    await message.answer(
        f"""
✅ <b>BOT CREATED SUCCESSFULLY!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🤖 <b>Name:</b> <code>{bot_name}</code>
📄 <b>File:</b> <code>{filename}</code>
🆔 <b>Process ID:</b> <code>{process_id}</code>

<b>⚡ Your bot is ready! Click Start to deploy!</b>
""",
        parse_mode="HTML",
        reply_markup=get_bot_control_keyboard(process_id, 'stopped')
    )


# ═══════════════════════════════════════════════════════════════
# 🔗 GIT CLONE
# ═══════════════════════════════════════════════════════════════

@user_router.callback_query(F.data == "git_clone")
async def cb_git_clone(callback: CallbackQuery):
    """Show git clone options"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if user['plan'] == 'free':
        await callback.answer("💎 Git Clone is a Premium feature!", show_alert=True)
        return
    
    text = """
🔗 <b>GIT CLONE</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>Clone a repository and auto-host!</b>

<b>Supported:</b>
• GitHub public repos
• GitLab public repos

<i>Send your repository URL to start.</i>
"""
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_git_clone_keyboard()
    )


@user_router.callback_query(F.data == "git_public")
async def cb_git_public(callback: CallbackQuery, state: FSMContext):
    """Start git clone process"""
    await callback.message.edit_text(
        """
🔗 <b>GIT CLONE</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>Send your public repository URL:</b>

<i>Example: https://github.com/user/repo</i>
""",
        parse_mode="HTML",
        reply_markup=get_back_keyboard("git_clone")
    )
    await state.set_state(UserStates.waiting_for_git_url)


@user_router.message(UserStates.waiting_for_git_url)
async def process_git_url(message: Message, state: FSMContext):
    """Process git URL and clone repo"""
    user_id = message.from_user.id
    url = message.text.strip()
    
    # Validate URL
    if not url.startswith(('https://github.com/', 'https://gitlab.com/', 'https://bitbucket.org/')):
        await message.answer("❌ Invalid URL. Only GitHub, GitLab, and Bitbucket are supported.")
        return
    
    await message.answer("⏳ <i>Cloning repository...</i>", parse_mode="HTML")
    
    # Clone repo
    from services.process_manager import git_manager
    
    success, msg, clone_dir = await git_manager.clone_repo(url, user_id)
    
    if not success:
        await message.answer(f"❌ {msg}")
        await state.clear()
        return
    
    # Find main file
    main_file = git_manager._find_main_file(clone_dir)
    
    if not main_file:
        await message.answer("❌ No Python file found in repository!")
        await state.clear()
        return
    
    # Create process
    repo_name = url.split('/')[-1].replace('.git', '')
    
    process_id = await db.add_process(
        user_id=user_id,
        process_name=f"Git: {repo_name}",
        filename=os.path.basename(main_file),
        file_path=main_file
    )
    
    await state.clear()
    
    if process_id == -1:
        await message.answer("❌ Failed to create process")
        return
    
    from keyboards import get_bot_control_keyboard
    
    await message.answer(
        f"""
✅ <b>REPOSITORY CLONED!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🔗 <b>Repo:</b> {repo_name}
📄 <b>Main File:</b> <code>{os.path.basename(main_file)}</code>
🆔 <b>Process ID:</b> <code>{process_id}</code>

<b>⚡ Ready to deploy!</b>
""",
        parse_mode="HTML",
        reply_markup=get_bot_control_keyboard(process_id, 'stopped')
    )


# ═══════════════════════════════════════════════════════════════
# 📦 MODULE INSTALLER
# ═══════════════════════════════════════════════════════════════

@user_router.callback_query(F.data == "install_module")
async def cb_install_module(callback: CallbackQuery):
    """Show module installer"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if user['plan'] == 'free':
        await callback.answer("💎 Module Installer is a Premium feature!", show_alert=True)
        return
    
    await callback.message.edit_text(
        """
📦 <b>MODULE INSTALLER</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>Select a package to install:</b>

<i>Or send a custom package name.</i>
""",
        parse_mode="HTML",
        reply_markup=get_module_install_keyboard()
    )


@user_router.callback_query(F.data.startswith("install_"))
async def cb_install_package(callback: CallbackQuery, state: FSMContext):
    """Install a package"""
    package = callback.data.split("_")[-1]
    
    if package == "custom":
        await callback.message.edit_text(
            """
📦 <b>CUSTOM MODULE</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>Send the package name to install:</b>

<i>Example: pandas, numpy, requests</i>
""",
            parse_mode="HTML",
            reply_markup=get_back_keyboard("install_module")
        )
        await state.set_state(UserStates.waiting_for_module)
        return
    
    await callback.message.edit_text(
        f"⏳ <i>Installing {package}...</i>",
        parse_mode="HTML"
    )
    
    from services.process_manager import module_installer
    
    success, output = await module_installer.install_module(package)
    
    if success:
        await callback.message.edit_text(
            f"✅ <b>{package} installed successfully!</b>\n\n<pre>{output[:500]}</pre>",
            parse_mode="HTML",
            reply_markup=get_back_keyboard("install_module")
        )
    else:
        await callback.message.edit_text(
            f"❌ <b>Installation failed!</b>\n\n<pre>{output[:500]}</pre>",
            parse_mode="HTML",
            reply_markup=get_back_keyboard("install_module")
        )


@user_router.message(UserStates.waiting_for_module)
async def process_custom_module(message: Message, state: FSMContext):
    """Process custom module installation"""
    package = message.text.strip().split()[0]  # Take first word
    
    await message.answer(f"⏳ <i>Installing {package}...</i>", parse_mode="HTML")
    
    from services.process_manager import module_installer
    
    success, output = await module_installer.install_module(package)
    
    await state.clear()
    
    if success:
        await message.answer(
            f"✅ <b>{package} installed successfully!</b>",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"❌ <b>Installation failed!</b>\n\n{output[:500]}",
            parse_mode="HTML"
        )


# ═══════════════════════════════════════════════════════════════
# ❌ CANCEL ACTION
# ═══════════════════════════════════════════════════════════════

@user_router.callback_query(F.data == "cancel_action")
async def cb_cancel_action(callback: CallbackQuery, state: FSMContext):
    """Cancel current action"""
    await state.clear()
    await cb_main_menu(callback)


# ═══════════════════════════════════════════════════════════════
# 📞 CONTACT SUPPORT
# ═══════════════════════════════════════════════════════════════

@user_router.callback_query(F.data == "contact_support")
async def cb_contact_support(callback: CallbackQuery):
    """Show contact info"""
    text = f"""
📞 <b>SUPPORT</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>Need help? Contact us!</b>

👤 <b>Owner:</b> @{OWNER_ID}
📢 <b>Channel:</b> @gadgetpremiumzone

<i>💡 Response time: 24-48 hours</i>
"""
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("help")
    )
