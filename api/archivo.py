from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from db import conectar_db
from telegram.helpers import escape_markdown

# ------------------ Configuración ---------------------
ADMIN_IDS = [2047892910]
TOKEN = '8154074350:AAE3KUzGqHN6xEt7mtEq1fIakFxgM-Jelzs'

# ------------------ Función de ayuda para Admin ---------------------
def es_admin(user_id):
    return user_id in ADMIN_IDS
# Cerca del inicio del código, después de la función start
async def mostrar_menu_principal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Genera y muestra el menú principal con los botones de inicio."""
    botones_inicio = [
        [InlineKeyboardButton("Recargar 📲", callback_data="recargar")],
        [InlineKeyboardButton("Historial 📜", callback_data="historial")]
    ]
    reply_markup = InlineKeyboardMarkup(botones_inicio)
    texto = "¡Bienvenido! Soy tu bot de recargas.\n¿Qué deseas hacer?"

    # Diferenciamos si es un comando nuevo o una edición de un mensaje existente
    if update.callback_query:
        # Si viene de un botón (callback), editamos el mensaje
        await update.callback_query.edit_message_text(text=texto, reply_markup=reply_markup)
    else:
        # Si viene de un comando (como /start), enviamos un nuevo mensaje
        await update.message.reply_text(text=texto, reply_markup=reply_markup)
# ------------------ Comando /start ---------------------
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
    
    # Llamamos a la nueva función para mostrar el menú
    await mostrar_menu_principal(update, context)
# ------------------ Manejador de todos los Botones (Callbacks) ---------------------
async def manejar_callback_unificado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    # --- LÓGICA PARA USUARIOS NORMALES ---
    if data == "recargar":
        botones_ofertas = [
            [InlineKeyboardButton("120 saldo x 250 CUP", callback_data="oferta_1")],
            [InlineKeyboardButton("240 saldo x 500 CUP", callback_data="oferta_2")],
            [InlineKeyboardButton("360 saldo x 800 CUP", callback_data="oferta_3")]
        ]
        await query.edit_message_text(text="📦 Ofertas disponibles:\nSelecciona una opción:", reply_markup=InlineKeyboardMarkup(botones_ofertas))

    elif data.startswith("oferta_"):
        oferta_id = int(data.split("_")[1])
        try:
            conn = conectar_db()
            with conn.cursor() as cur:
                cur.execute("SELECT descripcion FROM ofertas WHERE id = %s;", (oferta_id,))
                oferta_info = cur.fetchone()
            if not oferta_info:
                await query.edit_message_text("❌ Error: Esa oferta ya no existe.")
                return
            
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
                cur.execute("""
                    SELECT p.fecha_solicitud, o.descripcion, p.numero_destino, p.estado
                    FROM pedidos p
                    JOIN ofertas o ON p.oferta_id = o.id
                    WHERE p.usuario_id = %s
                    ORDER BY p.fecha_solicitud DESC
                    LIMIT 5;
                """, (user_id,))
                historial = cur.fetchall()

            if not historial:
                mensaje = "Aún no has realizado ninguna recarga. ¡Anímate a hacer la primera! 😊"
                botones = [[InlineKeyboardButton("⬅️ Volver", callback_data="menu_principal")]]
                await query.edit_message_text(text=mensaje, reply_markup=InlineKeyboardMarkup(botones))
                return

            # Diccionario para mapear estados a emojis y texto
            status_map = {
                "confirmado": "✅ Confirmado",
                "pendiente": "⏳ Pendiente",
                "rechazado": "❌ Rechazado"
            }

            # Construimos el mensaje del historial
            partes_mensaje = ["📜 *Tu historial de recargas recientes:*\n"]
            for fecha, oferta, numero, estado in historial:
                fecha_formateada = fecha.strftime('%d/%m/%Y %H:%M')
                status_texto = status_map.get(estado, f"❓ {estado.capitalize()}")
                linea = (
                    f"🗓️ *{fecha_formateada}*\n"
                    f"   - *Oferta:* {oferta}\n"
                    f"   - *Número:* `{numero}`\n"
                    f"   - *Estado:* {status_texto}\n"
                )
                partes_mensaje.append(linea)

            mensaje_final = "\n".join(partes_mensaje)
            botones = [[InlineKeyboardButton("⬅️ Volver al menú", callback_data="menu_principal")]]
            await query.edit_message_text(
                text=mensaje_final,
                reply_markup=InlineKeyboardMarkup(botones),
                parse_mode="Markdown"
            )

        except Exception as e:
            print(f"Error al obtener historial para {user_id}: {e}")
            await query.edit_message_text("❌ Ocurrió un error al cargar tu historial.")
        finally:
            if 'conn' in locals() and conn: conn.close()

    # Añade este nuevo elif para manejar el botón "Volver"
    elif data == "menu_principal":
        await mostrar_menu_principal(update, context)


    # --- LÓGICA PARA ADMINISTRADORES ---
    if es_admin(user_id):
        if data == "admin_pedidos":
            try:
                conn = conectar_db()
                with conn.cursor() as cur:
                    cur.execute("SELECT p.id, u.nombre, o.descripcion FROM pedidos p JOIN usuarios u ON p.usuario_id = u.telegram_id JOIN ofertas o ON p.oferta_id = o.id WHERE p.estado = 'pendiente' ORDER BY p.fecha_solicitud ASC LIMIT 10;")
                    pedidos = cur.fetchall()
                if not pedidos:
                    await query.edit_message_text("✅ No hay pedidos pendientes.")
                    return
                botones = [[InlineKeyboardButton(f"#{pid} - {nombre} ({oferta})", callback_data=f"ver_pedido_{pid}")] for pid, nombre, oferta in pedidos]
                botones.append([InlineKeyboardButton("⬅️ Volver al menú admin", callback_data="admin_menu")])
                await query.edit_message_text("📋 Pedidos pendientes:", reply_markup=InlineKeyboardMarkup(botones))
            except Exception as e:
                print(f"Error en admin_pedidos: {e}")
                await query.edit_message_text("❌ Error al cargar los pedidos.")
            finally:
                if 'conn' in locals() and conn:
                    conn.close()

        elif data.startswith("ver_pedido_"):
            pedido_id = int(data.split("_")[-1])
            try:
                conn = conectar_db()
                with conn.cursor() as cur:
                    cur.execute("SELECT p.id, u.nombre, u.username, p.numero_destino, o.descripcion, c.tipo, c.contenido FROM pedidos p JOIN usuarios u ON p.usuario_id = u.telegram_id JOIN ofertas o ON p.oferta_id = o.id LEFT JOIN comprobantes c ON c.pedido_id = p.id WHERE p.id = %s;", (pedido_id,))
                    pedido_info = cur.fetchone()
                if not pedido_info:
                    await query.edit_message_text("❌ Pedido no encontrado.")
                    return
                
                pid, nombre, username, numero, oferta, comp_tipo, comp_contenido = pedido_info
                
                nombre_escaped = escape_markdown(nombre or "Sin Nombre", version=2)
                username_escaped = escape_markdown(username or "N/A", version=2)
                oferta_escaped = escape_markdown(oferta or "Sin Descripción", version=2)
                numero_escaped = escape_markdown(numero or "Sin Número", version=2)
                
                # --- CORRECCIÓN FINAL EN LA LÍNEA SIGUIENTE ---
                mensaje = (
                    f"📦 *Detalle del Pedido \\#{pid}*\n\n"
                    f"👤 *Cliente:* {nombre_escaped} \\(@{username_escaped}\\)\n"  # Se escapan '(' y ')'
                    f"📱 *Número a Recargar:* `{numero_escaped}`\n"
                    f"🎁 *Oferta Solicitada:* {oferta_escaped}\n\n"
                    f"🧾 *Comprobante Adjunto:*"
                )
                # -------------------------------------------------

                await query.edit_message_text(mensaje, parse_mode="MarkdownV2")
                
                if comp_tipo == 'imagen':
                    await context.bot.send_photo(chat_id=user_id, photo=comp_contenido, caption="Comprobante de imagen:")
                elif comp_tipo == 'texto':
                    comp_contenido_escaped = escape_markdown(comp_contenido or "", version=2)
                    await context.bot.send_message(chat_id=user_id, text=f"Comprobante de texto:\n\n`{comp_contenido_escaped}`", parse_mode="MarkdownV2")
                else:
                    await context.bot.send_message(chat_id=user_id, text="⚠️ No se encontró comprobante para este pedido.")

                botones_accion = [
                    [InlineKeyboardButton("✅ Confirmar", callback_data=f"confirmar_{pid}"), InlineKeyboardButton("❌ Rechazar", callback_data=f"rechazar_{pid}")],
                    [InlineKeyboardButton("⬅️ Volver a la lista", callback_data="admin_pedidos")]
                ]
                await context.bot.send_message(chat_id=user_id, text="👇 ¿Qué deseas hacer?", reply_markup=InlineKeyboardMarkup(botones_accion))
            except Exception as e:
                print(f"Error en ver_pedido: {e}")
                await query.edit_message_text("❌ Error al cargar detalles.")
            finally:
                if 'conn' in locals() and conn:
                    conn.close()
        elif data.startswith("confirmar_"):
            pedido_id = int(data.split("_")[1])
            try:
                conn = conectar_db()
                with conn.cursor() as cur:
                    cur.execute("UPDATE pedidos SET estado = 'confirmado', fecha_confirmacion = CURRENT_TIMESTAMP WHERE id = %s RETURNING usuario_id;", (pedido_id,))
                    resultado = cur.fetchone()
                    conn.commit()
                if resultado:
                    await context.bot.send_message(chat_id=resultado[0], text=f"🎉 ¡Tu pedido #{pedido_id} ha sido confirmado!")
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

# ------------------ Manejador de mensajes de texto ---------------------
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
            if resultado:
                await context.bot.send_message(chat_id=resultado[0], text=f"❌ Tu pedido #{pedido_id} ha sido rechazado.\n*Motivo:* {motivo}")
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
            await update.message.reply_text("❌ Número inválido. Envía solo dígitos.")
            return
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
        # Manejar comprobantes de texto, aunque se esperan imágenes
        await update.message.reply_text("Por favor, envía el comprobante como una imagen, no como texto.")

# ------------------ Manejador de imágenes ---------------------
async def recibir_imagen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa imágenes, las guarda como comprobante y notifica a los admins."""
    user_id = update.effective_user.id
    if context.user_data.get("estado") != "esperando_comprobante":
        return

    file_id = update.message.photo[-1].file_id
    try:
        conn = conectar_db()
        with conn.cursor() as cur:
            # Guardamos el comprobante en la base de datos
            cur.execute("INSERT INTO comprobantes (pedido_id, tipo, contenido) VALUES (%s, %s, %s);", (context.user_data["pedido_id"], "imagen", file_id))
            conn.commit()
        
        # Notificamos al usuario que todo salió bien
        await update.message.reply_text("✅ ¡Imagen recibida! Tu pedido será validado por un administrador a la brevedad.")

        # --- INICIO: Bloque de Notificación a Administradores ---
        try:
            pedido_id = context.user_data["pedido_id"]
            user_nombre = update.effective_user.full_name
            oferta_txt = context.user_data.get("oferta_txt", "Oferta no especificada")

            botones_notificacion = [[
                InlineKeyboardButton("🔍 Ver y Gestionar Pedido Ahora", callback_data=f"ver_pedido_{pedido_id}")
            ]]
            markup = InlineKeyboardMarkup(botones_notificacion)

            mensaje_para_admin = (
                f"🔔 *¡Nueva Solicitud de Recarga Pendiente!* 🔔\n\n"
                f"👤 **De:** {user_nombre}\n"
                f"🎁 **Oferta:** {oferta_txt}"
            )

            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=mensaje_para_admin,
                        parse_mode="Markdown",
                        reply_markup=markup
                    )
                except Exception as e_inner:
                    print(f"Fallo al notificar al admin {admin_id}: {e_inner}")
        except Exception as e:
            print(f"Error crítico al intentar notificar a los admins: {e}")
        # --- FIN: Bloque de Notificación a Administradores ---

    except Exception as e:
        print(f"Error al guardar imagen de comprobante: {e}")
        await update.message.reply_text("❌ Ocurrió un error al guardar tu comprobante. Por favor, contacta a un administrador.")
    finally:
        # Limpiamos los datos del usuario al final de todo el proceso
        context.user_data.clear()
        if 'conn' in locals() and conn: conn.close()

# ------------------ Panel de Administración (/admin) ---------------------
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
    if not es_admin(update.effective_user.id):
        await update.message.reply_text("🚫 Acceso denegado.")
        return
    botones_admin = [[InlineKeyboardButton("📥 Ver Pedidos Pendientes", callback_data="admin_pedidos")]]
    texto = "🔐 Panel de Administración"
    reply_markup = InlineKeyboardMarkup(botones_admin)
    if is_callback:
        await update.callback_query.edit_message_text(text=texto, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text=texto, reply_markup=reply_markup)

# ------------------ Iniciar Bot ---------------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(manejar_callback_unificado))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_mensaje))
    app.add_handler(MessageHandler(filters.PHOTO, recibir_imagen))
    
    print("Bot iniciado...")
    app.run_polling()

if __name__ == "__main__":
    main()