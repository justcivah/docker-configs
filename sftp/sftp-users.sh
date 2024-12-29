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

    # Extract the username and password
    username="${key//\"/}"  # Remove any quotes from username
    # Remove surrounding quotes and preserve spaces in password
    password="${value//\"/}"  # Remove quotes
    password="${password%$'\r'}"  # Remove potential carriage return

    # Directories paths
    user_home="/sftp/$username"
    uploads_dir="/sftp/$username/uploads"
    temp_dir="/tmp/sftp_backup_$username"

    # Move existing uploads (if they exist) to a temporary location
    if [[ -d "$uploads_dir" ]]; then
        mkdir -p "$temp_dir"
        mv "$uploads_dir"/* "$temp_dir"/ 2>/dev/null || true
    fi

    # Delete old user and home directory
    rm -rf "$user_home"

    # Create the user with no shell access and add to sftpusers group
    useradd -m -d "$user_home" -s /sbin/nologin -g sftpusers "$username"
    
    # Set password without using printf %q
    echo "$username:$password" | chpasswd

    # Create user directory and ensure correct permissions
    mkdir -p "$uploads_dir"
    chown root:root "$user_home"
    chmod 755 "$user_home"

    # Set ownership and permissions for the uploads directory
    chown "$username:sftpusers" "$uploads_dir"
    chmod 700 "$uploads_dir"

    # Restore preserved uploads back into the directory
    if [[ -d "$temp_dir" ]]; then
        mv "$temp_dir"/* "$uploads_dir"/ 2>/dev/null || true
        rm -rf "$temp_dir"
    fi
done < /app/.env

# Remove the .env file securely
shred -u /app/.env
