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

from dbOperations import get_categories_data, update_my_blog_url

# Load environment variables
load_dotenv()

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

def rewrite_title_with_ai(original_title, topic):
    """Rewrite the title using AI to make it more engaging and SEO-friendly"""
    
    title_prompt = f"""
    Rewrite this title to make it more engaging, SEO-friendly, and professional:
    
    Original Title: {original_title}
    Topic: {topic}
    
    REQUIREMENTS:
    - Make it catchy and click-worthy
    - Keep it under 60 characters for SEO
    - Use action words and power words
    - Make it relevant to the African tech/startup context
    - Do NOT use hashtags, asterisks, or special formatting
    - Do NOT copy the original title exactly
    - Make it unique and original
    - Focus on the main benefit or insight
    
    Return ONLY the new title, no other text or formatting.
    """
    
    try:
        response = model.generate_content(title_prompt)
        new_title = response.text.strip()
        
        # Clean up any remaining markdown or special characters
        new_title = re.sub(r'[#*`]', '', new_title)  # Remove #, *, and backticks
        new_title = re.sub(r'\s+', ' ', new_title)  # Replace multiple spaces with single space
        new_title = new_title.strip()
        
        # Fallback if AI fails
        if not new_title or len(new_title) < 10:
            # Create a simple fallback title
            words = topic.split()[:6]  # Take first 6 words
            new_title = ' '.join(words)
            if len(new_title) < 20:
                new_title = f"Latest Updates: {new_title}"
        
        return new_title
        
    except Exception as e:
        print(f"Error rewriting title: {e}")
        # Fallback title
        words = topic.split()[:6]
        return ' '.join(words) if words else "Technology News Update"

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

def send_email_notification(topic, category, post_title, post_link):
    """Send email notification when a blog post is published"""
    # Email configuration
    sender_email = "blognotifier.alerts@gmail.com"
    sender_password = os.getenv('GOOGLE_APP_KEY') # App password
    # receiver_email = "shoaib.waqar665@gmail.com"
    receiver_email = "linkcrafter@gmail.com"
    
    # Create message
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = f"New Blog Post Published: {post_title}"
    
    # Email body
    body = f"""
    🎉 New Blog Post Published!
    
    📝 Topic: {topic}
    📂 Category: {category}
    📋 Title: {post_title}
    🔗 View Post: {post_link}
    
    Your blog post has been successfully published to WordPress.
    
    Best regards,
    Blog Notifier Bot
    """
    
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        # Create SMTP session
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        
        # Login to the server
        server.login(sender_email, sender_password)
        
        # Send email
        text = msg.as_string()
        server.sendmail(sender_email, receiver_email, text)
        server.quit()
        
        print(f"✅ Email notification sent to {receiver_email}")
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
        'status': 'draft',
        'categories': [category_id],
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
    You are a professional content writer. Rewrite the following content about '{topic}' to make it unique, SEO-optimized, and engaging.

    ORIGINAL CONTENT:
    {original_content[:2000]}  # Limit to first 2000 characters to avoid token limits

    REQUIREMENTS:
    - Rewrite the content completely in your own words
    - Keep the same main topic and key information
    - Make it SEO-optimized with relevant keywords
    - Write 800-1000 words
    - Use clear, professional language
    - Include specific examples and data where relevant
    - Do NOT copy any sentences from the original
    - Make it completely unique while maintaining accuracy
    - Focus on African tech/startup context when relevant
    - Use only complete, original content

    CRITICAL STRUCTURE REQUIREMENTS (MUST FOLLOW):
    1. Start with a main heading using ## (e.g., "## The Future of Digital Innovation")
    2. Write 2-3 introduction paragraphs
    3. Add 3-4 section headings using ## (e.g., "## Key Trends in Technology", "## Impact on African Markets", "## Future Outlook")
    4. Write 2-3 paragraphs under each section heading
    5. End with 1-2 conclusion paragraphs

    FORMATTING REQUIREMENTS:
    - Use ## for ALL section headings (not ### or #)
    - Each heading should be descriptive and engaging
    - Write in plain text only
    - Do not repeat the title
    - Do not use any special characters or formatting except ## for headings
    - Do not use the word 'Introduction' as a heading
    - Make sure each section has proper content under it

    EXAMPLE STRUCTURE:
    ## Main Heading Here
    [2-3 introduction paragraphs]

    ## First Section Heading
    [2-3 paragraphs of content]

    ## Second Section Heading
    [2-3 paragraphs of content]

    ## Third Section Heading
    [2-3 paragraphs of content]

    [1-2 conclusion paragraphs]
    """
    
    try:
        # Generate rewritten content
        response = model.generate_content(rewrite_prompt)
        content = response.text.strip()
        # Clean the content thoroughly
        content = clean_content(content, topic)
        
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

def process_scraped_articles(topic,content,url,title,category_received):
    """Process scraped articles from scraper.py and post to WordPress"""
    
    original_topic = topic
    original_content = content
    url = url
    original_title = title
    
    print(f"📝 Processing article: {original_topic}")
    print(f"🔗 Source: {url}")
    
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
            # send_email_notification(original_topic, category, new_title, result['link'])
        else:
            print(f"❌ Failed to post: {new_title}\n")
    else:
        print(f"❌ Failed to rewrite content for: {new_title}\n")
    
    # Add a small delay between posts to avoid rate limiting
    time.sleep(3)


def blog_main(topic,content,url,title,category):
    print("🤖 Starting blog generation and posting process...\n")
    print(f"📝 Using WordPress site: {wordpress_url}")
    print(f"👤 Username: {username}\n")
    
    # Process scraped articles instead of predefined topics
    process_scraped_articles(topic,content,url,title,category)

if __name__ == "__main__":
    blog_main()