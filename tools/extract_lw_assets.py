#!/usr/bin/env python
# Extract Cloudinary images and Neuronpedia links from a LessWrong HTML export.
# Usage (PowerShell):
#   python tools/extract_lw_assets.py ^
#     --html "docs/lesswrong_post/Automated Circuit Interpretation via Probe Prompting — LessWrong.html" ^
#     --figdir "paper/figures" ^
#     --links "paper/artifacts/neuronpedia_links.txt" ^
#     --convert-pdf
#
# Requires: requests, beautifulsoup4, pillow (if --convert-pdf)

import argparse
import os
import re
import sys
from urllib.parse import urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError as e:
    print("Please install dependencies: pip install requests beautifulsoup4 pillow", file=sys.stderr)
    raise

try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False


def sanitize_filename(url: str) -> str:
    parsed = urlparse(url)
    name = os.path.basename(parsed.path)
    name = re.sub(r'[^A-Za-z0-9_.-]+', '_', name)
    if not name:
        name = "image"
    return name


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def download_image(url: str, out_dir: str) -> str:
    ensure_dir(out_dir)
    filename = sanitize_filename(url)
    out_path = os.path.join(out_dir, filename)
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(r.content)
        return out_path
    except Exception as e:
        print(f"Failed to download {url}: {e}", file=sys.stderr)
        return ""


def convert_to_pdf(image_path: str) -> str:
    if not PIL_AVAILABLE:
        return ""
    try:
        img = Image.open(image_path)
        rgb = img.convert("RGB")
        pdf_path = os.path.splitext(image_path)[0] + ".pdf"
        rgb.save(pdf_path, "PDF", resolution=300.0)
        return pdf_path
    except Exception as e:
        print(f"Failed to convert {image_path} to PDF: {e}", file=sys.stderr)
        return ""


def extract_assets(html_path: str, fig_dir: str, links_out: str, convert_pdf: bool) -> None:
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    soup = BeautifulSoup(html, "html.parser")

    # Collect Cloudinary images
    img_urls = set()
    for tag in soup.find_all("img"):
        src = tag.get("src") or ""
        if "res.cloudinary.com" in src:
            img_urls.add(src)
        # srcset option
        srcset = tag.get("srcset")
        if srcset:
            for part in srcset.split(","):
                u = part.strip().split(" ")[0]
                if "res.cloudinary.com" in u:
                    img_urls.add(u)

    # Download images
    manifest = []
    for url in sorted(img_urls):
        path = download_image(url, fig_dir)
        if path:
            if convert_pdf:
                pdf = convert_to_pdf(path)
                if pdf:
                    manifest.append(pdf)
                else:
                    manifest.append(path)
            else:
                manifest.append(path)

    # Collect Neuronpedia links
    np_links = set()
    for a in soup.find_all("a"):
        href = a.get("href") or ""
        if "neuronpedia" in href:
            np_links.add(href)

    if links_out:
        ensure_dir(os.path.dirname(links_out))
        with open(links_out, "w", encoding="utf-8") as f:
            for link in sorted(np_links):
                f.write(link + "\n")

    # Write a manifest of figures
    manifest_path = os.path.join(fig_dir, "_manifest.txt")
    with open(manifest_path, "w", encoding="utf-8") as f:
        for p in manifest:
            f.write(p + "\n")

    print(f"Downloaded {len(manifest)} figure assets to {fig_dir}")
    print(f"Neuronpedia links: {len(np_links)} -> {links_out}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", required=True, help="Path to LessWrong HTML export")
    parser.add_argument("--figdir", default="paper/figures", help="Output directory for figures")
    parser.add_argument("--links", default="paper/artifacts/neuronpedia_links.txt", help="Output file for Neuronpedia links")
    parser.add_argument("--convert-pdf", action="store_true", help="Convert images to PDF via Pillow")
    args = parser.parse_args()
    extract_assets(args.html, args.figdir, args.links, args.convert_pdf)


if __name__ == "__main__":
    main()



