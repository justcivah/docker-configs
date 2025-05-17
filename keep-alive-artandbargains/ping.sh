#!/bin/sh

# Default to the provided Render.com endpoint, but allow override
SERVER_URL="${SERVER_URL:-https://backend-a2jy.onrender.com/api/keep/alive}"

# Log file to track ping history
LOG_FILE="/app/ping_log.txt"

echo "Starting ping service for $SERVER_URL"
echo "Logs will be saved to $LOG_FILE"

# Infinite loop to keep pinging
while true; do
    # Get current timestamp
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    
    echo "[$TIMESTAMP] Pinging $SERVER_URL..."
    
    # Make the request and capture the response status
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$SERVER_URL")
    
    # Log the result
    echo "[$TIMESTAMP] Ping result: $RESPONSE" | tee -a "$LOG_FILE"
    
    # Sleep for 5 minutes (300 seconds)
    echo "Sleeping for 5 minutes..."
    sleep 300
done
