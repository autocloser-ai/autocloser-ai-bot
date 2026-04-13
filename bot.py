import sqlite3
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from openai import OpenAI
from gtts import gTTS
import os

# ===== CONFIG =====
BOT_TOKEN = "7990678172:AAGQ4pwZ2gwFtm6Pju-gLXIEZnB5Pkac-ls"
OPENAI_KEY = "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"
AFFILIATE_LINK = "https://your-affiliate-link.com"
ADMIN_ID = 469109915
WHATSAPP_LINK = "Authenta "

client = OpenAI(api_key=OPENAI_KEY)

# ===== DATABASE =====
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    stage TEXT DEFAULT 'new',
    intent INTEGER DEFAULT 0,
    user_type TEXT DEFAULT 'unknown',
    last_interaction TEXT,
    clicked INTEGER DEFAULT 0,
    hot_lead INTEGER DEFAULT 0
)
""")
conn.commit()

# ===== SYSTEM PROMPT =====
SYSTEM_PROMPT = f"""
You are a high-level affiliate marketing closer.

- Be human
- Ask questions
- Understand user pain
- Build desire before link
- Remove doubts
- Simple beginner language

Only send link when ready:
{AFFILIATE_LINK}
"""

# ===== AI =====
async def get_intent_score(message):
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": "Score buying intent 0-100. Return number only."},
            {"role": "user", "content": message}
        ]
    )
    try:
        return int(response.choices[0].message.content.strip())
    except:
        return 0

async def ai_reply(message):
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message}
        ]
    )
    return response.choices[0].message.content

# ===== USER UPDATE =====
def update_user(user_id, username):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO users (user_id, username, last_interaction) VALUES (?, ?, ?)",
            (user_id, username, str(datetime.now()))
        )
    else:
        cursor.execute(
            "UPDATE users SET last_interaction=? WHERE user_id=?",
            (str(datetime.now()), user_id)
        )
    conn.commit()

# ===== FOLLOW UP =====
async def follow_up():
    now = datetime.now()
    cursor.execute("SELECT user_id, last_interaction FROM users")
    users = cursor.fetchall()

    for user_id, last_time in users:
        if last_time:
            last_time = datetime.fromisoformat(last_time)
            diff = now - last_time

            if diff > timedelta(hours=1) and diff < timedelta(hours=2):
                try:
                    await app.bot.send_message(chat_id=user_id, text="Still thinking? Start here ð\n" + AFFILIATE_LINK)
                except:
                    pass

# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    update_user(user.id, user.username)
    await update.message.reply_text("Welcome ð")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    msg = update.message.text.lower()
    update_user(user.id, user.username)

    intent = await get_intent_score(msg)

    cursor.execute("UPDATE users SET intent=? WHERE user_id=?", (intent, user.id))

    if intent >= 80:
        cursor.execute("UPDATE users SET hot_lead=1 WHERE user_id=?", (user.id,))
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"ð¥ HOT LEAD {user.id} - {intent}%")
        except:
            pass

    conn.commit()

    if intent >= 85:
        await update.message.reply_text("Start here ð\n" + AFFILIATE_LINK)
        return

    reply = await ai_reply(msg)

    # Voice (female-like via tld)
    tts = gTTS(reply, lang='en', tld='co.uk')
    tts.save("voice.mp3")

    await update.message.reply_text(reply)
    with open("voice.mp3", "rb") as audio:
        await update.message.reply_voice(audio)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE hot_lead=1")
    hot = cursor.fetchone()[0]

    await update.message.reply_text(f"Users: {total}\nHot Leads: {hot}")

# ===== APP =====
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

scheduler = AsyncIOScheduler()
scheduler.add_job(follow_up, "interval", minutes=10)
scheduler.start()

app.run_polling()
