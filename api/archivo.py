import os
import json
import asyncio
import requests
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    ContextTypes
)
from dotenv import load_dotenv
from telegram.helpers import escape_markdown

# ==== CARGA DE VARIABLES ====
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_IDS = json.loads(os.getenv("ADMIN_IDS", "[]"))

# ==== FLASK ====
app = Flask(__name__)

# ==== TELEGRAM BOT APP ====
application = ApplicationBuilder().token(TOKEN).build()

def es_admin(user_id):
    return user_id in ADMIN_IDS

# ==== COMANDOS BÁSICOS ====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Hola! Soy tu bot funcionando desde Vercel con webhook.")

application.add_handler(CommandHandler("start", start))

# ==== RUTA DE WEBHOOK ====
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        print("--- INFO: Petición /webhook recibida.")
        update = Update.de_json(request.get_json(force=True), application.bot)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(application.process_update(update))
    except Exception as e:
        print(f"--- ERROR al procesar webhook: {e}")
    return "ok"

# ==== RUTA PARA SETEAR EL WEBHOOK ====
@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    webhook_url = f"https://{os.getenv('VERCEL_URL')}/webhook"
    telegram_api_url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={webhook_url}"
    print(f"--- INFO: Estableciendo Webhook en: {webhook_url}")
    response = requests.get(telegram_api_url)
    return response.json()

# ==== RUTA RAÍZ ====
@app.route("/", methods=["GET"])
def home():
    return "✅ Bot de Telegram está vivo en Vercel"

# IMPORTANTE: Exportar correctamente la app para Vercel
app = app
