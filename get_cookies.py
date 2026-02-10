#!/usr/bin/env python3
"""
Cookie Extractor - Extract cookies from authenticated session

Opens an interactive browser window for manual login, then extracts and saves
session cookies to a JSON file for use with the web scraper.

Author: Jason Bisnette
License: MIT
"""
# Import json for writing cookies to file
import json
# Import argparse for command-line argument parsing
import argparse
# Import Playwright synchronous API for browser automation
from playwright.sync_api import sync_playwright

# Create an argument parser for command-line arguments
ap = argparse.ArgumentParser()
# Define required positional argument for the URL to authenticate at
ap.add_argument('url', help='URL to authenticate at')
# Define optional output file argument for saving cookies (defaults to 'cookies.json')
ap.add_argument('--output', '-o', default='cookies.json', help='Save cookies to this file')
# Parse the command-line arguments into an args object
args = ap.parse_args()

# Print message indicating that browser is opening
print(f"Opening browser to {args.url}")
# Instruct user to complete login and close browser window
print("Complete your login, then close the browser window...")

# Create a Playwright instance and launch browser in visible (non-headless) mode
with sync_playwright() as p:
    # Launch Chromium browser with GUI visible so user can interact with it
    browser = p.chromium.launch(headless=False)
    # Create a new browser context (session container)
    context = browser.new_context()
    # Create a new page (tab) within the browser context
    page = context.new_page()
    # Navigate to the specified URL in the browser
    page.goto(args.url)
    # Wait for user input before extracting cookies (user manually logs in during this time)
    input("Press Enter after closing browser or logging in...")
    # Extract all cookies from the browser context (includes session auth cookies)
    cookies = context.cookies()

# Open the output file for writing cookies as JSON
with open(args.output, 'w') as f:
    # Write the cookies list to the file in formatted JSON (with indentation for readability)
    json.dump(cookies, f, indent=2)

# Print confirmation message with the number of cookies saved
print(f"Saved {len(cookies)} cookies to {args.output}")

