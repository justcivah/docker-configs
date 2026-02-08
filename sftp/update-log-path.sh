#!/bin/bash
# Nome del container (come appare in docker ps, es. "sftp-docker")
CONTAINER_NAME="sftp"
# Dove vuoi il link fisso
LINK_PATH="/var/log/sftp-docker.log"

# Trova il percorso reale del file JSON
REAL_PATH=$(docker inspect --format='{{.LogPath}}' $CONTAINER_NAME)

# Crea o aggiorna il link simbolico
sudo ln -sf "$REAL_PATH" "$LINK_PATH"
