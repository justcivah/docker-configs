# Base image
FROM debian:latest

# Install necessary packages
RUN apt-get update && \
    apt-get install -y cron curl && \
    apt-get clean

# Create the script directory
WORKDIR /app

# Copy the scripts into the container
COPY ddns.sh /app/ddns.sh
COPY init.sh /app/init.sh

# Make the scripts executable
RUN chmod +x /app/ddns.sh
RUN chmod +x /app/init.sh

# Checks whether the cron daemon process is still running
HEALTHCHECK CMD ps aux | grep -v grep | grep -q cron || echo 1
