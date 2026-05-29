# crawler

Puppeteer-based crawler that fetches the main page of each URL in a Tranco-style CSV using a Pixel 5 mobile emulation profile, and stores the HTTP response headers and rendered DOM for each site.

## Install

```bash
npm install
```

## Input

A CSV with two columns (no header): `rank,url`. URLs may omit the scheme; `https://` is assumed.

```
1,example.com
2,github.com
3,httpbin.org
```

## Run

```bash
node src/index.js --input data/input.csv --out data/out --concurrency 5 --timeout 30000
```

Flags:
- `--input, -i` *(required)* CSV path
- `--out, -o` output directory (default `data/out`)
- `--concurrency, -c` parallel pages (default `5`)
- `--timeout, -t` per-page navigation timeout in ms (default `30000`)
- `--user-data-dir` path to a Chromium user-data root (the root, not a profile sub-folder); required for Chrome's own `adFrameStatus` to fire (the indexed Subresource Filter ruleset must live at `<root>/Subresource Filter/`)
- `--profile-directory` profile folder name inside `--user-data-dir` (e.g. `Default`, `Profile 5`); selects which profile to use
- `--executable-path` path to a Chromium/Chrome binary; required when the `--user-data-dir` was produced by a different build than Puppeteer's bundled Chromium (e.g. you point at an installed Google Chrome profile)
- `--delay` per-page waiting time before taking the snapshot in ms
- `--max-urls` stop after processing N URLs
- `--start-from` start from line N (1-indexed), skips all earlier lines

## Output

Per URL, one folder `<out>/<rank>_<host>/` containing:
- `headers.json` — `{ url, finalUrl, status, statusText, requestHeaders, responseHeaders, redirectChain, timestamp }`
- `frames/<id>.html` — rendered DOM of every frame discovered via `page.frames()`. `000.html` is the main frame; `001.html`, `002.html`, … are children in discovery order (zero-padded, local to this folder).
- `iframes.json` — array with one entry per frame: `{ frameId, url, name, isMainFrame, adFrameStatus, iframes: [{ childFrameId, ...attributes }] }`. `childFrameId` cross-references each `<iframe>` element to the frame it loaded (`null` if it didn't load or has no content document). `adFrameStatus` is Chrome's own ad-tagging verdict from CDP (`{ adFrameType: 'none' | 'child' | 'root', explanations? }`) — see caveat below.
- `error.json` — only on failure, with the error message and stack

Re-running skips URLs whose `headers.json` already exists.

## Ad-frame tagging: `adFrameStatus`

`adFrameStatus` comes from Chromium's CDP `Page.AdFrameStatus`, populated by Chrome's built-in Subresource Filter (the same mechanism that powers heavy-ad / abusive-ad interventions). The ruleset it matches against is delivered by Chromium's **Component Updater service** — which does **not** run in ephemeral headless sessions. As a result, `adFrameType` will report `"none"` for every frame in a default crawl, even on sites that obviously serve ads.

To make `adFrameStatus` actually fire, supply a persistent profile via `--user-data-dir` whose `Subresource Filter/Indexed Rules/<format>/<content>/` already contains a Chrome-populated ruleset. The crawler doesn't ship or manage the ruleset — see the "Create Data Directory" section below for the bootstrap flow.

We didn't use the data produced by this in the paper.

## Local test server

For exercising the crawler against controlled iframe scenarios (sandbox variants, nested frames, cross-origin, srcdoc, `data:` URLs, dynamic injection, hidden CMP-style locators, etc.) a small static server is included:

```bash
npm run test-server        # serves :3000 (primary) + :3001 (third-party)
# in another terminal:
node src/index.js --input data/input-test.csv --out data/out --concurrency 3
```

The two ports give real cross-origin frames (browsers treat different ports on the same host as distinct origins). Scenario pages live under `test-server/sites/primary/`; visit `http://localhost:3000/` for an index. `data/input-test.csv` enumerates each scenario as a separate crawl target.


## Create Data Directory

mkdir -p data/chrome-profile
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --user-data-dir="$(pwd)/data/chrome-profile" \
    --no-first-run \
    --no-default-browser-check


- navigate to `chrome://components` and update `Subresource Filter Rules`


## Command used

node src/index.js --input data/bucketed_1M.csv --out data/bucketed_1M_out/ --concurrency 16 --timeout 30000 --delay 10000 --user-data-dir data/chrome-profile/