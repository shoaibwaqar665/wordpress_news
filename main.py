import requests
import base64
import google.generativeai as genai
import os
from dotenv import load_dotenv
import re
from difflib import SequenceMatcher

# Load environment variables
load_dotenv()

# WordPress credentials from environment variables
username = os.getenv('WORDPRESS_USERNAME')
password = os.getenv('WORDPRESS_PASSWORD')
wordpress_url = os.getenv('WORDPRESS_URL')

# Validate environment variables
if not all([username, password, wordpress_url]):
    raise ValueError("Missing required environment variables. Please check your .env file.")

credentials = username + ':' + password
cred_token = base64.b64encode(credentials.encode())

url = f'{wordpress_url}/wp-json/wp/v2/posts'
header = {'Authorization': 'Basic ' + cred_token.decode('utf-8')}

# Configure Gemini AI
gemini_api_key = os.getenv('GEMINI_API_KEY')
if not gemini_api_key:
    raise ValueError("Missing GEMINI_API_KEY in environment variables.")

genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel("gemini-2.0-flash")
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


def get_category_id_by_name(category_name):
    """Get category ID by name"""
    categories = get_categories()
    for category in categories:
        if category['name'].lower() == category_name.lower():
            return category['id']
    
    # If category not found, print available categories
    print(f"❌ Category '{category_name}' not found.")
    print("Available categories:")
    for category in categories:
        print(f"  - {category['name']} (ID: {category['id']})")
    return None

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

def generate_blog_content(topic):
    """Generate blog content using Gemini AI"""
    
    # Stricter prompt with uniqueness
    main_prompt = f"""
    Write a comprehensive, SEO-optimized blog post about '{topic}'.

    STRICT REQUIREMENTS:
    - The first paragraph after the heading must NOT repeat or paraphrase the heading.
    - Each section must be unique and not repeat previous content.
    - Do NOT repeat any sentence or paragraph.
    - Do NOT use the word 'Introduction' as a heading or inline.
    - Do NOT use ellipsis ([...]) or incomplete sentences.
    - Do NOT use the word 'Introduction' at the start of any paragraph.
    - Start with a proper heading (e.g., ## or <h2>), not with the word 'Introduction'.
    - Use only complete, original content.
    - Write exactly 800-1000 words.
    - Use clear, professional language.
    - Include specific examples and data where relevant.
    - NO markdown formatting or HTML tags in the output (plain text only).

    STRUCTURE (follow exactly):
    1. Main Heading (use ## or <h2>, do not use 'Introduction')
    2. Introduction section (2 paragraphs, but do not use the word 'Introduction')
    3. Main Content (3-4 sections with clear headings)
    4. Conclusion (1-2 paragraphs, do not use the word 'Conclusion' as a heading)

    FORMATTING:
    - Use ## for section headings
    - Write in plain text only
    - Do not repeat the title
    - Do not use any special characters or formatting
    - Do not use the word 'Introduction' as a heading or inline
    - Do not use ellipsis ([...]) or incomplete sentences
    - Do not repeat any content
    - Start directly with the main heading
    """
    
    try:
        # Generate main content
        response = model.generate_content(main_prompt)
        content = response.text.strip()
        
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

def clean_content(content, topic):
    """Clean and format the content, removing repetition, ellipsis, improper headings, and near-duplicates."""
    import re
    # Remove HTML tags and markdown
    content = re.sub(r'<[^>]+>', '', content)
    content = re.sub(r'```[a-zA-Z]*\n', '', content)
    content = re.sub(r'```\n', '', content)
    content = re.sub(r'```', '', content)
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
        # Remove ellipsis or incomplete lines
        if '[...]' in para or para.endswith('...') or para.endswith('..'):
            continue
        # Remove lines with just dots
        if re.match(r'^\.+$', para):
            continue
        cleaned.append(para)
    # Remove near-duplicate paragraphs
    unique_paragraphs = remove_near_duplicates(cleaned, threshold=0.85)
    return '\n'.join(unique_paragraphs)

def convert_to_html(content):
    """Convert plain text content to proper HTML format for WordPress"""
    import re
    
    lines = content.split('\n')
    html_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check if it's a heading (starts with ## or is all caps)
        if line.startswith('##') or (line.isupper() and len(line) > 3 and len(line) < 100):
            # Remove ## if present and format as h2
            heading = line.replace('##', '').strip()
            html_lines.append(f'<h2>{heading}</h2>')
        elif line.startswith('###') or (line[0].isupper() and line.endswith(':') and len(line) < 80):
            # Format as h3
            heading = line.replace('###', '').strip()
            if heading.endswith(':'):
                heading = heading[:-1]
            html_lines.append(f'<h3>{heading}</h3>')
        else:
            # Regular paragraph
            if line:
                html_lines.append(f'<p>{line}</p>')
    
    return '\n'.join(html_lines)

def remove_heading_paragraph_repeat(content):
    import re
    lines = [line for line in content.split('\n') if line.strip()]
    # Find first heading
    heading = None
    heading_idx = None
    for i, line in enumerate(lines):
        if line.startswith('<h2>') and line.endswith('</h2>'):
            heading = re.sub(r'<.*?>', '', line).strip().lower()
            heading_idx = i
            break
    # Find first paragraph after heading
    if heading is not None and heading_idx is not None and heading_idx + 1 < len(lines):
        first_para = re.sub(r'<.*?>', '', lines[heading_idx + 1]).strip().lower()
        # If very similar, remove the paragraph
        if SequenceMatcher(None, heading, first_para).ratio() > 0.7:
            del lines[heading_idx + 1]
    return '\n'.join(lines)

def generate_keywords(topic):
    """Generate relevant keywords for the topic"""
    keyword_prompt = f"""
    Generate 8-10 relevant SEO keywords for a blog post about '{topic}'.
    Return ONLY the keywords separated by commas, no other text or formatting.
    Make them specific and relevant to the topic.
    Include both broad and specific keywords.
    """
    
    try:
        response = model.generate_content(keyword_prompt)
        keywords = response.text.strip()
        
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

def post_to_wordpress(title, content, category_name="Health"):
    """Post content to WordPress using category name"""
    # Get category ID by name
    category_id = get_category_id_by_name(category_name)
    
    post_data = {
        'title': title,
        'content': content,
        'status': 'draft',
        'categories': [category_id],
        'excerpt': '\u200e',
        'format': 'standard'
    }
    
    try:
        response = requests.post(url, headers=header, json=post_data)
        if response.status_code == 201:
            print(f"✅ Blog post '{title}' published successfully!")
            print(f"Post ID: {response.json().get('id')}")
            print(f"Category: {category_name}")
            print(f"View at: {response.json().get('link')}")
            return response.json()
        else:
            print(f"❌ Error publishing post: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error posting to WordPress: {e}")
        return None

def main():
    # List of topics with their categories
    topics_with_categories = [
        # {
        #     "topic": "Machine Learning Applications in Finance",
        #     "category": "Technology"
        # },
        {
            "topic": "The Future of Artificial Intelligence in Healthcare",
            "category": "Health"
        },
        
        # {
        #     "topic": "Sustainable Technology: Green Solutions for Tomorrow",
        #     "category": "Environment"
        # },
        # {
        #     "topic": "Cybersecurity Best Practices for Small Businesses",
        #     "category": "Business"
        # },
        # # {
        # #     "topic": "The Rise of Remote Work: Technology Trends",
        # #     "category": "Workplace"
        # # }
    ]
    
    print("🤖 Starting blog generation and posting process...\n")
    print(f"📝 Using WordPress site: {wordpress_url}")
    print(f"👤 Username: {username}\n")
    
    # Show available categories first
    print("📋 Available categories:")
    categories = get_categories()
    for category in categories:
        print(f"  - {category['name']} (ID: {category['id']})")
    print()
    
    for i, item in enumerate(topics_with_categories, 1):
        topic = item["topic"]
        category = item["category"]
        
        print(f"📝 Generating blog {i}/{len(topics_with_categories)}: {topic}")
        print(f"📂 Category: {category}")
        
        # Generate content using Gemini
        content = generate_blog_content(topic)
        
        if content:
            # write content to the txt file
            with open('content.txt', 'a') as f:
                f.write(f"Topic: {topic}\n")
                f.write(f"Category: {category}\n")
                f.write('--------------------------------\n')
                f.write(content)
                f.write('\n')
                f.write('\n')
            # Post to WordPress
            result = post_to_wordpress(topic, content, category)
            
            if result:
                print(f"✅ Successfully posted: {topic}\n")
            else:
                print(f"❌ Failed to post: {topic}\n")
        else:
            print(f"❌ Failed to generate content for: {topic}\n")
        
        # Add a small delay between posts to avoid rate limiting
        import time
        time.sleep(2)

if __name__ == "__main__":
    main()