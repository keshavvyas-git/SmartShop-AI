const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { ApiError, getAssistantReply } = require('./src/groq');

const ROOT_DIR = __dirname;
const PUBLIC_DIR = path.join(ROOT_DIR, 'public');
const ENV_FILE = path.join(ROOT_DIR, '.env');
const MAX_BODY_BYTES = 20 * 1024;
const RATE_LIMIT_WINDOW_MS = 10 * 60 * 1000;
const RATE_LIMIT_MAX_REQUESTS = 12;
const requestsByAddress = new Map();

if (fs.existsSync(ENV_FILE) && typeof process.loadEnvFile === 'function') {
  process.loadEnvFile(ENV_FILE);
}

const PORT = Number(process.env.PORT) || 3000;
const MIME_TYPES = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
};

function sendJson(response, statusCode, body, extraHeaders = {}) {
  response.writeHead(statusCode, {
    'Cache-Control': 'no-store',
    'Content-Type': 'application/json; charset=utf-8',
    ...extraHeaders,
  });
  response.end(JSON.stringify(body));
}

function sendError(response, error) {
  const statusCode = error instanceof ApiError ? error.status : 500;
  const message = error instanceof ApiError
    ? error.message
    : 'The server could not complete that request. Please try again.';

  if (!(error instanceof ApiError)) {
    console.error('Request failed:', error.message);
  }

  sendJson(response, statusCode, { error: message });
}

function clientAddress(request) {
  const forwardedFor = request.headers['x-forwarded-for'];
  if (typeof forwardedFor === 'string' && forwardedFor.length > 0) {
    return forwardedFor.split(',')[0].trim();
  }
  return request.socket.remoteAddress || 'unknown';
}

function checkRateLimit(request, response) {
  const now = Date.now();
  const address = clientAddress(request);
  const recentRequests = (requestsByAddress.get(address) || [])
    .filter((timestamp) => now - timestamp < RATE_LIMIT_WINDOW_MS);

  if (recentRequests.length >= RATE_LIMIT_MAX_REQUESTS) {
    const retryAfter = Math.ceil((RATE_LIMIT_WINDOW_MS - (now - recentRequests[0])) / 1000);
    sendJson(response, 429, {
      error: 'Ani has reached the short-term request limit for this connection. Please wait a few minutes and try again.',
    }, { 'Retry-After': String(retryAfter) });
    return false;
  }

  recentRequests.push(now);
  requestsByAddress.set(address, recentRequests);
  return true;
}

function readJsonBody(request) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let totalBytes = 0;
    let tooLarge = false;

    request.on('data', (chunk) => {
      totalBytes += chunk.length;
      if (totalBytes > MAX_BODY_BYTES) {
        tooLarge = true;
        chunks.length = 0;
        return;
      }
      chunks.push(chunk);
    });

    request.on('end', () => {
      if (tooLarge) {
        reject(new ApiError(413, 'That message is too large. Please shorten it and try again.'));
        return;
      }

      try {
        const body = Buffer.concat(chunks).toString('utf8');
        resolve(JSON.parse(body || '{}'));
      } catch {
        reject(new ApiError(400, 'The request body must be valid JSON.'));
      }
    });

    request.on('error', reject);
  });
}

function isSameOrigin(request) {
  const origin = request.headers.origin;
  if (!origin) return true;

  try {
    return new URL(origin).host === request.headers.host;
  } catch {
    return false;
  }
}

function setSecurityHeaders(response) {
  response.setHeader('Content-Security-Policy', [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "connect-src 'self'",
    "img-src 'self' data:",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join('; '));
  response.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
  response.setHeader('X-Content-Type-Options', 'nosniff');
  response.setHeader('X-Frame-Options', 'DENY');

  if (process.env.NODE_ENV === 'production') {
    response.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
  }
}

async function handleChat(request, response) {
  if (!isSameOrigin(request)) {
    sendJson(response, 403, { error: 'This request did not come from SmartShop.' });
    return;
  }

  if (!request.headers['content-type']?.includes('application/json')) {
    sendJson(response, 415, { error: 'Send the chat message as JSON.' });
    return;
  }

  if (!checkRateLimit(request, response)) return;

  try {
    const payload = await readJsonBody(request);
    const result = await getAssistantReply(payload.messages);
    sendJson(response, 200, result);
  } catch (error) {
    sendError(response, error);
  }
}

function staticFilePath(urlPath) {
  let decodedPath;
  try {
    decodedPath = decodeURIComponent(urlPath);
  } catch {
    throw new ApiError(400, 'The requested URL is invalid.');
  }

  const requestedPath = decodedPath === '/' ? '/index.html' : decodedPath;
  const filePath = path.resolve(PUBLIC_DIR, `.${requestedPath}`);
  const relativePath = path.relative(PUBLIC_DIR, filePath);

  if (relativePath.startsWith('..') || path.isAbsolute(relativePath)) {
    throw new ApiError(403, 'That file is not available.');
  }

  return filePath;
}

function serveStaticFile(request, response, urlPath) {
  let filePath;
  try {
    filePath = staticFilePath(urlPath);
  } catch (error) {
    sendError(response, error);
    return;
  }

  fs.stat(filePath, (statError, stats) => {
    if (statError || !stats.isFile()) {
      sendJson(response, 404, { error: 'Page not found.' });
      return;
    }

    response.setHeader('Cache-Control', 'no-cache');
    response.setHeader('Content-Type', MIME_TYPES[path.extname(filePath)] || 'application/octet-stream');

    if (request.method === 'HEAD') {
      response.writeHead(200);
      response.end();
      return;
    }

    const fileStream = fs.createReadStream(filePath);
    fileStream.on('error', () => {
      if (!response.headersSent) sendJson(response, 500, { error: 'The page could not be loaded.' });
      else response.destroy();
    });
    fileStream.pipe(response);
  });
}

async function handleRequest(request, response) {
  setSecurityHeaders(response);

  let url;
  try {
    url = new URL(request.url, `http://${request.headers.host || 'localhost'}`);
  } catch {
    sendJson(response, 400, { error: 'The request URL is invalid.' });
    return;
  }

  if (url.pathname === '/health' && request.method === 'GET') {
    const configured = Boolean(process.env.GROQ_API_KEY);
    sendJson(response, configured ? 200 : 503, {
      status: configured ? 'ok' : 'missing-configuration',
    });
    return;
  }

  if (url.pathname === '/api/chat' && request.method === 'POST') {
    await handleChat(request, response);
    return;
  }

  if (!['GET', 'HEAD'].includes(request.method)) {
    sendJson(response, 405, { error: 'Method not allowed.' }, { Allow: 'GET, HEAD, POST' });
    return;
  }

  serveStaticFile(request, response, url.pathname);
}

const server = http.createServer((request, response) => {
  handleRequest(request, response).catch((error) => sendError(response, error));
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`SmartShop AI is listening on port ${PORT}.`);
  if (!process.env.GROQ_API_KEY) {
    console.warn('GROQ_API_KEY is not configured. Set it in .env for local work or in your host’s environment settings.');
  }
});

function shutDown() {
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(1), 10_000).unref();
}

process.on('SIGTERM', shutDown);
process.on('SIGINT', shutDown);
