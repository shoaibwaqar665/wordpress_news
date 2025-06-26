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
model = genai.GenerativeModel("gemini-2.0-flash-lite")


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
    Assigns the most appropriate categories to the given content
    based on a list of categories using Gemini 2.0 Flash.
    """
    try:
        # Format categories as bullet list
        formatted_categories = "\n".join(f"- {cat}" for cat in categories_data)

        # Construct the prompt
        prompt = f"""
You are an expert content classifier. Given the content and a list of possible categories,
choose the **most relevant categories** from the list that best match the content.

Return the categories as a comma-separated list.

Content:
\"\"\"
{content}
\"\"\"

Categories:
{formatted_categories}

Respond with only the category names from the list above, separated by commas.
"""

        response = model.generate_content(prompt)
        prediction = response.text.strip()

        # Basic cleanup / normalization
        prediction = prediction.strip('"\'')
        
        # Split by comma and clean up each category
        predicted_categories = [cat.strip() for cat in prediction.split(',')]
        
        # Filter to only include valid categories
        valid_categories = []
        invalid_categories = []
        
        for cat in predicted_categories:
            if cat in categories_data:
                valid_categories.append(cat)
            else:
                invalid_categories.append(cat)
        
        if invalid_categories:
            print(f"[⚠️] Model responded with unexpected categories: {invalid_categories}")
        
        return valid_categories

    except Exception as e:
        print(f"[🔥 Error] Failed to assign categories: {e}")
        return []


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
