import requests
from bs4 import BeautifulSoup
import json
import time
from urllib.parse import urljoin, urlparse


url = "https://techpoint.africa/"
# add headers to the request
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
}

def extract_metadata(article_url):
    """Extract metadata from an article page"""
    try:
        response = requests.get(article_url, headers=headers, timeout=10)
        print(f"    [DEBUG] Status code for {article_url}: {response.status_code}")
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract title
        title = ""
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text().strip()
        
        # Extract meta description
        description = ""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            description = meta_desc.get('content', '').strip()
        
        # Extract Open Graph title
        og_title = ""
        og_title_tag = soup.find('meta', attrs={'property': 'og:title'})
        if og_title_tag:
            og_title = og_title_tag.get('content', '').strip()
        
        # Extract Open Graph description
        og_desc = ""
        og_desc_tag = soup.find('meta', attrs={'property': 'og:description'})
        if og_desc_tag:
            og_desc = og_desc_tag.get('content', '').strip()
        
        # Extract author
        author = ""
        author_tag = soup.find('meta', attrs={'name': 'author'})
        if author_tag:
            author = author_tag.get('content', '').strip()
        
        # Try to find author in article content
        if not author:
            author_elements = soup.find_all(['span', 'div', 'p'], class_=lambda x: x and 'author' in x.lower())
            for elem in author_elements:
                if elem.get_text().strip():
                    author = elem.get_text().strip()
                    break
        
        # Extract publication date
        date = ""
        date_tag = soup.find('meta', attrs={'property': 'article:published_time'})
        if date_tag:
            date = date_tag.get('content', '').strip()
        
        # Try to find date in article content
        if not date:
            date_elements = soup.find_all(['time', 'span', 'div'], class_=lambda x: x and 'date' in x.lower())
            for elem in date_elements:
                if elem.get_text().strip():
                    date = elem.get_text().strip()
                    break
        
        # Extract main image
        image = ""
        og_image = soup.find('meta', attrs={'property': 'og:image'})
        if og_image:
            image = og_image.get('content', '').strip()
        
        # Extract article category/tags
        category = ""
        category_elements = soup.find_all(['a', 'span'], class_=lambda x: x and 'category' in x.lower())
        for elem in category_elements:
            if elem.get_text().strip():
                category = elem.get_text().strip()
                break
        
        return {
            'url': article_url,
            'title': title or og_title,
            'description': description or og_desc,
            'author': author,
            'date': date,
            'image': image,
            'category': category
        }
        
    except Exception as e:
        print(f"    [DEBUG] Error extracting metadata from {article_url}: {str(e)}")
        return None

response = requests.get(url, headers=headers)

soup = BeautifulSoup(response.text, 'html.parser')

# print(soup.prettify())

# get all the links in the page
links = soup.find_all('a')
for link in links:
    href = link.get('href')
    if href:  # Only process links that have an href attribute
        print(href)
        # write the link to a file
        with open('links.txt', 'a') as f:
            f.write(href + '\n')

# remove the duplicates from the links.txt file and also remove the links that are not in the url and also remove that are social media links like facebook, twitter, instagram, linkedin, youtube, etc. and contact pages
with open('links.txt', 'r') as f:
    links = f.readlines()
    links = list(set(links))    
    # remove the links that are not in the url
    links = [link for link in links if link.startswith(url)]
    
    # filter out links containing any unwanted patterns
    filtered_links = []
    for link in links:
        link = link.strip()  # remove newlines
        
        # Only include actual article URLs
        article_patterns = ['/news/', '/insight/', '/feature/', '/general/', '/brandpress/']
        is_article = any(pattern in link for pattern in article_patterns)
        
        # Exclude social media and other unwanted links
        unwanted_patterns = [
            'x.com', 'web.facebook.com', 'www.instagram.com', 'www.linkedin.com',
            'forms.techpoint.africa', '/subject/', '/about/', '/contact', '/category/',
            '/editorial-team/', '/newsletter-privacy-policy/', '/brand-press/account/'
        ]
        is_unwanted = any(pattern in link for pattern in unwanted_patterns)
        
        if is_article and not is_unwanted and link != url and link != url.rstrip('/'):
            filtered_links.append(link)
    
    # write the filtered links back to file
    with open('links.txt', 'w') as f:
        for link in filtered_links:
            f.write(link + '\n')

# Now extract metadata from each article link
print("\nExtracting metadata from articles...")
print(f"Found {len(filtered_links)} article links to process")
articles_data = []

for i, link in enumerate(filtered_links):
    link = link.strip()
    if link:  # Process all links
        print(f"Processing {i+1}/{len(filtered_links)}: {link}")
        metadata = extract_metadata(link)
        if metadata:
            articles_data.append(metadata)
            print(f"  ✓ Success: {metadata['title'][:50]}...")
        else:
            print(f"  ✗ Failed to extract metadata")
        time.sleep(1)  # Be respectful to the server

# Save metadata to JSON file
with open('articles_metadata.json', 'w', encoding='utf-8') as f:
    json.dump(articles_data, f, indent=2, ensure_ascii=False)

# Also save a simplified CSV-like format for easy reading
with open('articles_summary.txt', 'w', encoding='utf-8') as f:
    f.write("URL | Title | Author | Date | Category\n")
    f.write("-" * 100 + "\n")
    for article in articles_data:
        f.write(f"{article['url']} | {article['title']} | {article['author']} | {article['date']} | {article['category']}\n")

print(f"\nExtracted metadata from {len(articles_data)} articles")
print("Data saved to 'articles_metadata.json' and 'articles_summary.txt'")




