FROM nodered/node-red

# Install InfluxDB nodes for the MQTT → InfluxDB flow
RUN npm install --save node-red-contrib-influxdb

# Stage flow files in /opt/flows (entrypoint copies them to /data volume at runtime)
COPY settings.js /opt/flows/settings.js
COPY flows.json /opt/flows/flows.json
COPY entrypoint.sh /usr/src/node-red/entrypoint.sh

USER root
RUN chmod +x /usr/src/node-red/entrypoint.sh
USER node-red

ENTRYPOINT ["/usr/src/node-red/entrypoint.sh"]
