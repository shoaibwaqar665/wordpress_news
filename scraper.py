from newspaper import Article
import os
import re
from urllib.parse import urlparse
import json
import google.generativeai as genai
import os
from dotenv import load_dotenv
from blog import blog_main
from dbOperations import get_categories_data, get_urls, soft_delete_url

load_dotenv()

# Initialize Gemini model
gemini_api_key = os.getenv('GEMINI_API_KEY')
genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel("gemini-2.0-flash")


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


def assign_category_with_gemini(content, categories_data):
    """
    Assigns the most appropriate category to the given content
    based on a list of categories using Gemini 2.0 Flash.
    """
    try:
        # Format categories as bullet list
        formatted_categories = "\n".join(f"- {cat}" for cat in categories_data)

        # Construct the prompt
        prompt = f"""
You are an expert content classifier. Given the content and a list of possible categories,
choose the **one best matching category** from the list.

Only return the exact category name.

Content:
\"\"\"
{content}
\"\"\"

Categories:
{formatted_categories}

Respond with only one category from the list above.
"""

        response = model.generate_content(prompt)
        prediction = response.text.strip()

        # Basic cleanup / normalization
        prediction = prediction.strip('"\'')

        if prediction not in categories_data:
            print(f"[⚠️] Model responded with unexpected category: {prediction}")
            return None
        
        return prediction

    except Exception as e:
        print(f"[🔥 Error] Failed to assign category: {e}")
        return None


def scraper_main(url, category):
    
    result = scrape_url(url)
    if result:
        blog_main(result['topic'],result['text'],result['url'],result['title'],category)
        return result['topic'], result['title'], result['url']
    return None


def scrap_db_urls_and_write_blogs():
    urls = get_urls()
    if not urls:
        print("No URLs found in the database.")
        return None
    print(f"Found {len(urls)} URLs to scrape")
    for url in urls:
        result = scrape_url(url)
        if result:
            categories_data = get_categories_data()
            category = assign_category_with_gemini(result['text'], categories_data)
            print(f"📂 Category: {category}")
            if category:
                blog_main(result['topic'],result['text'],result['url'],result['title'],category)
                soft_delete_url(url,category)
            else:
                print(f"❌ No category found for {url}")
                continue
        else:
            print(f"❌ No result found for {url}")
            return None

if __name__ == "__main__":
    # scraper_main("Health")
    scrap_db_urls_and_write_blogs()
