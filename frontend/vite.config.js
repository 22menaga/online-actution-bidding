import { readFileSync } from 'node:fs';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Which port is the Django backend on? BACKEND_PORT wins; otherwise `manage.py start_local` writes backend/.port
// (it moves off 8000 when another program is using it); otherwise 8000.
// Read on every request, so it does not matter whether the frontend or the backend was started first.
function backendPort() {
  if (process.env.BACKEND_PORT) return process.env.BACKEND_PORT;
  try { return readFileSync(new URL('../backend/.port', import.meta.url), 'utf8').trim() || '8000'; } catch { return '8000'; }
}

// Vite's default when the backend is down is a bare HTTP 500 that the app can only show as "Request failed (500)".
// Answer with a clear JSON 503 instead, and always forward to the *current* backend port.
const dynamicProxy = (scheme) => ({
  target: `${scheme}://127.0.0.1:8000`, // placeholder, replaced per request below
  ws: scheme === 'ws',
  configure: (proxy) => {
    const web = proxy.web.bind(proxy);
    const ws = proxy.ws.bind(proxy);
    proxy.web = (req, res, opts, cb) => web(req, res, { ...opts, target: `http://127.0.0.1:${backendPort()}` }, cb);
    proxy.ws = (req, socket, head, opts, cb) => ws(req, socket, head, { ...opts, target: `ws://127.0.0.1:${backendPort()}` }, cb);
    proxy.on('error', (_err, _req, res) => {
      if (!res || res.headersSent || typeof res.writeHead !== 'function') { try { res?.destroy?.(); } catch { /* socket */ } return; }
      res.writeHead(503, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ detail: 'The auction server is not running. In another terminal run:  cd backend ; .\\.venv\\Scripts\\python.exe manage.py start_local   then refresh this page.' }));
    });
  },
});

export default defineConfig({
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 900,
    rollupOptions: { output: { manualChunks: { three: ['three'] } } },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': dynamicProxy('http'),
      '/health': dynamicProxy('http'),
      '/media': dynamicProxy('http'),
      '/ws': dynamicProxy('ws'),
    },
  },
});
