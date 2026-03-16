#!/bin/bash
source /root/.openclaw/workspace/.env

TIMESTAMP=$(date +%s000)
QUERY="timestamp=$TIMESTAMP"
SIGNATURE=$(echo -n "$QUERY" | openssl dgst -sha256 -hmac "$BINANCE_API_SECRET" | awk '{print $2}')

curl -4 -s -H "X-MBX-APIKEY: $BINANCE_API_KEY" "https://api.binance.com/api/v3/account?$QUERY&signature=$SIGNATURE"
