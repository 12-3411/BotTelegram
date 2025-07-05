import os
import json
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv
import requests

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
VERCEL_URL = os.getenv("VERCEL_URL")
ADMIN_IDS = json.loads(os.getenv("ADMIN_IDS", "[]"))

app = Flask(__name__)
application = ApplicationBuilder().token(TOKEN).build()

def es_admin(user_id):
    return user_id in ADMIN_IDS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot en Vercel funcionando vía webhook.")

application.add_handler(CommandHandler("start", start))

@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.run(application.process_update(update))
    return "ok"

@app.route("/set_webhook")
def set_webhook():
    url = f"https://{VERCEL_URL}/webhook"
    r = requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={url}")
    return r.json()

@app.route("/")
def index():
    return "🟢 Bot funcionando"
