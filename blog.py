import requests
import base64
import google.generativeai as genai
import os
from dotenv import load_dotenv
import re
from difflib import SequenceMatcher
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import time
from datetime import datetime, timedelta

from dbOperations import get_categories_data, update_my_blog_url

# Load environment variables
load_dotenv()

# Rate limiting tracking for blog content generation
class BlogRateLimiter:
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

# Initialize blog rate limiter
blog_rate_limiter = BlogRateLimiter()

# WordPress credentials from environment variables
username = os.getenv('WORDPRESS_USERNAME')
password = os.getenv('WORDPRESS_PASSWORD')
wordpress_url = os.getenv('WORDPRESS_URL')

# Unsplash API credentials
unsplash_access_key = os.getenv('UNSPLASH_ACCESS_KEY')

# Validate environment variables
if not all([username, password, wordpress_url]):
    raise ValueError("Missing required environment variables. Please check your .env file.")

if not unsplash_access_key:
    print("⚠️ Warning: UNSPLASH_ACCESS_KEY not found. Image functionality will be limited.")

credentials = username + ':' + password
cred_token = base64.b64encode(credentials.encode())

url = f'{wordpress_url}/wp-json/wp/v2/posts'
header = {'Authorization': 'Basic ' + cred_token.decode('utf-8')}

# Configure Gemini AI
gemini_api_key = os.getenv('GEMINI_API_KEY')
if not gemini_api_key:
    raise ValueError("Missing GEMINI_API_KEY in environment variables.")

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
    if blog_rate_limiter.should_sleep_for_hour():
        remaining_time = 3600 - (datetime.now() - blog_rate_limiter.all_models_rate_limited_time).total_seconds()
        print(f"[⏰] All models still rate limited. Sleeping for {remaining_time:.0f} more seconds...")
        time.sleep(remaining_time)
        blog_rate_limiter.reset_rate_limit_tracking()
        return True
    
    # Check if all models are currently rate limited
    if blog_rate_limiter.are_all_models_rate_limited():
        blog_rate_limiter.mark_all_models_rate_limited()
        print("[😴] Sleeping for 1 hour due to all models being rate limited...")
        time.sleep(3600)  # Sleep for 1 hour
        blog_rate_limiter.reset_rate_limit_tracking()
        return True
    
    # Normal rate limit waiting for specific model
    wait_time = blog_rate_limiter.get_wait_time(model_type)
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

def generate_content_with_retry(prompt, max_retries=3):
    """Generate content with retry logic and model switching"""
    global current_model_name, model
    
    for attempt in range(max_retries):
        try:
            # Wait for rate limit before making request
            model_type = get_model_type()
            wait_for_rate_limit(model_type)
            
            # Record the request for rate limiting
            blog_rate_limiter.record_request(model_type)
            
            response = model.generate_content(prompt)
            content = response.text.strip()
            
            if content:
                print(f"[✅] Successfully generated content with {model_type} model")
                return content
            else:
                print(f"[❌] Empty response from {model_type} model, retrying...")
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
                    return None
    
    print(f"[❌] Failed to generate content after {max_retries} attempts")
    return None

def get_categories():
    """Fetch all categories from WordPress, handling pagination."""
    categories = []
    page = 1
    while True:
        categories_url = f'{wordpress_url}/wp-json/wp/v2/categories?per_page=100&page={page}'
        try:
            response = requests.get(categories_url, headers=header)
            if response.status_code == 200:
                page_data = response.json()
                if not page_data:
                    break
                categories.extend(page_data)
                page += 1
            else:
                print(f"❌ Error fetching categories: {response.status_code}")
                break
        except Exception as e:
            print(f"❌ Exception while fetching categories: {e}")
            break

    return categories


def get_category_id_by_name(category_names):
    """Get category IDs by names (accepts single name or list of names)"""
    # Convert single string to list for consistent processing
    if isinstance(category_names, str):
        category_names = [category_names]
    
    categories = get_categories()
    matching_ids = []
    not_found_names = []
    
    for category_name in category_names:
        found = False
        for category in categories:
            if category['name'].lower() == category_name.lower():
                matching_ids.append(category['id'])
                found = True
                break
        
        if not found:
            not_found_names.append(category_name)
    
    # If any categories not found, print available categories
    if not_found_names:
        print(f"❌ Categories not found: {', '.join(not_found_names)}")
        print("Available categories:")
        for category in categories:
            print(f"  - {category['name']} (ID: {category['id']})")
    
    return matching_ids

def create_category_if_not_exists(category_name):
    """Create a new category if it doesn't exist"""
    categories_url = f'{wordpress_url}/wp-json/wp/v2/categories'
    category_data = {
        'name': category_name,
        'slug': category_name.lower().replace(' ', '-')
    }
    
    try:
        response = requests.post(categories_url, headers=header, json=category_data)
        if response.status_code == 201:
            print(f"✅ Created new category: {category_name}")
            return response.json()['id']
        else:
            print(f"❌ Error creating category: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error creating category: {e}")
        return None

def is_similar(a, b, threshold=0.85):
    return SequenceMatcher(None, a, b).ratio() > threshold

def remove_near_duplicates(paragraphs, threshold=0.85):
    unique_paragraphs = []
    for para in paragraphs:
        if not any(is_similar(para, up, threshold) for up in unique_paragraphs):
            unique_paragraphs.append(para)
    return unique_paragraphs

def is_english_content(text):
    """Check if the content is primarily in English"""
    import re
    
    # Common English words and patterns
    english_patterns = [
        r'\b(the|and|or|but|in|on|at|to|for|of|with|by|from|up|about|into|through|during|before|after|above|below|between|among|within|without|against|toward|towards|upon|across|behind|beneath|beside|beyond|inside|outside|under|over|throughout|underneath|along|around|down|off|out|past|since|until|upon|via|per|except|like|unlike|as|than|despite|according|regarding|concerning|including|excluding|following|preceding|during|while|when|where|why|how|what|which|who|whom|whose|this|that|these|those|i|you|he|she|it|we|they|me|him|her|us|them|my|your|his|her|its|our|their|mine|yours|his|hers|ours|theirs|myself|yourself|himself|herself|itself|ourselves|yourselves|themselves|am|is|are|was|were|be|been|being|have|has|had|do|does|did|will|would|could|should|may|might|must|can|shall|ought|need|dare|used|going|gonna|wanna|gotta|lemme|gimme|wanna|gotta|lemme|gimme|wanna|gotta|lemme|gimme)\b',
        r'\b(a|an|and|are|as|at|be|by|for|from|has|he|in|is|it|its|may|not|of|on|or|that|the|to|was|will|with|the|and|for|are|but|not|you|all|any|can|had|her|was|one|our|out|day|get|has|him|his|how|man|new|now|old|see|two|way|who|boy|did|its|let|put|say|she|too|use)\b'
    ]
    
    # Count English words
    english_word_count = 0
    total_word_count = 0
    
    # Split text into words
    words = re.findall(r'\b\w+\b', text.lower())
    total_word_count = len(words)
    
    if total_word_count == 0:
        return True  # Assume English if no words found
    
    # Check for English patterns
    for pattern in english_patterns:
        english_word_count += len(re.findall(pattern, text.lower()))
    
    # Calculate percentage of English words
    english_percentage = english_word_count / total_word_count if total_word_count > 0 else 0
    
    # Also check for common non-English characters
    non_english_chars = re.findall(r'[àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿāăąćĉċčďđēĕėęěĝğġģĥħĩīĭįıĳĵķĸĺļľŀłńņňŉŋōŏőœŕŗřśŝşšſţťŧũūŭůűųŵŷźżž]', text.lower())
    
    # If there are many non-English characters, it's likely not English
    if len(non_english_chars) > len(text) * 0.1:  # More than 10% non-English chars
        return False
    
    # Consider it English if more than 60% of words match English patterns
    return english_percentage > 0.6

def generate_blog_content(topic):
    """Generate blog content using Gemini AI"""
    
    # Optimized prompt for token efficiency
    main_prompt = f"""
Write a comprehensive blog post about '{topic}' (800-1000 words).

Structure:
1. Main heading (## format)
2. 2 introduction paragraphs
3. 3-4 sections with ## headings
4. 1-2 conclusion paragraphs

Requirements:
- If the topic contains text in a language other than English, translate it to English first
- SEO-optimized content
- Professional language
- Specific examples and data
- No markdown formatting except ## headings
- Start directly with main heading
- Do not use 'Introduction' as heading
- Ensure all content is in clear, professional English

Topic: {topic}

Content:"""

    try:
        # Generate main content using retry logic
        content = generate_content_with_retry(main_prompt)
        
        if not content:
            print("❌ Failed to generate content after all retries")
            return None
        
        # Clean the content thoroughly
        content = clean_content(content, topic)
        
        # Convert to proper HTML format for WordPress
        content = convert_to_html(content)
        
        # Generate keywords separately
        keywords = generate_keywords(topic)
        
        # Add keywords section with proper formatting
        keywords_section = f"""
<h3>Keywords</h3>
<p><strong>Related Keywords:</strong> {keywords}</p>
"""
        
        # Combine content with keywords
        final_content = f"{content}\n{keywords_section}"
        
        return final_content
        
    except Exception as e:
        print(f"Error generating content: {e}")
        return None

def rewrite_title_with_ai(original_title, topic):
    """Rewrite the title using AI to make it more engaging and SEO-friendly, ensuring complete sentences and proper meaning."""
    import re
    
    MAX_TITLE_LENGTH = 80  # Increased from 60 to allow for more complete sentences
    
    def is_bad_title(title):
        # Check if title contains non-English characters (common in other languages)
        non_english_chars = re.findall(r'[^\x00-\x7F\u00A0-\u00FF\u0100-\u017F\u0180-\u024F\u1E00-\u1EFF\u2C60-\u2C7F\uA720-\uA7FF]', title)
        if non_english_chars:
            print(f"[⚠️] Title contains non-English characters: {non_english_chars}")
            return True
            
        # Patterns to avoid (case-insensitive)
        bad_patterns = [
            r"here are a few options",
            r"prioritizing seo",
            r"engagement",
            r"keeping (in mind|the african tech context)",
            r"character[s]?",
            r"option[s]?",
            r"context",
            r"limit[s]?",
            r"list",
            r"seo",
            r"african tech context",
            r"\d+ character[s]?",
            r"\d+ option[s]?",
            r"\d+ character[s]?",
            r"\d+ word[s]?",
            r"\d+ headline[s]?",
            r"headline[s]?",
            r"title[s]?",
            r"meta",
            r"instruction[s]?",
            r"suggestion[s]?",
            r"example[s]?",
            r"catchy title[s]?",
            r"engaging title[s]?",
            r"seo[- ]?friendly",
            r"african tech context",
            r"keeping.*context",
            r"option[s]?",
            r"option[s]?:",
            r"option[s]? -",
            r"option[s]?:",
            r"option[s]? ",
            r"option[s]?\d*",
            r"\d+ option[s]?",
            r"\d+ character[s]?",
            r"\d+ headline[s]?",
            r"\d+ title[s]?",
            r"\d+ suggestion[s]?",
            r"\d+ example[s]?",
            r"\d+ list[s]?",
            r"list of",
            r"list:"
        ]
        title_lower = title.lower()
        for pat in bad_patterns:
            if re.search(pat, title_lower):
                return True
        # Avoid titles that are just a list or meta-instructions
        if any(sep in title_lower for sep in [":", "-", "|", ","]):
            # If the title is just a list of options, not a real headline
            if len(title_lower.split()) < 8 and (":" in title_lower or "," in title_lower):
                return True
        # Avoid titles that are too generic or not meaningful
        if len(title_lower) < 10:
            return True
        # Avoid titles that are too long
        if len(title) > MAX_TITLE_LENGTH:
            return True
        return False

    def create_intelligent_fallback_title(topic, original_title):
        """Create a meaningful fallback title when AI generation fails."""
        # Clean the topic and original title
        clean_topic = re.sub(r'[^\w\s]', ' ', topic).strip()
        clean_original = re.sub(r'[^\w\s]', ' ', original_title).strip()
        
        # Try to extract meaningful words
        meaningful_words = []
        
        # Add words from topic (prioritize longer, more meaningful words)
        topic_words = [word for word in clean_topic.split() if len(word) > 3]
        meaningful_words.extend(topic_words[:4])
        
        # Add words from original title if different from topic
        if clean_original.lower() != clean_topic.lower():
            original_words = [word for word in clean_original.split() if len(word) > 3]
            meaningful_words.extend(original_words[:3])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_words = []
        for word in meaningful_words:
            if word.lower() not in seen:
                seen.add(word.lower())
                unique_words.append(word)
        
        # Create a meaningful title
        if len(unique_words) >= 3:
            # Try to create a complete sentence
            base_title = ' '.join(unique_words[:6])
            
            # Add context words to make it more meaningful
            context_words = ['Technology', 'Innovation', 'Development', 'News', 'Update', 'Trend']
            
            # Check if the title already has a context word
            has_context = any(word.lower() in base_title.lower() for word in context_words)
            
            if not has_context and len(base_title) < 40:
                # Add a context word to make it more meaningful
                base_title = f"{context_words[0]} {base_title}"
            
            return base_title
        else:
            # Fallback to a generic but meaningful title
            return "Latest Technology News and Updates"

    def ensure_complete_sentence(title):
        """Ensure the title forms a complete sentence or meaningful phrase."""
        # Remove trailing punctuation that might indicate incomplete sentences
        title = re.sub(r'[,\s]+$', '', title)
        
        # If title ends with incomplete words (like "tech" instead of "technology"), try to complete them
        common_incomplete_endings = {
            'tech': 'technology',
            'dev': 'development',
            'innov': 'innovation',
            'start': 'startup',
            'fin': 'finance',
            'crypt': 'cryptocurrency',
            'block': 'blockchain',
            'artif': 'artificial',
            'intell': 'intelligence',
            'mach': 'machine',
            'learn': 'learning',
            'data': 'data',
            'cloud': 'cloud',
            'cyber': 'cybersecurity',
            'digit': 'digital',
            'mob': 'mobile',
            'web': 'web',
            'app': 'application',
            'soft': 'software',
            'hard': 'hardware'
        }
        
        words = title.split()
        if words:
            last_word = words[-1].lower()
            for incomplete, complete in common_incomplete_endings.items():
                if last_word.startswith(incomplete) and len(last_word) <= len(incomplete) + 2:
                    words[-1] = complete
                    title = ' '.join(words)
                    break
        
        return title

    # Detect if the original title or topic is in a non-English language
    def detect_language(text):
        """Simple language detection for common non-English patterns."""
        # Common non-English character patterns
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        arabic_chars = re.findall(r'[\u0600-\u06ff]', text)
        cyrillic_chars = re.findall(r'[\u0400-\u04ff]', text)
        hindi_chars = re.findall(r'[\u0900-\u097f]', text)
        
        if chinese_chars:
            return "Chinese"
        elif arabic_chars:
            return "Arabic"
        elif cyrillic_chars:
            return "Cyrillic"
        elif hindi_chars:
            return "Hindi"
        else:
            return "English"

    detected_lang = detect_language(original_title + " " + topic)
    
    if detected_lang != "English":
        print(f"[🌐] Detected {detected_lang} language, will translate to English")

    title_prompt = f"""
Create an engaging and SEO-friendly title for this article (under {MAX_TITLE_LENGTH} characters):

Original: {original_title}
Topic: {topic}

IMPORTANT REQUIREMENTS:
- ALWAYS output the title in English only
- If the original is not in English, translate the meaning to English first
- The title must be a complete sentence or meaningful phrase
- Catchy and click-worthy
- Under {MAX_TITLE_LENGTH} characters
- Use action words and be specific
- Relevant to African tech context
- No hashtags or special formatting
- Do NOT use phrases like 'Here are a few options', 'SEO', 'engagement', 'context', 'character(s)', 'option(s)', or any meta-instructions
- The title must be meaningful and directly relevant to the article
- Start directly with the title - NO explanations or meta-commentary
- Ensure the title accurately reflects the original article's content and context
- Make sure the title forms a complete thought or sentence

Title:"""

    try:
        max_attempts = 3
        for attempt in range(max_attempts):
            new_title = generate_content_with_retry(title_prompt)
            if not new_title:
                print("❌ Failed to rewrite title after all retries")
                return create_intelligent_fallback_title(topic, original_title)
            
            # Clean up any remaining markdown or special characters
            new_title = re.sub(r'[#*`]', '', new_title)
            new_title = re.sub(r'\s+', ' ', new_title)
            new_title = new_title.strip()
            
            # Remove any meta-instructions or explanations from the title
            meta_patterns = [
                r"^title:\s*",
                r"^new title:\s*",
                r"^here's.*:",
                r"^here is.*:",
                r"^rewritten.*:",
                r"^seo.*:",
                r"^engaging.*:",
                r"^catchy.*:"
            ]
            for pattern in meta_patterns:
                new_title = re.sub(pattern, '', new_title, flags=re.IGNORECASE)
            new_title = new_title.strip()
            
            # Ensure complete sentence
            new_title = ensure_complete_sentence(new_title)
            
            # Truncate if slightly over length (as a last resort)
            if len(new_title) > MAX_TITLE_LENGTH:
                # Try to cut at the last space before the limit
                cut = new_title[:MAX_TITLE_LENGTH].rstrip()
                if ' ' in cut:
                    cut = cut[:cut.rfind(' ')].rstrip()
                new_title = cut
                # Ensure it's still a complete sentence
                new_title = ensure_complete_sentence(new_title)
            
            # Check for bad patterns or length
            if not is_bad_title(new_title):
                break
            else:
                print(f"[⚠️] AI generated a bad or lengthy title, retrying... Attempt {attempt+1}")
                new_title = None
        
        # Fallback if AI fails or all attempts are bad
        if not new_title or len(new_title) < 10 or is_bad_title(new_title):
            new_title = create_intelligent_fallback_title(topic, original_title)
        
        return new_title
        
    except Exception as e:
        print(f"Error rewriting title: {e}")
        return create_intelligent_fallback_title(topic, original_title)

def clean_content(content, topic):
    """Clean and format the content, removing repetition, ellipsis, improper headings, near-duplicates, and markdown formatting."""
    import re
    # Remove HTML tags and markdown
    content = re.sub(r'<[^>]+>', '', content)
    content = re.sub(r'```[a-zA-Z]*\n', '', content)
    content = re.sub(r'```\n', '', content)
    content = re.sub(r'```', '', content)
    
    # Remove markdown formatting BUT PRESERVE ## headings
    # content = re.sub(r'#{1,6}\s*', '', content)  # REMOVED - Don't remove ## headings!
    content = re.sub(r'\*\*(.*?)\*\*', r'\1', content)  # Remove **bold**
    content = re.sub(r'\*(.*?)\*', r'\1', content)  # Remove *italic*
    content = re.sub(r'`(.*?)`', r'\1', content)  # Remove `code`
    content = re.sub(r'~~(.*?)~~', r'\1', content)  # Remove ~~strikethrough~~
    content = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', content)  # Remove [link](url) -> link
    content = re.sub(r'\[(.*?)\]', r'\1', content)  # Remove [text] -> text
    
    # Remove ellipsis and bracketed content
    content = re.sub(r'\[.*?\]', '', content)
    content = re.sub(r'\.{2,}', '.', content)
    
    # Split into paragraphs and clean
    paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
    cleaned = []
    for para in paragraphs:
        # Remove lines that start with 'Introduction' (unless it's a heading)
        if para.lower().startswith('introduction') and not (para.startswith('##') or para.startswith('<h2>')):
            continue
        # Remove lines with only 'Introduction'
        if para.strip().lower() == 'introduction':
            continue
        # Remove meta-instructions and explanations
        meta_patterns = [
            r"here's a rewritten",
            r"here is a rewritten",
            r"seo-optimized version",
            r"tailored for.*context",
            r"adhering to.*specifications",
            r"comprehensive blog post about",
            r"original content:",
            r"structure:",
            r"requirements:",
            r"content:",
            r"meta-instructions",
            r"meta-commentary"
        ]
        para_lower = para.lower()
        if any(re.search(pattern, para_lower) for pattern in meta_patterns):
            continue
        # Remove ellipsis or incomplete lines
        if '[...]' in para or para.endswith('...') or para.endswith('..'):
            continue
        # Remove lines with just dots
        if re.match(r'^\.+$', para):
            continue
        # Remove lines that are just markdown formatting (but keep ## headings)
        if re.match(r'^[*`\s]+$', para) and not para.startswith('##'):
            continue
        cleaned.append(para)
    
    # Remove near-duplicate paragraphs
    unique_paragraphs = remove_near_duplicates(cleaned, threshold=0.85)
    return '\n'.join(unique_paragraphs)

def convert_to_html(content):
    """Convert plain text content to proper HTML format for WordPress with better heading detection"""
    import re
    
    lines = content.split('\n')
    html_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Detect ## headings BEFORE removing markdown
        if line.startswith('##'):
            heading = line[2:].strip()
            html_lines.append(f'<h2>{heading}</h2>')
            continue
        # Detect subheadings (not used by AI, but keep for future)
        if line.startswith('###'):
            heading = line[3:].strip()
            html_lines.append(f'<h3>{heading}</h3>')
            continue
        
        # Now clean any remaining markdown
        line = re.sub(r'#{1,6}\s*', '', line)  # Remove # headings (shouldn't be needed now)
        line = re.sub(r'\*\*(.*?)\*\*', r'\1', line)  # Remove **bold**
        line = re.sub(r'\*(.*?)\*', r'\1', line)  # Remove *italic*
        line = re.sub(r'`(.*?)`', r'\1', line)  # Remove `code`
        
        # Regular paragraph - only if it's substantial content
        if line and len(line) > 20:
            html_lines.append(f'<p>{line}</p>')
    
    return '\n'.join(html_lines)

def generate_keywords(topic):
    """Generate relevant keywords for the topic"""
    keyword_prompt = f"""
Generate 8-10 SEO keywords for '{topic}'.
Return only keywords separated by commas.

Requirements:
- If the topic contains text in a language other than English, translate it to English first
- Generate keywords in English only
- Focus on relevant, searchable terms related to the topic

Keywords:"""

    try:
        keywords = generate_content_with_retry(keyword_prompt)
        
        if not keywords:
            print("❌ Failed to generate keywords after all retries")
            # Generate fallback keywords based on topic
            topic_words = topic.lower().split()
            fallback_keywords = topic_words + ['technology', 'innovation', 'digital', 'transformation', 'future', 'trends', 'industry', 'development']
            keywords = ', '.join(fallback_keywords[:10])
            return keywords
        
        # Clean keywords
        keywords = keywords.replace('\n', ', ')
        keywords = re.sub(r'[^\w\s,]', '', keywords)  # Remove special characters except commas
        keywords = ', '.join([k.strip() for k in keywords.split(',') if k.strip()])
        
        # Fallback if no keywords generated
        if not keywords or len(keywords) < 10:
            # Generate fallback keywords based on topic
            topic_words = topic.lower().split()
            fallback_keywords = topic_words + ['technology', 'innovation', 'digital', 'transformation', 'future', 'trends', 'industry', 'development']
            keywords = ', '.join(fallback_keywords[:10])
        
        return keywords
        
    except Exception as e:
        print(f"Error generating keywords: {e}")
        # Fallback keywords
        topic_words = topic.lower().split()
        fallback_keywords = topic_words + ['technology', 'innovation', 'digital', 'transformation', 'future', 'trends', 'industry', 'development']
        return ', '.join(fallback_keywords[:10])

def generate_excerpt(content, max_length=160):
    """Generate an excerpt from the content"""
    # Remove HTML tags for excerpt
    import re
    clean_content = re.sub(r'<[^>]+>', '', content)
    # Take first few sentences
    sentences = clean_content.split('.')
    excerpt = ''
    for sentence in sentences:
        if len(excerpt + sentence) < max_length:
            excerpt += sentence + '. '
        else:
            break
    return excerpt.strip()[:max_length]

def send_email_notification_blog(uploaded_urls, receiver_emails=None):
    """Send email notification to multiple recipients when blog posts are published"""
    
    if not uploaded_urls:
        print("📧 No posts to notify about")
        return False
    
    if receiver_emails is None:
        receiver_emails = [
            "shoaib.waqar665@gmail.com",
            "linkcrafter@gmail.com"
        ]
    
    # Email configuration
    sender_email = "blognotifier.alerts@gmail.com"
    sender_password = os.getenv('GOOGLE_APP_KEY')  # App password
    
    # Create message
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = ", ".join(receiver_emails)
    
    # Set subject based on number of posts
    if len(uploaded_urls) == 1:
        msg['Subject'] = f"New Blog Post Published: {uploaded_urls[0]['title']}"
    else:
        msg['Subject'] = f"New Blog Posts Published: {len(uploaded_urls)} Articles"
    
    # Build email body
    if len(uploaded_urls) == 1:
        post = uploaded_urls[0]
        body = f"""
🎉 New Blog Post Published!

📝 Topic: {post['original_topic']}
📂 Category: {post['category']}
📋 Title: {post['title']}
🔗 View Post: {post['link']}

Your blog post has been successfully published to WordPress.

Best regards,
Blog Notifier Bot
"""
    else:
        body = f"""
🎉 New Blog Posts Published!

📊 Total Posts: {len(uploaded_urls)}

"""
        for i, post in enumerate(uploaded_urls, 1):
            body += f"""
📝 Post {i}:
   Topic: {post['original_topic']}
   Category: {post['category']}
   Title: {post['title']}
   🔗 View Post: {post['link']}

"""
        body += """
All blog posts have been successfully published to WordPress.

Best regards,
Blog Notifier Bot
"""
    
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        # Create SMTP session
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        
        # Send email to all recipients
        server.sendmail(sender_email, receiver_emails, msg.as_string())
        server.quit()
        
        print(f"✅ Email notification sent to: {', '.join(receiver_emails)}")
        print(f"📧 Notified about {len(uploaded_urls)} post(s)")
        return True
        
    except Exception as e:
        print(f"❌ Error sending email notification: {e}")
        return False

def post_to_wordpress(title, content, category_name="Health", featured_image_id=None):
    """Post content to WordPress using category name"""
    # Get category ID by name
    category_id = get_category_id_by_name(category_name)
    
    post_data = {
        'title': title,
        'content': content,
        'status': 'publish',
        'categories': category_id,
        'excerpt': '\u200e',
        'format': 'standard'
    }
    
    # Add featured image if provided
    if featured_image_id:
        post_data['featured_media'] = featured_image_id
    
    try:
        response = requests.post(url, headers=header, json=post_data)
        if response.status_code == 201:
            print(f"✅ Blog post '{title}' published successfully!")
            print(f"Post ID: {response.json().get('id')}")
            print(f"Category: {category_name}")
            if featured_image_id:
                print(f"Featured Image ID: {featured_image_id}")
            print(f"View at: {response.json().get('link')}")
            return response.json()
        else:
            print(f"❌ Error publishing post: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error posting to WordPress: {e}")
        return None

def generate_blog_image(topic, category):
    """Get a relevant image for the blog post using Unsplash API"""
    if not unsplash_access_key:
        print("❌ Unsplash access key not available")
        return None
    category = category[0]
    try:
        # Create search query based on topic and category
        search_terms = [topic, category]
        # Add some generic terms for better results
        if "technology" in category.lower():
            search_terms.extend(["technology", "digital", "innovation"])
        elif "health" in category.lower():
            search_terms.extend(["healthcare", "medical", "wellness"])
        elif "business" in category.lower():
            search_terms.extend(["business", "corporate", "professional"])
        elif "environment" in category.lower():
            search_terms.extend(["environment", "sustainability", "green"])
        
        # Try different search terms until we find an image
        for search_term in search_terms[:3]:  # Limit to first 3 terms
            try:
                query = search_term.replace(" ", "+")
                response = requests.get(
                    f"https://api.unsplash.com/search/photos?query={query}&per_page=1&orientation=landscape",
                    headers={"Authorization": f"Client-ID {unsplash_access_key}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data['results']:
                        img_url = data['results'][0]['urls']['regular']
                        print(f"✅ Found Unsplash image for: {search_term}")
                        return img_url
                        
            except Exception as e:
                print(f"❌ Error searching for '{search_term}': {e}")
                continue
        
        print("❌ No suitable images found on Unsplash")
        return None
        
    except Exception as e:
        print(f"❌ Error getting image from Unsplash: {e}")
        return None

def upload_image_to_wordpress(image_url, filename, title):
    """Upload image to WordPress media library from URL"""
    try:
        # Download image from URL
        print(f"📥 Downloading image from: {image_url}")
        image_response = requests.get(image_url)
        
        if image_response.status_code != 200:
            print(f"❌ Failed to download image: {image_response.status_code}")
            return None
        
        image_bytes = image_response.content
        
        # Prepare the upload
        media_url = f'{wordpress_url}/wp-json/wp/v2/media'
        
        # Create multipart form data
        files = {
            'file': (filename, image_bytes, 'image/jpeg')
        }
        
        data = {
            'title': title,
            'caption': title,
            'alt_text': title
        }
        
        # Upload the image
        response = requests.post(media_url, headers=header, files=files, data=data)
        
        if response.status_code == 201:
            media_info = response.json()
            print(f"✅ Image uploaded successfully: {media_info['source_url']}")
            return media_info['id'], media_info['source_url']
        else:
            print(f"❌ Error uploading image: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error uploading image to WordPress: {e}")
        return None

def add_images_to_content(content, topic, category):
    """Finds and uploads a single Unsplash image and returns its ID, without modifying the content."""
    try:
        # Get main featured image
        print("🎨 Getting featured image from Unsplash...")
        featured_image_url = generate_blog_image(topic, category)
        
        if featured_image_url:
            # Upload featured image
            featured_filename = f"featured_{topic.lower().replace(' ', '_')}.jpg"
            upload_result = upload_image_to_wordpress(featured_image_url, featured_filename, f"Featured image for {topic}")
            
            if upload_result:
                featured_image_id, _ = upload_result
                # Return the original content (unmodified) and the new featured image ID
                return content, featured_image_id
        
        print("⚠️ No image found, proceeding with text-only content")
        return content, None
        
    except Exception as e:
        print(f"❌ Error adding image to content: {e}")
        return content, None

def rewrite_scraped_content(original_content, topic):
    """Rewrite scraped content using Gemini AI to make it unique and SEO-optimized"""
    
    rewrite_prompt = f"""
Write a comprehensive blog post about '{topic}' (300-400 words).

Original content: {original_content[:1000]}  # Limit to save tokens

Structure:
1. Main heading (## format)
2. 1 introduction paragraph
3. 1 section with ## heading
4. 1 conclusion paragraph

Requirements:
- If the original content is in a language other than English, translate it to English first
- Completely rewrite in your own words while maintaining the original context and key information
- Preserve all important facts, data, quotes, and technical details from the original article
- Do not add information that wasn't in the original content
- Do not remove critical information from the original article
- SEO-optimized with relevant keywords
- Professional language
- No markdown except ## headings
- Focus on African tech context when relevant
- Start directly with the main heading - NO meta-instructions or explanations
- Do NOT include phrases like "Here's a rewritten version", "SEO-optimized version", or any meta-commentary
- Ensure the rewritten content accurately reflects the original article's message and intent

Content:"""

    try:
        # Generate rewritten content using retry logic
        content = generate_content_with_retry(rewrite_prompt)
        
        if not content:
            print("❌ Failed to rewrite content after all retries")
            return None
        
        # Clean the content thoroughly
        content = clean_content(content, topic)

        # Additional cleaning to remove any remaining meta-instructions
        content_lines = content.split('\n')
        cleaned_lines = []
        for line in content_lines:
            line_lower = line.lower()
            # Skip lines that contain meta-instructions
            if any(phrase in line_lower for phrase in [
                "here's a rewritten",
                "here is a rewritten", 
                "seo-optimized version",
                "tailored for",
                "adhering to",
                "comprehensive blog post",
                "original content:",
                "structure:",
                "requirements:",
                "content:",
                "meta-instructions",
                "meta-commentary"
            ]):
                continue
            cleaned_lines.append(line)
        content = '\n'.join(cleaned_lines)

        # Convert to proper HTML format for WordPress
        content = convert_to_html(content)
        
        # Generate keywords separately
        keywords = generate_keywords(topic)
        
        # Add keywords section with proper formatting
        keywords_section = f"""
<h3><strong>Keywords</strong></h3>
<p><strong>Related Keywords:</strong> {keywords}</p>
"""
        
        # Combine content with keywords
        final_content = f"{content}\n{keywords_section}"
        
        return final_content
        
    except Exception as e:
        print(f"Error rewriting content: {e}")
        return None

def process_scraped_articles(topic,content,url,title,category_received,uploaded_urls):
    """Process scraped articles from scraper.py and post to WordPress"""
    
    original_topic = topic
    original_content = content
    url = url
    original_title = title
    
    print(f"📝 Processing article: {original_topic}")
    print(f"🔗 Source: {url}")
    
    # Check if content needs translation
    if not is_english_content(original_content):
        print("🌐 Detected non-English content, will translate during processing...")
    
    # Rewrite title with AI
    print("✏️ Rewriting title...")
    new_title = rewrite_title_with_ai(original_title, original_topic)
    print(f"📋 New title: {new_title}")
    
    # Determine category based on topic content
    category = category_received
    print(f"📂 Category: {category}")
    
    # Rewrite content using Gemini
    print("🔄 Rewriting content...")
    rewritten_content = rewrite_scraped_content(original_content, original_topic)
    
    if rewritten_content:
        # Add images to content
        print("🖼️ Adding images to content...")
        content_with_images, featured_image_id = add_images_to_content(rewritten_content, new_title, category)
        category = category_received
        print(f"📂 Category: {category}")
      
        # Post to WordPress
        result = post_to_wordpress(new_title, content_with_images, category, featured_image_id)
        
        if result:
            print(f"✅ Successfully posted: {new_title}\n")
            update_my_blog_url(url,result['link'])
            # Send email notification
            # append title category and link to uploaded_urls
            uploaded_urls.append({'title': new_title, 'category': category, 'link': result['link'], 'original_topic': original_topic})
            # send_email_notification(original_topic, category, new_title, result['link'])
        else:
            print(f"❌ Failed to post: {new_title}\n")
    else:
        print(f"❌ Failed to rewrite content for: {new_title}\n")
    
    # Add a small delay between posts to avoid rate limiting
    time.sleep(3)
    return uploaded_urls


def blog_main(topic,content,url,title,category,uploaded_urls):
    print("🤖 Starting blog generation and posting process...\n")
    print(f"📝 Using WordPress site: {wordpress_url}")
    print(f"👤 Username: {username}\n")
    
    # Process scraped articles instead of predefined topics
    uploaded_urls = process_scraped_articles(topic,content,url,title,category,uploaded_urls)
    return uploaded_urls

if __name__ == "__main__":
    blog_main()