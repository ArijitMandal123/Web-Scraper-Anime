import re
from urllib.parse import urljoin
import html
from bs4 import BeautifulSoup

def parse_screenrant(soup, base_url):
    """
    Parse ScreenRant article with correct image-to-section matching.
    
    Returns:
        dict: {
            'description': str,
            'main_image': str,
            'side_images': list of dict with full metadata,
            'video_link': str,
            'html_content': str (reconstructed HTML),
            'max_side_images': int
        }
    """
    data = {}
    
    # Find main article
    article = soup.find('article')
    if not article:
        return data
    
    # --- EXTRACT MAIN IMAGE ---
    main_image = None
    
    # Try to get from og:image first
    og_image = soup.find('meta', property='og:image')
    if og_image:
        main_image = og_image.get('content')
    
    # If not found, get first image in article
    if not main_image:
        first_img = article.find('img')
        if first_img:
            main_image = first_img.get('src')
    
    data['main_image'] = main_image
    
    # --- EXTRACT ALL CONTENT SECTIONS ---
    sections = []
    all_text_parts = []
    side_images = []
    seen_image_srcs = set()  # Track which images we've already added
    
    # --- FIRST: Scan ALL display cards in the article for videos and large posters ---
    display_cards = article.find_all('div', class_='display-card')
    for card in display_cards:
        # Skip sidebar featured articles (like ScreenRant StoryHub)
        if 'sidebar-featured-article' in card.get('class', []):
            continue
            
        # Extract video from display card (can be inside or outside card)
        video_elem = card.find('video')
        if video_elem:
            video_source = video_elem.find('source')
            if video_source and video_source.get('src'):
                if not data.get('video_link'):  # Only set first video found
                    data['video_link'] = video_source.get('src')
        
        # Extract ONLY the main large poster image (filter out cast/logos/small images)
        # Look for the primary poster - can be in different containers
        poster_img = None
        
        # Try different container patterns
        dc_img = card.find('div', class_='dc-img')
        if dc_img:
            poster_img = dc_img.find('img')
        
        # Also try w-img > body-img pattern (common in type-screen cards)
        if not poster_img:
            w_img = card.find('div', class_='w-img')
            if w_img:
                body_img = w_img.find('div', class_='body-img')
                if body_img:
                    poster_img = body_img.find('img')
        
        if poster_img:
            img_src = poster_img.get('src', '') or poster_img.get('data-img-url', '')
            width = poster_img.get('width', '0')
            height = poster_img.get('height', '0')
            alt_text = poster_img.get('alt', '')
            
            try:
                width_int = int(width) if width else 0
                height_int = int(height) if height else 0
            except:
                width_int = 0
                height_int = 0
            
            # STRICT FILTER: Only posters with BOTH dimensions >= 200
            # This filters out:
            # - Cast photos (typically 100x130)
            # - Logos (typically 150x150 or smaller)
            # - Small thumbnails
            # Keeps: Main posters (typically 300x400+)
            
            is_large_poster = (width_int >= 200 and height_int >= 200)
            
            # Additional check: Skip if alt text suggests it's a cast member or logo
            is_cast_or_logo = any(keyword in alt_text.lower() for keyword in [
                'headshot', 'logo', 'icon', 'avatar'
            ])
            
            if is_large_poster and not is_cast_or_logo and img_src:
                if not img_src.startswith('data:'):
                    if not img_src.startswith('http'):
                        img_src = urljoin(base_url, img_src)
                    
                    if img_src != main_image and img_src not in seen_image_srcs:
                        img_data = {
                            'src': img_src,
                            'alt': alt_text,
                            'class': ' '.join(poster_img.get('class', [])),
                            'width': width,
                            'height': height,
                            'loading': poster_img.get('loading', 'lazy'),
                            'caption': alt_text  # Use alt text as caption for posters
                        }
                        side_images.append(img_data)
                        seen_image_srcs.add(img_src)
    
    # --- THEN: Process content sections by headers ---
    headers = article.find_all(['h2', 'h3'])
    
    for header in headers:
        heading_text = header.get_text(strip=True)
        
        # Skip navigation/junk headers
        skip_keywords = [
            'Screen Rant Report',
            'Subscribe',
            'Related:',
            'RELATED',
            'More:',
            'Next:',
            'Continue scrolling',
            'Keep Reading',
            'StoryHub'
        ]
        if any(kw in heading_text for kw in skip_keywords):
            continue
        
        section = {
            'heading': heading_text,
            'heading_tag': header.name,
            'images': [],
            'paragraphs': []
        }
        
        # Collect all elements between this header and the next header
        found_images = []
        
        for sibling in header.find_next_siblings():
            if sibling.name in ['h2', 'h3']:
                break
            
            # Skip junk containers
            if sibling.name == 'div':
                classes = sibling.get('class', [])
                if any(c in str(classes) for c in ['newsletter', 'ad', 'related', 'widget']):
                    continue
            
            # Skip display cards - we handle them separately above
            if sibling.name == 'div' and ('display-card' in sibling.get('class', []) or 
                                          'w-display-card-media' in sibling.get('class', [])):
                continue
            
            # --- EXTRACT GALLERY IMAGES ---
            gallery_scripts = sibling.find_all('script', string=re.compile(r'window\.arrayOfGalleries'))
            for script in gallery_scripts:
                script_text = script.string
                if script_text:
                    import html
                    match = re.search(r'window\.arrayOfGalleries\[.*?\]\s*=\s*([\'"])(.*?)\1;', script_text, re.DOTALL)
                    if match:
                        escaped_html = match.group(2)
                        unescaped_html = html.unescape(html.unescape(escaped_html)).replace('\\/', '/')
                        gallery_soup = BeautifulSoup(unescaped_html, "lxml")
                        
                        for img in gallery_soup.find_all('img'):
                            src = img.get('src') or img.get('data-img-url')
                            if src:
                                src = src.replace('\\/', '/').replace('\\"', '')
                                base_src = src.split('?')[0]
                                
                                if base_src and not base_src.startswith('http'):
                                    base_src = urljoin(base_url, base_src)
                                    
                                main_image_base = main_image.split('?')[0] if main_image else ''
                                
                                if base_src and base_src != main_image_base and base_src not in seen_image_srcs:
                                    img_data = {
                                        'src': base_src,
                                        'alt': img.get('alt', '').replace('\\"', '').strip('" '),
                                        'class': 'gallery-image',
                                        'width': img.get('width', '').replace('\\"', '').strip('" '),
                                        'height': img.get('height', '').replace('\\"', '').strip('" '),
                                        'loading': 'lazy',
                                        'caption': img.get('alt', '').replace('\\"', '').strip('" ')
                                    }
                                    found_images.append(img_data)
                                    side_images.append(img_data)
                                    seen_image_srcs.add(base_src)

            # --- EXTRACT REGULAR IMAGES WITH FULL METADATA ---
            imgs = sibling.find_all('img')
            for img in imgs:
                img_src = img.get('src', '')
                width = img.get('width', '0')
                height = img.get('height', '0')
                
                # Convert to int for filtering
                try:
                    width_int = int(width) if width else 0
                    height_int = int(height) if height else 0
                except:
                    width_int = 0
                    height_int = 0
                
                # FILTER: Skip small images (minimum 300x300 for article images)
                if width_int < 300 and height_int < 300:
                    continue
                
                # Skip data URIs
                if img_src.startswith('data:'):
                    continue
                
                # Make absolute URL
                if img_src and not img_src.startswith('http'):
                    img_src = urljoin(base_url, img_src)
                
                # Skip if empty, is main image, or already added
                if not img_src or img_src == main_image or img_src in seen_image_srcs:
                    continue
                
                img_data = {
                    'src': img_src,
                    'alt': img.get('alt', ''),
                    'class': ' '.join(img.get('class', [])),
                    'width': width,
                    'height': height,
                    'loading': img.get('loading', 'lazy'),
                    'caption': ''
                }
                
                # Get caption from figcaption
                fig = img.find_parent('figure')
                if fig:
                    cap = fig.find('figcaption')
                    if cap:
                        img_data['caption'] = cap.get_text(strip=True)
                
                found_images.append(img_data)
                side_images.append(img_data)
                seen_image_srcs.add(img_src)
            
            # --- EXTRACT PARAGRAPHS ---
            if sibling.name == 'p':
                text = sibling.get_text(strip=True)
                # Filter out junk text
                if len(text) > 30 and not any(skip in text for skip in ['Subscribe to', 'Screen Rant', 'newsletter']):
                    section['paragraphs'].append(text)
                    all_text_parts.append(text)
        
        section['images'] = found_images
        
        # Only add section if it has content
        if section['paragraphs'] or section['images']:
            sections.append(section)
    
    # --- BUILD DESCRIPTION (ALL TEXT) ---
    data['description'] = '\n\n'.join(all_text_parts)
    
    # --- BUILD SIDE IMAGES LIST (NO DUPLICATES) ---
    unique_side_images = []
    seen_srcs = set()
    for img in side_images:
        if img['src'] and img['src'] not in seen_srcs:
            seen_srcs.add(img['src'])
            unique_side_images.append(img)
    
    data['side_images'] = unique_side_images
    data['max_side_images'] = 50  # Allow many images for ScreenRant
    
    # --- EXTRACT VIDEO FROM YOUTUBE IFRAMES (if not already found in display cards) ---
    if not data.get('video_link'):
        video_link = None
        for iframe in soup.find_all('iframe'):
            src = iframe.get('src', '')
            if 'youtube' in src or 'youtu.be' in src:
                match = re.search(r'(?:v=|/embed/|/1/|/v/|https://youtu\.be/)([^#&?]{11})', src)
                if match:
                    video_link = f"https://www.youtube.com/watch?v={match.group(1)}"
                    break
        
        if video_link:
            data['video_link'] = video_link
    
    # Get final video link (from display cards or iframes)
    final_video_link = data.get('video_link')
    
    # --- RECONSTRUCT HTML ---
    html_content = reconstruct_screenrant_html(sections, main_image, final_video_link, soup)
    data['html_content'] = html_content
    
    # Store sections for detailed output
    data['sections'] = sections
    
    return data


def reconstruct_screenrant_html(sections, main_image, video_link, original_soup):
    """
    Reconstruct clean HTML matching the original article structure.
    """
    html_parts = []
    
    html_parts.append('<!DOCTYPE html>')
    html_parts.append('<html lang="en">')
    html_parts.append('<head>')
    html_parts.append('    <meta charset="UTF-8">')
    html_parts.append('    <meta name="viewport" content="width=device-width, initial-scale=1.0">')
    
    # Get title
    title = original_soup.title.string.strip() if original_soup.title else "Article"
    html_parts.append(f'    <title>{title}</title>')
    
    # Basic styling
    html_parts.append('    <style>')
    html_parts.append('        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; ')
    html_parts.append('               max-width: 800px; margin: 40px auto; padding: 0 20px; ')
    html_parts.append('               line-height: 1.6; color: #333; background: #fff; }')
    html_parts.append('        h1 { font-size: 2.5em; margin-bottom: 20px; font-weight: 700; }')
    html_parts.append('        h2 { font-size: 1.8em; margin-top: 30px; margin-bottom: 15px; font-weight: 600; }')
    html_parts.append('        h3 { font-size: 1.4em; margin-top: 25px; margin-bottom: 12px; font-weight: 600; }')
    html_parts.append('        figure { margin: 30px 0; }')
    html_parts.append('        figure img { width: 100%; height: auto; display: block; }')
    html_parts.append('        figcaption { font-size: 0.9em; color: #666; margin-top: 8px; font-style: italic; }')
    html_parts.append('        p { margin: 15px 0; font-size: 1.1em; }')
    html_parts.append('        .video-container { margin: 30px 0; }')
    html_parts.append('        .video-container iframe { width: 100%; aspect-ratio: 16/9; border: none; }')
    html_parts.append('        ul, ol { margin: 15px 0; padding-left: 30px; }')
    html_parts.append('        li { margin: 8px 0; }')
    html_parts.append('        blockquote { margin: 20px 0; padding: 15px 20px; border-left: 4px solid #ccc; ')
    html_parts.append('                     background: #f9f9f9; font-style: italic; }')
    html_parts.append('    </style>')
    html_parts.append('</head>')
    html_parts.append('<body>')
    
    # Add main title
    html_parts.append(f'    <h1>{title}</h1>')
    
    # Add main image if exists
    if main_image:
        html_parts.append('    <figure class="main-image">')
        html_parts.append(f'        <img src="{main_image}" alt="Main article image" loading="lazy">')
        html_parts.append('    </figure>')
    
    # Add video if exists
    if video_link:
        video_id = video_link.split('v=')[-1].split('&')[0]
        html_parts.append('    <div class="video-container">')
        html_parts.append(f'        <iframe src="https://www.youtube.com/embed/{video_id}" ')
        html_parts.append('                allowfullscreen></iframe>')
        html_parts.append('    </div>')
    
    # Add all sections
    for section in sections:
        # Add heading
        heading_tag = section['heading_tag']
        heading_text = section["heading"]
        html_parts.append(f'    <{heading_tag}>{heading_text}</{heading_tag}>')
        
        # IMPORTANT: Add images right after heading (ScreenRant layout)
        section_images = section.get('images', [])
        if section_images:
            for img_data in section_images:
                html_parts.append('    <figure>')
                
                img_attrs = []
                img_attrs.append(f'src="{img_data["src"]}"')
                if img_data.get('alt'):
                    img_alt_escaped = img_data['alt'].replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
                    img_attrs.append(f'alt="{img_alt_escaped}"')
                if img_data.get('width'):
                    img_attrs.append(f'width="{img_data["width"]}"')
                if img_data.get('height'):
                    img_attrs.append(f'height="{img_data["height"]}"')
                img_attrs.append('loading="lazy"')
                
                html_parts.append(f'        <img {" ".join(img_attrs)}>')
                
                if img_data.get('caption'):
                    caption_escaped = img_data['caption'].replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
                    html_parts.append(f'        <figcaption>{caption_escaped}</figcaption>')
                
                html_parts.append('    </figure>')
        
        # Add paragraphs after images
        section_paragraphs = section.get('paragraphs', [])
        for para in section_paragraphs:
            # Escape any HTML in paragraphs but preserve the text
            para_text = str(para).replace('<', '&lt;').replace('>', '&gt;')
            html_parts.append(f'    <p>{para_text}</p>')
    
    html_parts.append('</body>')
    html_parts.append('</html>')
    
    return '\n'.join(html_parts)
