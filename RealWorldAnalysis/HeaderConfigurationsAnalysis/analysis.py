import json
import re
import sys
from collections import Counter

# File path configuration
INPUT_FILE = sys.argv[1]

def csp_frame_ancestors_allows(csp_headers):
    """
    Parse frame-ancestors directives from all CSP headers and determine if the page allows being framed by external sites.
    Returns a tuple: (has_frame_ancestors_directive, allows_external_framing)
    """
    directives = []
    for header in csp_headers:
        # Split directives by semicolon
        parts = [p.strip() for p in header.lower().split(';')]
        for part in parts:
            if part.startswith('frame-ancestors'):
                directives.append(part)
                break  # As per spec, only consider the first frame-ancestors directive per header
                
    if not directives:
        return False, True 
    
    # Apply the most restrictive directive logic: if any directive disallows framing, then it's disallowed overall.
    allowed = False
    for dir_text in directives:
        # Check for explicitly allowed generic sources. Empty means 'none'.
        dir_text_el = [token.strip() for token in dir_text.split()]
        if any('http:' == token or 'https:' == token or '*' == token for token in dir_text_el):
            allowed = True
        else:
            # If the directive doesn't contain any allowed sources, it effectively disallows framing.
            return True, False 
            
    return True, allowed

def analyze_row(row):
    """
    Evaluates whether a site is embeddable.
    Returns the embeddable boolean, and the formatted strings for stats tracking.
    """
    xfo_headers_pre = [h.strip().upper() for h in row.get("xfo_headers", []) if h.strip()]
    xfo_headers = []
    for el in xfo_headers_pre:
        xfo_headers.extend([h.strip() for h in el.split(',')])
    has_xfo = len(xfo_headers) > 0
    xfo_allows = (not has_xfo) or (not any('DENY' == h or 'SAMEORIGIN' == h for h in xfo_headers))

    csp_headers = [h.strip() for h in row.get("csp_headers", []) if h.strip()]
    
    has_csp_fa, csp_fa_allows = csp_frame_ancestors_allows(csp_headers)
    
    if has_csp_fa:
        # If CSP frame-ancestors is present, it completely overrides XFO.
        embeddable = csp_fa_allows
    else:
        # If no CSP frame-ancestors is present, fallback to XFO logic.
        embeddable = xfo_allows

    # -------------------------------------------------------------
    # Create normalized representation for global stats
    # -------------------------------------------------------------
    xfo_val = " | ".join(xfo_headers_pre) if xfo_headers_pre else "No XFO"
    
    csp_fa_vals = []
    for header in csp_headers:
        match = re.search(r'frame-ancestors\s+([^;]+)', header, re.IGNORECASE)
        if match:
            csp_fa_vals.append(match.group(1).strip())
            
    csp_fa_val = " | ".join(csp_fa_vals) if csp_fa_vals else "No frame-ancestors"
    
    combined_val = f"XFO: {xfo_val} | CSP FA: {csp_fa_val}"
    
    return embeddable, xfo_val, csp_fa_val, combined_val

def print_top_10(counter_obj, title_str, total_processed, none_key):
    """
    Helper function to print the stats neatly, including percentage 
    relative to header adoption.
    """
    # Total adopted is everything EXCEPT the 'none' key
    total_adopted = total_processed - counter_obj.get(none_key, 0)
    
    print("\n" + "="*100)
    print(title_str)
    print(f"Total Processed: {total_processed:,} | Total Using Header(s): {total_adopted:,}")
    print("="*100)
    
    for i, (comb, count) in enumerate(counter_obj.most_common(10), 1):
        global_pct = (count / total_processed) * 100 if total_processed > 0 else 0
        
        # Format the display line
        if comb == none_key:
            # If this is the "No header" value, adoption percentage doesn't apply
            adoption_str = "N/A"
        else:
            adoption_pct = (count / total_adopted) * 100 if total_adopted > 0 else 0
            adoption_str = f"{adoption_pct:>5.1f}% of adoption"
            
        print(f"{i:2d}. {comb:<60} -> {count:<7,d} ({global_pct:>5.1f}% overall) | [{adoption_str}]")

def main():
    buckets = {
        "Top 1K":   {"max_rank": 1000, "embeddable": 0, "blocked": 0},
        "Top 10K":  {"max_rank": 10000, "embeddable": 0, "blocked": 0},
        "Top 100K": {"max_rank": 100000, "embeddable": 0, "blocked": 0},
        "Top 1M":   {"max_rank": 1000000, "embeddable": 0, "blocked": 0}
    }
    
    xfo_counts = Counter()
    csp_fa_counts = Counter()
    combined_counts = Counter()
    
    total_processed = 0

    print(f"Reading and analyzing '{INPUT_FILE}'...")
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                rank = int(row.get("rank", 0))
                
                is_embeddable, xfo_val, csp_fa_val, combined_val = analyze_row(row)
                
                xfo_counts[xfo_val] += 1
                csp_fa_counts[csp_fa_val] += 1
                combined_counts[combined_val] += 1
                
                total_processed += 1
                
                for bucket_name, config in buckets.items():
                    if rank <= config["max_rank"]:
                        if is_embeddable:
                            config["embeddable"] += 1
                        else:
                            config["blocked"] += 1
                            
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Skipping malformed line {line_num}: {e}")

    # -------------------------------------------------------------
    # Display Stats per Popularity Bucket
    # -------------------------------------------------------------
    print("\n" + "="*85)
    print("STATS PER POPULARITY BUCKET (CUMULATIVE)")
    print("="*85)
    print(f"{'Bucket':<12} | {'Embeddable':<22} | {'Blocked':<22} | {'Total':<12}")
    print("-" * 85)
    for b_name, data in buckets.items():
        total_b = data["embeddable"] + data["blocked"]
        
        # Calculate percentages safely
        embed_pct = (data["embeddable"] / total_b * 100) if total_b > 0 else 0.0
        block_pct = (data["blocked"] / total_b * 100) if total_b > 0 else 0.0
        
        # Format strings to display count + percentage
        embed_str = f"{data['embeddable']:,} ({embed_pct:.1f}%)"
        block_str = f"{data['blocked']:,} ({block_pct:.1f}%)"
        
        print(f"{b_name:<12} | {embed_str:<22} | {block_str:<22} | {total_b:<12,}")

    # -------------------------------------------------------------
    # Display Global Header Breakdowns
    # -------------------------------------------------------------
    print_top_10(
        xfo_counts, 
        "TOP 10 MOST COMMON X-FRAME-OPTIONS VALUES", 
        total_processed, 
        "No XFO"
    )
    
    print_top_10(
        csp_fa_counts, 
        "TOP 10 MOST COMMON CSP FRAME-ANCESTORS VALUES", 
        total_processed, 
        "No frame-ancestors"
    )
    
    print_top_10(
        combined_counts, 
        "TOP 10 MOST COMMON COMBINATIONS", 
        total_processed, 
        "XFO: No XFO | CSP FA: No frame-ancestors"
    )

if __name__ == "__main__":
    main()
