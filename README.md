# MeshBot
Script Python che legge il traffico dalla USB (/dev/ttyUSB0) e li reindirizza in un gruppo Telegram indicato. Lo script deve necessariamente girare sulla stessa piattaforma dove il Nodo LoRa e' collegato.
Nel mio caso ho utilizzato un Raspberry Pi 3B+ alimentato con un hat PoE sul quale vi e' collegato un TTGO T-Beam via USB.

## Comandi principali del Bot Telegran
> **/lora <messaggio>** _Invia il messaggio sul canale di default (3 secondario)_

> **/canale <n_canale> <messaggio>** _Invia il messaggio sul canale specificato Es: /canale 0 Ciao_

> **/info** _Restuisce le informazioni del nodo locale_

> **/ultimi** _Restituisce l'elenco degli ultimi nodi ascoltati di recente_

> **/posizione** _Restituisce la posizione GPS e altitudine del nodo locale_

> **/invia_a <id_nodo> <messaggio>** _Invia il messaggio al nodo specificato NB: l'ID nodo NON deve contenere il punto esclamativo "!"_

