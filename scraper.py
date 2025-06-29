from newspaper import Article
import os
import re
from urllib.parse import urlparse
import json
import google.generativeai as genai
import os
from dotenv import load_dotenv
from blog import blog_main, send_email_notification_blog
from dbOperations import get_categories_data, get_urls, soft_delete_url
import time
from datetime import datetime, timedelta

load_dotenv()

# Global flag to prevent multiple scraping instances
scraping_in_progress = False

# Rate limiting tracking
class RateLimiter:
    def __init__(self):
        self.primary_requests = []  # Flash requests
        self.fallback_requests = []  # Flash-Lite requests
        self.fallback_pro_requests = []  # 2.5 Pro requests
        self.fallback_flash_requests = []  # 2.5 Flash requests
        
        # Rate limits for different models
        self.primary_rpm = 15  # Gemini 2.0 Flash RPM
        self.fallback_rpm = 30  # Gemini 2.0 Flash-Lite RPM
        self.fallback_pro_rpm = 20  # Gemini 2.5 Pro RPM (estimated)
        self.fallback_flash_rpm = 25  # Gemini 2.5 Flash RPM (estimated)
        
        self.primary_tpm = 1000000  # Flash TPM
        self.fallback_tpm = 1000000  # Flash-Lite TPM
        self.fallback_pro_tpm = 1000000  # 2.5 Pro TPM
        self.fallback_flash_tpm = 1000000  # 2.5 Flash TPM
        
        self.primary_rpd = 200  # Flash RPD
        self.fallback_rpd = 200  # Flash-Lite RPD
        self.fallback_pro_rpd = 200  # 2.5 Pro RPD
        self.fallback_flash_rpd = 200  # 2.5 Flash RPD
        
        # Track when all models are rate limited
        self.all_models_rate_limited_time = None
    
    def get_requests_list(self, model_type):
        """Get the appropriate requests list based on model type"""
        if model_type == 'primary':
            return self.primary_requests
        elif model_type == 'fallback':
            return self.fallback_requests
        elif model_type == 'fallback-pro':
            return self.fallback_pro_requests
        elif model_type == 'fallback-flash':
            return self.fallback_flash_requests
        else:
            return self.fallback_requests  # Default to fallback
    
    def get_rpm_limit(self, model_type):
        """Get the RPM limit for the specified model type"""
        if model_type == 'primary':
            return self.primary_rpm
        elif model_type == 'fallback':
            return self.fallback_rpm
        elif model_type == 'fallback-pro':
            return self.fallback_pro_rpm
        elif model_type == 'fallback-flash':
            return self.fallback_flash_rpm
        else:
            return self.fallback_rpm  # Default to fallback
    
    def are_all_models_rate_limited(self):
        """Check if all models have reached their rate limits"""
        model_types = ['primary', 'fallback', 'fallback-flash', 'fallback-pro']
        
        for model_type in model_types:
            if self.can_make_request(model_type):
                return False
        return True
    
    def should_sleep_for_hour(self):
        """Check if we should sleep for an hour due to all models being rate limited"""
        if self.all_models_rate_limited_time is None:
            return False
        
        # Check if 1 hour has passed since all models were rate limited
        time_since_rate_limit = datetime.now() - self.all_models_rate_limited_time
        return time_since_rate_limit.total_seconds() < 3600  # 1 hour in seconds
    
    def mark_all_models_rate_limited(self):
        """Mark that all models are currently rate limited"""
        self.all_models_rate_limited_time = datetime.now()
        print(f"[🚫] All models are rate limited. Sleeping for 1 hour until {self.all_models_rate_limited_time + timedelta(hours=1)}")
    
    def reset_rate_limit_tracking(self):
        """Reset the rate limit tracking when models become available again"""
        self.all_models_rate_limited_time = None
        print("[✅] Rate limit tracking reset - models available again")
    
    def can_make_request(self, model_type='primary'):
        """Check if we can make a request based on rate limits"""
        now = datetime.now()
        window_start = now - timedelta(minutes=1)
        
        requests = self.get_requests_list(model_type)
        rpm_limit = self.get_rpm_limit(model_type)
        
        # Clean old requests (older than 1 minute)
        requests[:] = [req_time for req_time in requests if req_time > window_start]
        
        # Check RPM limit
        if len(requests) >= rpm_limit:
            return False
        
        return True
    
    def record_request(self, model_type='primary'):
        """Record a request for rate limiting"""
        requests = self.get_requests_list(model_type)
        requests.append(datetime.now())
    
    def get_wait_time(self, model_type='primary'):
        """Calculate how long to wait before next request"""
        now = datetime.now()
        window_start = now - timedelta(minutes=1)
        
        requests = self.get_requests_list(model_type)
        rpm_limit = self.get_rpm_limit(model_type)
        
        # Clean old requests
        requests[:] = [req_time for req_time in requests if req_time > window_start]
        
        if len(requests) >= rpm_limit:
            # Find the oldest request in the window
            oldest_request = min(requests)
            wait_until = oldest_request + timedelta(minutes=1)
            return max(0, (wait_until - now).total_seconds())
        
        return 0

# Initialize rate limiter
rate_limiter = RateLimiter()

# Initialize Gemini model
gemini_api_key = os.getenv('GEMINI_API_KEY')
genai.configure(api_key=gemini_api_key)

# Model configurations
MODELS = {
    'primary': "gemini-2.0-flash",
    'fallback': "gemini-2.0-flash-lite",
    'fallback-pro': "gemini-2.5-pro",
    'fallback-flash': "gemini-2.5-flash"
}

current_model_name = 'primary'
model = genai.GenerativeModel(MODELS[current_model_name])

def switch_model():
    """Switch between models in a priority order"""
    global current_model_name, model
    
    # Define switching order based on availability and performance
    model_priority = ['primary', 'fallback', 'fallback-flash', 'fallback-pro']
    
    try:
        # Find current model index
        current_index = model_priority.index(current_model_name)
        # Move to next model in priority list
        next_index = (current_index + 1) % len(model_priority)
        current_model_name = model_priority[next_index]
        
        print(f"[🔄] Switching to model: {MODELS[current_model_name]} ({current_model_name})")
        model = genai.GenerativeModel(MODELS[current_model_name])
        return model
    except ValueError:
        # If current model not in priority list, start with primary
        current_model_name = 'primary'
        print(f"[🔄] Resetting to primary model: {MODELS[current_model_name]}")
        model = genai.GenerativeModel(MODELS[current_model_name])
        return model

def get_model_type():
    """Get the current model type for rate limiting"""
    return current_model_name  # Return the actual model name for proper rate limiting

def wait_for_rate_limit(model_type='primary'):
    """Wait if necessary to respect rate limits"""
    # First check if we should sleep for an hour due to all models being rate limited
    if rate_limiter.should_sleep_for_hour():
        remaining_time = 3600 - (datetime.now() - rate_limiter.all_models_rate_limited_time).total_seconds()
        print(f"[⏰] All models still rate limited. Sleeping for {remaining_time:.0f} more seconds...")
        time.sleep(remaining_time)
        rate_limiter.reset_rate_limit_tracking()
        return True
    
    # Check if all models are currently rate limited
    if rate_limiter.are_all_models_rate_limited():
        rate_limiter.mark_all_models_rate_limited()
        print("[😴] Sleeping for 1 hour due to all models being rate limited...")
        time.sleep(3600)  # Sleep for 1 hour
        rate_limiter.reset_rate_limit_tracking()
        return True
    
    # Normal rate limit waiting for specific model
    wait_time = rate_limiter.get_wait_time(model_type)
    if wait_time > 0:
        print(f"[⏳] Rate limit reached for {model_type} model. Waiting {wait_time:.1f} seconds...")
        time.sleep(wait_time)
    return True

def is_rate_limit_error(error):
    """Check if the error is a rate limiting error"""
    error_str = str(error).lower()
    rate_limit_indicators = [
        'rate limit',
        'quota exceeded',
        'too many requests',
        'rate exceeded',
        'quota limit',
        'resource exhausted',
        '429',
        'rate limit exceeded'
    ]
    return any(indicator in error_str for indicator in rate_limit_indicators)

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


def assign_category_with_gemini(content, categories_data, max_retries=3):
    """
    Assigns the most appropriate categories to the given content
    based on a list of categories using Gemini 2.0 Flash with rate limiting handling.
    """
    global current_model_name, model
    
    for attempt in range(max_retries):
        try:
            # Wait for rate limit before making request
            model_type = get_model_type()
            wait_for_rate_limit(model_type)
            
            # Format categories as bullet list
            formatted_categories = "\n".join(f"- {cat}" for cat in categories_data)

            # Construct the prompt - optimized for token efficiency
            prompt = f"""
Classify this content into the most relevant categories from the list below.
Return only category names separated by commas.

Content: {content[:1500]}  # Limit content to save tokens

Categories:
{formatted_categories}

Categories:"""

            # Record the request for rate limiting
            rate_limiter.record_request(model_type)
            
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
            
            if valid_categories:
                print(f"[✅] Successfully categorized with {model_type} model")
                return valid_categories
            else:
                print(f"[❌] No valid categories found, retrying...")
                continue

        except Exception as e:
            print(f"[🔥 Error] Attempt {attempt + 1}/{max_retries} failed: {e}")
            
            if is_rate_limit_error(e):
                print(f"[⏳] Rate limit detected, switching model...")
                switch_model()
                # Add a longer delay for rate limit errors
                time.sleep(5)
                continue
            else:
                # For non-rate-limit errors, try switching model anyway
                if attempt < max_retries - 1:
                    print(f"[🔄] Non-rate-limit error, trying with different model...")
                    switch_model()
                    time.sleep(2)
                    continue
                else:
                    print(f"[❌] All attempts failed. Final error: {e}")
                    return []
    
    print(f"[❌] Failed to assign categories after {max_retries} attempts")
    return []


def scraper_main(url, category):
    uploaded_urls = []  # Initialize empty array for single URL processing
    result = scrape_url(url)
    if result:
        uploaded_urls = blog_main(result['topic'], result['text'], result['url'], result['title'], category, uploaded_urls)
        return result['topic'], result['title'], result['url'], uploaded_urls
    return None, None, None, []


def scrap_db_urls_and_write_blogs():
    global scraping_in_progress
    
    if scraping_in_progress:
        print("[Scraper] Another scraping instance is already running, skipping...")
        return []
    
    scraping_in_progress = True
    try:
        print(f"[Scraper] Starting scrap_db_urls_and_write_blogs at {datetime.now()}")
        urls = get_urls()
        if not urls:
            print("[Scraper] No URLs found in the database.")
            return []
        print(f"[Scraper] Found {len(urls)} URLs to scrape")
        
        uploaded_urls = []  # Initialize array to collect uploaded posts
        
        for url in urls:
            print(f"[Scraper] Processing URL: {url}")
            result = scrape_url(url)
            if result:
                categories_data = get_categories_data()
                category = assign_category_with_gemini(result['text'], categories_data)
                print(f"[Scraper] Category: {category}")
                if category:
                    # Pass the uploaded_urls array to collect results
                    uploaded_urls = blog_main(result['topic'], result['text'], result['url'], result['title'], category, uploaded_urls)
                    soft_delete_url(url, str(category))
                    time.sleep(5)
                else:
                    print(f"[Scraper] No category found for {url}")
                    continue
            else:
                print(f"[Scraper] No result found for {url}")
                # retry for 3 times
                continue
        
        print(f"[Scraper] Completed scrap_db_urls_and_write_blogs. Uploaded {len(uploaded_urls)} posts.")
        return uploaded_urls
    finally:
        scraping_in_progress = False


