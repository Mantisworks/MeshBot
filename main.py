#!/usr/bin/env python3

import logging
import subprocess
import re
import os
import threading
import time
import io
import contextlib

from telegram import Update, ChatAction
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from functools import wraps

import meshtastic
import meshtastic.serial_interface
from pubsub import pub

# CONFIG
GROUP_CHAT_ID = "" # Inserisci l'ID del gruppo Telegram 
BOT_TOKEN = "" # Inserisci la key del BOT
ADMINS = [] # Inserisci gli ID degli amministrator

# SERIALIZZAZIONE
serial_lock = threading.Lock()
SERIAL_TIMEOUT = 5

# LOGGING
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Global
lora_interface = None
updater = None
stop_event = threading.Event()

def restricted(func):
    @wraps(func)
    def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        user_id = update.effective_user.id
        ######################################################################################
        # ATTENZIONE! Decommenta se vuoi restringere le funzionalita' ai soli Amministratori #
        ######################################################################################
        
        #if user_id not in ADMINS: 
        #    logger.warning("Utente NON autorizzato: %d", user_id)
        #    return
        return func(update, context, *args, **kwargs)
    return wrapper

def send_message_lora(message: str, channel_index: int = 0):
    global lora_interface
    try:
        if lora_interface is None:
            logger.error("Interfaccia LoRa non inizializzata.")
            return False
        if serial_lock.acquire(timeout=SERIAL_TIMEOUT):
            try:
                logger.info(f"Invio su canale {channel_index}: {message}")
                lora_interface.sendText(message, wantAck=False, channelIndex=channel_index)
            finally:
                serial_lock.release()
        return True
    except Exception as e:
        logger.error(f"Errore nell'invio del messaggio LoRa: {e}")
        return False

#
# Invia messaggio via nodo locale (canale di default 3 secondario )
#
@restricted
def lora(update: Update, context: CallbackContext):
    user_name = update.effective_user.first_name or "Anonimo"
    text = update.message.text.replace("/lora", "").strip()
    if not text:
        update.message.reply_text("Scrivi qualcosa dopo /lora. Es: /lora <messaggio>")
        return
    update.message.chat.send_action(ChatAction.TYPING)
    full_msg = f"{user_name}: {text}"
    success = send_message_lora(full_msg, channel_index=3) # ATTENZIONE: Modifica qui il tuo canale di default
    update.message.reply_text("✅ Inviato via etere." if success else "❌ Errore durante l'invio.")

#
# Informazioni del nodo locale
#
def info(update: Update, context: CallbackContext):
    try:
        local_node = find_local_node(lora_interface)
        if not local_node:
            update.message.reply_text("❌ Nodo locale non trovato nella lista.")
            return

        # Log per verificare la struttura completa del nodo
        logger.info(f"🔍 Nodo locale trovato: {local_node}")

        user = local_node.get("user", {})
        node_id = user.get("id", "N/D")  # ID nodo
        long_name = user.get("longName", "N/D")  # Nome lungo
        short_name = user.get("shortName", "N/D")  # Nome breve
        battery = local_node.get("deviceMetrics", {}).get("batteryLevel", "N/D")  # Batteria

        # La temperatura sembra non essere presente, quindi la mettiamo come "N/D"
        temp = "N/D"

        response = f"""📡 *Info Nodo LoRa*
🆔 *ID Nodo:* `{node_id}`
👤 *Nome:* {long_name} ({short_name})
🌡 *Temp:* {temp}
🔋 *Batteria:* {battery}"""

        update.message.reply_text(response, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Errore in /info: {e}")
        update.message.reply_text("❌ Errore durante il comando /info.")

#
#  Ultimi nodi ascoltati (LoRa  MQTT)
#
@restricted
def ultimi(update: Update, context: CallbackContext):
    try:
        if not lora_interface:
            update.message.reply_text("❌ Interfaccia LoRa non inizializzata.")
            return

        with io.StringIO() as buf, contextlib.redirect_stdout(buf):
            lora_interface.showNodes()
            output = buf.getvalue()

        if not output.strip():
            update.message.reply_text("Nessun nodo trovato.")
            return

        lines = [line for line in output.splitlines() if line.strip().startswith("│") and "│" in line]
        if len(lines) < 2:
            update.message.reply_text("Nessun nodo trovato.")
            return

        message = "*🌐 Ultimi Nodi Ricevuti*\n"
        for line in lines[2:7]:
            parts = [p.strip() for p in line.strip("│").split("│")]
            if len(parts) >= 3:
                name = parts[1]
                node_id = parts[2]
                aka = parts[3]
                battery = parts[10]
                last_seen = parts[-1]
                message += f"🔹 *{name}* (`{node_id}`)\n"
                message += f"    Alias: `{aka}`\n"
                message += f"    🔋 Batteria: {battery} | 🕒 Ultimo: {last_seen}\n\n"

        update.message.reply_text(message, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Errore in /ultimi: {e}")
        update.message.reply_text("❌ Errore nel recupero nodi.")

#
# Invio messaggio a canale specifico
#
@restricted
def canale(update: Update, context: CallbackContext):
    match = re.match(r"/canale\s+(\d+)\s+(.+)", update.message.text)
    if not match:
        update.message.reply_text("Uso corretto: /canale <numero> <messaggio>")
        return
    channel_index = int(match.group(1))
    text = match.group(2).strip()
    user_name = update.effective_user.first_name or "Anonimo"
    full_msg = f"{user_name}: {text}"
    update.message.chat.send_action(ChatAction.TYPING)
    success = send_message_lora(full_msg, channel_index=channel_index)
    update.message.reply_text(f"✅ Inviato sul canale {channel_index}." if success else "❌ Errore durante l'invio.")

@restricted
def handle_text(update: Update, context: CallbackContext):
    update.message.reply_text("Usa /lora per inviare o /canale <n> per scegliere un canale.")

def on_receive(packet, interface):
    try:
        rx_channel = packet.get("channel", 0)
        decoded = packet.get("decoded", {})
        payload = decoded.get("text", "")

        if rx_channel == 3 and payload:
            logger.info(f"Messaggio ricevuto su canale 3: {payload}")
            updater.bot.send_message(chat_id=GROUP_CHAT_ID, text=f"[LoRa] {payload}")
    except Exception as e:
        logger.error(f"Errore nel parsing del pacchetto: {e}")

def start_lora_listener():
    global lora_interface
    try:
        lora_interface = meshtastic.serial_interface.SerialInterface()
        pub.subscribe(on_receive, "meshtastic.receive")
        logger.info("Interfaccia LoRa inizializzata e in ascolto...")
    except Exception as e:
        logger.error(f"Errore nella connessione Meshtastic: {e}")

def lora_watchdog():
    global lora_interface
    while not stop_event.is_set():
        time.sleep(60)
        try:
            if lora_interface and not lora_interface.isConnected:
                logger.warning("Watchdog: disconnessione rilevata. Riconnessione...")
                pub.unsubscribe(on_receive, "meshtastic.receive")
                lora_interface.close()
                time.sleep(5)
                start_lora_listener()
        except Exception as e:
            logger.error(f"Errore nel watchdog: {e}")

def get_local_node_id(interface):
    try:
        my_id = interface.myInfo.my_node_num
        my_id_hex = f"!{my_id:08x}"
        logger.info(f"ID nodo locale: {my_id_hex}")
        return my_id_hex
    except Exception as e:
        logger.error(f"Errore ottenendo ID nodo locale: {e}")
        return None

def find_local_node(interface):
    local_id = get_local_node_id(interface)
    if not local_id:
        logger.warning("❌ ID nodo locale non disponibile.")
        return None

    logger.info(f"Cercando nodo con ID: {local_id}")

    try:
        # Cerchiamo il nodo locale nella lista dei nodi noti
        for node_id, node in interface.nodes.items():
            logger.info(f"Nodo trovato: {node.get('user', {}).get('longName', 'N/D')} | ID: {node_id} | Ruolo: {node.get('role', 'N/A')}")
            if node_id == local_id:
                logger.info(f"🔍 Nodo locale trovato: {node}")
                return node
        logger.warning("❌ Nodo locale non trovato nella lista.")
        return None
    except Exception as e:
        logger.error(f"Errore cercando il nodo locale nella lista: {e}")
        return None

#
# Invia messaggio a nodo specifico
#
@restricted
def invia_a(update: Update, context: CallbackContext):
    try:
        args = context.args
        if len(args) < 2:
            update.message.reply_text("Uso: /invia_a <node_id> <messaggio>")
            return

        node_id = args[0]
        if not node_id.startswith("!"):
            node_id = f"!{node_id}"  # 👈 Aggiunge ! se manca

        message = " ".join(args[1:])
        target_node = next((node for node in lora_interface.nodes.values()
                            if node.get('user', {}).get('id') == node_id), None)

        if not target_node:
            update.message.reply_text(f"❌ Nodo {node_id} non trovato.")
            return

        logger.info(f"Inviando a {node_id}: {message}")
        lora_interface.sendText(message, destinationId=node_id, wantAck=True)
        update.message.reply_text(f"✅ Messaggio inviato a {node_id}.")

    except Exception as e:
        logger.error(f"Errore in /invia_a: {e}")
        update.message.reply_text("❌ Errore durante l'invio.")

#
# Posizione nodo locale
#
def posizione(update: Update, context: CallbackContext):
    try:
        local_node = find_local_node(lora_interface)
        if not local_node:
            update.message.reply_text("❌ Nodo locale non trovato.")
            return

        position = local_node.get("position", {})
        latitude = position.get("latitude", "N/D")
        longitude = position.get("longitude", "N/D")
        altitude = position.get("altitude", "N/D")

        response = f"""📡 *Posizione Nodo LoRa*
🌍 *Latitudine:* {latitude}
🌍 *Longitudine:* {longitude}
⛰ *Altitudine:* {altitude} m"""

        update.message.reply_text(response, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Errore in /posizione: {e}")
        update.message.reply_text("❌ Errore durante il comando /posizione.")


def main():
    global updater
    updater = Updater(BOT_TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("lora", lora)) # Invia messaggio al canale 3 LoRa (default)
    dp.add_handler(CommandHandler("canale", canale)) # Invia in messaggio al canale specificato es: /canale 0 <messaggio> (canale 0 = MediumFast primario)
    dp.add_handler(CommandHandler("info", info)) # Restituisce le informazioni del nodo locale
    dp.add_handler(CommandHandler("ultimi", ultimi)) # Restituisce gli ultimi nodi ascoltati dal nodo via LoRa e MQTT
    dp.add_handler(CommandHandler("invia_a", invia_a)) # Invia un messaggio al nodo specificato es: /invia_a <id_nodo> <messaggio> (id_nodo non deve contenere il "!")
    dp.add_handler(CommandHandler("posizione", posizione)) # Restituisce la posizione GPS e altitudine del nodo locale)
    
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))

    threading.Thread(target=start_lora_listener, daemon=True).start()
    threading.Thread(target=lora_watchdog, daemon=True).start()

    logger.info("Bot avviato.")
    updater.start_polling()
    updater.idle()
    stop_event.set()

if __name__ == '__main__':
    main()
