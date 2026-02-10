# Web Scraper

Generic web scraper for crawling documentation sites or text-based content and converting to Markdown.

## Quick Start

1. Create virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Run the scraper:

```bash
python scraper.py "https://docs.trimblecloud.com/identity-and-access-management/" --output combined_iam.md
```

## Options

- `--output` / `-o`: Output file path (default: `combined.md`)
- `--max-pages`: Limit number of pages to crawl (default: 200)
- `--delay`: Delay between requests in seconds (default: 0.5)
- `--path-prefix`: Restrict crawling to a specific path prefix (defaults to start URL's path)

## Usage

The scraper:
- Crawls pages starting from a given URL
- Extracts main article content (main, article, or common doc containers)
- Converts HTML to Markdown
- Combines all pages into a single output file with page breaks

Perfect for feeding documentation or text content into LLMs or building embeddings.

## Notes

- Check `robots.txt` and terms of service before scraping
- Adjust `--delay` to be respectful to the server
- For JS-heavy sites, consider using Playwright for rendering
