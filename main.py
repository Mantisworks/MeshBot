#!/usr/bin/env python3

import logging
import subprocess
import re
import os
import threading
import time

from telegram import Update, ChatAction
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from functools import wraps

import meshtastic
import meshtastic.serial_interface
from pubsub import pub

# CONFIG
GROUP_CHAT_ID = "" # Inserisci l'ID della chat dove inoltrare i messaggi ricevuti dal nodo
BOT_TOKEN = "" # Inserisci il Token del tuo bot
ADMINS = []  # Sostituisci con il tuo Telegram user ID

# SERIALIZZAZIONE
serial_lock = threading.Lock()
SERIAL_TIMEOUT = 5  # secondi

# LOGGING
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Global
lora_interface = None
updater = None  # Servirà per inviare i messaggi al bot da altri thread

# Restrict access to admins
def restricted(func):
    @wraps(func)
    def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ADMINS:
            logger.warning("Utente NON autorizzato: %d", user_id)
            #update.message.reply_text("Non sei autorizzato.")
            return
        return func(update, context, *args, **kwargs)
    return wrapper

# Invia messaggio su canale specifico
def send_message_lora(message: str, channel_index: int = 0):
    global lora_interface
    try:
        if lora_interface is None:
            logger.error("Interfaccia LoRa non inizializzata.")
            return False
        if serial_lock.acquire(timeout=SERIAL_TIMEOUT):
            try:
                # invio messaggio
                logger.info(f"Invio su canale {channel_index}: {message}")
                lora_interface.sendText(message, wantAck=False, channelIndex=channel_index)
            finally:
                serial_lock.release()
        return True
    except Exception as e:
        logger.error(f"Errore nell'invio del messaggio LoRa: {e}")
        return False

# /start
@restricted
def start(update: Update, context: CallbackContext):
    update.message.reply_text("Bot Meshtastic pronto. Usa /lora o /canale <n> per inviare messaggi.")

@restricted
def lora(update: Update, context: CallbackContext):
    user_name = update.effective_user.first_name or "Anonimo"
    text = update.message.text.replace("/lora", "").strip()
    if not text:
        update.message.reply_text("Scrivi qualcosa dopo /lora. Es: /lora <messaggio>, il testo verra' inviato via protocollo LoRa dal nodo.")
        return
    update.message.chat.send_action(ChatAction.TYPING)
    full_msg = f"{user_name}: {text}"
    success = send_message_lora(full_msg, channel_index=3)  # <-- CANALE 3 DI DEFAULT
    update.message.reply_text("✅ Inviato via etere." if success else "❌ Errore durante l'invio.")


# /canale n messaggio
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

# Catch-all per messaggi diretti
@restricted
def handle_text(update: Update, context: CallbackContext):
    update.message.reply_text("Usa /lora per inviare o /canale <n> per scegliere un canale.")

# Funzione per inoltrare messaggi dal canale 3 al bot Telegram
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

# Thread per la connessione a Meshtastic
def start_lora_listener():
    global lora_interface
    try:
        lora_interface = meshtastic.serial_interface.SerialInterface()
        pub.subscribe(on_receive, "meshtastic.receive")
        logger.info("Interfaccia LoRa inizializzata e in ascolto...")
    except Exception as e:
        logger.error(f"Errore nella connessione Meshtastic: {e}")

# MAIN
def main():
    global updater
    updater = Updater(BOT_TOKEN)
    dp = updater.dispatcher

    # Comandi
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("lora", lora))
    dp.add_handler(CommandHandler("canale", canale))

    # Messaggi generici
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))

    # Avvia listener Meshtastic in thread separato
    threading.Thread(target=start_lora_listener, daemon=True).start()

    # Avvio bot Telegram
    updater.start_polling()
    logger.info("Bot avviato.")
    updater.idle()

if __name__ == '__main__':
    main()
