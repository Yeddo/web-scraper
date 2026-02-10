#!/usr/bin/env python3
import argparse
import time
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from markdownify import markdownify as md
import os

HEADERS = {"User-Agent": "WebScraper/1.0 (+https://github.com/Yeddo)"}


def same_domain(a, b):
    return urlparse(a).netloc == urlparse(b).netloc


def is_within_prefix(url, prefix):
    p = urlparse(prefix).path
    return urlparse(url).path.startswith(p)


def get_links(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    out = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("#"):
            continue
        full = urljoin(base_url, href)
        out.add(full.split('#')[0])
    return out


def extract_main_content(html):
    soup = BeautifulSoup(html, "html.parser")
    # Try common doc site containers
    selectors = ["main", "article", "div.doc-content", "div.content", "div#content"]
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            return str(el)
    # Fallback: body
    return str(soup.body or soup)


def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.text


def crawl(start_url, max_pages=200, delay=0.5, path_prefix=None):
    seen = set()
    to_visit = [start_url]
    pages = []
    while to_visit and len(pages) < max_pages:
        url = to_visit.pop(0)
        if url in seen:
            continue
        if not same_domain(start_url, url):
            continue
        if path_prefix and not is_within_prefix(url, path_prefix):
            continue
        try:
            print(f"Fetching: {url}")
            html = fetch(url)
        except Exception as e:
            print(f"Failed {url}: {e}")
            seen.add(url)
            continue
        seen.add(url)
        main = extract_main_content(html)
        title = BeautifulSoup(html, "html.parser").title
        title_text = title.get_text().strip() if title else url
        pages.append({"url": url, "title": title_text, "html": main})
        links = get_links(html, url)
        for l in links:
            if l not in seen and l not in to_visit and same_domain(start_url, l):
                if not path_prefix or is_within_prefix(l, path_prefix):
                    to_visit.append(l)
        time.sleep(delay)
    return pages


def save_pages(pages, out_path):
    combined = []
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    for p in pages:
        md_text = md(p['html'], heading_style="ATX")
        header = f"# {p['title']}\n\nSource: {p['url']}\n\n"
        combined.append(header + md_text)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n\n---\n\n'.join(combined))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('start_url')
    ap.add_argument('--output', '-o', default='combined.md')
    ap.add_argument('--max-pages', type=int, default=200)
    ap.add_argument('--delay', type=float, default=0.5)
    ap.add_argument('--path-prefix', type=str, default=None)
    args = ap.parse_args()
    if not args.path_prefix:
        args.path_prefix = args.start_url
    pages = crawl(args.start_url, args.max_pages, args.delay, args.path_prefix)
    save_pages(pages, args.output)
    print(f"Saved {len(pages)} pages to {args.output}")
