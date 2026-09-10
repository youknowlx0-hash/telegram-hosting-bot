from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from config import BOT_TOKEN, ADMIN_ID, FORCE_CHANNELS
from database import init_db, add_user


async def check_force_join(bot, user_id):
    for channel in FORCE_CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)

            if member.status in ["left", "kicked"]:
                return False

        except Exception:
            return False

    return True


def force_join_keyboard():
    buttons = []

    for i, channel in enumerate(FORCE_CHANNELS, 1):
        buttons.append([
            InlineKeyboardButton(
                f"📢 Channel {i}",
                url=f"https://t.me/{channel.replace('@', '')}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("✅ Verify", callback_data="verify")
    ])

    return InlineKeyboardMarkup(buttons)


def main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚀 My Projects", callback_data="projects"),
            InlineKeyboardButton("📤 Upload", callback_data="upload"),
        ],
        [
            InlineKeyboardButton("👤 My Account", callback_data="account"),
            InlineKeyboardButton("📚 Help", callback_data="help"),
        ]
    ])


def admin_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👥 Users", callback_data="admin_users"),
            InlineKeyboardButton("📦 Projects", callback_data="admin_projects"),
        ],
        [
            InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
            InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"),
        ]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    add_user(user)

    joined = await check_force_join(
        context.bot,
        user.id
    )

    if not joined:
        await update.message.reply_text(
            "🔒 *Join Required*\n\n"
            "Please join all required channels and then "
            "press Verify.",
            reply_markup=force_join_keyboard(),
            parse_mode="Markdown"
        )
        return

    await update.message.reply_text(
        f"🚀 *Welcome {user.first_name}!*\n\n"
        "Your personal Telegram hosting panel is ready.\n\n"
        "📤 Upload your project\n"
        "▶️ Start your service\n"
        "⏹ Stop your service\n"
        "📜 View logs\n"
        "📊 Check status",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if query.data == "verify":

        joined = await check_force_join(
            context.bot,
            user_id
        )

        if not joined:
            await query.answer(
                "❌ Please join all channels first.",
                show_alert=True
            )
            return

        await query.edit_message_text(
            "✅ Verification successful!\n\n"
            "Welcome to your hosting panel.",
            reply_markup=main_keyboard()
        )

    elif query.data == "projects":

        await query.edit_message_text(
            "📦 *My Projects*\n\n"
            "You don't have any projects yet.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "📤 Upload Project",
                        callback_data="upload"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data="home"
                    )
                ]
            ])
        )

    elif query.data == "upload":

        await query.edit_message_text(
            "📤 *Upload Project*\n\n"
            "Send your project file as a document.\n\n"
            "ZIP projects are recommended.",
            parse_mode="Markdown"
        )

    elif query.data == "account":

        await query.edit_message_text(
            f"👤 *Account*\n\n"
            f"ID: `{user_id}`",
            parse_mode="Markdown"
        )

    elif query.data == "help":

        await query.edit_message_text(
            "📚 *Hosting Bot Help*\n\n"
            "Upload your project and manage it "
            "from the project panel.",
            parse_mode="Markdown"
        )

    elif query.data == "home":

        await query.edit_message_text(
            "🏠 *Main Menu*",
            reply_markup=main_keyboard(),
            parse_mode="Markdown"
        )


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access denied.")
        return

    await update.message.reply_text(
        "👑 *ADMIN PANEL*\n\n"
        "Select an option:",
        reply_markup=admin_keyboard(),
        parse_mode="Markdown"
    )


def run():

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing")

    init_db()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(
        CallbackQueryHandler(callbacks)
    )

    print("🚀 Bot started...")

    app.run_polling()


if __name__ == "__main__":
    run()
