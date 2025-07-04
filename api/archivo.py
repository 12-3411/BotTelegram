
import os
import json
import asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters as Filters # Renombramos para evitar conflictos
)
import sys
from dotenv import load_dotenv
current_dir = os.path.dirname(os.path.abspath(__file__))

project_root = os.path.dirname(current_dir)

sys.path.append(project_root)
load_dotenv(os.path.join(project_root, '.env'))

from telegram.helpers import escape_markdown
from db import conectar_db


TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Leemos los ADMIN_IDS como una cadena de texto y la convertimos a lista de Python
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "[]") # Usamos "[]" como valor por defecto
ADMIN_IDS = json.loads(ADMIN_IDS_STR)

# --- INICIALIZACIÓN DE FLASK ---
app = Flask(__name__)

def es_admin(user_id):
    return user_id in ADMIN_IDS

async def mostrar_menu_principal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Genera y muestra el menú principal con los botones de inicio."""
    botones_inicio = [
        [InlineKeyboardButton("Recargar 📲", callback_data="recargar")],
        [InlineKeyboardButton("Historial 📜", callback_data="historial")]
    ]
    reply_markup = InlineKeyboardMarkup(botones_inicio)
    texto = "¡Bienvenido! Soy tu bot de recargas.\n¿Qué deseas hacer?"
    if update.callback_query:
        await update.callback_query.edit_message_text(text=texto, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text=texto, reply_markup=reply_markup)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /start. Registra al usuario y muestra el menú."""
    user = update.effective_user
    telegram_id = user.id
    nombre = user.full_name
    username = user.username or "N/A"
    try:
        conn = conectar_db()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO usuarios (telegram_id, nombre, username)
                VALUES (%s, %s, %s)
                ON CONFLICT (telegram_id) DO UPDATE SET
                    nombre = EXCLUDED.nombre,
                    username = EXCLUDED.username;
            """, (telegram_id, nombre, username))
            conn.commit()
    except Exception as e:
        print(f"Error al guardar usuario {telegram_id}: {e}")
    finally:
        if 'conn' in locals() and conn: conn.close()
    await mostrar_menu_principal(update, context)

async def manejar_callback_unificado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    if data == "recargar":
        botones_ofertas = [[InlineKeyboardButton("120 saldo x 250 CUP", callback_data="oferta_1")], [InlineKeyboardButton("240 saldo x 500 CUP", callback_data="oferta_2")], [InlineKeyboardButton("360 saldo x 800 CUP", callback_data="oferta_3")]]
        await query.edit_message_text(text="📦 Ofertas disponibles:\nSelecciona una opción:", reply_markup=InlineKeyboardMarkup(botones_ofertas))
    elif data.startswith("oferta_"):
        oferta_id = int(data.split("_")[1])
        try:
            conn = conectar_db()
            with conn.cursor() as cur:
                cur.execute("SELECT descripcion FROM ofertas WHERE id = %s;", (oferta_id,))
                oferta_info = cur.fetchone()
            if not oferta_info:
                await query.edit_message_text("❌ Error: Esa oferta ya no existe."); return
            oferta_txt = oferta_info[0]
            context.user_data["estado"] = "esperando_numero"
            context.user_data["oferta_id"] = oferta_id
            context.user_data["oferta_txt"] = oferta_txt
            await query.edit_message_text(f"✅ Has seleccionado: {oferta_txt}.\n\n📱 Ahora, por favor, escribe el número de teléfono que deseas recargar:")
        except Exception as e:
            print(f"Error al buscar oferta {oferta_id}: {e}")
            await query.edit_message_text("❌ Ocurrió un error.")
        finally:
            if 'conn' in locals() and conn: conn.close()
    elif data == "historial":
        try:
            conn = conectar_db()
            with conn.cursor() as cur:
                cur.execute("SELECT p.fecha_solicitud, o.descripcion, p.numero_destino, p.estado FROM pedidos p JOIN ofertas o ON p.oferta_id = o.id WHERE p.usuario_id = %s ORDER BY p.fecha_solicitud DESC LIMIT 5;", (user_id,))
                historial = cur.fetchall()
            if not historial:
                await query.edit_message_text(text="Aún no has realizado ninguna recarga. ¡Anímate a hacer la primera! 😊", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Volver", callback_data="menu_principal")]])); return
            status_map = {"confirmado": "✅ Confirmado", "pendiente": "⏳ Pendiente", "rechazado": "❌ Rechazado"}
            partes_mensaje = ["📜 *Tu historial de recargas recientes:*\n"]
            for fecha, oferta, numero, estado in historial:
                fecha_formateada = fecha.strftime('%d/%m/%Y %H:%M')
                status_texto = status_map.get(estado, f"❓ {estado.capitalize()}")
                partes_mensaje.append(f"🗓️ *{fecha_formateada}*\n   - *Oferta:* {oferta}\n   - *Número:* `{numero}`\n   - *Estado:* {status_texto}\n")
            await query.edit_message_text(text="\n".join(partes_mensaje), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Volver al menú", callback_data="menu_principal")]]), parse_mode="Markdown")
        except Exception as e:
            print(f"Error al obtener historial para {user_id}: {e}")
            await query.edit_message_text("❌ Ocurrió un error al cargar tu historial.")
        finally:
            if 'conn' in locals() and conn: conn.close()
    elif data == "menu_principal":
        await mostrar_menu_principal(update, context)
    if es_admin(user_id):
        if data == "admin_pedidos":
            try:
                conn = conectar_db()
                with conn.cursor() as cur:
                    cur.execute("SELECT p.id, u.nombre, o.descripcion FROM pedidos p JOIN usuarios u ON p.usuario_id = u.telegram_id JOIN ofertas o ON p.oferta_id = o.id WHERE p.estado = 'pendiente' ORDER BY p.fecha_solicitud ASC LIMIT 10;")
                    pedidos = cur.fetchall()
                if not pedidos:
                    await query.edit_message_text("✅ No hay pedidos pendientes."); return
                botones = [[InlineKeyboardButton(f"#{pid} - {nombre} ({oferta})", callback_data=f"ver_pedido_{pid}")] for pid, nombre, oferta in pedidos]
                botones.append([InlineKeyboardButton("⬅️ Volver al menú admin", callback_data="admin_menu")])
                await query.edit_message_text("📋 Pedidos pendientes:", reply_markup=InlineKeyboardMarkup(botones))
            except Exception as e:
                print(f"Error en admin_pedidos: {e}")
                await query.edit_message_text("❌ Error al cargar los pedidos.")
            finally:
                if 'conn' in locals() and conn: conn.close()
        elif data.startswith("ver_pedido_"):
            pedido_id = int(data.split("_")[-1])
            try:
                conn = conectar_db()
                with conn.cursor() as cur:
                    cur.execute("SELECT p.id, u.nombre, u.username, p.numero_destino, o.descripcion, c.tipo, c.contenido FROM pedidos p JOIN usuarios u ON p.usuario_id = u.telegram_id JOIN ofertas o ON p.oferta_id = o.id LEFT JOIN comprobantes c ON c.pedido_id = p.id WHERE p.id = %s;", (pedido_id,))
                    pedido_info = cur.fetchone()
                if not pedido_info:
                    await query.edit_message_text("❌ Pedido no encontrado."); return
                pid, nombre, username, numero, oferta, comp_tipo, comp_contenido = pedido_info
                mensaje = (f"📦 *Detalle del Pedido \\#{pid}*\n\n"
                           f"👤 *Cliente:* {escape_markdown(nombre or '', version=2)} \\(@{escape_markdown(username or 'N/A', version=2)}\\)\n"
                           f"📱 *Número a Recargar:* `{escape_markdown(numero or '', version=2)}`\n"
                           f"🎁 *Oferta Solicitada:* {escape_markdown(oferta or '', version=2)}\n\n"
                           f"🧾 *Comprobante Adjunto:*")
                await query.edit_message_text(mensaje, parse_mode="MarkdownV2")
                if comp_tipo == 'imagen': await context.bot.send_photo(chat_id=user_id, photo=comp_contenido, caption="Comprobante de imagen:")
                elif comp_tipo == 'texto': await context.bot.send_message(chat_id=user_id, text=f"Comprobante de texto:\n\n`{escape_markdown(comp_contenido or '', version=2)}`", parse_mode="MarkdownV2")
                else: await context.bot.send_message(chat_id=user_id, text="⚠️ No se encontró comprobante para este pedido.")
                botones_accion = [[InlineKeyboardButton("✅ Confirmar", callback_data=f"confirmar_{pid}"), InlineKeyboardButton("❌ Rechazar", callback_data=f"rechazar_{pid}")], [InlineKeyboardButton("⬅️ Volver a la lista", callback_data="admin_pedidos")]]
                await context.bot.send_message(chat_id=user_id, text="👇 ¿Qué deseas hacer?", reply_markup=InlineKeyboardMarkup(botones_accion))
            except Exception as e:
                print(f"Error en ver_pedido: {e}")
                await query.edit_message_text("❌ Error al cargar detalles.")
            finally:
                if 'conn' in locals() and conn: conn.close()
        elif data.startswith("confirmar_"):
            pedido_id = int(data.split("_")[1])
            try:
                conn = conectar_db()
                with conn.cursor() as cur:
                    cur.execute("UPDATE pedidos SET estado = 'confirmado', fecha_confirmacion = CURRENT_TIMESTAMP WHERE id = %s RETURNING usuario_id;", (pedido_id,))
                    resultado = cur.fetchone()
                    conn.commit()
                if resultado: await context.bot.send_message(chat_id=resultado[0], text=f"🎉 ¡Tu pedido #{pedido_id} ha sido confirmado!")
                await query.edit_message_text(f"✅ Pedido #{pedido_id} confirmado y usuario notificado.")
            except Exception as e:
                print(f"Error al confirmar pedido {pedido_id}: {e}")
            finally:
                if 'conn' in locals() and conn: conn.close()
        elif data.startswith("rechazar_"):
            pedido_id = int(data.split("_")[1])
            context.user_data["estado_admin"] = "esperando_motivo_rechazo"
            context.user_data["pedido_a_rechazar_id"] = pedido_id
            await query.edit_message_text("✏️ Escribe el motivo del rechazo. Se le enviará al usuario.")
        elif data == "admin_menu":
             await admin(update, context, is_callback=True)

async def recibir_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mensaje = update.message.text
    if es_admin(user_id) and context.user_data.get("estado_admin") == "esperando_motivo_rechazo":
        pedido_id = context.user_data.get("pedido_a_rechazar_id")
        motivo = mensaje
        try:
            conn = conectar_db()
            with conn.cursor() as cur:
                cur.execute("UPDATE pedidos SET estado = 'rechazado', motivo_rechazo = %s WHERE id = %s RETURNING usuario_id;", (motivo, pedido_id))
                resultado = cur.fetchone()
                conn.commit()
            if resultado: await context.bot.send_message(chat_id=resultado[0], text=f"❌ Tu pedido #{pedido_id} ha sido rechazado.\n*Motivo:* {motivo}")
            await update.message.reply_text(f"❌ Pedido #{pedido_id} rechazado y usuario notificado.")
        except Exception as e:
            print(f"Error al rechazar pedido {pedido_id}: {e}")
        finally:
            if 'conn' in locals() and conn: conn.close()
            context.user_data.clear()
        return
    estado_usuario = context.user_data.get("estado")
    if not estado_usuario: return
    if estado_usuario == "esperando_numero":
        if not (mensaje.isdigit() and len(mensaje) >= 8):
            await update.message.reply_text("❌ Número inválido. Envía solo dígitos."); return
        context.user_data["numero"] = mensaje
        context.user_data["estado"] = "esperando_comprobante"
        try:
            conn = conectar_db()
            with conn.cursor() as cur:
                cur.execute("INSERT INTO pedidos (usuario_id, oferta_id, numero_destino) VALUES (%s, %s, %s) RETURNING id;", (user_id, context.user_data["oferta_id"], mensaje))
                pedido_id = cur.fetchone()[0]
                conn.commit()
            context.user_data["pedido_id"] = pedido_id
            await update.message.reply_text("🔢 Número guardado.\n\n💸 Ahora envía una captura del comprobante de pago.")
        except Exception as e:
            print(f"Error al guardar pedido: {e}")
        finally:
            if 'conn' in locals() and conn: conn.close()
    elif estado_usuario == "esperando_comprobante":
        await update.message.reply_text("Por favor, envía el comprobante como una imagen, no como texto.")

async def recibir_imagen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if context.user_data.get("estado") != "esperando_comprobante": return
    file_id = update.message.photo[-1].file_id
    try:
        conn = conectar_db()
        with conn.cursor() as cur:
            cur.execute("INSERT INTO comprobantes (pedido_id, tipo, contenido) VALUES (%s, %s, %s);", (context.user_data["pedido_id"], "imagen", file_id))
            conn.commit()
        await update.message.reply_text("✅ ¡Imagen recibida! Tu pedido será validado por un administrador a la brevedad.")
        try:
            pedido_id = context.user_data["pedido_id"]
            user_nombre = update.effective_user.full_name
            oferta_txt = context.user_data.get("oferta_txt", "Oferta no especificada")
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔍 Ver y Gestionar Pedido Ahora", callback_data=f"ver_pedido_{pedido_id}")]])
            mensaje_para_admin = (f"🔔 *¡Nueva Solicitud de Recarga Pendiente!* 🔔\n\n👤 **De:** {user_nombre}\n🎁 **Oferta:** {oferta_txt}")
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(chat_id=admin_id, text=mensaje_para_admin, parse_mode="Markdown", reply_markup=markup)
                except Exception as e_inner:
                    print(f"Fallo al notificar al admin {admin_id}: {e_inner}")
        except Exception as e:
            print(f"Error crítico al intentar notificar a los admins: {e}")
    except Exception as e:
        print(f"Error al guardar imagen de comprobante: {e}")
        await update.message.reply_text("❌ Ocurrió un error al guardar tu comprobante.")
    finally:
        context.user_data.clear()
        if 'conn' in locals() and conn: conn.close()

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
    if not es_admin(update.effective_user.id):
        await update.message.reply_text("🚫 Acceso denegado."); return
    botones_admin = [[InlineKeyboardButton("📥 Ver Pedidos Pendientes", callback_data="admin_pedidos")]]
    texto = "🔐 Panel de Administración"
    reply_markup = InlineKeyboardMarkup(botones_admin)
    if is_callback:
        await update.callback_query.edit_message_text(text=texto, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text=texto, reply_markup=reply_markup)

# ====================================================================
#          SECCIÓN FINAL PARA INTEGRACIÓN CON VERCEL
#          Esta parte reemplaza tu antigua función `main()`
# ====================================================================

# 1. Creamos la "aplicación" de Telegram y le añadimos todos los manejadores de eventos.
#    Esto se hace una sola vez cuando Vercel carga el script.
application = ApplicationBuilder().token(TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("admin", admin))
application.add_handler(CallbackQueryHandler(manejar_callback_unificado))
application.add_handler(MessageHandler(Filters.TEXT & ~Filters.COMMAND, recibir_mensaje))
application.add_handler(MessageHandler(Filters.PHOTO, recibir_imagen))

# 2. Definimos las rutas web que Vercel expondrá al mundo.
@app.route('/webhook', methods=['POST'])
def webhook_handler():
    """Esta función se ejecuta cada vez que Telegram envía un mensaje."""
    # Usamos asyncio.run() para ejecutar el código asíncrono de la librería
    # desde el entorno síncrono de Flask.
    asyncio.run(application.process_update(
        Update.de_json(request.get_json(force=True), application.bot)
    ))
    return 'ok'

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Esta ruta es para configurar el webhook la primera vez."""
    # Vercel nos da la URL pública en una variable de entorno.
    vercel_url = f'https://{os.getenv("VERCEL_URL")}'
    # Le decimos a Telegram a dónde debe enviar los mensajes.
    success = asyncio.run(application.bot.set_webhook(f'{vercel_url}/webhook'))
    return "¡Webhook configurado exitosamente!" if success else "Error al configurar el webhook."

@app.route('/')
def index():
    """Una ruta de prueba para saber que el bot está desplegado y vivo."""
    return '¡El servidor del bot de Telegram está funcionando!'

