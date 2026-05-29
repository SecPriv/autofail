#!/usr/bin/env python3
"""
Generate bucketed Tranco list for crawling.

Creates a list with:
- First n websites (ranks 1 to n)
- n websites sampled from ranks n+1 to 10,000
- n websites sampled from ranks 10,001 to 100,000
- n websites sampled from ranks 100,001 to 1,000,000
"""

import argparse
import csv
import random
import sys
from pathlib import Path


def load_tranco_list(filepath):
    """Load Tranco CSV file and return list of (rank, url) tuples."""
    sites = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 2:
                rank = int(row[0])
                url = row[1]
                sites.append((rank, url))
    return sites


def generate_buckets(input_file, n, output_file=None):
    """
    Generate bucketed list from Tranco CSV.
    
    Args:
        input_file: Path to Tranco CSV file
        n: Number of websites per bucket
        output_file: Optional path to write output CSV
    """
    sites = load_tranco_list(input_file)
    
    # Sort by rank to ensure proper ordering
    sites.sort(key=lambda x: x[0])
    
    # Create rank lookup for faster access
    sites_by_rank = {rank: url for rank, url in sites}
    
    # Define buckets
    bucket_ranges = [
        (1, n, "Top n (1-{n})"),
        (n + 1, 10000, "Top 10k ({start}-{end})"),
        (10001, 100000, "Top 100k ({start}-{end})"),
        (100001, 1000000, "Top 1M ({start}-{end})"),
    ]
    
    result = []
    
    for start, end, label in bucket_ranges:
        label = label.format(start=start, end=end, n=n)
        
        # Get available sites in this range
        available_sites = []
        for rank in range(start, min(end, max(sites_by_rank.keys()) + 1) + 1):
            if rank in sites_by_rank:
                available_sites.append((rank, sites_by_rank[rank]))
        
        if not available_sites:
            print(f"Warning: No sites available in range {start}-{end}")
            continue
        
        # For the first bucket, take all (should be exactly n)
        if start == 1:
            selected = available_sites[:n]
            print(f"Bucket 1 - {label}: Taking first {len(selected)} sites")
        else:
            # Sample n sites randomly from available
            if len(available_sites) < n:
                print(f"Warning: Only {len(available_sites)} sites available in range {start}-{end}, taking all")
                selected = available_sites
            else:
                selected = random.sample(available_sites, n)
                print(f"Bucket - {label}: Sampled {len(selected)} sites from {len(available_sites)} available")
        
        result.extend(selected)
    
    # Sort result by rank for consistent output
    result.sort(key=lambda x: x[0])
    
    # Write output if specified
    if output_file:
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            for rank, url in result:
                writer.writerow([rank, url])
        print(f"\nWrote {len(result)} sites to {output_file}")
    else:
        # Print to stdout
        print(f"\nGenerated {len(result)} sites:")
        for rank, url in result:
            print(f"{rank},{url}")
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description='Generate bucketed Tranco list for crawling',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 generate_buckets_list.py data/tranco_VNG7N.csv 100
  python3 generate_buckets_list.py data/tranco_VNG7N.csv 500 -o output.csv
        """
    )
    parser.add_argument(
        'input_file',
        help='Path to Tranco CSV file (rank,url format)'
    )
    parser.add_argument(
        'n',
        type=int,
        help='Number of websites per bucket'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output CSV file (default: print to stdout)'
    )
    
    args = parser.parse_args()
    
    if not Path(args.input_file).exists():
        print(f"Error: File '{args.input_file}' not found")
        sys.exit(1)
    
    # Set random seed for reproducibility
    random.seed(42)
    
    generate_buckets(args.input_file, args.n, args.output)


if __name__ == '__main__':
    main()
