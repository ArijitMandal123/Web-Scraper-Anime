import re
from urllib.parse import urljoin
import html
from bs4 import BeautifulSoup

def parse_animecorner(soup, base_url):
    """
    Parse AnimeCorner article.
    
    Returns:
        dict: {
            'description': str,
            'main_image': str,
            'side_images': list of dict with full metadata,
            'video_link': str,
            'html_content': str (reconstructed HTML),
        }
    """
    
    # 1. Get Title
    title_el = soup.find('h1', class_='post-title') or soup.find('h1', class_='entry-title')
    title = title_el.text.strip() if title_el else ""
    
    # 2. Get Main Image
    main_image = ""
    # Main image is usually before the entry-content, or inside post-image
    main_img_el = soup.find('div', class_='post-image')
    if main_img_el:
        img = main_img_el.find('img')
        if img:
            main_image = img.get('data-src') or img.get('src', '')
            if main_image and main_image.startswith('data:'):
                main_image = ""
                
    # 3. Find article content
    entry_content = soup.find('div', class_='entry-content') or soup.find('div', class_='inner-post-entry')
    if not entry_content:
        return {
            'status': 'error',
            'message': 'Could not find entry-content div'
        }
        
    # Remove unwanted sections like share boxes or author bio inside content if any
    for unwanted in entry_content.find_all(class_=['post-share', 'tags-share-box', 'post-tags', 'post-author']):
        unwanted.decompose()
    
    # 4. Extract sections
    sections = []
    current_section = {
        'header': None,
        'elements': []
    }
    
    for child in entry_content.children:
        if child.name is None:
            continue
            
        if child.name in ['h2', 'h3', 'h1', 'h4']:
            if current_section['header'] is not None or current_section['elements']:
                sections.append(current_section)
            current_section = {
                'header': child,
                'elements': []
            }
        else:
            if child.name == 'p' and not child.text.strip() and not child.find('img'):
                continue
            if child.name in ['script', 'style', 'iframe', 'div'] and not child.find('img'):
                # keep youtube embeds if any
                if child.name == 'iframe' and 'youtube' in (child.get('src') or ''):
                    current_section['elements'].append(child)
                continue
            
            current_section['elements'].append(child)
            
    if current_section['header'] is not None or current_section['elements']:
        sections.append(current_section)
        
    side_images = []
    seen_image_srcs = set()
    if main_image:
        seen_image_srcs.add(main_image)
        
    reconstructed_html = f"<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n    <meta charset=\"UTF-8\">\n    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n    <title>{title}</title>\n    <style>\n        body {{ font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, sans-serif; \n               max-width: 800px; margin: 40px auto; padding: 0 20px; \n               line-height: 1.6; color: #333; background: #fff; }}\n        h1 {{ font-size: 2.5em; margin-bottom: 20px; font-weight: 700; }}\n        h2 {{ font-size: 1.8em; margin-top: 30px; margin-bottom: 15px; font-weight: 600; }}\n        h3 {{ font-size: 1.4em; margin-top: 25px; margin-bottom: 12px; font-weight: 600; }}\n        figure {{ margin: 30px 0; }}\n        figure img {{ width: 100%; height: auto; display: block; }}\n        figcaption {{ font-size: 0.9em; color: #666; margin-top: 8px; font-style: italic; }}\n        p {{ margin: 15px 0; font-size: 1.1em; }}\n    </style>\n</head>\n<body>\n"
    
    reconstructed_html += f"    <h1>{title}</h1>\n"
    if main_image:
        reconstructed_html += f'    <figure class="main-image">\n        <img src="{main_image}" alt="Main article image" loading="lazy">\n    </figure>\n'
        
    for section in sections:
        if section['header']:
            header_text = section['header'].text.strip()
            header_tag = section['header'].name
            reconstructed_html += f"    <{header_tag}>{header_text}</{header_tag}>\n"
            
        for el in section['elements']:
            imgs = el.find_all('img')
            for img in imgs:
                src = img.get('data-src') or img.get('data-lazy-src') or img.get('src')
                if src and not src.startswith('data:'):
                    # Clean up URL
                    src = src.split('?')[0]
                    
                    if src not in seen_image_srcs:
                        alt = img.get('alt', '')
                        width = img.get('width', '')
                        height = img.get('height', '')
                        
                        caption_text = ""
                        figcaption = el.find_parent('figure')
                        if figcaption and figcaption.find('figcaption'):
                            caption_text = figcaption.find('figcaption').text.strip()
                            
                        img_data = {
                            'src': src,
                            'alt': alt,
                            'class': 'content-image',
                            'width': width,
                            'height': height,
                            'loading': 'lazy',
                            'caption': caption_text or alt
                        }
                        side_images.append(img_data)
                        seen_image_srcs.add(src)
                        
                        reconstructed_html += f'    <figure>\n        <img src="{src}" alt="{html.escape(alt)}" width="{width}" height="{height}" loading="lazy">\n'
                        if caption_text:
                            reconstructed_html += f'        <figcaption>{html.escape(caption_text)}</figcaption>\n'
                        elif alt:
                            reconstructed_html += f'        <figcaption>{html.escape(alt)}</figcaption>\n'
                        reconstructed_html += f'    </figure>\n'
            
            # Add text content
            if el.name == 'p':
                text = el.text.strip()
                if text:
                    reconstructed_html += f'    <p>{html.escape(text)}</p>\n'
            elif el.name in ['ul', 'ol']:
                reconstructed_html += f'    <{el.name}>\n'
                for li in el.find_all('li'):
                    reconstructed_html += f'        <li>{html.escape(li.text.strip())}</li>\n'
                reconstructed_html += f'    </{el.name}>\n'
            elif el.name == 'blockquote':
                reconstructed_html += f'    <blockquote>{html.escape(el.text.strip())}</blockquote>\n'

    reconstructed_html += "</body>\n</html>"
    
    description = ""
    first_p = entry_content.find('p')
    if first_p:
        description = first_p.text.strip()
        
    return {
        'description': description,
        'main_image': main_image,
        'side_images': side_images,
        'video_link': "",
        'html_content': reconstructed_html
    }
