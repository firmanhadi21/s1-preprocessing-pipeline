#!/usr/bin/env python3
"""
Generate ASF Vertex search URLs for all 31 periods

Creates clickable links for easy manual downloading via ASF web interface
"""

import sys
from urllib.parse import urlencode

sys.path.insert(0, '.')
from period_utils import get_period_dates


# Java Island bounding box (WGS84)
JAVA_AOI = "POLYGON((105 -5, 116 -5, 116 -9, 105 -9, 105 -5))"

# ASF Vertex base URL
ASF_BASE = "https://search.asf.alaska.edu/"


def generate_search_url(period: int, year: int = 2024, orbit: str = "ASCENDING") -> str:
    """Generate ASF search URL for a specific period"""

    # Get period dates
    start_date, end_date = get_period_dates(year, period)

    # ASF Vertex parameters
    params = {
        'platform': 'Sentinel-1A',
        'processingLevel': 'GRD_HD',
        'beamMode': 'IW',
        'flightDirection': orbit,
        'start': start_date,
        'end': end_date,
        'polygon': JAVA_AOI,
        'resultsLoaded': 'true',
        'zoom': '6',
        'center': '110.5,-7'  # Java center
    }

    # Build URL
    url = ASF_BASE + "#/?" + urlencode(params)

    return url


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Generate ASF search URLs for all periods')
    parser.add_argument('--year', type=int, default=2024, help='Year (default: 2024)')
    parser.add_argument('--orbit', default='ASCENDING', choices=['ASCENDING', 'DESCENDING'],
                       help='Orbit direction (default: ASCENDING)')
    parser.add_argument('--output', help='Save URLs to file')
    parser.add_argument('--html', action='store_true', help='Generate clickable HTML file')

    args = parser.parse_args()

    print("="*70)
    print(f"ASF VERTEX SEARCH URLS FOR JAVA ISLAND {args.year}")
    print("="*70)
    print(f"Orbit: {args.orbit}")
    print(f"AOI: Java Island")
    print("="*70)
    print()

    urls = []

    # Generate URLs for all periods
    for period in range(1, 32):
        start_date, end_date = get_period_dates(args.year, period)
        url = generate_search_url(period, args.year, args.orbit)

        urls.append({
            'period': period,
            'start': start_date,
            'end': end_date,
            'url': url
        })

        # Highlight growing season
        if 12 <= period <= 20:
            marker = "⭐ PRIORITY"
        else:
            marker = ""

        print(f"Period {period:2d} ({start_date} to {end_date}) {marker}")
        print(f"  {url}")
        print()

    # Save to file if requested
    if args.output:
        with open(args.output, 'w') as f:
            f.write(f"# ASF Search URLs for Java Island {args.year}\n")
            f.write(f"# Orbit: {args.orbit}\n\n")

            for item in urls:
                marker = " # PRIORITY" if 12 <= item['period'] <= 20 else ""
                f.write(f"# Period {item['period']:2d} ({item['start']} to {item['end']}){marker}\n")
                f.write(f"{item['url']}\n\n")

        print(f"✓ URLs saved to: {args.output}")

    # Generate HTML if requested
    if args.html:
        html_file = args.output.replace('.txt', '.html') if args.output else f'asf_urls_{args.year}.html'

        with open(html_file, 'w') as f:
            f.write(f"""<!DOCTYPE html>
<html>
<head>
    <title>ASF Search URLs - Java Island {args.year}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .period {{ margin: 20px 0; padding: 15px; background: #f5f5f5; border-left: 4px solid #4CAF50; }}
        .priority {{ border-left-color: #ff9800; background: #fff8e1; }}
        .link {{ display: block; margin: 10px 0; color: #1976d2; }}
        .dates {{ color: #666; font-size: 0.9em; }}
    </style>
</head>
<body>
    <h1>ASF Vertex Search URLs - Java Island {args.year}</h1>
    <p><strong>Orbit:</strong> {args.orbit}</p>
    <p><strong>AOI:</strong> Java Island (105°E-116°E, 5°S-9°S)</p>
    <p><strong>Instructions:</strong> Click each link, search, select all results, and download to downloads_N/ folder</p>
    <hr>
""")

            for item in urls:
                priority_class = 'priority' if 12 <= item['period'] <= 20 else ''
                priority_text = ' ⭐ PRIORITY - Growing Season' if 12 <= item['period'] <= 20 else ''

                f.write(f"""
    <div class="period {priority_class}">
        <h2>Period {item['period']}{priority_text}</h2>
        <p class="dates">Dates: {item['start']} to {item['end']}</p>
        <a class="link" href="{item['url']}" target="_blank">
            → Open in ASF Vertex (new tab)
        </a>
        <p><strong>Download to:</strong> workspace/downloads_{item['period']}/</p>
    </div>
""")

            f.write("""
</body>
</html>
""")

        print(f"✓ HTML file created: {html_file}")
        print(f"  Open in browser and click links!")

    print("\n" + "="*70)
    print("INSTRUCTIONS")
    print("="*70)
    print("1. Click a URL (or open the HTML file)")
    print("2. ASF Vertex will open with search results")
    print("3. Select all results")
    print("4. Click 'Queue' then 'Download'")
    print("5. Save to workspace/downloads_N/ folder")
    print("6. Repeat for each period")
    print()
    print("TIP: Start with periods 12-20 (growing season) marked with ⭐")
    print("="*70)


if __name__ == '__main__':
    main()
