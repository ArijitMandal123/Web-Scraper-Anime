import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup

def parse_dotesports(soup, base_url):
    """
    Parse DotEsports article.
    """
    data = {
        'description': '',
        'main_image': None,
        'side_images': [],
        'video_link': None,
        'html_content': '',
        'max_side_images': 50
    }
    
    # Main Image
    og_image = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'twitter:image'})
    if og_image:
        data['main_image'] = og_image.get('content')
        
    # Try to find main content wrapper
    content_body = soup.find('div', class_='wp-block-gamurs-article-content')
    if not content_body:
        return data
        
    all_text = []
    seen_images = set()
    if data['main_image']:
        seen_images.add(data['main_image'])
        
    sections = []
    current_section = {
        'heading': None,
        'heading_tag': None,
        'images': [],
        'paragraphs': []
    }
    
    # Extract headers, paragraphs, and images
    for elem in content_body.find_all(['p', 'h2', 'h3', 'figure', 'img']):
        if elem.name == 'p':
            text = elem.get_text(strip=True)
            if text and len(text) > 5:
                current_section['paragraphs'].append(text)
                all_text.append(text)
        elif elem.name in ['h2', 'h3']:
            if current_section['paragraphs'] or current_section['images']:
                sections.append(current_section)
            current_section = {
                'heading': elem.get_text(strip=True),
                'heading_tag': elem.name,
                'images': [],
                'paragraphs': []
            }
        elif elem.name == 'figure' or elem.name == 'img':
            if elem.name == 'figure':
                img_tag = elem.find('img')
            else:
                if elem.find_parent('figure'):
                    continue
                img_tag = elem
                
            if img_tag:
                src = img_tag.get('data-src') or img_tag.get('src')
                        
                if src and not src.startswith('data:'):
                    # Ensure absolute URL
                    if not src.startswith('http'):
                        src = urljoin(base_url, src)
                        
                    # Exclude obvious junk
                    is_junk = any(j in src.lower() for j in ['logo', 'avatar', 'author', 'icon'])
                    
                    if not is_junk and src not in seen_images:
                        caption = ''
                        if elem.name == 'figure':
                            caption_elem = elem.find('figcaption')
                            if caption_elem:
                                caption = caption_elem.get_text(strip=True)
                                
                        img_data = {
                            'src': src,
                            'alt': img_tag.get('alt', ''),
                            'width': img_tag.get('width', ''),
                            'height': img_tag.get('height', ''),
                            'caption': caption,
                            'loading': 'lazy',
                            'class': ' '.join(img_tag.get('class', [])) if isinstance(img_tag.get('class'), list) else str(img_tag.get('class', ''))
                        }
                        current_section['images'].append(img_data)
                        data['side_images'].append(img_data)
                        seen_images.add(src)
                        
    if current_section['paragraphs'] or current_section['images']:
        sections.append(current_section)
        
    data['description'] = '\n\n'.join(all_text)
    
    # Check for youtube videos in iframe
    for iframe in soup.find_all('iframe'):
        src = iframe.get('src') or iframe.get('data-src') or ''
        if 'youtube' in src or 'youtu.be' in src:
            match = re.search(r'(?:v=|/embed/|/1/|/v/|https://youtu\.be/)([^#&?]{11})', src)
            if match:
                data['video_link'] = f"https://www.youtube.com/watch?v={match.group(1)}"
                break
                
    # Reconstruct HTML
    title_elem = soup.find('h1', class_=re.compile(r'title|header'))
    if not title_elem:
        title_elem = soup.find('h1')
    title = title_elem.get_text(strip=True) if title_elem else (soup.title.string.strip() if soup.title else "DotEsports Article")
    
    html_parts = [
        '<!DOCTYPE html>',
        '<html lang="en">',
        '<head>',
        '    <meta charset="UTF-8">',
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f'    <title>{title}</title>',
        '    <style>',
        '        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;',
        '               max-width: 800px; margin: 40px auto; padding: 0 20px;',
        '               line-height: 1.6; color: #333; background: #fff; }',
        '        h1 { font-size: 2.5em; margin-bottom: 20px; font-weight: 700; }',
        '        h2 { font-size: 1.8em; margin-top: 30px; margin-bottom: 15px; font-weight: 600; }',
        '        h3 { font-size: 1.4em; margin-top: 25px; margin-bottom: 12px; font-weight: 600; }',
        '        figure { margin: 30px 0; }',
        '        figure img { width: 100%; height: auto; display: block; }',
        '        figcaption { font-size: 0.9em; color: #666; margin-top: 8px; font-style: italic; }',
        '        p { margin: 15px 0; font-size: 1.1em; }',
        '        .video-container { margin: 30px 0; }',
        '        .video-container iframe { width: 100%; aspect-ratio: 16/9; border: none; }',
        '    </style>',
        '</head>',
        '<body>',
        f'    <h1>{title}</h1>'
    ]
    
    if data['main_image']:
        html_parts.append('    <figure class="main-image">')
        html_parts.append(f'        <img src="{data["main_image"]}" alt="Main article image" loading="lazy">')
        html_parts.append('    </figure>')
        
    if data['video_link']:
        video_id = data['video_link'].split('v=')[-1].split('&')[0]
        html_parts.append('    <div class="video-container">')
        html_parts.append(f'        <iframe src="https://www.youtube.com/embed/{video_id}" allowfullscreen></iframe>')
        html_parts.append('    </div>')
        
    for sec in sections:
        if sec['heading']:
            html_parts.append(f'    <{sec["heading_tag"]}>{sec["heading"]}</{sec["heading_tag"]}>')
            
        for img in sec['images']:
            html_parts.append('    <figure>')
            alt = img['alt'].replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
            html_parts.append(f'        <img src="{img["src"]}" alt="{alt}" loading="lazy">')
            if img.get('caption'):
                cap = img['caption'].replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
                html_parts.append(f'        <figcaption>{cap}</figcaption>')
            html_parts.append('    </figure>')
            
        for p in sec['paragraphs']:
            p_text = str(p).replace('<', '&lt;').replace('>', '&gt;')
            html_parts.append(f'    <p>{p_text}</p>')
            
    html_parts.append('</body>\n</html>')
    
    data['html_content'] = '\n'.join(html_parts)
    
    return data
