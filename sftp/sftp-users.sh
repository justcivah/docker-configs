#!/bin/bash

set -e

# Ensure the SFTP group exists
groupadd -f sftpusers

# Read the .env file line by line
while IFS='=' read -r key value; do
    # Skip empty lines and comments
    if [[ -z "$key" || "$key" == \#* ]]; then
        continue
    fi

    # Extract the username and password
    username="$key"
    password="$value"

    # Create the user with no shell access and add to sftpusers group
    useradd -m -d /sftp/"$username" -s /sbin/nologin -g sftpusers "$username"
    echo "$username:$password" | chpasswd

    # Create user directory
    mkdir -p /sftp/"$username"/uploads

    # Set permissions for the user's directory
    chown root:root /sftp/"$username"
    chmod 755 /sftp/"$username"

    # Set ownership and permissions for the upload directory
    chown "$username":"sftpusers" /sftp/"$username"/uploads
    chmod 700 /sftp/"$username"/uploads

done < /app/.env

# Remove the .env file securely
shred -u /app/.env
