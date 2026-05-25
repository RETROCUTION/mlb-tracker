#!/usr/bin/env python3
"""
download_logos.py
Downloads official MLB team logos and converts them to 1-bit PNG
suitable for the Waveshare e-ink display.

Run once from the dodgers-tracker directory:
    python3 download_logos.py

Requires: requests, Pillow
"""

import os
import sys
import requests
from PIL import Image

LOGO_DIR  = "assets/logos"
LOGO_SIZE = 64  # pixels — resize all logos to this square size

# MLB team logo URLs from MLB's CDN
# Format: team_abbr -> (team_id, logo_url)
TEAMS = [
    ("LAD", 119, "https://www.mlbstatic.com/team-logos/119.svg"),
    ("LAA", 108, "https://www.mlbstatic.com/team-logos/108.svg"),
    ("ARI", 109, "https://www.mlbstatic.com/team-logos/109.svg"),
    ("BAL", 110, "https://www.mlbstatic.com/team-logos/110.svg"),
    ("BOS", 111, "https://www.mlbstatic.com/team-logos/111.svg"),
    ("CHC", 112, "https://www.mlbstatic.com/team-logos/112.svg"),
    ("CIN", 113, "https://www.mlbstatic.com/team-logos/113.svg"),
    ("CLE", 114, "https://www.mlbstatic.com/team-logos/114.svg"),
    ("COL", 115, "https://www.mlbstatic.com/team-logos/115.svg"),
    ("DET", 116, "https://www.mlbstatic.com/team-logos/116.svg"),
    ("HOU", 117, "https://www.mlbstatic.com/team-logos/117.svg"),
    ("KC",  118, "https://www.mlbstatic.com/team-logos/118.svg"),
    ("WSH", 120, "https://www.mlbstatic.com/team-logos/120.svg"),
    ("NYM", 121, "https://www.mlbstatic.com/team-logos/121.svg"),
    ("ATH", 133, "https://www.mlbstatic.com/team-logos/133.svg"),
    ("PIT", 134, "https://www.mlbstatic.com/team-logos/134.svg"),
    ("SD",  135, "https://www.mlbstatic.com/team-logos/135.svg"),
    ("SEA", 136, "https://www.mlbstatic.com/team-logos/136.svg"),
    ("SF",  137, "https://www.mlbstatic.com/team-logos/137.svg"),
    ("STL", 138, "https://www.mlbstatic.com/team-logos/138.svg"),
    ("TB",  139, "https://www.mlbstatic.com/team-logos/139.svg"),
    ("TEX", 140, "https://www.mlbstatic.com/team-logos/140.svg"),
    ("TOR", 141, "https://www.mlbstatic.com/team-logos/141.svg"),
    ("MIN", 142, "https://www.mlbstatic.com/team-logos/142.svg"),
    ("PHI", 143, "https://www.mlbstatic.com/team-logos/143.svg"),
    ("ATL", 144, "https://www.mlbstatic.com/team-logos/144.svg"),
    ("CWS", 145, "https://www.mlbstatic.com/team-logos/145.svg"),
    ("MIA", 146, "https://www.mlbstatic.com/team-logos/146.svg"),
    ("NYY", 147, "https://www.mlbstatic.com/team-logos/147.svg"),
    ("MIL", 158, "https://www.mlbstatic.com/team-logos/158.svg"),
]

# Fallback PNG URLs if SVG isn't renderable directly
PNG_FALLBACK = "https://www.mlbstatic.com/team-logos/team-cap-on-light/{team_id}.svg"


def svg_to_1bit_png(svg_data, out_path, size=LOGO_SIZE):
    """
    Convert SVG bytes to a 1-bit PNG using cairosvg if available,
    otherwise fall back to a placeholder.
    """
    try:
        import cairosvg
        png_data = cairosvg.svg2png(
            bytestring=svg_data,
            output_width=size,
            output_height=size,
            background_color="white"
        )
        from io import BytesIO
        img = Image.open(BytesIO(png_data)).convert("RGBA")
    except ImportError:
        print("  ⚠  cairosvg not installed — trying PNG fallback")
        return False
    except Exception as e:
        print(f"  ⚠  SVG render failed: {e} — trying PNG fallback")
        return False

    return _convert_and_save(img, out_path, size)


def png_to_1bit_png(png_data, out_path, size=LOGO_SIZE):
    """Convert PNG bytes to a 1-bit PNG."""
    from io import BytesIO
    try:
        img = Image.open(BytesIO(png_data)).convert("RGBA")
        return _convert_and_save(img, out_path, size)
    except Exception as e:
        print(f"  ⚠  PNG convert failed: {e}")
        return False


def _convert_and_save(img, out_path, size):
    """Resize, dither to 1-bit, and save."""
    img = img.resize((size, size), Image.LANCZOS)
    r, g, b, a = img.split()
    gray     = img.convert("L")
    out_1bit = Image.new("1", (size, size), 255)

    for x in range(size):
        for y in range(size):
            alpha = a.getpixel((x, y))
            pixel = gray.getpixel((x, y))
            if alpha > 128 and pixel < 180:
                out_1bit.putpixel((x, y), 0)

    out_1bit.save(out_path)
    return True


def fetch(url, team_id):
    """Try SVG first, fall back to PNG."""
    headers = {"User-Agent": "mlb-tracker/1.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return r.content, "svg"
    except Exception:
        pass

    # Try PNG cap logo fallback
    png_url = f"https://www.mlbstatic.com/team-logos/team-cap-on-light/{team_id}.svg"
    try:
        r = requests.get(png_url, headers=headers, timeout=10)
        r.raise_for_status()
        return r.content, "svg"
    except Exception:
        pass

    return None, None


def main():
    os.makedirs(LOGO_DIR, exist_ok=True)

    # Check if cairosvg is available
    try:
        import cairosvg
        has_cairo = True
        print("✓ cairosvg available — SVG rendering enabled")
    except ImportError:
        has_cairo = False
        print("⚠  cairosvg not found.")
        print("   Install it with: pip install cairosvg --break-system-packages")
        print("   Falling back to MLB PNG cap logos instead.\n")

    ok    = 0
    fail  = 0
    skip  = 0

    for abbr, team_id, svg_url in TEAMS:
        out_path = os.path.join(LOGO_DIR, f"{abbr}.png")

        if os.path.exists(out_path):
            print(f"  ✓ {abbr:4s}  already exists — skipping")
            skip += 1
            continue

        print(f"  ↓ {abbr:4s}  fetching...", end=" ", flush=True)
        data, fmt = fetch(svg_url, team_id)

        if data is None:
            print("FAILED (no data)")
            fail += 1
            continue

        if fmt == "svg" and has_cairo:
            success = svg_to_1bit_png(data, out_path)
        else:
            # Try PNG cap logo
            png_url = f"https://www.mlbstatic.com/team-logos/team-cap-on-light/{team_id}.svg"
            png_data, _ = fetch(png_url, team_id)
            if png_data and has_cairo:
                success = svg_to_1bit_png(png_data, out_path)
            else:
                print("SKIPPED (need cairosvg)")
                fail += 1
                continue

        if success:
            print(f"saved → {out_path}")
            ok += 1
        else:
            print("FAILED (conversion error)")
            fail += 1

    print(f"\nDone: {ok} saved, {skip} skipped, {fail} failed")

    if fail > 0:
        print("\nFor any failures, install cairosvg and re-run:")
        print("  pip install cairosvg --break-system-packages")
        print("  python3 download_logos.py")


if __name__ == "__main__":
    main()
