from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from curl_cffi import requests
from bs4 import BeautifulSoup, Tag
from urllib.parse import urljoin
import re
import os
import secrets

from scrapers.screenrant import parse_screenrant
from scrapers.animecorner import parse_animecorner
from scrapers.inasianspaces import parse_inasianspaces
from scrapers.crowsworldofanime import parse_crowsworldofanime
from scrapers.cbr import parse_cbr

app = FastAPI()
security = HTTPBasic()

# --- 1. DEBUGGING GATEKEEPER ---
def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = os.environ.get("AUTH_USERNAME", "admin")
    correct_password = os.environ.get("AUTH_PASSWORD", "password")

    # Secure Comparison
    is_correct_username = secrets.compare_digest(credentials.username, correct_username)
    is_correct_password = secrets.compare_digest(credentials.password, correct_password)

    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

class ScrapeRequest(BaseModel):
    url: str

# --- 2. SURGICAL PARSERS ---

def parse_myanimelist(soup):
    data = {}
    content_div = soup.find("div", class_="news-container") or soup.find("div", class_="content-container")
    
    if content_div:
        # Clean junk
        junk_classes = ["side-content", "news-recent", "mt16", "tags", "d-none", "related-db", "caption", "auto-load"]
        for junk in content_div.find_all("div", class_=junk_classes):
            junk.decompose()
        
        # Get Full Text
        paragraphs = []
        for p in content_div.find_all("p"):
            text = p.get_text(strip=True)
            if len(text) > 5 and "Source:" not in text:
                paragraphs.append(text)
        
        data['description'] = "\n\n".join(paragraphs)
        img = content_div.find("img")
        if img: data['main_image'] = img.get("src")
        
    data['max_side_images'] = 3
    return data

def parse_crunchyroll(soup):
    data = {}
    article_body = soup.select_one(".news-content, .body-text, [class*='ArticleBody']")
    if article_body:
        data['description'] = article_body.get_text(separator="\n\n", strip=True)
        img = article_body.find("img")
        if img: data['main_image'] = img.get("src")
    data['max_side_images'] = 3
    return data

def parse_animeanime(soup):
    """
    ANIMEANIME.JP FIXES:
    - Updated Selector: Finds <article class="arti-body"> (based on your file)
    - Removes Amazon/Rakuten boxes (.af_box)
    """
    data = {}
    
    # --- FIX IS HERE: Added 'article.arti-body' ---
    article_body = soup.find("article", class_="arti-body") or \
                   soup.find("section", class_="article-body") or \
                   soup.find("div", id="response_body") or \
                   soup.find("div", class_="article_body")

    if article_body:
        # 1. GUILLOTINE (Remove Editor's Picks/Related)
        stop_headers = article_body.find_all(["h2", "h3", "div"], string=re.compile(r"注目記事|関連記事|併せて読みたい|編集部おすすめ"))
        for header in stop_headers:
            parent_block = header.find_parent(["div", "section"])
            if parent_block and parent_block in article_body.parents:
                header.decompose() 
            elif parent_block:
                parent_block.decompose()

        # 2. CLEAN ADS & JUNK (Added 'af_box')
        junk_classes = ["affiliate", "related", "tags", "author", "title-link", "pickup", "recommend", "slider", "af_box"]
        for junk in article_body.find_all(["div", "section", "ul"], class_=junk_classes):
            junk.decompose()

        # 3. GET FULL TEXT
        paragraphs = []
        for p in article_body.find_all("p"):
            text = p.get_text(strip=True)
            if len(text) > 1 and "アニメ！アニメ！" not in text:
                paragraphs.append(text)
        
        data['description'] = "\n\n".join(paragraphs)
        data['content_body'] = article_body 

    data['max_side_images'] = 50 
    return data


# --- 3. MAIN ENDPOINT ---
@app.post("/scrape", dependencies=[Depends(get_current_username)])
def scrape_data(request: ScrapeRequest):
    print(f"Scraping: {request.url}")
    
    try:
        response = requests.get(
            request.url,
            impersonate="chrome124",
            headers={
                "Referer": "https://www.google.com/",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=25,
            allow_redirects=True 
        )

        soup = BeautifulSoup(response.content, "lxml")
        
        # Metadata
        meta_data = {
            "title": soup.title.string.strip() if soup.title else "No Title",
            "description": "",
            "main_image": None,
            "video_link": None
        }
        
        if soup.find("meta", property="og:title"):
            meta_data["title"] = soup.find("meta", property="og:title")["content"]
        if soup.find("meta", property="og:image"):
            meta_data["main_image"] = soup.find("meta", property="og:image")["content"]
        if soup.find("meta", property="og:description"):
            meta_data["description"] = soup.find("meta", property="og:description")["content"]

        # Video
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src", "")
            if "youtube" in src or "youtu.be" in src:
                match = re.search(r"(?:v=|\/embed\/|\/1\/|\/v\/|https:\/\/youtu\.be\/)([^#\&\?]{11})", src)
                if match:
                    meta_data["video_link"] = f"https://www.youtube.com/watch?v={match.group(1)}"
                    break

        # Parsing - NOW WITH SCREENRANT
        parsed_data = {}
        if "myanimelist.net" in request.url:
            parsed_data = parse_myanimelist(soup)
        elif "animeanime.jp" in request.url:
            parsed_data = parse_animeanime(soup)
        elif "screenrant.com" in request.url:
            parsed_data = parse_screenrant(soup, request.url)
        elif "cbr.com" in request.url:
            parsed_data = parse_cbr(soup, request.url)
        elif "animecorner.me" in request.url:
            parsed_data = parse_animecorner(soup, request.url)
        elif "inasianspaces.com" in request.url:
            parsed_data = parse_inasianspaces(soup, request.url)
        elif "crowsworldofanime.com" in request.url:
            parsed_data = parse_crowsworldofanime(soup, request.url)
        
        # Merge
        final_desc = parsed_data.get("description") if parsed_data.get("description") else meta_data["description"]
        final_image = parsed_data.get("main_image") if parsed_data.get("main_image") else meta_data["main_image"]
        final_video = parsed_data.get("video_link") if parsed_data.get("video_link") else meta_data["video_link"]
        max_images = parsed_data.get('max_side_images', 3)
        
        if final_image and not final_image.startswith("http"):
            final_image = urljoin(request.url, final_image)

        # --- IMAGE EXTRACTION ---
        # For ScreenRant, CBR, InAsianSpaces, AnimeCorner, and CrowsWorldOfAnime, use the detailed side_images
        if ("screenrant.com" in request.url or "cbr.com" in request.url or "inasianspaces.com" in request.url or "animecorner.me" in request.url or "crowsworldofanime.com" in request.url) and 'side_images' in parsed_data:
            side_images_data = parsed_data['side_images']
        else:
            # Original image extraction for other sites
            side_images_data = []
            search_area = parsed_data.get('content_body', soup)
            
            banned_img_terms = ["icon", "logo", "avatar", "writer", "series", "banner", "ranking", "button"]
            
            for img in search_area.find_all("img"):
                src = img.get("src")
                if img.get("data-original"):
                    src = img.get("data-original")
                
                if src:
                    if not src.startswith("http"):
                        src = urljoin(request.url, src)

                    if src != final_image and not src.startswith("data:"):
                        
                        if any(term in src.lower() for term in banned_img_terms):
                            continue

                        if "animeanime.jp" in request.url:
                            if "sq_sl" in src or "thumb" in src or "list_m" in src:
                                continue 
                            
                        # Size check
                        width = img.get("width", "100") 
                        if str(width).isdigit():
                            if int(width) < 150: continue 
                        
                        # Build image data
                        img_data = {
                            'src': src,
                            'alt': img.get('alt', ''),
                            'width': img.get('width', ''),
                            'height': img.get('height', ''),
                        }
                        side_images_data.append(img_data)

            # Remove duplicates
            unique_images = []
            seen = set()
            for img in side_images_data:
                if img['src'] not in seen:
                    seen.add(img['src'])
                    unique_images.append(img)
            side_images_data = unique_images[:max_images]

        # Build response data
        response_data = {
            "title": meta_data["title"],
            "main_image": final_image,
            "side_images": side_images_data,  # Now includes full metadata for ScreenRant and CBR
            "video_link": final_video,
            "description": final_desc,
            "url": request.url
        }
        
        # Add HTML content if ScreenRant, CBR, InAsianSpaces, AnimeCorner, or CrowsWorldOfAnime
        if ("screenrant.com" in request.url or "cbr.com" in request.url or "inasianspaces.com" in request.url or "animecorner.me" in request.url or "crowsworldofanime.com" in request.url) and 'html_content' in parsed_data:
            response_data['html_content'] = parsed_data['html_content']

        return {
            "status": "success",
            "data": response_data
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/")
def home():
    return {"status": "Online", "mode": "V9 with ScreenRant Support (Full HTML + Image Metadata)"}