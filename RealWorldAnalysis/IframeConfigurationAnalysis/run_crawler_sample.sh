#!/bin/bash
#
# run_crawler_sample.sh - Crawler script for artifact evaluation
#
# PURPOSE:
#   Randomly samples a configurable number of websites from the Tranco-style
#   CSV list and runs the iframe crawler on them. Results are saved for
#   manual reviewer inspection.
#
# USAGE:
#   ./run_crawler_sample.sh
#
#   Reviewers can modify the configuration section below to:
#   - Change the number of websites to sample
#   - Use a different random seed for reproducibility
#   - Adjust crawler performance parameters
#
# OUTPUT:
#   - evaluator_sample_output/  : Directory containing crawled data
#   - evaluator_sample_output/sampled_websites.csv : List of sampled sites
#
# EXPECTED RUNTIME:
#   Approximately 6-10 minutes for 50 websites with concurrency=4
#   (actual time depends on network conditions and website complexity)
#
# MANUAL INSPECTION:
#   After running, reviewers can:
#   1. Check evaluator_sample_output/sampled_websites.csv for the list of sites
#   2. Examine individual site folders (e.g., evaluator_sample_output/18_google.com/)
#   3. Review headers.json for HTTP response information
#   4. Check frames/*.html for rendered DOM content
#   5. Inspect iframes.json for iframe structure and attributes
#   6. Run analyze.py on the output directory for statistical analysis
#
# REPRODUCIBILITY:
#   Use the same RANDOM_SEED value to reproduce the exact same sample.
#   Change RANDOM_SEED to get a different random sample.
#
################################################################################

set -e  # Exit on error

################################################################################
# CONFIGURATION SECTION - Reviewers can modify these values
################################################################################

SAMPLE_SIZE=50           # Number of websites to sample
RANDOM_SEED=42           # Fixed seed for reproducibility (change for different sample)
INPUT_CSV="crawler/data/bucketed_1M.csv"
OUTPUT_DIR="evaluator_sample_output"
CONCURRENCY=4            # Parallel pages (conservative for various setups)
TIMEOUT=30000            # Per-page navigation timeout in milliseconds
DELAY=10000              # Delay before capturing snapshot (as used in paper)

################################################################################
# END OF CONFIGURATION SECTION
################################################################################

# Colors for output (works in most terminals)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if input CSV exists
if [ ! -f "$INPUT_CSV" ]; then
    print_error "Input CSV not found: $INPUT_CSV"
    print_error "Please ensure you're running this script from the IframeConfigurationAnalysis directory"
    print_error "or provide the correct path to bucketed_1M.csv"
    exit 1
fi

print_info "Input CSV found: $INPUT_CSV"

# Check if Node.js is available
if ! command -v node &> /dev/null; then
    print_error "Node.js is not installed or not in PATH"
    print_error "Please install Node.js to run the crawler"
    exit 1
fi

print_info "Node.js version: $(node --version)"

# Create output directory
mkdir -p "$OUTPUT_DIR"
print_info "Output directory: $OUTPUT_DIR"

# Create a temporary file for the sampled CSV
TEMP_CSV=$(mktemp /tmp/sampled_websites_XXXXXX.csv)
trap "rm -f $TEMP_CSV" EXIT

print_info "Randomly sampling $SAMPLE_SIZE websites from $(wc -l < "$INPUT_CSV") total websites..."
print_info "Using random seed: $RANDOM_SEED"

# Use Python for reproducible random sampling
python3 << EOF
import random
import csv

random.seed($RANDOM_SEED)

# Read all URLs from the input CSV
with open('$INPUT_CSV', 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    all_rows = list(reader)

total_count = len(all_rows)
print(f"Total websites available: {total_count}")

# Sample the specified number of websites
if $SAMPLE_SIZE > total_count:
    print(f"Warning: Sample size ($SAMPLE_SIZE) is larger than total websites ({total_count})")
    print(f"Sampling all {total_count} websites instead")
    sampled = all_rows
else:
    sampled = random.sample(all_rows, $SAMPLE_SIZE)

# Sort by rank to maintain order (optional, but makes output more organized)
sampled.sort(key=lambda x: int(x[0]) if x[0].isdigit() else float('inf'))

# Write sampled websites to temporary file
with open('$TEMP_CSV', 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerows(sampled)

# Also save to output directory for reference
with open('$OUTPUT_DIR/sampled_websites.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerows(sampled)

print(f"Sampled {len(sampled)} websites")
print(f"Saved sampled list to: $OUTPUT_DIR/sampled_websites.csv")
EOF

print_info "Temporary CSV created: $TEMP_CSV"
print_info ""
print_info "Starting crawler with the following parameters:"
print_info "  - Concurrency: $CONCURRENCY"
print_info "  - Timeout: ${TIMEOUT}ms"
print_info "  - Delay: ${DELAY}ms"
print_info ""
print_info "This may take several minutes. Progress will be shown below:"
print_info "--------------------------------------------------------------------------------"

# Run the crawler
# Note: We use || true to prevent script exit on crawler errors (individual site failures are expected)
cd crawler

# Check if crawler dependencies are installed
if [ ! -d "node_modules" ]; then
    print_warning "Node modules not found. Installing dependencies..."
    npm install || true
fi

node src/index.js \
    --input "$TEMP_CSV" \
    --out "../$OUTPUT_DIR" \
    --concurrency "$CONCURRENCY" \
    --timeout "$TIMEOUT" \
    --delay "$DELAY" \
    || true
cd ..

print_info "--------------------------------------------------------------------------------"
print_info ""
print_info "Crawling complete!"
print_info ""

# Count results
SUCCESS_COUNT=$(find "$OUTPUT_DIR" -maxdepth 1 -type d -name "*_*" | wc -l)
ERROR_COUNT=$(find "$OUTPUT_DIR" -maxdepth 1 -type f -name "error.json" | wc -l)

print_success "Results summary:"
print_info "  - Successfully crawled: $SUCCESS_COUNT websites"
print_info "  - Errors: $ERROR_COUNT websites"
print_info "  - Sampled websites list: $OUTPUT_DIR/sampled_websites.csv"
print_info ""
print_info "Output directory: $OUTPUT_DIR/"
print_info ""
print_info "Next steps for manual inspection:"
print_info "  1. Browse $OUTPUT_DIR/ to see individual website folders"
print_info "  2. Each folder contains:"
print_info "     - headers.json (HTTP response information)"
print_info "     - frames/*.html (rendered DOM for each frame)"
print_info "     - iframes.json (iframe structure and attributes)"
print_info "  3. Run analyze.py for statistical analysis:"
print_info "     python3 analyze.py $OUTPUT_DIR ${OUTPUT_DIR}_report"
print_info ""
print_success "Done! Results saved to: $OUTPUT_DIR/"
