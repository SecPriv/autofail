#!/bin/bash

# compare_results.sh - Compare provided file's bq results with original
# Usage: ./compare_results.sh <provided_file.json> [--verbose]
# Exit code: 0 = identical, 1 = different

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORIGINAL_FILE="${SCRIPT_DIR}/bq_result.json"
SPLITTED_DIR="${SCRIPT_DIR}/bq_result_splitted"
VERBOSE=false

# Parse arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <provided_file.json> [--verbose]"
    exit 1
fi

REVIEWER_FILE="$1"
shift

while [ $# -gt 0 ]; do
    case "$1" in
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 <reviewer_file.json> [--verbose]"
            exit 1
            ;;
    esac
done

# Check if provided file exists
if [ ! -f "$REVIEWER_FILE" ]; then
    echo "Error: provided file '$REVIEWER_FILE' not found"
    exit 1
fi

# Function to aggregate original file from parts
aggregate_original() {
    echo "Aggregating original bq_result.json from split parts..."
    
    # Count parts
    NUM_PARTS=$(ls -1 "${SPLITTED_DIR}"/bq_result.json.part* 2>/dev/null | wc -l)
    
    if [ "$NUM_PARTS" -eq 0 ]; then
        echo "Error: No split parts found in ${SPLITTED_DIR}"
        exit 1
    fi
    
    echo "Found $NUM_PARTS parts"
    
    # Aggregate parts
    cat "${SPLITTED_DIR}"/bq_result.json.part* > "$ORIGINAL_FILE"
    
    echo "Aggregation complete: $ORIGINAL_FILE"
}

# Check if original file exists, if not aggregate it
if [ ! -f "$ORIGINAL_FILE" ]; then
    echo "Original file not found. Checking for split parts..."
    if [ -d "$SPLITTED_DIR" ]; then
        aggregate_original
    else
        echo "Error: Neither $ORIGINAL_FILE nor $SPLITTED_DIR found"
        exit 1
    fi
fi

# Create temporary files for sorted versions
TEMP_DIR=$(mktemp -d)
ORIGINAL_SORTED="${TEMP_DIR}/original_sorted.json"
REVIEWER_SORTED="${TEMP_DIR}/provided_sorted.json"

# Cleanup function
cleanup() {
    rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

# Sort both files by URL using Python for efficiency with large files
sort_ndjson_by_url() {
    local input_file="$1"
    local output_file="$2"
    
    python3 -c "
import json
import sys

input_file = sys.argv[1]
output_file = sys.argv[2]

records = []
with open(input_file, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line:
            try:
                record = json.loads(line)
                records.append(record)
            except json.JSONDecodeError:
                pass

# Sort by url field
records.sort(key=lambda x: x.get('url', ''))

# Write sorted records
with open(output_file, 'w', encoding='utf-8') as f:
    for record in records:
        f.write(json.dumps(record, separators=(',', ':')) + '\n')
" "$input_file" "$output_file"
}

echo "Sorting original file by URL..."
sort_ndjson_by_url "$ORIGINAL_FILE" "$ORIGINAL_SORTED"

echo "Sorting provided file by URL..."
sort_ndjson_by_url "$REVIEWER_FILE" "$REVIEWER_SORTED"

# Compare the sorted files
echo "Comparing files..."

if [ "$VERBOSE" = true ]; then
    echo ""
    echo "=== Differences ==="
    DIFF_OUTPUT=$(diff "$ORIGINAL_SORTED" "$REVIEWER_SORTED" || true)
    if [ -n "$DIFF_OUTPUT" ]; then
        echo "$DIFF_OUTPUT"
    else
        echo "No differences found"
    fi
    echo "==================="
    echo ""
fi

# Run diff and capture exit code
if diff -q "$ORIGINAL_SORTED" "$REVIEWER_SORTED" > /dev/null 2>&1; then
    echo "SUCCESS: The files match"
    exit 0
else
    echo "FAILURE: The files do not match"
    exit 1
fi
