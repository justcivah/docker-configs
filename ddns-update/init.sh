#!/bin/bash

# Write out the cron job with environment variables available at runtime
echo "*/10 * * * * /app/ddns.sh $ZONE_ID $DNS_RECORD_ID $CLOUDFLARE_API_KEY >> /var/log/cron.log" > /etc/cron.d/ddns

# Apply cron job permissions
chmod 0644 /etc/cron.d/ddns

# Apply the cron job
crontab /etc/cron.d/ddns

# Start cron service in the foreground
cron -f
