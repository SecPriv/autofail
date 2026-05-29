import { parseArgs } from 'node:util';
import puppeteer from 'puppeteer';
import pLimit from 'p-limit';
import { readUrls } from './csv.js';
import { crawlOne } from './crawl.js';
import { outDirFor } from './fs-utils.js';

const { values } = parseArgs({
  options: {
    input: { type: 'string', short: 'i' },
    out: { type: 'string', short: 'o', default: 'data/out' },
    concurrency: { type: 'string', short: 'c', default: '5' },
    timeout: { type: 'string', short: 't', default: '30000' },
    delay: { type: 'string', short: 'd', default: '0' },
    'start-from': { type: 'string', short: 's' },
    'max-urls': { type: 'string', short: 'm' },
    'user-data-dir': { type: 'string' },
    'profile-directory': { type: 'string' },
    'executable-path': { type: 'string' },
    help: { type: 'boolean', short: 'h' },
  },
});

if (values.help || !values.input) {
  console.log(`Usage: node src/index.js --input <csv> [--out <dir>] [--concurrency N] [--timeout ms]
                       [--delay ms] [--scroll] [--start-from N] [--max-urls N]
                       [--user-data-dir <path>] [--profile-directory <name>]
                       [--executable-path <path>]

Reads a Tranco-style CSV (rank,url) and crawls each URL with a Pixel 5
Puppeteer session. Writes headers.json + frames/ + iframes.json per URL
into <out>/<rank>_<slug>/.

  --delay ms           extra wait after networkidle2 before capturing DOM (for lazy ads)
  --scroll             scroll page to bottom and back before capturing (triggers lazy-load)
  --start-from N       start from line N (1-indexed), skips all earlier lines
  --max-urls N         stop after processing N URLs
  --user-data-dir      Chromium user-data root; required for Page.AdFrameStatus
                       to actually fire (the binary Subresource Filter ruleset
                       lives at <root>/Subresource Filter/)
  --profile-directory  profile folder name inside --user-data-dir (e.g. "Default",
                       "Profile 5"); selects which profile to use
  --executable-path    path to a Chromium/Chrome binary; required when the
                       --user-data-dir was produced by a different build than
                       Puppeteer's bundled Chromium`);
  process.exit(values.input ? 0 : 1);
}

const concurrency = Number.parseInt(values.concurrency, 10);
const timeoutMs = Number.parseInt(values.timeout, 10);
const delayMs = Number.parseInt(values.delay, 10);
const doScroll = values.scroll;
const startFrom = values['start-from'] ? Number.parseInt(values['start-from'], 10) : null;
const maxUrls = values['max-urls'] ? Number.parseInt(values['max-urls'], 10) : null;

let urls = await readUrls(values.input);
console.log(`Loaded ${urls.length} URLs from ${values.input}`);

if (startFrom != null && startFrom > 1) {
  console.log(`Skipping first ${startFrom - 1} lines, starting from line ${startFrom}`);
  urls = urls.slice(startFrom - 1);
}

if (maxUrls != null) {
  console.log(`Limiting to ${maxUrls} URLs`);
  urls = urls.slice(0, maxUrls);
}

const launchArgs = [
  '--no-sandbox',
  '--disable-setuid-sandbox',
];
if (values['profile-directory']) {
  launchArgs.push(`--profile-directory=${values['profile-directory']}`);
}

const browser = await puppeteer.launch({
  headless: true,
  userDataDir: values['user-data-dir'],
  executablePath: values['executable-path'],
  args: launchArgs,
});

const limit = pLimit(concurrency);
let done = 0;
const counts = { ok: 0, error: 0, skipped: 0 };

const tasks = urls.map(({ rank, url }) =>
  limit(async () => {
    const outDir = outDirFor(values.out, rank, url);
    const result = await crawlOne({ browser, rank, url, outDir, timeoutMs, delayMs, });
    done += 1;
    if (result.skipped) {
      counts.skipped += 1;
      console.log(`[${done}/${urls.length}] ${rank} ${url} -> skipped`);
    } else if (result.error) {
      counts.error += 1;
      console.log(`[${done}/${urls.length}] ${rank} ${url} -> ERROR: ${result.error}`);
    } else {
      counts.ok += 1;
      console.log(`[${done}/${urls.length}] ${rank} ${url} -> ${result.status}`);
    }
  })
);

try {
  await Promise.all(tasks);
} finally {
  await browser.close();
}

console.log(`\nDone. ok=${counts.ok} error=${counts.error} skipped=${counts.skipped}`);
