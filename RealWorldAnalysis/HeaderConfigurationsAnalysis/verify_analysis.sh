#!/bin/bash

# verify_analysis.sh - Verify analysis results match paper statistics
# Usage: ./verify_analysis.sh
# Exit code: 0 = all values match, 1 = any discrepancy

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORIGINAL_FILE="${SCRIPT_DIR}/bq_result.json"
SPLITTED_DIR="${SCRIPT_DIR}/bq_result_splitted"
ANALYSIS_SCRIPT="${SCRIPT_DIR}/analysis.py"

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

# Check if analysis script exists
if [ ! -f "$ANALYSIS_SCRIPT" ]; then
    echo "Error: Analysis script not found: $ANALYSIS_SCRIPT"
    exit 1
fi

# Run analysis and capture output
echo "Running analysis on bq_result.json..."
ANALYSIS_OUTPUT=$(python3 "$ANALYSIS_SCRIPT" "$ORIGINAL_FILE" 2>&1)

# Hardcoded expected values from paper
EXPECTED_TOTAL=822439
EXPECTED_EMBEDDABLE=485470
EXPECTED_BLOCKED=336969

# Expected top 5 combinations (name and count)
EXPECTED_COMB_NAMES_0="XFO: No XFO | CSP FA: No frame-ancestors"
EXPECTED_COMB_COUNTS_0=478682

EXPECTED_COMB_NAMES_1="XFO: SAMEORIGIN | CSP FA: No frame-ancestors"
EXPECTED_COMB_COUNTS_1=167436

EXPECTED_COMB_NAMES_2="XFO: DENY | CSP FA: 'none'"
EXPECTED_COMB_COUNTS_2=53999

EXPECTED_COMB_NAMES_3="XFO: SAMEORIGIN | CSP FA: 'self'"
EXPECTED_COMB_COUNTS_3=28637

EXPECTED_COMB_NAMES_4="XFO: DENY | CSP FA: No frame-ancestors"
EXPECTED_COMB_COUNTS_4=22914

# Parse the analysis output to extract values
# Top 1M line format: "Top 1M       | 485,470 (59.0%)        | 336,969 (41.0%)        | 822,439"
top1m_line=$(echo "$ANALYSIS_OUTPUT" | grep "^Top 1M" | head -1)

if [ -z "$top1m_line" ]; then
    echo "Error: Could not parse Top 1M statistics from analysis output"
    exit 1
fi

# Extract embeddable and blocked more carefully - get first number only
# Remove commas first to get complete numbers
ACTUAL_EMBEDDABLE=$(echo "$top1m_line" | awk -F'|' '{print $2}' | tr -d ',' | grep -oE '[0-9]+' | head -1)
ACTUAL_BLOCKED=$(echo "$top1m_line" | awk -F'|' '{print $3}' | tr -d ',' | grep -oE '[0-9]+' | head -1)
ACTUAL_TOTAL=$(echo "$top1m_line" | awk -F'|' '{print $4}' | tr -d ',' | grep -oE '[0-9]+' | head -1)

# Extract only the COMBINATIONS section
COMB_SECTION=$(echo "$ANALYSIS_OUTPUT" | sed -n '/TOP 10 MOST COMMON COMBINATIONS/,/^[[:space:]]*$/p')

# Extract combinations directly (not using function to avoid scope issues)
# Format: " 1. XFO: ... -> 478,682 ( 58.2% overall) | [N/A]"

# Combination 1
line1=$(echo "$COMB_SECTION" | grep -E "^[[:space:]]*1\\." | head -1)
ACTUAL_COMB_NAMES_0=$(echo "$line1" | sed 's/^[[:space:]]*[0-9][[:space:]]*\.//' | sed 's/[[:space:]]*->.*//' | sed 's/^[[:space:]]*//')
ACTUAL_COMB_COUNTS_0=$(echo "$line1" | sed 's/.*->[[:space:]]*//' | sed 's/[[:space:]]*(.*//' | tr -d ',' | tr -d ' ')

# Combination 2
line2=$(echo "$COMB_SECTION" | grep -E "^[[:space:]]*2\\." | head -1)
ACTUAL_COMB_NAMES_1=$(echo "$line2" | sed 's/^[[:space:]]*[0-9][[:space:]]*\.//' | sed 's/[[:space:]]*->.*//' | sed 's/^[[:space:]]*//')
ACTUAL_COMB_COUNTS_1=$(echo "$line2" | sed 's/.*->[[:space:]]*//' | sed 's/[[:space:]]*(.*//' | tr -d ',' | tr -d ' ')

# Combination 3
line3=$(echo "$COMB_SECTION" | grep -E "^[[:space:]]*3\\." | head -1)
ACTUAL_COMB_NAMES_2=$(echo "$line3" | sed 's/^[[:space:]]*[0-9][[:space:]]*\.//' | sed 's/[[:space:]]*->.*//' | sed 's/^[[:space:]]*//')
ACTUAL_COMB_COUNTS_2=$(echo "$line3" | sed 's/.*->[[:space:]]*//' | sed 's/[[:space:]]*(.*//' | tr -d ',' | tr -d ' ')

# Combination 4
line4=$(echo "$COMB_SECTION" | grep -E "^[[:space:]]*4\\." | head -1)
ACTUAL_COMB_NAMES_3=$(echo "$line4" | sed 's/^[[:space:]]*[0-9][[:space:]]*\.//' | sed 's/[[:space:]]*->.*//' | sed 's/^[[:space:]]*//')
ACTUAL_COMB_COUNTS_3=$(echo "$line4" | sed 's/.*->[[:space:]]*//' | sed 's/[[:space:]]*(.*//' | tr -d ',' | tr -d ' ')

# Combination 5
line5=$(echo "$COMB_SECTION" | grep -E "^[[:space:]]*5\\." | head -1)
ACTUAL_COMB_NAMES_4=$(echo "$line5" | sed 's/^[[:space:]]*[0-9][[:space:]]*\.//' | sed 's/[[:space:]]*->.*//' | sed 's/^[[:space:]]*//')
ACTUAL_COMB_COUNTS_4=$(echo "$line5" | sed 's/.*->[[:space:]]*//' | sed 's/[[:space:]]*(.*//' | tr -d ',' | tr -d ' ')

# Compare values
all_match=true

# Compare overall statistics
if [ "$ACTUAL_TOTAL" != "$EXPECTED_TOTAL" ]; then all_match=false; fi
if [ "$ACTUAL_EMBEDDABLE" != "$EXPECTED_EMBEDDABLE" ]; then all_match=false; fi
if [ "$ACTUAL_BLOCKED" != "$EXPECTED_BLOCKED" ]; then all_match=false; fi

# Compare top 5 combinations
if [ "$ACTUAL_COMB_NAMES_0" != "$EXPECTED_COMB_NAMES_0" ] || [ "$ACTUAL_COMB_COUNTS_0" != "$EXPECTED_COMB_COUNTS_0" ]; then all_match=false; fi
if [ "$ACTUAL_COMB_NAMES_1" != "$EXPECTED_COMB_NAMES_1" ] || [ "$ACTUAL_COMB_COUNTS_1" != "$EXPECTED_COMB_COUNTS_1" ]; then all_match=false; fi
if [ "$ACTUAL_COMB_NAMES_2" != "$EXPECTED_COMB_NAMES_2" ] || [ "$ACTUAL_COMB_COUNTS_2" != "$EXPECTED_COMB_COUNTS_2" ]; then all_match=false; fi
if [ "$ACTUAL_COMB_NAMES_3" != "$EXPECTED_COMB_NAMES_3" ] || [ "$ACTUAL_COMB_COUNTS_3" != "$EXPECTED_COMB_COUNTS_3" ]; then all_match=false; fi
if [ "$ACTUAL_COMB_NAMES_4" != "$EXPECTED_COMB_NAMES_4" ] || [ "$ACTUAL_COMB_COUNTS_4" != "$EXPECTED_COMB_COUNTS_4" ]; then all_match=false; fi

# Function to format number with commas
format_num() {
    echo "$1" | sed ':a;s/\B[0-9]\{3\}\>$/,&/;ta'
}

# Output results
echo ""
echo "=== Verification Results ==="
printf "%-32s | %-9s | %-9s | %s\n" "Metric" "Expected" "Actual" "Match"
echo "-------------------------------|-----------|-----------|------"

# Overall statistics
match_total="$([ "$ACTUAL_TOTAL" == "$EXPECTED_TOTAL" ] && echo "YES" || echo "NO")"
printf "%-32s | %-9s | %-9s | %s\n" \
    "Total websites" \
    "$(format_num $EXPECTED_TOTAL)" \
    "$(format_num ${ACTUAL_TOTAL:-0})" \
    "$match_total"

match_embeddable="$([ "$ACTUAL_EMBEDDABLE" == "$EXPECTED_EMBEDDABLE" ] && echo "YES" || echo "NO")"
printf "%-32s | %-9s | %-9s | %s\n" \
    "Embeddable websites" \
    "$(format_num $EXPECTED_EMBEDDABLE)" \
    "$(format_num ${ACTUAL_EMBEDDABLE:-0})" \
    "$match_embeddable"

match_blocked="$([ "$ACTUAL_BLOCKED" == "$EXPECTED_BLOCKED" ] && echo "YES" || echo "NO")"
printf "%-32s | %-9s | %-9s | %s\n" \
    "Blocked websites" \
    "$(format_num $EXPECTED_BLOCKED)" \
    "$(format_num ${ACTUAL_BLOCKED:-0})" \
    "$match_blocked"

# Top 5 combinations
match_0_name="$([ "${ACTUAL_COMB_NAMES_0}" == "${EXPECTED_COMB_NAMES_0}" ] && echo "YES" || echo "NO")"
match_0_count="$([ "${ACTUAL_COMB_COUNTS_0}" == "${EXPECTED_COMB_COUNTS_0}" ] && echo "YES" || echo "NO")"
match_0="$([ "$match_0_name" == "YES" ] && [ "$match_0_count" == "YES" ] && echo "YES" || echo "NO")"

name_display="${EXPECTED_COMB_NAMES_0:0:28}"
if [ ${#EXPECTED_COMB_NAMES_0} -gt 28 ]; then
    name_display="${name_display}..."
fi
printf "%-32s | %-9s | %-9s | %s\n" \
    "Top 1: $name_display" \
    "$(format_num ${EXPECTED_COMB_COUNTS_0})" \
    "$(format_num ${ACTUAL_COMB_COUNTS_0:-0})" \
    "$match_0"

match_1_name="$([ "${ACTUAL_COMB_NAMES_1}" == "${EXPECTED_COMB_NAMES_1}" ] && echo "YES" || echo "NO")"
match_1_count="$([ "${ACTUAL_COMB_COUNTS_1}" == "${EXPECTED_COMB_COUNTS_1}" ] && echo "YES" || echo "NO")"
match_1="$([ "$match_1_name" == "YES" ] && [ "$match_1_count" == "YES" ] && echo "YES" || echo "NO")"

name_display="${EXPECTED_COMB_NAMES_1:0:28}"
if [ ${#EXPECTED_COMB_NAMES_1} -gt 28 ]; then
    name_display="${name_display}..."
fi
printf "%-32s | %-9s | %-9s | %s\n" \
    "Top 2: $name_display" \
    "$(format_num ${EXPECTED_COMB_COUNTS_1})" \
    "$(format_num ${ACTUAL_COMB_COUNTS_1:-0})" \
    "$match_1"

match_2_name="$([ "${ACTUAL_COMB_NAMES_2}" == "${EXPECTED_COMB_NAMES_2}" ] && echo "YES" || echo "NO")"
match_2_count="$([ "${ACTUAL_COMB_COUNTS_2}" == "${EXPECTED_COMB_COUNTS_2}" ] && echo "YES" || echo "NO")"
match_2="$([ "$match_2_name" == "YES" ] && [ "$match_2_count" == "YES" ] && echo "YES" || echo "NO")"

name_display="${EXPECTED_COMB_NAMES_2:0:28}"
if [ ${#EXPECTED_COMB_NAMES_2} -gt 28 ]; then
    name_display="${name_display}..."
fi
printf "%-32s | %-9s | %-9s | %s\n" \
    "Top 3: $name_display" \
    "$(format_num ${EXPECTED_COMB_COUNTS_2})" \
    "$(format_num ${ACTUAL_COMB_COUNTS_2:-0})" \
    "$match_2"

match_3_name="$([ "${ACTUAL_COMB_NAMES_3}" == "${EXPECTED_COMB_NAMES_3}" ] && echo "YES" || echo "NO")"
match_3_count="$([ "${ACTUAL_COMB_COUNTS_3}" == "${EXPECTED_COMB_COUNTS_3}" ] && echo "YES" || echo "NO")"
match_3="$([ "$match_3_name" == "YES" ] && [ "$match_3_count" == "YES" ] && echo "YES" || echo "NO")"

name_display="${EXPECTED_COMB_NAMES_3:0:28}"
if [ ${#EXPECTED_COMB_NAMES_3} -gt 28 ]; then
    name_display="${name_display}..."
fi
printf "%-32s | %-9s | %-9s | %s\n" \
    "Top 4: $name_display" \
    "$(format_num ${EXPECTED_COMB_COUNTS_3})" \
    "$(format_num ${ACTUAL_COMB_COUNTS_3:-0})" \
    "$match_3"

match_4_name="$([ "${ACTUAL_COMB_NAMES_4}" == "${EXPECTED_COMB_NAMES_4}" ] && echo "YES" || echo "NO")"
match_4_count="$([ "${ACTUAL_COMB_COUNTS_4}" == "${EXPECTED_COMB_COUNTS_4}" ] && echo "YES" || echo "NO")"
match_4="$([ "$match_4_name" == "YES" ] && [ "$match_4_count" == "YES" ] && echo "YES" || echo "NO")"

name_display="${EXPECTED_COMB_NAMES_4:0:28}"
if [ ${#EXPECTED_COMB_NAMES_4} -gt 28 ]; then
    name_display="${name_display}..."
fi
printf "%-32s | %-9s | %-9s | %s\n" \
    "Top 5: $name_display" \
    "$(format_num ${EXPECTED_COMB_COUNTS_4})" \
    "$(format_num ${ACTUAL_COMB_COUNTS_4:-0})" \
    "$match_4"

echo ""
if [ "$all_match" = true ]; then
    echo "Result: TRUE"
    exit 0
else
    echo "Result: FALSE"
    exit 1
fi
