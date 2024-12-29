#!/bin/bash
set -e

# Ensure the SFTP group exists
groupadd -f sftpusers

# Read the .env file line by line, preserving quotes
while IFS='=' read -r key value; do
    # Skip empty lines and comments
    if [[ -z "$key" || "$key" == \#* ]]; then
        continue
    fi
    
    username="${key//\"/}"
    password="${value//\"/}"
    password="${password%$'\r'}"
    
    # Directories paths
    user_home="/sftp/$username"
    uploads_dir="/sftp/$username/uploads"
    
    # Create the user with no shell access and add to sftpusers group
    if id "$username" &>/dev/null; then
        # If user exists, just update password
        echo "$username:$password" | chpasswd
    else
        useradd -m -d "$user_home" -s /sbin/nologin -g sftpusers "$username"
        echo "$username:$password" | chpasswd
    fi
    
    # Create uploads directory if it doesn't exist
    mkdir -p "$uploads_dir"
    
    # Set correct permissions and ownership
    chown root:root "$user_home"
    chmod 755 "$user_home"
    chown "$username:sftpusers" "$uploads_dir"
    chmod 700 "$uploads_dir"
    
done < /app/.env

# Remove the .env file securely
shred -u /app/.env
