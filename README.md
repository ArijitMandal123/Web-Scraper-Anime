# Anime Web Scraper API

A robust FastAPI-based web scraping service designed specifically to extract content, images, and metadata from various anime and pop culture news websites. The API takes an article URL and returns structured JSON containing the article's text, main poster image, associated gallery/side images, embedded videos, and a cleanly reconstructed HTML format.

## Features

- **Multi-Site Support**: Custom parsing logic for major sites including:
  - ScreenRant
  - CBR
  - AnimeCorner
  - InAsianSpaces
  - Sakugabooru
  - Crow's World of Anime
- **Advanced Scraping**: Uses `curl_cffi` to bypass anti-bot protections and Cloudflare.
- **Structured Data**: Extracts detailed metadata for images, including alternative text, captions, and dimensions.
- **Smart Filtering**: Automatically filters out sidebar noise, ads, thumbnails, and non-article content.
- **HTML Reconstruction**: Generates a clean, stripped-down HTML string of the core article content and its original layout flow.

## Installation

Ensure you have Python 3.8+ installed. It is recommended to use `uv` or a virtual environment.

```bash
# Clone the repository
git clone <your-repo-url>
cd "web scaper for anime"

# Install dependencies
pip install -r requirements.txt
# OR with uv
uv pip install -r requirements.txt
```

## Usage

### Running the API Server

Start the FastAPI development server:

```bash
fastapi dev main.py
# OR
uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

### API Endpoint

**POST `/scrape`**

Request Body (JSON):
```json
{
  "url": "https://animecorner.me/example-article"
}
```

Response format:
```json
{
  "status": "success",
  "data": {
    "description": "Full text content of the article...",
    "main_image": "https://example.com/main_image.jpg",
    "side_images": [
      {
        "src": "https://example.com/image1.jpg",
        "alt": "Image Description",
        "width": "800",
        "height": "600",
        "caption": "Image Caption"
      }
    ],
    "video_link": "https://www.youtube.com/watch?v=...",
    "html_content": "<!DOCTYPE html><html>...</html>"
  }
}
```

### Testing locally

You can test the scraper directly without starting the server by editing the URL in `test_scraper.py` and running:

```bash
python test_scraper.py
```
This will output the scraped JSON data and save it to a file.

## Architecture

- `main.py`: The FastAPI server and routing logic that detects the domain and delegates to the appropriate parser.
- `scrapers/`: Directory containing individual parsing modules tailored for the HTML structure of each supported website.
- `requirements.txt`: Python package dependencies (FastAPI, BeautifulSoup4, curl_cffi, etc).