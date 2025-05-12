# MeshBot
Script Python che legge il traffico dalla USB (/dev/ttyUSB0) e li reindirizza in un gruppo Telegram indicato. Lo script deve necessariamente girare sulla stessa piattaforma dove il Nodo LoRa e' collegato.
Nel mio caso ho utilizzato un Raspberry Pi 3B+ alimentato con un hat PoE sul quale vi e' collegato un TTGO T-Beam via USB. Il Raspberry e' dotato di un hot-spot WiFi per permettere la comunicazione tra nodo e MQTT.


## Comandi principali del Bot Telegran
> **/lora <messaggio>** _Invia il messaggio sul canale di default (3 secondario)_

> **/canale <n_canale> <messaggio>** _Invia il messaggio sul canale specificato Es: /canale 0 Ciao_

> **/info** _Restuisce le informazioni del nodo locale_
![alt text](https://github.com/Mantisworks/MeshBot/blob/main/img/info.PNG)

> **/ultimi** _Restituisce l'elenco degli ultimi nodi ascoltati di recente_
![alt text](https://github.com/Mantisworks/MeshBot/blob/main/img/ultimi.PNG)

> **/posizione** _Restituisce la posizione GPS e altitudine del nodo locale_
![alt text](https://github.com/Mantisworks/MeshBot/blob/main/img/posizione.PNG)

> **/invia_a <id_nodo> <messaggio>** _Invia il messaggio al nodo specificato NB: l'ID nodo NON deve contenere il punto esclamativo "!"_
![alt text](https://github.com/Mantisworks/MeshBot/blob/main/img/invia_a.PNG)


## Aggiunta dello script al Crontab
Assicurati di modificare lo script add_cron_boot.sh, aggiungendo il path dello script .py
1. Rendi eseguibile lo script:
> chmod +x add_cron_boot.sh
2. Eseguilo come root:
> sudo ./add_cron_boot.sh
