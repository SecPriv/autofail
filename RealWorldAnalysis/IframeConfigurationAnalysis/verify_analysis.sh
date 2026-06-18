#!/bin/bash
#
# verify_analysis.sh - Run iframe analysis and verify against paper results
#
# PURPOSE:
#   This script runs the iframe analysis on the pre-crawled dataset and
#   verifies that the results match the statistics reported in the paper.
#
# USAGE:
#   ./verify_analysis.sh
#
#   Run from the IframeConfigurationAnalysis directory.
#   Expects crawler/data/bucketed_1M_out/ to contain the pre-crawled data.
#
# OUTPUT:
#   - verification_output/              : Directory containing analysis reports
#   - verification_output_robots/       : Directory containing JSON reports
#   - verification_report.txt           : Verification results (pass/fail)
#
# EXIT CODES:
#   0 - All metrics verified successfully
#   1 - One or more metrics failed verification
#
# EXPECTED RUNTIME:
#   Approximately 30-60 seconds for analysis + verification
#
################################################################################

set -e

# === CONFIGURATION ===
INPUT_DIR="crawler/data/bucketed_1M_out"
OUTPUT_DIR="verification_output"
REPORT_FILE="verification_report.txt"
JSON_DIR="${OUTPUT_DIR}_robots"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "================================================================================"
echo "IFRAME ANALYSIS VERIFICATION"
echo "================================================================================"
echo ""
print_info "Running analysis on pre-crawled dataset..."
print_info "  Input:  $INPUT_DIR"
print_info "  Output: $OUTPUT_DIR"
echo ""

# Check if input directory exists
if [ ! -d "$INPUT_DIR" ]; then
    print_error "Input directory not found: $INPUT_DIR"
    print_error "Please ensure you're running this script from the IframeConfigurationAnalysis directory"
    exit 1
fi

# Step 1: Run analysis
python3 analyze.py "$INPUT_DIR" "$OUTPUT_DIR" > /dev/null 2>&1

print_success "Analysis complete. Verifying metrics..."
echo ""

# Step 2: Run verification using Python (parses JSON files)
python3 << 'PYTHON_SCRIPT'
import json
import os
from datetime import datetime

# === HARDCODED EXPECTED VALUES (from paper Section 8a and tables) ===

# Overall Statistics
EXPECTED = {
    'total_sites': 3522,
    'total_iframe_elements': 9552,
    'sandboxed_iframes': 2167,
    'sandbox_allow_same_origin_pct': 90.4,
    'sandbox_allow_scripts_pct': 88.5,
    'sandbox_both_directives_pct': 82.6,
    'sites_with_login': 412,
    'sites_login_cross_site_pct': 38.8,
    'sites_risky_visible_count': 826,
    'credentialless_iframes': 0
}

# Per-Bucket Statistics (Table: tab:iframe_sandbox_stats_single)
BUCKETS = {
    'top_1k': {
        'file': 'report_01_first_1000.json',
        'expected': {
            'total_iframe_elements': 3336,
            'cross_site_iframes': 1192,
            'sandbox_cross_site': 487,
            'non_sandbox_cross_site': 705,
            'same_site_iframes': 2144,
            'sandbox_same_site': 263,
            'non_sandbox_same_site': 1881
        },
        'sandbox_directives': {
            'allow_same_origin': 93.7,
            'allow_scripts': 86.3,
            'allow_forms': 44.5,
            'allow_popups': 44.3,
            'allow_popups_escape': 41.1
        }
    },
    'top_10k': {
        'file': 'report_02_second_1000.json',
        'expected': {
            'total_iframe_elements': 2912,
            'cross_site_iframes': 1103,
            'sandbox_cross_site': 463,
            'non_sandbox_cross_site': 640,
            'same_site_iframes': 1809,
            'sandbox_same_site': 222,
            'non_sandbox_same_site': 1587
        },
        'sandbox_directives': {
            'allow_same_origin': 94.9,
            'allow_scripts': 86.6,
            'allow_forms': 54.3,
            'allow_popups': 51.7,
            'allow_popups_escape': 49.9
        }
    },
    'top_100k': {
        'file': 'report_03_third_1000.json',
        'expected': {
            'total_iframe_elements': 2230,
            'cross_site_iframes': 908,
            'sandbox_cross_site': 329,
            'non_sandbox_cross_site': 579,
            'same_site_iframes': 1322,
            'sandbox_same_site': 166,
            'non_sandbox_same_site': 1156
        },
        'sandbox_directives': {
            'allow_same_origin': 82.6,
            'allow_scripts': 91.1,
            'allow_forms': 69.3,
            'allow_popups': 54.5,
            'allow_popups_escape': 52.3
        }
    },
    'top_1m': {
        'file': 'report_04_fourth_1000.json',
        'expected': {
            'total_iframe_elements': 1074,
            'cross_site_iframes': 479,
            'sandbox_cross_site': 166,
            'non_sandbox_cross_site': 313,
            'same_site_iframes': 595,
            'sandbox_same_site': 71,
            'non_sandbox_same_site': 524
        },
        'sandbox_directives': {
            'allow_same_origin': 83.5,
            'allow_scripts': 95.4,
            'allow_forms': 86.5,
            'allow_popups': 71.3,
            'allow_popups_escape': 67.9
        }
    }
}

# === VERIFICATION FUNCTIONS ===

def compare_values(expected, actual, metric_name):
    """Compare integer values and return (passed, message)"""
    if actual == expected:
        return True, f"PASS: {metric_name}\n   Expected: {expected} | Actual: {actual}"
    else:
        diff = actual - expected
        return False, f"❌ FAIL: {metric_name}\n   Expected: {expected} | Actual: {actual} | Difference: {diff}"

def compare_percentages(expected, actual, metric_name, tolerance=0.1):
    """Compare percentages with tolerance and return (passed, message)"""
    diff = abs(actual - expected)
    if diff < tolerance:
        return True, f"PASS: {metric_name}\n   Expected: {expected}% | Actual: {actual}%"
    else:
        return False, f"❌ FAIL: {metric_name}\n   Expected: {expected}% | Actual: {actual}% | Difference: {diff:.3f}%"

# === MAIN VERIFICATION ===

json_dir = "verification_output_robots"
report_file = "verification_report.txt"

# Load aggregated JSON
with open(os.path.join(json_dir, 'report_all_aggregated.json'), 'r') as f:
    data = json.load(f)

# Calculate percentages for verification
sandboxed = data['sandboxed_iframes']
allow_same_origin_pct = (data['sandbox_allow_same_origin_count'] / sandboxed * 100) if sandboxed > 0 else 0
allow_scripts_pct = (data['sandbox_allow_scripts_count'] / sandboxed * 100) if sandboxed > 0 else 0
both_directives_pct = (data['sandbox_allow_same_origin_and_scripts'] / sandboxed * 100) if sandboxed > 0 else 0

# Calculate login cross-site percentage
sites_login = data['sites_with_login']
login_cross_site_pct = (data['sites_with_cross_site_and_login'] / sites_login * 100) if sites_login > 0 else 0

# Initialize report
report_lines = []
report_lines.append("=" * 80)
report_lines.append("IFRAME ANALYSIS VERIFICATION REPORT")
report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
report_lines.append("=" * 80)
report_lines.append("")

pass_count = 0
fail_count = 0

# Verify overall statistics
report_lines.append("OVERALL STATISTICS (3,522 sites)")
report_lines.append("-" * 80)
report_lines.append(f"{'Metric':<35} {'Expected':<12} {'Actual':<12} {'Status'}")
report_lines.append("-" * 80)

# Total sites
passed, msg = compare_values(EXPECTED['total_sites'], data['total_sites'], "Total sites analyzed")
report_lines.append(msg)
pass_count += 1 if passed else 0
fail_count += 0 if passed else 1

# Total iframe elements
passed, msg = compare_values(EXPECTED['total_iframe_elements'], data['total_iframe_elements'], "Total iframe elements")
report_lines.append(msg)
pass_count += 1 if passed else 0
fail_count += 0 if passed else 1

# Sandboxed iframes
passed, msg = compare_values(EXPECTED['sandboxed_iframes'], data['sandboxed_iframes'], "Sandboxed iframes")
report_lines.append(msg)
pass_count += 1 if passed else 0
fail_count += 0 if passed else 1

# allow-same-origin percentage
passed, msg = compare_percentages(EXPECTED['sandbox_allow_same_origin_pct'], allow_same_origin_pct, "allow-same-origin usage")
report_lines.append(msg)
pass_count += 1 if passed else 0
fail_count += 0 if passed else 1

# allow-scripts percentage
passed, msg = compare_percentages(EXPECTED['sandbox_allow_scripts_pct'], allow_scripts_pct, "allow-scripts usage")
report_lines.append(msg)
pass_count += 1 if passed else 0
fail_count += 0 if passed else 1

# Both directives percentage
passed, msg = compare_percentages(EXPECTED['sandbox_both_directives_pct'], both_directives_pct, "Both directives combined")
report_lines.append(msg)
pass_count += 1 if passed else 0
fail_count += 0 if passed else 1

# Sites with login
passed, msg = compare_values(EXPECTED['sites_with_login'], data['sites_with_login'], "Sites with login forms")
report_lines.append(msg)
pass_count += 1 if passed else 0
fail_count += 0 if passed else 1

# Login + cross-site percentage
passed, msg = compare_percentages(EXPECTED['sites_login_cross_site_pct'], login_cross_site_pct, "Login + cross-site iframes")
report_lines.append(msg)
pass_count += 1 if passed else 0
fail_count += 0 if passed else 1

# Cross-Site Suggestions count
passed, msg = compare_values(EXPECTED['sites_risky_visible_count'], data['sites_with_risky_visible_cross_site_iframes'], "Cross-Site Suggestions precond.")
report_lines.append(msg)
pass_count += 1 if passed else 0
fail_count += 0 if passed else 1

# Credentialless iframes
passed, msg = compare_values(EXPECTED['credentialless_iframes'], data['credentialless_iframes'], "Credentialless iframes")
report_lines.append(msg)
pass_count += 1 if passed else 0
fail_count += 0 if passed else 1

    # Verify per-bucket statistics
report_lines.append("")
report_lines.append("PER-BUCKET VERIFICATION")
report_lines.append("-" * 80)

for bucket_name, bucket_info in BUCKETS.items():
    json_file = bucket_info['file']
    expected_values = bucket_info['expected']
    
    with open(os.path.join(json_dir, json_file), 'r') as f:
        bucket_data = json.load(f)
    
    report_lines.append("")
    report_lines.append(f"Bucket: {bucket_name.upper().replace('_', ' ')}")
    
    # Verify each metric for this bucket
    for metric, expected in expected_values.items():
        actual = bucket_data.get(metric, 0)
        passed, msg = compare_values(expected, actual, metric.replace('_', ' ').title())
        report_lines.append(msg)
        pass_count += 1 if passed else 0
        fail_count += 0 if passed else 1
    
    # Verify sandbox directive percentages for this bucket
    report_lines.append("")
    report_lines.append(f"  Sandbox Directive Usage:")
    
    sandbox_directives_expected = bucket_info.get('sandbox_directives', {})
    sandboxed = bucket_data.get('sandboxed_iframes', 0)
    
    # Map metric names to JSON field names
    directive_mapping = {
        'allow_same_origin': 'sandbox_allow_same_origin_count',
        'allow_scripts': 'sandbox_allow_scripts_count',
        'allow_forms': 'sandbox_allow_forms_count',
        'allow_popups': 'sandbox_allow_popups_count',
        'allow_popups_escape': 'sandbox_allow_popups_escape_count'
    }
    
    for directive_name, expected_pct in sandbox_directives_expected.items():
        json_field = directive_mapping.get(directive_name)
        count = bucket_data.get(json_field, 0)
        actual_pct = (count / sandboxed * 100) if sandboxed > 0 else 0
        
        # Format directive name for display
        display_name = directive_name.replace('_', '-').upper()
        passed, msg = compare_percentages(expected_pct, actual_pct, f"  {display_name}")
        report_lines.append(msg)
        pass_count += 1 if passed else 0
        fail_count += 0 if passed else 1

# Generate summary
total_metrics = pass_count + fail_count
report_lines.append("")
report_lines.append("=" * 80)

if fail_count == 0:
    report_lines.append(f"OVERALL RESULT: PASS: ALL {total_metrics} METRICS VERIFIED SUCCESSFULLY")
    report_lines.append("=" * 80)
else:
    report_lines.append(f"OVERALL RESULT: FAIL {fail_count} OF {total_metrics} METRICS FAILED VERIFICATION")
    report_lines.append("=" * 80)
    report_lines.append("")
    report_lines.append("Please review the failed metrics above.")

# Write report
with open(report_file, 'w') as f:
    f.write('\n'.join(report_lines))

# Print full report to console
print('\n'.join(report_lines))
print("")
print(f"Full report saved to: {report_file}")
print("=" * 80)

# Exit with appropriate code
if fail_count == 0:
    exit(0)
else:
    exit(1)
PYTHON_SCRIPT

# Capture Python exit code
PYTHON_EXIT_CODE=$?

if [ $PYTHON_EXIT_CODE -eq 0 ]; then
    print_success "All metrics verified successfully!"
    exit 0
else
    print_error "Some metrics failed verification. Check $REPORT_FILE for details."
    exit 1
fi
