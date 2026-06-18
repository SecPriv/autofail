# Artifact Evaluation: Iframe Configuration Analysis

This document guides reviewers through reproducing the iframe configuration analysis from our study.

## Overview

The artifact evaluation consists of three main steps:

1. **Crawling (Sample)**: Collect iframe data from a random sample of 50 websites
2. **Crawling (Full)**: Use pre-crawled data from 3,522 websites (already available)
3. **Verification**: Run analysis and verify results match the paper's statistics

## Step 1: Crawling a Sample of Websites (Optional)

We provide a script to randomly sample and crawl websites from the Tranco top 1M list.

### Quick Start

```bash
cd RealWorldAnalysis/IframeConfigurationAnalysis
./run_crawler_sample.sh
```

This will:
- Randomly sample **50 websites** from the Tranco list
- Crawl each website using Puppeteer with mobile emulation
- Save the results to `evaluator_sample_output/`
- Expected runtime: **6-10 minutes**

### Configuration

Edit `run_crawler_sample.sh` to customize:

```bash
SAMPLE_SIZE=50           # Number of websites to sample
RANDOM_SEED=42           # Change for different random sample
CONCURRENCY=4            # Parallel crawls (adjust based on your system)
TIMEOUT=30000            # Per-page timeout (milliseconds)
DELAY=10000              # Delay before capturing (milliseconds)
```

### Reproducibility

To reproduce the **exact same sample**, use the same `RANDOM_SEED` value (default: 42).

To get a **different random sample**, change the `RANDOM_SEED` value.

### Output Structure

After crawling, you'll have:

```
evaluator_sample_output/
├── sampled_websites.csv       # List of 50 sampled sites
├── 27_allegro.pl/
│   ├── headers.json           # HTTP response information
│   ├── frames/
│   │   ├── 000.html           # Main frame DOM
│   │   ├── 001.html           # Child frame DOM
│   │   └── ...
│   └── iframes.json           # Iframe structure and attributes
├── 103_booking.com/
│   └── ...
└── ...
```

### Manual Inspection

Reviewers can manually inspect:

1. **HTTP Headers**: `headers.json` contains response headers, status codes, and redirect chains
2. **Frame DOM**: `frames/*.html` files contain the rendered HTML of each frame
3. **Iframe Structure**: `iframes.json` contains:
   - Frame URLs and hierarchy
   - Iframe element attributes (sandbox, credentialless, etc.)
   - Visibility information
   - Cross-origin relationships

Example inspection:
```bash
# View sampled websites
cat evaluator_sample_output/sampled_websites.csv

# Inspect a specific site's headers
cat evaluator_sample_output/27_allegro.pl/headers.json | jq .

# Count iframes in a site
cat evaluator_sample_output/27_allegro.pl/iframes.json | jq '.[].iframes | length'
```

## Step 2: Verification Against Paper Results (Main Evaluation)

To verify that the analysis reproduces the paper's results, run the verification script on the pre-crawled dataset:

```bash
cd RealWorldAnalysis/IframeConfigurationAnalysis
./verify_analysis.sh
```

This will:
1. Run `analyze.py` on the pre-crawled dataset (3,522 sites from `crawler/data/bucketed_1M_out/`)
2. Generate statistical reports in `verification_output/`
3. Compare all metrics with the paper's reported statistics
4. Generate `verification_report.txt` with pass/fail for each metric
5. Exit with code 0 if all metrics match, 1 otherwise

**Expected runtime:** 30-60 seconds

**Expected output:**
```
OVERALL RESULT:  ALL 38 METRICS VERIFIED SUCCESSFULLY

The analysis results match the paper's reported statistics exactly.
Reproducibility: VERIFIED
```

### Metrics Verified

The script verifies 38 metrics total:

**Overall Statistics (10 metrics):**
- Total sites analyzed: 3,522
- Total iframe elements: 9,552
- Sandboxed iframes: 2,167
- allow-same-origin usage: 90.4%
- allow-scripts usage: 88.5%
- Both directives combined: 82.6%
- Sites with login forms: 412
- Login + cross-site iframes: 38.8%
- Cross-Site Suggestions preconditions: 826 sites (23.5%)
- Credentialless iframes: 0

**Per-Bucket Breakdown (28 metrics):**
- Top 1K (1-1000): 7 metrics from `table_iframes.tex`
- Top 10K (1001-2000): 7 metrics
- Top 100K (2001-3000): 7 metrics
- Top 1M (3001-4000): 7 metrics

All metrics must match exactly (percentages have 0.1% tolerance).



## Summary of Scripts

| Script | Purpose | Runtime | Output |
|--------|---------|---------|--------|
| `./run_crawler_sample.sh` | Crawl 50 random websites | 6-10 min | `evaluator_sample_output/` |
| `./verify_analysis.sh` | **Verify paper results** (main evaluation) | 30-60 sec | `verification_report.txt`  |
| `python3 analyze.py ...` | Analyze custom dataset | Varies | Analysis reports |

**For artifact evaluators:** The main evaluation is running `./verify_analysis.sh` which verifies that the pre-crawled data produces the exact statistics reported in the paper.

## Troubleshooting

### Missing Dependencies

If you get Node.js errors:
```bash
cd crawler
npm install
```

### Crawler Timeout Issues

Increase the timeout value in `run_crawler_sample.sh`:
```bash
TIMEOUT=60000  # 60 seconds instead of 30
```

### Memory Issues

Reduce concurrency:
```bash
CONCURRENCY=2  # Fewer parallel crawls
```

### Individual Site Failures

The crawler continues on individual site failures. Check `error.json` files in site folders for details. Failed sites are normal and expected.

## Questions?

For issues or questions about the artifact evaluation, please contact the authors.
