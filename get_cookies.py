#!/usr/bin/env python3
"""
Helper to extract cookies from authenticated session.
Usage: python get_cookies.py <url> --output cookies.json
"""
import json
import argparse
from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument('url', help='URL to authenticate at')
ap.add_argument('--output', '-o', default='cookies.json', help='Save cookies to this file')
args = ap.parse_args()

print(f"Opening browser to {args.url}")
print("Complete your login, then close the browser window...")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto(args.url)
    input("Press Enter after closing browser or logging in...")
    cookies = context.cookies()
    
with open(args.output, 'w') as f:
    json.dump(cookies, f, indent=2)

print(f"Saved {len(cookies)} cookies to {args.output}")
