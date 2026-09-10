import os
import logging
import sqlite3
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
FORCE_CHANNELS = [x.strip() for x in os.getenv("FORCE_CHANNELS", "").split(",") if x.strip()]
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
PROJECT_DIR = DATA_DIR / "projects"
DB_PATH = DATA_DIR / "bot.db"
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "50"))

DATA_DIR.mkdir(parents=True, exist_ok=True)
PROJECT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("hosting-bot")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
        banned INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        filename TEXT NOT NULL,
        size INTEGER NOT NULL,
        status TEXT DEFAULT 'uploaded',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()


def upsert_user(user):
    conn = db()
    conn.execute("""
        INSERT INTO users(user_id, username, first_name)
        VALUES(?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET
        username=excluded.username,
        first_name=excluded.first_name,
        last_seen=CURRENT_TIMESTAMP
    """, (user.id, user.username or "", user.first_name or ""))
    conn.commit()
    conn.close()


def is_banned(user_id):
    conn = db()
    row = conn.execute("SELECT banned FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return bool(row and row["banned"])


async def joined_all(bot, user_id):
    for channel in FORCE_CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status in ("left", "kicked"):
                return False
        except Exception:
            return False
    return True


def join_keyboard():
    rows = []
    for i, channel in enumerate(FORCE_CHANNELS, 1):
        rows.append([InlineKeyboardButton(
            f"📢 Channel {i}",
            url=f"https://t.me/{channel.lstrip('@')}"
        )])
    rows.append([InlineKeyboardButton("✅ Verify", callback_data="verify")])
    return InlineKeyboardMarkup(rows)


def home_keyboard(user_id):
    rows = [
        [InlineKeyboardButton("🚀 My Projects", callback_data="projects"),
         InlineKeyboardButton("📤 Upload", callback_data="upload")],
        [InlineKeyboardButton("👤 Account", callback_data="account"),
         InlineKeyboardButton("📚 Help", callback_data="help")]
    ]
    if user_id == ADMIN_ID:
        rows.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin")])
    return InlineKeyboardMarkup(rows)


def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Users", callback_data="admin_users"),
         InlineKeyboardButton("📦 Projects", callback_data="admin_projects")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
         InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Home", callback_data="home")]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user)

    if is_banned(user.id):
        await update.message.reply_text("🚫 Your account is blocked.")
        return

    if FORCE_CHANNELS and not await joined_all(context.bot, user.id):
        await update.message.reply_text(
            "🔒 *Join Required*\n\nJoin all required channels, then press Verify.",
            parse_mode="Markdown",
            reply_markup=join_keyboard()
        )
        return

    await update.message.reply_text(
        f"🚀 *Welcome, {user.first_name}!*

"
        "Your Telegram hosting dashboard is ready.

"
        "📤 Upload projects
📦 Manage projects
📊 View account details",
        parse_mode="Markdown",
        reply_markup=home_keyboard(user.id)
    )


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    upsert_user(user)

    if q.data == "verify":
        if FORCE_CHANNELS and not await joined_all(context.bot, user.id):
            await q.answer("❌ Join every required channel first.", show_alert=True)
            return
        await q.edit_message_text(
            "✅ *Verified!*\n\nWelcome to your hosting dashboard.",
            parse_mode="Markdown",
            reply_markup=home_keyboard(user.id)
        )
        return

    if q.data == "home":
        await q.edit_message_text("🏠 *Main Menu*", parse_mode="Markdown",
                                  reply_markup=home_keyboard(user.id))
        return

    if q.data == "upload":
        context.user_data["waiting_upload"] = True
        await q.edit_message_text(
            "📤 *Upload Project*\n\n"
            "Send your project as a Telegram document. ZIP is recommended.\n\n"
            "The uploaded file will be stored and tracked by the bot.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="home")]
            ])
        )
        return

    if q.data == "projects":
        conn = db()
        rows = conn.execute(
            "SELECT id,name,filename,size,status FROM projects WHERE user_id=? "
            "ORDER BY id DESC LIMIT 20", (user.id,)
        ).fetchall()
        conn.close()

        text = "📦 *My Projects*\n\n"
        if not rows:
            text += "No projects yet."
        else:
            for r in rows:
                text += f"• `#{r['id']}` {r['name']} — {r['status']} — {r['size']/1024/1024:.2f} MB\n"

        await q.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Upload", callback_data="upload")],
                [InlineKeyboardButton("🔙 Back", callback_data="home")]
            ])
        )
        return

    if q.data == "account":
        conn = db()
        count = conn.execute("SELECT COUNT(*) c FROM projects WHERE user_id=?", (user.id,)).fetchone()["c"]
        conn.close()
        await q.edit_message_text(
            f"👤 *Account*\n\nID: `{user.id}`\nUsername: @{user.username or 'none'}\nProjects: `{count}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="home")]
            ])
        )
        return

    if q.data == "help":
        await q.edit_message_text(
            "📚 *Help*\n\n"
            "1. Open Upload.\n2. Send a project as a document.\n"
            "3. Open My Projects to view it.\n\n"
            "Never upload secrets such as bot tokens or passwords.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="home")]
            ])
        )
        return

    if q.data == "admin":
        if user.id != ADMIN_ID:
            await q.answer("❌ Admin only.", show_alert=True)
            return
        await q.edit_message_text("👑 *ADMIN PANEL*", parse_mode="Markdown",
                                  reply_markup=admin_keyboard())
        return

    if q.data.startswith("admin_"):
        if user.id != ADMIN_ID:
            await q.answer("❌ Admin only.", show_alert=True)
            return
        await admin_action(q, context)


async def admin_action(q, context):
    conn = db()

    if q.data == "admin_users":
        total = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        banned = conn.execute("SELECT COUNT(*) c FROM users WHERE banned=1").fetchone()["c"]
        text = f"👥 *Users*\n\nTotal: `{total}`\nBanned: `{banned}`"

    elif q.data == "admin_projects":
        total = conn.execute("SELECT COUNT(*) c FROM projects").fetchone()["c"]
        text = f"📦 *Projects*\n\nTotal: `{total}`"

    elif q.data == "admin_stats":
        users = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        projects = conn.execute("SELECT COUNT(*) c FROM projects").fetchone()["c"]
        size = conn.execute("SELECT COALESCE(SUM(size),0) s FROM projects").fetchone()["s"]
        text = (f"📊 *Statistics*\n\nUsers: `{users}`\nProjects: `{projects}`\n"
                f"Stored: `{size/1024/1024:.2f} MB`")

    elif q.data == "admin_broadcast":
        context.user_data["broadcast_mode"] = True
        conn.close()
        await q.edit_message_text(
            "📢 *Broadcast Mode*\n\nSend the message to broadcast.\nUse /cancel to cancel.",
            parse_mode="Markdown"
        )
        return
    else:
        conn.close()
        return

    conn.close()
    await q.edit_message_text(text, parse_mode="Markdown",
                              reply_markup=InlineKeyboardMarkup([
                                  [InlineKeyboardButton("🔙 Admin", callback_data="admin")]
                              ]))


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access denied.")
        return
    await update.message.reply_text("👑 *ADMIN PANEL*", parse_mode="Markdown",
                                    reply_markup=admin_keyboard())


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled.")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user)

    if user.id == ADMIN_ID and context.user_data.get("broadcast_mode"):
        context.user_data["broadcast_mode"] = False
        conn = db()
        ids = [r["user_id"] for r in conn.execute(
            "SELECT user_id FROM users WHERE banned=0").fetchall()]
        conn.close()

        sent = failed = 0
        for uid in ids:
            try:
                await update.message.copy(chat_id=uid)
                sent += 1
            except Exception:
                failed += 1
        await update.message.reply_text(f"📢 Broadcast finished.\n\nSent: {sent}\nFailed: {failed}")
        return

    if not context.user_data.get("waiting_upload"):
        await update.message.reply_text("Use /start → 📤 Upload first.")
        return

    doc = update.message.document
    if not doc:
        await update.message.reply_text("❌ Send the project as a document.")
        return

    if doc.file_size and doc.file_size > MAX_FILE_MB * 1024 * 1024:
        await update.message.reply_text(f"❌ File too large. Limit: {MAX_FILE_MB} MB.")
        return

    safe_name = Path(doc.file_name or "upload.bin").name
    user_dir = PROJECT_DIR / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    target = user_dir / safe_name

    if target.exists():
        target = user_dir / f"{doc.file_unique_id}_{safe_name}"

    tg_file = await context.bot.get_file(doc.file_id)
    await tg_file.download_to_drive(custom_path=str(target))

    conn = db()
    cur = conn.execute(
        "INSERT INTO projects(user_id,name,filename,size,status) VALUES(?,?,?,?,?)",
        (user.id, target.stem, target.name,
         doc.file_size or target.stat().st_size, "uploaded")
    )
    project_id = cur.lastrowid
    conn.commit()
    conn.close()

    context.user_data["waiting_upload"] = False

    await update.message.reply_text(
        f"✅ *Project uploaded!*\n\n"
        f"ID: `#{project_id}`\nFile: `{safe_name}`\n"
        f"Size: `{(doc.file_size or 0)/1024/1024:.2f} MB`\n"
        f"Status: `uploaded`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📦 My Projects", callback_data="projects")],
            [InlineKeyboardButton("🏠 Home", callback_data="home")]
        ])
    )


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is missing")

    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, message_handler))

    log.info("Bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
