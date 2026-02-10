#!/usr/bin/env python3
import argparse
import time
import json
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
    # Skip patterns that are auth/nav fragments
    skip_patterns = ['sign_in', 'login', 'logout', 'recover', 'reset', 'register', '#']
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("#"):
            continue
        # Skip auth-related links
        if any(p in href.lower() for p in skip_patterns):
            continue
        full = urljoin(base_url, href)
        full = full.split('#')[0]
        out.add(full)
    return out


def extract_main_content(html):
    soup = BeautifulSoup(html, "html.parser")
    # Try common doc site containers
    selectors = ["main", "article", "div.doc-content", "div.content", "div#content", "div.article-body"]
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            return str(el)
    # Fallback: body
    return str(soup.body or soup)


def fetch(url, use_playwright=False, cookies=None, context=None):
    if use_playwright:
        try:
            from playwright.sync_api import sync_playwright
            if context:
                # Use provided context (with cookies/auth)
                page = context.new_page()
                page.goto(url, wait_until="networkidle", timeout=30000)
                html = page.content()
                page.close()
                return html
            else:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    browser_context = browser.new_context()
                    if cookies:
                        browser_context.add_cookies(cookies)
                    page = browser_context.new_page()
                    page.goto(url, wait_until="networkidle", timeout=30000)
                    html = page.content()
                    browser.close()
                    return html
        except Exception as e:
            print(f"Playwright failed, falling back to requests: {e}")
            return fetch_requests(url)
    return fetch_requests(url)


def fetch_requests(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.text


def crawl(start_url, max_pages=200, delay=0.5, path_prefix=None, use_playwright=False, cookies=None, context=None):
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
            html = fetch(url, use_playwright=use_playwright, cookies=cookies, context=context)
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
    ap.add_argument('--playwright', action='store_true', help='Use Playwright for JS rendering')
    ap.add_argument('--cookies', type=str, help='Load cookies from JSON file')
    args = ap.parse_args()
    
    if not args.path_prefix:
        args.path_prefix = args.start_url
    
    cookies = None
    
    if args.cookies:
        with open(args.cookies, 'r') as f:
            cookies = json.load(f)
        print(f"Loaded {len(cookies)} cookies from {args.cookies}")
    
    pages = crawl(args.start_url, args.max_pages, args.delay, args.path_prefix, use_playwright=args.playwright, cookies=cookies)
    save_pages(pages, args.output)
    print(f"Saved {len(pages)} pages to {args.output}")

