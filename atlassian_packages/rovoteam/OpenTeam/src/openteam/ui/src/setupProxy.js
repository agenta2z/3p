/**
 * Development proxy — routes /api requests to the FastAPI backend.
 */

const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  const backendPort = process.env.REACT_APP_BACKEND_PORT || '8000';
  const backendTarget = `http://localhost:${backendPort}`;

  app.use(
    '/api',
    createProxyMiddleware({
      target: backendTarget,
      changeOrigin: true,
      onError: (err) => console.error(`[Proxy] Error: ${err.message}`),
    })
  );

  // WebSocket proxy for streaming chat
  // Note: CRA dev server needs the WS proxy registered on the server instance,
  // not just as express middleware. We use onAfterSetupMiddleware-style approach
  // by creating the proxy and explicitly upgrading.
  // CRITICAL: Proxy ONLY /ws/manager (the app's WebSocket), NOT /ws (catch-all).
  // webpack-dev-server uses ws://localhost:3000/ws for its HMR (hot module
  // reload) protocol. If we proxy /ws (which would catch /ws/...) the HMR
  // upgrade requests get forwarded to our backend's /ws (which doesn't exist —
  // backend only serves /ws/manager). The backend responds with HTTP, the
  // browser sees garbage instead of a valid WS frame → "Invalid frame header"
  // → infinite reconnect loop spamming the console with thousands of errors.
  // Scoping the proxy path to /ws/manager leaves HMR alone.
  const wsProxy = createProxyMiddleware('/ws/manager', {
    target: backendTarget,
    changeOrigin: true,
    ws: true,
    logLevel: 'warn',
    onError: (err) => console.error(`[WS Proxy] Error: ${err.message}`),
  });
  app.use(wsProxy);

  // Attach WebSocket upgrade handler to the underlying HTTP server
  // CRA's dev server exposes this after setup
  if (app.server) {
    app.server.on('upgrade', wsProxy.upgrade);
  } else {
    // Fallback: hook into the 'listening' event
    const origListen = app.listen;
    if (origListen) {
      app.listen = function(...args) {
        const server = origListen.apply(this, args);
        if (server && server.on) {
          server.on('upgrade', wsProxy.upgrade);
        }
        return server;
      };
    }
  }
};
