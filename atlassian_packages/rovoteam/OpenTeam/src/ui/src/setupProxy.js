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
};
