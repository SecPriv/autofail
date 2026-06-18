To respect the size limit of files for github, we spltitted the query result into smaller files that can be found in the `bq_result_splitted` directory. To restore the  file again, run the `file_aggregator.py` script.

## Scripts for Evaluators

### Comparing Results

To verify that an evaluator's results match the original data, use the `compare_results.sh` script:

```bash
./compare_results.sh <evaluator_file.json> [--verbose]
```

**Arguments:**
- `<evaluator_file.json>`: Path to the evaluator's bq results JSON file (required)
- `--verbose` or `-v`: Show all differences (optional)

**Output:**
- Prints `TRUE` if the files are identical (after sorting by URL)
- Prints `FALSE` if there are differences
- Exit code 0: Files match
- Exit code 1: Files differ

**Examples:**
```bash
# Simple comparison (boolean output)
./compare_results.sh /path/to/evaluator/results.json

# Show all differences
./compare_results.sh /path/to/evaluator/results.json --verbose
```

**How it works:**
1. Automatically aggregates `bq_result.json` from split parts if not present
2. Sorts both files by the `url` field to handle different ordering
3. Performs strict comparison of all fields
4. Reports boolean result and appropriate exit code

### Verifying Analysis Results

To verify that the analysis results match the statistics reported in the paper, use the `verify_analysis.sh` script:

```bash
./verify_analysis.sh
```

**Output:**
- Prints a detailed comparison table showing expected vs actual values
- Prints `Result: TRUE` if all statistics match the paper
- Prints `Result: FALSE` if any discrepancy is found
- Exit code 0: All values match
- Exit code 1: Discrepancies found

**Example:**
```bash
./verify_analysis.sh
```

**What it verifies:**
1. Automatically aggregates `bq_result.json` from split parts if not present
2. Runs `analysis.py` on the aggregated data
3. Compares the following against paper statistics:
   - Total websites analyzed
   - Embeddable websites count
   - Blocked (non-embeddable) websites count
   - Top 5 most common header combinations (names and counts)
4. Reports detailed comparison table and boolean result with appropriate exit code