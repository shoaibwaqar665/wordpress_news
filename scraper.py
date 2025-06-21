from newspaper import Article
import os
import re
from urllib.parse import urlparse
import json

from blog import blog_main

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

def scraper_main(url, category):
    
    result = scrape_url(url)
    if result:
        blog_main(result['topic'],result['text'],result['url'],result['title'],category)
        return result['topic'], result['title'], result['url']
    return None


if __name__ == "__main__":
    scraper_main("Health")
