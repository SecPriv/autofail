import path from 'node:path';

export function normalizeUrl(raw) {
  const trimmed = raw.trim();
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  return `https://${trimmed}`;
}

export function slugify(url) {
  let raw;
  try {
    const u = new URL(normalizeUrl(url));
    const pathPart = u.pathname === '/' ? '' : u.pathname;
    raw = `${u.hostname}${pathPart}`;
  } catch {
    raw = url;
  }
  return raw.toLowerCase().replace(/[^a-z0-9._-]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '').slice(0, 80);
}

export function outDirFor(baseDir, rank, url) {
  return path.join(baseDir, `${rank}_${slugify(url)}`);
}
