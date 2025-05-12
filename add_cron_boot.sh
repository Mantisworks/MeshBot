#!/bin/bash

# Percorso assoluto allo script Python
SCRIPT_PATH="/usr/dietpi/MeshBot/main.py"  # Modifica questo percorso se diverso

# Controlla che lo script esista
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "Errore: lo script $SCRIPT_PATH non esiste."
    exit 1
fi

# Aggiunge la riga @reboot al crontab dell'utente root se non già presente
CRON_CMD="@reboot /usr/bin/python3 $SCRIPT_PATH"

# Verifica se è già presente
crontab -l 2>/dev/null | grep -F "$CRON_CMD" > /dev/null
if [ $? -eq 0 ]; then
    echo "La riga crontab è già presente. Nessuna modifica effettuata."
else
    (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
    echo "Riga crontab aggiunta con successo."
fi
