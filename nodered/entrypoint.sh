#!/bin/sh
# Copy flow files into the data volume only if they don't exist (preserves UI edits)
[ -f /data/flows.json ] || cp /opt/flows/flows.json /data/flows.json
[ -f /data/settings.js ] || cp /opt/flows/settings.js /data/settings.js

# Create credentials file with the InfluxDB token from environment
cat > /data/flows_cred.json <<EOF
{
  "influxdb-config": {
    "token": "${INFLUXDB_TOKEN}"
  }
}
EOF

# Start Node-RED
exec npm start -- --userDir /data
