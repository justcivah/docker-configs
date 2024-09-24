#!/bin/bash

ZONE_ID=$1
DNS_RECORD_ID=$2
CLOUDFLARE_API_KEY=$3

# Get your current public IP address
PUBLIC_IP=$(curl -s ifconfig.me)

# Update the DNS record with the new IP address, and capture the response
API_URL="https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$DNS_RECORD_ID"
PAYLOAD="{\"type\":\"A\",\"name\":\"@\",\"content\":\"$PUBLIC_IP\",\"proxied\":false,\"ttl\":3600}"

RESPONSE=$(curl \
  --request PATCH \
  --url "$API_URL" \
  --header 'Content-Type: application/json' \
  --header "Authorization: Bearer $CLOUDFLARE_API_KEY" \
  --data "$PAYLOAD" -s)

# Check for successful update based on the response
if [[ "$RESPONSE" =~ '"success":true' ]]; then
  # Successful update
  echo "$(basename $0): Successfully updated DNS record with IP: $PUBLIC_IP"
else
  # Failed update
  echo "$(basename $0): Failed to update DNS record. Response: $RESPONSE"
fi
