#!/usr/bin/env python3
"""
Web Scraper - Extract and convert web pages to Markdown

A generic web scraper for crawling documentation sites and text-based content,
converting HTML to Markdown, and combining multiple pages into a single document.
Supports both public sites and authenticated content via Playwright and cookie-based auth.

Author: Jason Bisnette
License: MIT
"""
# Import argparse for command-line argument parsing
import argparse
# Import time for sleep delays between requests
import time
# Import json for parsing cookies from file
import json
# Import requests library for HTTP requests
import requests
# Import URL parsing utilities
from urllib.parse import urljoin, urlparse
# Import BeautifulSoup for HTML parsing
from bs4 import BeautifulSoup
# Import markdownify to convert HTML to Markdown
from markdownify import markdownify as md
# Import os for file and directory operations
import os

# Define User-Agent header to identify the scraper to web servers
HEADERS = {"User-Agent": "WebScraper/1.0 (+https://github.com/Yeddo)"}


def same_domain(a, b):
    """
    Check if two URLs belong to the same domain.
    
    Args:
        a (str): First URL
        b (str): Second URL
        
    Returns:
        bool: True if both URLs have the same netloc (domain)
    """
    # Extract netloc (domain + port) from both URLs and compare them
    return urlparse(a).netloc == urlparse(b).netloc


def is_within_prefix(url, prefix):
    """
    Check if a URL's path is within a given path prefix.
    
    Args:
        url (str): URL to check
        prefix (str): Path prefix to match against
        
    Returns:
        bool: True if the URL's path starts with the prefix path
    """
    # Extract the path component from the prefix URL
    p = urlparse(prefix).path
    # Check if the target URL's path starts with the prefix path
    return urlparse(url).path.startswith(p)


def get_links(html, base_url):
    """
    Extract all links from HTML content, filtering out auth/nav fragments.
    
    Args:
        html (str): HTML content to parse
        base_url (str): Base URL for resolving relative links
        
    Returns:
        set: Set of absolute URLs found in the HTML
    """
    # Parse the HTML using BeautifulSoup with the html.parser backend
    soup = BeautifulSoup(html, "html.parser")
    # Initialize empty set to store unique URLs (sets prevent duplicates)
    out = set()
    # Define patterns for URLs to skip (authentication pages, login forms, etc.)
    skip_patterns = ['sign_in', 'login', 'logout', 'recover', 'reset', 'register', '#']
    
    # Find all anchor (<a>) tags in the HTML that have an href attribute
    for a in soup.find_all("a", href=True):
        # Extract the href value from the anchor tag
        href = a["href"]
        # Skip fragment-only links (anchors that navigate within the same page)
        if href.startswith("#"):
            continue
        # Skip any href that contains authentication-related patterns
        if any(p in href.lower() for p in skip_patterns):
            continue
        # Convert relative URLs to absolute URLs using the base URL
        full = urljoin(base_url, href)
        # Remove fragment identifiers from the URL (everything after # character)
        full = full.split('#')[0]
        # Add the cleaned, absolute URL to our set
        out.add(full)
    
    # Return the set of all extracted and filtered links
    return out


def extract_main_content(html):
    """
    Extract main article content from HTML by targeting common container selectors.
    
    Args:
        html (str): HTML content to parse
        
    Returns:
        str: HTML string of the main content area
    """
    # Parse the HTML using BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    
    # List of CSS selectors for common documentation/article containers
    # Ordered by specificity and likelihood of containing the main article content
    selectors = ["main", "article", "div.doc-content", "div.content", "div#content", "div.article-body"]
    
    # Iterate through selectors to find the first matching element in order
    for sel in selectors:
        # Try to select an element using the current CSS selector
        el = soup.select_one(sel)
        # If an element matching the selector was found, return its HTML
        if el:
            return str(el)
    
    # Fallback if no article container is found: return body or entire document
    return str(soup.body or soup)


def fetch(url, use_playwright=False, cookies=None, context=None):
    """
    Fetch HTML content from a URL, with optional JavaScript rendering via Playwright.
    
    Args:
        url (str): URL to fetch
        use_playwright (bool): Whether to use Playwright for JavaScript rendering
        cookies (list): List of cookie dictionaries to inject into the request
        context (object): Playwright browser context with existing authenticated session
        
    Returns:
        str: HTML content of the page
    """
    # Check if Playwright-based fetching with JS rendering is requested
    if use_playwright:
        try:
            # Import Playwright's synchronous API
            from playwright.sync_api import sync_playwright
            
            # If a browser context with existing cookies/session is provided, reuse it
            if context:
                # Create a new page within the existing context
                page = context.new_page()
                # Navigate to the URL and wait until network is idle (JS complete)
                page.goto(url, wait_until="networkidle", timeout=30000)
                # Extract the fully rendered HTML after JavaScript execution
                html = page.content()
                # Close the page (context remains open for reuse)
                page.close()
                # Return the fetched HTML
                return html
            else:
                # No context provided, create a fresh Playwright instance
                with sync_playwright() as p:
                    # Launch Chromium browser in headless mode (no GUI)
                    browser = p.chromium.launch(headless=True)
                    # Create a new browser context
                    browser_context = browser.new_context()
                    # If cookies were provided, add them to the context for authentication
                    if cookies:
                        browser_context.add_cookies(cookies)
                    # Create a new page within the browser context
                    page = browser_context.new_page()
                    # Navigate to the URL with networkidle wait condition for JS completion
                    page.goto(url, wait_until="networkidle", timeout=30000)
                    # Extract the fully rendered HTML content
                    html = page.content()
                    # Close the browser (context and page close automatically)
                    browser.close()
                    # Return the HTML content
                    return html
        # Catch any Playwright-related errors and fallback to requests library
        except Exception as e:
            # Log the error message to inform user of fallback behavior
            print(f"Playwright failed, falling back to requests: {e}")
            # Call the requests-based fetcher as a fallback
            return fetch_requests(url)
    
    # If Playwright is not requested, use the standard requests-based method
    return fetch_requests(url)


def fetch_requests(url):
    """
    Fetch HTML content from a URL using the requests library.
    
    Args:
        url (str): URL to fetch
        
    Returns:
        str: HTML content of the page
        
    Raises:
        requests.HTTPError: If the HTTP request returns an error status code
    """
    # Send a GET request to the URL with custom headers and a timeout
    r = requests.get(url, headers=HEADERS, timeout=15)
    # Raise an HTTPError exception if the response status indicates an error
    r.raise_for_status()
    # Return the response text content (the HTML)
    return r.text


def crawl(start_url, max_pages=200, delay=0.5, path_prefix=None, use_playwright=False, cookies=None, context=None):
    """
    Crawl a website starting from a URL, extracting and storing page content.
    
    Args:
        start_url (str): URL to begin crawling from
        max_pages (int): Maximum number of pages to crawl
        delay (float): Delay in seconds between requests (for politeness)
        path_prefix (str): Only crawl URLs matching this path prefix
        use_playwright (bool): Whether to use Playwright for JavaScript rendering
        cookies (list): Cookie dictionaries to use for authenticated requests
        context (object): Playwright browser context for reusing authenticated session
        
    Returns:
        list: List of dictionaries with keys: url, title, html
    """
    # Initialize a set to track URLs we've already visited (prevents duplicates)
    seen = set()
    # Initialize a queue (list) of URLs to visit, starting with the entry point
    to_visit = [start_url]
    # Initialize a list to accumulate successfully fetched and processed pages
    pages = []
    
    # Continue the crawl while there are URLs to visit AND we haven't reached max_pages
    while to_visit and len(pages) < max_pages:
        # Pop the first URL from the queue (FIFO - breadth-first crawling)
        url = to_visit.pop(0)
        
        # Skip this URL if we've already visited and processed it
        if url in seen:
            continue
        
        # Skip this URL if it's on a different domain than the starting URL
        if not same_domain(start_url, url):
            continue
        
        # Skip this URL if a path prefix filter is active and this URL doesn't match it
        if path_prefix and not is_within_prefix(url, path_prefix):
            continue
        
        # Attempt to fetch the webpage at this URL
        try:
            # Print progress message showing the current URL being fetched
            print(f"Fetching: {url}")
            # Fetch the HTML content using the configured fetch method
            html = fetch(url, use_playwright=use_playwright, cookies=cookies, context=context)
        # Catch any exception that occurs during fetching
        except Exception as e:
            # Print error message with URL and exception details for debugging
            print(f"Failed {url}: {e}")
            # Mark this URL as seen even though it failed (don't retry)
            seen.add(url)
            # Continue to process the next URL in the queue
            continue
        
        # Mark this URL as visited since we successfully processed it
        seen.add(url)
        
        # Extract the main article/content area from the full HTML
        main = extract_main_content(html)
        
        # Parse the HTML to extract the page's title element
        title = BeautifulSoup(html, "html.parser").title
        # Get the text content from the title tag, or fallback to the URL if missing
        title_text = title.get_text().strip() if title else url
        
        # Create a dictionary entry for this page with its metadata and content
        pages.append({"url": url, "title": title_text, "html": main})
        
        # Extract all hyperlinks from the current page's HTML
        links = get_links(html, url)
        
        # Process each extracted link for potential future crawling
        for l in links:
            # Add link to the crawl queue if it hasn't been seen and meets criteria
            if l not in seen and l not in to_visit and same_domain(start_url, l):
                # Also check if the link matches the path prefix (if one is specified)
                if not path_prefix or is_within_prefix(l, path_prefix):
                    # Add the link to the end of the queue for future processing
                    to_visit.append(l)
        
        # Sleep for the specified delay to be respectful to the server's resources
        time.sleep(delay)
    
    # Return the complete list of successfully fetched and processed pages
    return pages


def save_pages(pages, out_path):
    """
    Convert fetched pages to Markdown format and save to a file.
    
    Args:
        pages (list): List of page dictionaries with url, title, and html keys
        out_path (str): File path where the combined Markdown should be saved
    """
    # Initialize a list to hold individual page Markdown documents before combining
    combined = []
    
    # Create the output directory and any parent directories if they don't exist
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    
    # Iterate through each page to convert and format it
    for p in pages:
        # Convert the HTML content to Markdown format using ATX-style headings
        md_text = md(p['html'], heading_style="ATX")
        
        # Create a header section with the page title and source URL as metadata
        header = f"# {p['title']}\n\nSource: {p['url']}\n\n"
        
        # Combine the header and Markdown content for this page
        combined.append(header + md_text)
    
    # Open the output file for writing in text mode with UTF-8 character encoding
    with open(out_path, 'w', encoding='utf-8') as f:
        # Join all pages with a page break separator (---) and write to the file
        f.write('\n\n---\n\n'.join(combined))


# Entry point: execute this block only when script is run directly (not when imported)
if __name__ == '__main__':
    # Create an argument parser for parsing command-line arguments
    ap = argparse.ArgumentParser()
    # Define required positional argument for the starting URL to scrape
    ap.add_argument('start_url')
    # Define optional output file path argument (defaults to 'combined.md')
    ap.add_argument('--output', '-o', default='combined.md')
    # Define optional argument for maximum number of pages to crawl (defaults to 200)
    ap.add_argument('--max-pages', type=int, default=200)
    # Define optional argument for delay between requests in seconds (defaults to 0.5)
    ap.add_argument('--delay', type=float, default=0.5)
    # Define optional argument for path prefix to restrict crawling scope
    ap.add_argument('--path-prefix', type=str, default=None)
    # Define flag to enable Playwright JavaScript rendering (default: disabled)
    ap.add_argument('--playwright', action='store_true', help='Use Playwright for JS rendering')
    # Define optional argument for path to JSON file containing authentication cookies
    ap.add_argument('--cookies', type=str, help='Load cookies from JSON file')
    # Parse the command-line arguments into an args object
    args = ap.parse_args()
    
    # If no path prefix was specified, default to using the start URL's path
    if not args.path_prefix:
        args.path_prefix = args.start_url
    
    # Initialize cookies variable as None (will load if file is provided)
    cookies = None
    
    # Check if a cookies file path was provided via command-line argument
    if args.cookies:
        # Open the cookies JSON file for reading
        with open(args.cookies, 'r') as f:
            # Parse the JSON file and load the cookies list into memory
            cookies = json.load(f)
        # Print confirmation message with the number of loaded cookies
        print(f"Loaded {len(cookies)} cookies from {args.cookies}")
    
    # Execute the web crawling with all specified parameters
    pages = crawl(args.start_url, args.max_pages, args.delay, args.path_prefix, use_playwright=args.playwright, cookies=cookies)
    
    # Save all collected pages as a combined Markdown document
    save_pages(pages, args.output)
    
    # Print completion message with the total number of pages successfully saved
    print(f"Saved {len(pages)} pages to {args.output}")
