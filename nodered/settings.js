/**
 * Node-RED Settings — Industrial IoT Pipeline
 * Configured for containerized deployment with auto-installed nodes.
 */
module.exports = {
  flowFile: "flows.json",
  flowFilePretty: true,
  credentialSecret: false,

  uiPort: process.env.PORT || 1880,
  uiHost: "0.0.0.0",

  diagnostics: {
    enabled: true,
    ui: true,
  },

  logging: {
    console: {
      level: "info",
      metrics: false,
      audit: false,
    },
  },

  functionExternalModules: false,
  functionTimeout: 0,

  debugMaxLength: 1000,

  mqttReconnectTime: 15000,

  editorTheme: {
    projects: {
      enabled: false,
    },
  },
};
