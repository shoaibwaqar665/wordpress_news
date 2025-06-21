from newspaper import Article
import os
import re
from urllib.parse import urlparse
import json

def clean_filename(url):
    """Convert URL to a valid filename"""
    # Parse the URL to get domain and path
    parsed = urlparse(url)
    domain = parsed.netloc.replace('www.', '').replace('.', '_')
    path = parsed.path.strip('/').replace('/', '_')
    
    # Combine domain and path, clean up special characters
    filename = f"{domain}_{path}" if path else domain
    filename = re.sub(r'[^\w\-_.]', '_', filename)
    filename = filename.strip('_')
    
    return filename

def extract_topic_from_title(title):
    """Extract a clean topic from the article title"""
    if not title:
        return "Technology News"
    
    # Remove common suffixes and prefixes
    title = re.sub(r'\s*[-|]\s*.*$', '', title)  # Remove everything after dash or pipe
    title = re.sub(r'^\s*[A-Z\s]+\s*[-|]\s*', '', title)  # Remove prefix like "TECHNOLOGY -"
    title = re.sub(r'\s*•\s*.*$', '', title)  # Remove everything after bullet
    title = re.sub(r'\s*\|.*$', '', title)  # Remove everything after pipe
    
    # Clean up the title
    title = title.strip()
    title = re.sub(r'\s+', ' ', title)  # Replace multiple spaces with single space
    
    # If title is too short, add context
    if len(title) < 10:
        title = f"Technology News: {title}"
    
    return title

def scrape_url(url):
    """Scrape a single URL and return title and text"""
    try:
        print(f"Scraping: {url}")
        article = Article(url)
        article.download()
        article.parse()
        
        # Extract topic from title
        topic = extract_topic_from_title(article.title)
        
        return {
            'topic': topic,
            'title': article.title,
            'text': article.text,
            'url': url
        }
    except Exception as e:
        print(f"Error scraping {url}: {str(e)}")
        return None

def main():
    # Read URLs from content.txt
    with open('content_2.txt', 'r') as f:
        urls = [line.strip() for line in f if line.strip()]
    
    print(f"Found {len(urls)} URLs to scrape")
    
    # Create output directory if it doesn't exist
    output_dir = 'scraped_articles'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Store all scraped data for main.py
    scraped_data = []
    
    # Scrape each URL
    for url in urls:
        result = scrape_url(url)
        
        if result:
            # Create filename from URL
            filename = clean_filename(url)
            filepath = os.path.join(output_dir, f"{filename}.txt")
            
            # Save to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"URL: {result['url']}\n")
                f.write(f"Topic: {result['topic']}\n")
                f.write(f"Title: {result['title']}\n")
                f.write(f"{'='*50}\n")
                f.write(result['text'])
            
            # Add to scraped_data for main.py
            scraped_data.append({
                'topic': result['topic'],
                'content': result['text'],
                'url': result['url'],
                'original_title': result['title'],
                'category': 'Technology'
            })
            
            print(f"Saved: {filepath}")
        else:
            print(f"Failed to scrape: {url}")
    
    # Save all data in JSON format for main.py to read
    with open('scraped_data.json', 'w', encoding='utf-8') as f:
        json.dump(scraped_data, f, indent=4, ensure_ascii=False)
    
    print(f"✅ Scraping completed! {len(scraped_data)} articles scraped successfully.")
    print("📄 Data saved to scraped_data.json for main.py to process.")

if __name__ == "__main__":
    main()
