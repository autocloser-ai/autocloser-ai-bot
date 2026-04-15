import os
import sqlite3
from datetime import datetime
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, filters
from openai import OpenAI

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_KEY")
AFFILIATE_LINK = os.getenv("AFFILIATE_LINK")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

client = OpenAI(api_key=OPENAI_KEY)

# ===== TELEGRAM SETUP =====
bot = Bot(token=BOT_TOKEN)
app = Flask(__name__)
dispatcher = Dispatcher(bot, None, workers=4)

# ===== DATABASE =====
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    intent INTEGER DEFAULT 0,
    last_interaction TEXT
)
""")
conn.commit()

# ===== AI =====
def ai_reply(message):
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": f"You are an expert affiliate closer. Only send this link when needed: {AFFILIATE_LINK}"},
            {"role": "user", "content": message}
        ]
    )
    return response.choices[0].message.content

# ===== HANDLERS =====
def start(update, context):
    user = update.message.from_user
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, last_interaction) VALUES (?, ?, ?)",
                   (user.id, user.username, str(datetime.now())))
    conn.commit()
    update.message.reply_text("Welcome 👋")

def handle(update, context):
    msg = update.message.text
    reply = ai_reply(msg)

    if "start" in msg.lower():
        update.message.reply_text("Start here 👇\n" + AFFILIATE_LINK)
        return

    update.message.reply_text(reply)

# ===== REGISTER =====
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(filters.TEXT, handle))

# ===== WEBHOOK ROUTE =====
@app.route("/", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

# ===== HEALTH CHECK =====
@app.route("/", methods=["GET"])
def health():
    return "Bot is running"

# ===== RUN =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
