import fs from 'node:fs/promises';
import { readFileSync } from 'node:fs'; // Import just the sync function you need
import path, { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout } from 'node:timers/promises';
import puppeteer, { KnownDevices } from 'puppeteer';
import { normalizeUrl } from './fs-utils.js';
import { log } from 'node:console';

// ######### START OF DuckDuckGo Autoconsent

const autoconsentScript = readFileSync(
  resolve(
    dirname(fileURLToPath(import.meta.resolve('@duckduckgo/autoconsent'))),
    'autoconsent.playwright.js'
  ),
  'utf8'
)

// Load the rule bundles shipped with the package
const rules = JSON.parse(
  readFileSync(
    fileURLToPath(import.meta.resolve('@duckduckgo/autoconsent/rules/rules.json')),
    'utf8'
  )
)

// See https://github.com/duckduckgo/autoconsent/blob/main/docs/api.md
const autoconsentConfig = {
  enabled: true,
  autoAction: 'optOut',
  disabledCmps: [],
  enablePrehide: true,
  enableCosmeticRules: true,
  enableGeneratedRules: true,
  detectRetries: 20,
  isMainWorld: false,
  prehideTimeout: 2000,
  enableFilterList: false,
  enableHeuristicDetection: true,
  enableHeuristicAction: true,
  logs: {
    lifecycle: false,
    rulesteps: false,
    detectionsteps: false,
    evals: false,
    errors: true,
    messages: false,
    waits: false,
  },
}

const sendMessage = (page, message) =>
  page
    .evaluate(msg => {
      if (window.autoconsentReceiveMessage) {
        return window.autoconsentReceiveMessage(msg)
      }
    }, message)
    .catch(() => {})

async function setupAutoconsent(page) {
  await page.exposeFunction('autoconsentSendMessage', async message => {
    if (!message || typeof message !== 'object') return

    switch (message.type) {
      case 'init':
        return sendMessage(page, {
          type: 'initResp',
          config: autoconsentConfig,
          rules, // must include rules or no CMPs will be detected
        })

      case 'eval': {
        const result = await page.evaluate(message.code)
        return sendMessage(page, {
          type: 'evalResp',
          id: message.id,
          result,
        })
      }

      // informational messages — silenced
      case 'cmpDetected':
      case 'popupFound':
      case 'optOutResult':
      case 'autoconsentDone':
      case 'autoconsentError':
        break
    }
  })

  await page.evaluateOnNewDocument(autoconsentScript);
}


// ############### END OF DuckDuckGo AutoConsent

const DEVICE = KnownDevices['Pixel 5'];

function serializeRedirectChain(mainRequest) {
  return mainRequest.redirectChain().map((req) => {
    const res = req.response();
    return {
      url: req.url(),
      method: req.method(),
      status: res?.status() ?? null,
      responseHeaders: res?.headers() ?? null,
    };
  });
}

function assignFrameIds(page) {
  const frames = page.frames();
  const main = page.mainFrame();
  const ordered = [main, ...frames.filter((f) => f !== main)];
  const ids = new Map();
  ordered.forEach((frame, i) => {
    ids.set(frame, String(i).padStart(3, '0'));
  });
  return { ids, ordered };
}

async function writeFrameDom(frame, framesDir, id) {
  try {
    const html = await frame.content();
    await fs.writeFile(path.join(framesDir, `${id}.html`), html);
    return true;
  } catch {
    return false;
  }
}

async function extractIframes(frame, frameIds) {
  let handles;
  try {
    handles = await frame.$$('iframe');
  } catch {
    return [];
  }
  const records = [];
  for (const h of handles) {
    try {
      const attrs = await h.evaluate((el) => {
        const o = {};
        for (const a of el.attributes) o[a.name] = a.value;
        return o;
      });
      const childFrame = await h.contentFrame().catch(() => null);
      const childFrameId = childFrame ? frameIds.get(childFrame) ?? null : null;
      records.push({ childFrameId, ...attrs });
    } catch {
      // ignore individual iframe failures
    } finally {
      await h.dispose().catch(() => {});
    }
  }
  return records;
}

async function getAdFrameStatuses(page) {
  const client = await page.createCDPSession();
  try {
    const { frameTree } = await client.send('Page.getFrameTree');
    const map = new Map();
    const walk = (node) => {
      map.set(node.frame.id, node.frame.adFrameStatus ?? null);
      for (const child of node.childFrames ?? []) walk(child);
    };
    walk(frameTree);
    return map;
  } finally {
    try {
      await Promise.race([
        client.detach(),
        new Promise((_, reject) => {
          setTimeout(() => reject(new Error('CDP detach timeout')), 2000);
        }),
      ]);
    } catch {
      // CDP session detach failed - skip silently
    }
  }
}

// Puppeteer's Frame#_id is private but de-facto stable and matches the CDP frame id.
function cdpFrameId(frame) {
  return frame._id ?? null;
}

async function collectFrames(page, framesDir) {
  const { ids, ordered } = assignFrameIds(page);
  const adStatuses = await getAdFrameStatuses(page).catch(() => new Map());
  const main = page.mainFrame();
  const out = [];
  for (const frame of ordered) {
    const id = ids.get(frame);
    await writeFrameDom(frame, framesDir, id);
    const iframes = await extractIframes(frame, ids);
    out.push({
      frameId: id,
      url: frame.url(),
      name: frame.name() || null,
      isMainFrame: frame === main,
      adFrameStatus: adStatuses.get(cdpFrameId(frame)) ?? null,
      iframes,
    });
  }
  return out;
}

async function withTimeout(promise, ms, label = 'Operation') {
  let timeoutId;
  const timeoutPromise = new Promise((_, reject) => {
    timeoutId = setTimeout(() => {
      reject(new Error(`${label} timed out after ${ms}ms`));
    }, ms);
  });
  const result = await Promise.race([promise, timeoutPromise]);
  clearTimeout(timeoutId);
  return result;
}

async function closeWithTimeout(resource, ms, label) {
  try {
    await Promise.race([
      resource.close(),
      new Promise((_, reject) => {
        setTimeout(() => reject(new Error(`${label} close timeout`)), ms);
      }),
    ]);
  } catch {
    // Resource didn't close cleanly - skip silently, browser will clean up on shutdown
  }
}

export async function crawlOne({ browser, rank, url, outDir, timeoutMs, delayMs = 0}) {
  const target = normalizeUrl(url);
  await fs.mkdir(outDir, { recursive: true });

  const headersPath = path.join(outDir, 'headers.json');
  try {
    await fs.access(headersPath);
    return { rank, url, skipped: true };
  } catch { /* not present, continue */ }

  const context = await browser.createBrowserContext();
  const page = await context.newPage();

  await setupAutoconsent(page);

  const totalTimeoutMs = timeoutMs + 5000;

  try {
    await withTimeout(
      (async () => {
        await page.emulate(DEVICE);

        const response = await page.goto(target, {
          timeout: timeoutMs,
        });

        await setTimeout(delayMs);
        
        if (!response) {
          throw new Error('No response received');
        }

        const mainRequest = response.request();
        const framesDir = path.join(outDir, 'frames');
        await fs.mkdir(framesDir, { recursive: true });
        
        const frames = await collectFrames(page, framesDir);

        const headersOut = {
          url: target,
          finalUrl: response.url(),
          status: response.status(),
          statusText: response.statusText(),
          requestHeaders: mainRequest.headers(),
          responseHeaders: response.headers(),
          redirectChain: serializeRedirectChain(mainRequest),
          timestamp: new Date().toISOString(),
        };

        await fs.writeFile(headersPath, JSON.stringify(headersOut, null, 2));
        await fs.writeFile(path.join(outDir, 'iframes.json'), JSON.stringify(frames, null, 2));
        return { rank, url, status: response.status() };
      })(),
      totalTimeoutMs,
      `Crawl for ${target}`
    );
    return { rank, url, status: 'ok' };
  } catch (err) {
    const errOut = {
      url: target,
      error: err.message,
      stack: err.stack,
      timestamp: new Date().toISOString(),
    };
    await fs.writeFile(path.join(outDir, 'error.json'), JSON.stringify(errOut, null, 2));
    return { rank, url, error: err.message };
  } finally {
    await closeWithTimeout(page, 2000, 'Page');
    await closeWithTimeout(context, 2000, 'Context');
  }
}
