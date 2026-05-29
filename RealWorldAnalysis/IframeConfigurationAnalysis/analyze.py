#!/usr/bin/env python3
"""
Iframe Analysis Script

Analyzes iframe data from web crawler output directories.
Provides statistics on:
- Cross-site vs same-site iframes (based on registrable domain)
- Sandbox attribute usage and directive combinations (cross-site only)
- Per-site statistics
- Sites with cross-site iframes and login forms
- Visible & interactable risky cross-site iframes
- Credentialless iframe usage

Outputs chunked statistical reports to a specified target directory (.txt) 
and machine-readable JSON files to an adjacent _robots directory.
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

try:
    import tldextract
except ImportError:
    print("Error: tldextract is required. Install with: pip install -r requirements.txt")
    sys.exit(1)


def get_registrable_domain(url):
    """
    Extract the registrable domain (public suffix + domain) from a URL.
    For about:blank and similar, returns None.
    """
    if not url or url in ('about:blank', 'about:srcdoc'):
        return None
    
    parsed = urlparse(url)
    if not parsed.hostname:
        return None
    
    extracted = tldextract.extract(parsed.hostname)
    if extracted.suffix:
        return f"{extracted.domain}.{extracted.suffix}"
    return extracted.domain


def get_full_hostname(url):
    """Get the full hostname from a URL."""
    if not url or url in ('about:blank', 'about:srcdoc'):
        return None
    parsed = urlparse(url)
    return parsed.hostname


def is_same_site(url1, url2):
    """
    Check if two URLs are same-site (same registrable domain).
    about:blank iframes are considered same-site as their parent.
    """
    if not url1 or not url2:
        return False
    
    if url2 in ('about:blank', 'about:srcdoc'):
        return True
    if url1 in ('about:blank', 'about:srcdoc'):
        return True
    
    domain1 = get_registrable_domain(url1)
    domain2 = get_registrable_domain(url2)
    
    if domain1 is None or domain2 is None:
        return False
    
    return domain1 == domain2


def parse_sandbox_directives(sandbox_value):
    """
    Parse sandbox attribute value into a set of directives.
    Empty string means all restrictions (no directives).
    """
    if sandbox_value is None:
        return None
    
    if not sandbox_value or not sandbox_value.strip():
        return set()
    
    directives = set(sandbox_value.strip().split())
    return directives


def is_iframe_visible_and_interactable(iframe_elem):
    """
    Determine if an iframe is visible and interactable, safely handling raw numbers,
    strings, CSS units, and inline styles. 
    Filters out tracking pixels (<= 5x5) and non-interactable frames.
    """
    if iframe_elem.get('aria-hidden') in ('true', True, '1'):
        return False

    if 'isVisible' in iframe_elem:
        return iframe_elem['isVisible']
    if 'visible' in iframe_elem:
        return iframe_elem['visible']

    style = iframe_elem.get('style', '').lower()
    if style:
        if 'display: none' in style or 'display:none' in style:
            return False
        if 'visibility: hidden' in style or 'visibility:hidden' in style:
            return False
        if 'opacity: 0' in style or 'opacity:0' in style:
            return False
        if 'pointer-events: none' in style or 'pointer-events:none' in style:
            return False
        if re.search(r'(top|left):\s*-[1-9]\d{3,}px', style):
            return False

    def parse_dim(val):
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            match = re.search(r'^([\d.]+)', val.strip())
            if match:
                return float(match.group(1))
        return None

    width = parse_dim(iframe_elem.get('width'))
    height = parse_dim(iframe_elem.get('height'))
    
    # Fallback to checking inline style if HTML attributes are missing
    if width is None and style:
        match = re.search(r'width:\s*([\d.]+)px', style)
        if match: width = float(match.group(1))
        
    if height is None and style:
        match = re.search(r'height:\s*([\d.]+)px', style)
        if match: height = float(match.group(1))

    # Threshold: > 5x5 pixels required to be considered visible and interactable
    if width is not None and height is not None:
        return width > 5 and height > 5
        
    if (width is not None and width <= 5) or (height is not None and height <= 5):
        return False

    return True


def has_password_input(html_content):
    """
    Check if HTML content contains a password input field.
    Looks for <input type="password"> patterns.
    """
    if not html_content:
        return False
    
    password_pattern = r'<input[^>]*type\s*=\s*["\']password["\'][^>]*>'
    if re.search(password_pattern, html_content, re.IGNORECASE):
        return True
    
    password_pattern_no_quotes = r'<input[^>]*type\s*=\s*password[^>]*>'
    if re.search(password_pattern_no_quotes, html_content, re.IGNORECASE):
        return True
    
    return False


def check_site_has_login(site_dir):
    """
    Check if any frame in the site has a password input field.
    Returns True if a login form is found.
    """
    frames_dir = os.path.join(site_dir, 'frames')
    
    if not os.path.exists(frames_dir):
        return False
    
    for frame_file in os.listdir(frames_dir):
        if frame_file.endswith('.html'):
            frame_path = os.path.join(frames_dir, frame_file)
            try:
                with open(frame_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if has_password_input(content):
                        return True
            except Exception:
                continue
    
    return False


def collect_site_data(site_dir):
    """
    Collect all iframe data from a single site directory.
    """
    iframes_file = os.path.join(site_dir, 'iframes.json')
    headers_file = os.path.join(site_dir, 'headers.json')
    
    if not os.path.exists(iframes_file):
        return None
    
    main_url = None
    if os.path.exists(headers_file):
        with open(headers_file, 'r', encoding='utf-8') as f:
            headers_data = json.load(f)
            main_url = headers_data.get('finalUrl') or headers_data.get('url')
    
    with open(iframes_file, 'r', encoding='utf-8') as f:
        frames_data = json.load(f)
    
    site_info = {
        'site_dir': site_dir,
        'site_name': os.path.basename(site_dir),
        'main_url': main_url,
        'frames': [],
        'iframe_elements': [],
        'has_login': check_site_has_login(site_dir)
    }
    
    frame_lookup = {}
    for frame in frames_data:
        frame_lookup[frame['frameId']] = frame
    
    for frame in frames_data:
        frame_info = {
            'frameId': frame.get('frameId'),
            'url': frame.get('url'),
            'isMainFrame': frame.get('isMainFrame', False),
            'registrableDomain': get_registrable_domain(frame.get('url')),
            'hostname': get_full_hostname(frame.get('url')),
        }
        
        if frame.get('url') in ('about:blank', 'about:srcdoc'):
            frame_info['isSameSite'] = True
        else:
            frame_info['isSameSite'] = main_url and is_same_site(main_url, frame.get('url'))
        
        site_info['frames'].append(frame_info)
    
    for frame in frames_data:
        for iframe_elem in frame.get('iframes', []):
            child_frame_id = iframe_elem.get('childFrameId')
            sandbox = iframe_elem.get('sandbox')
            
            cred_val = iframe_elem.get('credentialless')
            has_credentialless = cred_val is not None and cred_val is not False
            
            iframe_info = {
                'parentFrameId': frame.get('frameId'),
                'childFrameId': child_frame_id,
                'src': iframe_elem.get('src'),
                'hasSandbox': sandbox is not None,
                'sandboxDirectives': parse_sandbox_directives(sandbox),
                'sandboxRaw': sandbox,
                'hasCredentialless': has_credentialless,
                'isVisible': is_iframe_visible_and_interactable(iframe_elem)
            }
            
            child_frame = frame_lookup.get(child_frame_id) if child_frame_id else None
            if child_frame:
                iframe_info['childUrl'] = child_frame.get('url')
                if child_frame.get('url') in ('about:blank', 'about:srcdoc'):
                    iframe_info['isCrossSite'] = False
                else:
                    parent_frame_url = frame.get('url')
                    iframe_info['isCrossSite'] = not is_same_site(parent_frame_url, child_frame.get('url'))
            else:
                iframe_info['childUrl'] = None
                iframe_info['isCrossSite'] = False
            
            site_info['iframe_elements'].append(iframe_info)
    
    return site_info


def get_rank(name):
    """Extract numeric rank from a site directory or name (e.g., '1_google.com' -> 1)"""
    match = re.match(r'^(\d+)', name)
    return int(match.group(1)) if match else float('inf')


def analyze_directory(input_dir):
    """
    Parses all sites in the input directory and returns a sorted list of site data.
    """
    input_path = Path(input_dir)
    
    if not input_path.exists():
        print(f"Error: Directory '{input_dir}' does not exist")
        sys.exit(1)
    
    all_sites = []
    for site_dir in sorted(input_path.iterdir(), key=lambda p: (get_rank(p.name), p.name)):
        if site_dir.is_dir():
            site_data = collect_site_data(str(site_dir))
            if site_data:
                all_sites.append(site_data)
    
    if not all_sites:
        print(f"No valid site data found in '{input_dir}'")
        sys.exit(1)
        
    return all_sites


def calculate_stats(sites):
    """
    Takes a list of site data dictionaries and calculates statistics.
    """
    stats = {
        'total_sites': len(sites),
        'total_frames': 0,
        'total_iframe_elements': 0,
        'cross_site_iframes': 0,
        'same_site_iframes': 0,
        'sandboxed_iframes': 0,
        'non_sandboxed_iframes': 0,
        'credentialless_iframes': 0,
        'sandbox_specific_condition_frames': 0,
        'sandbox_allow_same_origin_and_scripts': 0,
        
        'sandbox_cross_site': 0,
        'sandbox_same_site': 0,
        
        'non_sandbox_cross_site': 0,
        'non_sandbox_same_site': 0,
        
        'sandbox_directives_count': Counter(),
        'sandbox_combinations': Counter(),
        
        'sites_with_iframes': 0,
        'sites_with_cross_site_iframes': 0,
        'sites_with_sandboxed_iframes': 0,
        'sites_with_login': 0,
        
        'sites_with_cross_site_and_login': 0,
        'sites_with_risky_cross_site_and_login': 0,
        'sites_with_risky_visible_cross_site_iframes': 0
    }
    
    for site in sites:
        site_has_iframes = len(site['iframe_elements']) > 0
        site_has_cross_site = False
        site_has_sandbox = False
        site_has_login = site.get('has_login', False)
        
        site_has_risky_cross_site = False
        site_has_risky_visible_cross_site = False
        
        if site_has_login:
            stats['sites_with_login'] += 1
        
        stats['total_frames'] += len(site['frames'])
        
        for iframe in site['iframe_elements']:
            stats['total_iframe_elements'] += 1
            
            is_cross_site = iframe.get('isCrossSite', False)
            has_sandbox = iframe.get('hasSandbox', False)
            has_credentialless = iframe.get('hasCredentialless', False)
            is_visible = iframe.get('isVisible', False)
            sandbox_directives = iframe.get('sandboxDirectives')
            
            if has_credentialless:
                stats['credentialless_iframes'] += 1
            
            if is_cross_site:
                stats['cross_site_iframes'] += 1
                site_has_cross_site = True
                
                # Check for login condition risk: unsandboxed OR sandboxed with allow-scripts
                if not has_sandbox:
                    site_has_risky_cross_site = True
                elif sandbox_directives is not None and 'allow-scripts' in sandbox_directives:
                    site_has_risky_cross_site = True
                
                # Check for Visible & Interactable Risk Condition
                if is_visible:
                    if not has_sandbox:
                        site_has_risky_visible_cross_site = True
                    elif sandbox_directives is not None and ('allow-scripts' in sandbox_directives or 'allow-forms' in sandbox_directives):
                        site_has_risky_visible_cross_site = True

            else:
                stats['same_site_iframes'] += 1
            
            if has_sandbox:
                stats['sandboxed_iframes'] += 1
                site_has_sandbox = True
                
                if sandbox_directives is not None:
                    # Check for the specific condition: CROSS-SITE AND (allow-scripts OR allow-forms) AND NOT allow-same-origin
                    has_scripts_or_forms = 'allow-scripts' in sandbox_directives or 'allow-forms' in sandbox_directives
                    no_same_origin = 'allow-same-origin' not in sandbox_directives
                    
                    if has_scripts_or_forms and no_same_origin and is_cross_site:
                        stats['sandbox_specific_condition_frames'] += 1
                        
                    # Check for sandboxed iframes with BOTH allow-same-origin and allow-scripts
                    if 'allow-same-origin' in sandbox_directives and 'allow-scripts' in sandbox_directives:
                        stats['sandbox_allow_same_origin_and_scripts'] += 1
                
                if is_cross_site:
                    stats['sandbox_cross_site'] += 1
                    
                    # Track sandbox directives ONLY for cross-site iframes
                    if sandbox_directives is not None:
                        if len(sandbox_directives) == 0:
                            stats['sandbox_directives_count']['(empty)'] += 1
                            stats['sandbox_combinations']['(empty)'] += 1
                        else:
                            for directive in sorted(sandbox_directives):
                                stats['sandbox_directives_count'][directive] += 1
                            combination = ' + '.join(sorted(sandbox_directives))
                            stats['sandbox_combinations'][combination] += 1
                else:
                    stats['sandbox_same_site'] += 1
            else:
                stats['non_sandboxed_iframes'] += 1
                
                if is_cross_site:
                    stats['non_sandbox_cross_site'] += 1
                else:
                    stats['non_sandbox_same_site'] += 1
        
        if site_has_iframes:
            stats['sites_with_iframes'] += 1
        if site_has_cross_site:
            stats['sites_with_cross_site_iframes'] += 1
        if site_has_sandbox:
            stats['sites_with_sandboxed_iframes'] += 1
        
        if site_has_cross_site and site_has_login:
            stats['sites_with_cross_site_and_login'] += 1
            
        if site_has_risky_cross_site and site_has_login:
            stats['sites_with_risky_cross_site_and_login'] += 1
            
        if site_has_risky_visible_cross_site:
            stats['sites_with_risky_visible_cross_site_iframes'] += 1
            
    return stats


def format_percentage(count, total):
    """Format a count as a percentage of total."""
    if total == 0:
        return "0.0%"
    return f"{(count / total) * 100:.1f}%"


def write_json_report(stats, output_path):
    """Write raw statistics to a machine-readable JSON file."""
    # Convert Counters to standard dicts so json.dump doesn't crash
    json_ready_stats = stats.copy()
    json_ready_stats['sandbox_directives_count'] = dict(stats['sandbox_directives_count'])
    json_ready_stats['sandbox_combinations'] = dict(stats['sandbox_combinations'])
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(json_ready_stats, f, indent=4)


def write_report(stats, output_path, title):
    """Write formatted statistics to a specified file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write(f"IFRAME ANALYSIS REPORT: {title}\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Total sites analyzed: {stats['total_sites']}\n")
        f.write(f"Total frames (all types): {stats['total_frames']}\n")
        f.write(f"Total iframe elements: {stats['total_iframe_elements']}\n\n")
        
        total_iframes = stats['total_iframe_elements']
        total_sites = stats['total_sites']
        
        f.write("-" * 80 + "\n")
        f.write("1. CROSS-SITE vs SAME-SITE IFRAMES\n")
        f.write("-" * 80 + "\n")
        f.write(f"Total iframe elements: {total_iframes}\n\n")
        f.write(f"  Cross-site iframes: {stats['cross_site_iframes']:>6}  ({format_percentage(stats['cross_site_iframes'], total_iframes)})\n")
        f.write(f"  Same-site iframes:  {stats['same_site_iframes']:>6}  ({format_percentage(stats['same_site_iframes'], total_iframes)})\n\n")
        
        f.write("-" * 80 + "\n")
        f.write("2. SANDBOX ATTRIBUTE USAGE\n")
        f.write("-" * 80 + "\n")
        f.write(f"Total iframe elements: {total_iframes}\n\n")
        f.write(f"  With sandbox:    {stats['sandboxed_iframes']:>6}  ({format_percentage(stats['sandboxed_iframes'], total_iframes)})\n")
        f.write(f"  Without sandbox: {stats['non_sandboxed_iframes']:>6}  ({format_percentage(stats['non_sandboxed_iframes'], total_iframes)})\n\n")
        
        f.write("  Sandbox breakdown by cross-site:\n")
        f.write(f"    Sandboxed iframes:\n")
        total_sandbox = stats['sandboxed_iframes']
        f.write(f"      Cross-site:    {stats['sandbox_cross_site']:>6}  ({format_percentage(stats['sandbox_cross_site'], total_sandbox) if total_sandbox > 0 else 'N/A'})\n")
        f.write(f"      Same-site:     {stats['sandbox_same_site']:>6}  ({format_percentage(stats['sandbox_same_site'], total_sandbox) if total_sandbox > 0 else 'N/A'})\n")
        f.write(f"    Non-sandboxed iframes:\n")
        total_non_sandbox = stats['non_sandboxed_iframes']
        f.write(f"      Cross-site:    {stats['non_sandbox_cross_site']:>6}  ({format_percentage(stats['non_sandbox_cross_site'], total_non_sandbox) if total_non_sandbox > 0 else 'N/A'})\n")
        f.write(f"      Same-site:     {stats['non_sandbox_same_site']:>6}  ({format_percentage(stats['non_sandbox_same_site'], total_non_sandbox) if total_non_sandbox > 0 else 'N/A'})\n\n")
        
        f.write("-" * 80 + "\n")
        f.write("3. SANDBOX DIRECTIVES (CROSS-SITE IFRAMES ONLY)\n")
        f.write("-" * 80 + "\n")
        total_cross_site_sandbox = stats['sandbox_cross_site']
        f.write(f"Total sandboxed cross-site iframes: {total_cross_site_sandbox}\n\n")
        
        f.write("  Specific conditions (Out of all sandboxed):\n")
        f.write(f"    Cross-site + Sandboxed + (allow-scripts OR allow-forms) + NO allow-same-origin: {stats['sandbox_specific_condition_frames']:>6}  ({format_percentage(stats['sandbox_specific_condition_frames'], total_sandbox)})\n")
        f.write(f"    Sandboxed + allow-scripts + allow-same-origin: {stats['sandbox_allow_same_origin_and_scripts']:>6}  ({format_percentage(stats['sandbox_allow_same_origin_and_scripts'], total_sandbox)})\n\n")
        
        f.write("  Individual directive usage (Cross-site):\n")
        for directive, count in stats['sandbox_directives_count'].most_common():
            f.write(f"    {directive:<50} {count:>6}  ({format_percentage(count, total_cross_site_sandbox)})\n")
        f.write("\n")
        
        f.write("  Directive combinations (top 20, Cross-site):\n")
        for i, (combination, count) in enumerate(stats['sandbox_combinations'].most_common(20)):
            f.write(f"    {i+1:>2}. {combination:<60} {count:>6}  ({format_percentage(count, total_cross_site_sandbox)})\n")
        f.write("\n")
        
        f.write("-" * 80 + "\n")
        f.write("4. PER-SITE STATISTICS\n")
        f.write("-" * 80 + "\n")
        f.write(f"Total sites: {total_sites}\n\n")
        f.write(f"  Sites with any iframes:           {stats['sites_with_iframes']:>6}  ({format_percentage(stats['sites_with_iframes'], total_sites)})\n")
        f.write(f"  Sites with cross-site iframes:    {stats['sites_with_cross_site_iframes']:>6}  ({format_percentage(stats['sites_with_cross_site_iframes'], total_sites)})\n")
        f.write(f"  Sites with sandboxed iframes:     {stats['sites_with_sandboxed_iframes']:>6}  ({format_percentage(stats['sites_with_sandboxed_iframes'], total_sites)})\n")
        f.write(f"  Sites with login forms:           {stats['sites_with_login']:>6}  ({format_percentage(stats['sites_with_login'], total_sites)})\n\n")
        
        f.write("-" * 80 + "\n")
        f.write("5. SITES WITH CROSS-SITE IFRAMES AND LOGIN FORMS\n")
        f.write("-" * 80 + "\n")
        f.write(f"Total sites: {total_sites}\n")
        f.write(f"Total sites with login forms: {stats['sites_with_login']}\n\n")
        
        f.write(f"  Sites with BOTH cross-site iframes AND login forms:\n")
        f.write(f"    Count: {stats['sites_with_cross_site_and_login']:>6}\n")
        f.write(f"    % of total analyzed sites:   {format_percentage(stats['sites_with_cross_site_and_login'], total_sites)}\n")
        f.write(f"    % of sites with login forms: {format_percentage(stats['sites_with_cross_site_and_login'], stats['sites_with_login'])}\n\n")
        
        f.write(f"  Sites with BOTH cross-site iframes AND login forms where the cross-site\n")
        f.write(f"  iframe is either NOT SANDBOXED or allows scripts (allow-scripts):\n")
        f.write(f"    Count: {stats['sites_with_risky_cross_site_and_login']:>6}\n")
        f.write(f"    % of total analyzed sites:   {format_percentage(stats['sites_with_risky_cross_site_and_login'], total_sites)}\n")
        f.write(f"    % of sites with login forms: {format_percentage(stats['sites_with_risky_cross_site_and_login'], stats['sites_with_login'])}\n\n")
        
        f.write("-" * 80 + "\n")
        f.write("6. VISIBLE, INTERACTABLE & RISKY CROSS-SITE IFRAMES (PER SITE)\n")
        f.write("-" * 80 + "\n")
        f.write(f"Total sites: {total_sites}\n\n")
        f.write("  Sites containing at least one iframe that is:\n")
        f.write("  - Cross-site\n")
        f.write("  - Visible & interactable\n")
        f.write("  - Non-sandboxed OR sandboxed with allow-scripts/allow-forms\n\n")
        f.write(f"    Count: {stats['sites_with_risky_visible_cross_site_iframes']:>6}\n")
        f.write(f"    % of total analyzed sites: {format_percentage(stats['sites_with_risky_visible_cross_site_iframes'], total_sites)}\n\n")

        f.write("-" * 80 + "\n")
        f.write("7. CREDENTIALLESS IFRAMES\n")
        f.write("-" * 80 + "\n")
        f.write(f"Total iframe elements: {total_iframes}\n\n")
        f.write(f"  Iframes using credentialless: {stats['credentialless_iframes']:>6}  ({format_percentage(stats['credentialless_iframes'], total_iframes)})\n\n")
        
        f.write("=" * 80 + "\n")
        f.write("END OF REPORT\n")
        f.write("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description='Analyze iframe data from web crawler output and generate chunked reports.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 analyze.py data/out_tranco_PW6XJ ./reports_folder
  python3 analyze.py /path/to/crawler/output /path/to/save/reports
        """
    )
    parser.add_argument(
        'input_dir',
        help='Directory containing crawler output (with site subdirectories)'
    )
    parser.add_argument(
        'output_dir',
        help='Directory where the chunked text reports will be saved'
    )
    
    args = parser.parse_args()
    
    print(f"Reading and analyzing sites from: {args.input_dir}...")
    all_sites = analyze_directory(args.input_dir)
    print(f"Successfully loaded {len(all_sites)} sites.")
    
    # Ensure the standard output directory exists
    base_output_dir = os.path.normpath(args.output_dir)
    os.makedirs(base_output_dir, exist_ok=True)
    
    # Ensure the parallel 'robots' directory exists for JSON output
    robots_dir = f"{base_output_dir}_robots"
    os.makedirs(robots_dir, exist_ok=True)
    
    # Define the chunk mapping
    chunks = [
        ("AGGREGATED ALL SITES", all_sites, "report_all_aggregated.txt"),
        ("FIRST 1000 (1-1000)", all_sites[0:1000], "report_01_first_1000.txt"),
        ("SECOND 1000 (1001-2000)", all_sites[1000:2000], "report_02_second_1000.txt"),
        ("THIRD 1000 (2001-3000)", all_sites[2000:3000], "report_03_third_1000.txt"),
        ("FOURTH 1000 (3001-4000)", all_sites[3000:4000], "report_04_fourth_1000.txt"),
    ]
    
    # Process and save each chunk
    for title, site_chunk, filename in chunks:
        if not site_chunk:
            print(f"Skipping '{title}' (no sites in this range).")
            continue
            
        print(f"Processing '{title}' ({len(site_chunk)} sites)...")
        stats = calculate_stats(site_chunk)
        
        # Save standard text report
        txt_output_path = os.path.join(base_output_dir, filename)
        write_report(stats, txt_output_path, title)
        print(f" -> Saved text report to: {txt_output_path}")
        
        # Save machine-readable JSON report
        json_filename = filename.replace('.txt', '.json')
        json_output_path = os.path.join(robots_dir, json_filename)
        write_json_report(stats, json_output_path)
        print(f" -> Saved JSON report to: {json_output_path}")

    print("\nAll reports generated successfully!")


if __name__ == '__main__':
    main() 