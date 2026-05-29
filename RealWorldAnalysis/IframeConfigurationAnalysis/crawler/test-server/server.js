import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const SITES = [
  { port: 3000, root: path.join(__dirname, 'sites/primary'), label: 'primary' },
  { port: 3001, root: path.join(__dirname, 'sites/third-party'), label: 'third-party' },
];

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
};

function resolveFile(root, urlPath) {
  const cleanPath = urlPath.split('?')[0].split('#')[0];
  const requested = cleanPath === '/' ? '/index.html' : cleanPath;
  const resolved = path.resolve(root, '.' + requested);
  if (!resolved.startsWith(root)) return null;
  return resolved;
}

for (const { port, root, label } of SITES) {
  http.createServer(async (req, res) => {
    const file = resolveFile(root, req.url);
    if (!file) {
      res.statusCode = 400;
      return res.end('bad path');
    }
    try {
      const data = await fs.readFile(file);
      res.setHeader('content-type', MIME[path.extname(file)] || 'application/octet-stream');
      res.end(data);
    } catch {
      res.statusCode = 404;
      res.end('not found');
    }
  }).listen(port, () => {
    console.log(`[${label}] http://localhost:${port}  (root: ${root})`);
  });
}
