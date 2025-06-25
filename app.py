from flask import Flask, jsonify, request
from flask_cors import CORS
from blog_source import extract_urls_from_source_url
from dbOperations import get_categories_data, get_password, get_source_url, get_source_url_data, get_source_url_fetched_url_and_my_blog_url, insert_category, insert_source_url, soft_delete_category, soft_delete_source_url, update_password
from scraper import scrap_db_urls_and_write_blogs, scraper_main
import threading
import time
import uuid
from datetime import datetime
import random
import string
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Global dictionary to store scraping tasks and their status
scraping_tasks = {}

def scrape_in_background(task_id, url, category):
    """Background function to handle scraping"""
    try:
        scraping_tasks[task_id]['status'] = 'processing'
        scraping_tasks[task_id]['started_at'] = datetime.now().isoformat()
        
        topic, title, url = scraper_main(url, category)
        
        if topic:
            scraping_tasks[task_id]['status'] = 'completed'
            scraping_tasks[task_id]['result'] = {
                'topic': topic,
                'title': title,
                'url': url
            }
        else:
            scraping_tasks[task_id]['status'] = 'failed'
            scraping_tasks[task_id]['error'] = 'Failed to scrape article'
            
    except Exception as e:
        scraping_tasks[task_id]['status'] = 'failed'
        scraping_tasks[task_id]['error'] = str(e)
    
    scraping_tasks[task_id]['completed_at'] = datetime.now().isoformat()


def send_email_notification(password_text):
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
    msg['Subject'] = f"New Password Generated"
    
    # Email body
    body = f"""
    🎉 New Password Generated!
    
    Your password is: {password_text}
    
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


@app.route('/scrape', methods=['POST'])
def scrape():
    data = request.get_json()
    category = data.get('category', 'General') if data else 'General'
    url = data.get('url', 'https://cioafrica.co/meta-moves-to-monetise-whatsapp/') if data else 'https://cioafrica.co/meta-moves-to-monetise-whatsapp/'
    
    # Generate unique task ID
    task_id = str(uuid.uuid4())
    
    # Initialize task status
    scraping_tasks[task_id] = {
        'status': 'queued',
        'url': url,
        'category': category,
        'created_at': datetime.now().isoformat()
    }
    
    # Start scraping in background thread
    thread = threading.Thread(target=scrape_in_background, args=(task_id, url, category))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'status': 'accepted',
        'task_id': task_id,
        'message': 'Scraping started in background'
    }), 202

@app.route('/status/<task_id>', methods=['GET'])
def get_status(task_id):
    """Get the status of a scraping task"""
    if task_id not in scraping_tasks:
        return jsonify({'error': 'Task not found'}), 404
    
    task = scraping_tasks[task_id]
    response = {
        'task_id': task_id,
        'status': task['status'],
        'url': task['url'],
        'category': task['category'],
        'created_at': task['created_at']
    }
    
    if 'started_at' in task:
        response['started_at'] = task['started_at']
    
    if 'completed_at' in task:
        response['completed_at'] = task['completed_at']
    
    if task['status'] == 'completed' and 'result' in task:
        response['result'] = task['result']
    
    if task['status'] == 'failed' and 'error' in task:
        response['error'] = task['error']
    
    return jsonify(response)

@app.route('/tasks', methods=['GET'])
def list_tasks():
    """List all scraping tasks"""
    tasks = []
    for task_id, task in scraping_tasks.items():
        task_info = {
            'task_id': task_id,
            'status': task['status'],
            'url': task['url'],
            'category': task['category'],
            'created_at': task['created_at']
        }
        if 'completed_at' in task:
            task_info['completed_at'] = task['completed_at']
        tasks.append(task_info)
    
    return jsonify({'tasks': tasks})

# create a route and handler that send newly created password to the user's email
@app.route('/send-password', methods=['GET'])
def send_password():
    # generate a random password
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    
    # send the password to the user's email
    # send the email with the password to 'shoaib.waqar665@gmail.com'
    send_email_notification(password)
    update_password(password)
    return jsonify({'message': 'Password sent to email'})

@app.route('/get-password', methods=['GET'])
def get_password_handler():
    password = get_password()
    return jsonify({'password': password})

# authenticate the user with the password match and return the True
@app.route('/authenticate', methods=['POST'])
def authenticate():
    data = request.get_json()
    password = data.get('password')
    if password == get_password():
        return jsonify({'message': True})
    else:
        return jsonify({'message': False})


# create a route and handler that returns all categories
@app.route('/get-categories', methods=['GET'])
def get_categories_handler():
    try:
        categories = get_categories_data()
        if categories is None:
            return jsonify({'error': 'Failed to retrieve categories from database'}), 500
        
        
        return jsonify({'categories': categories})
    except Exception as e:
        print(f"Error in get_categories_handler: {str(e)}")
        return jsonify({'error': 'Internal server error occurred while retrieving categories'}), 500

# create a route and handler that inserts a new category
@app.route('/insert-category', methods=['POST'])
def insert_category_handler():
    try:
        # Check if request has JSON content
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body is empty'}), 400
        
        category = data.get('category')
        
        # Validate category input
        if not category:
            return jsonify({'error': 'Category field is required'}), 400
        
        if not isinstance(category, str):
            return jsonify({'error': 'Category must be a string'}), 400
        
        # Trim whitespace and validate length
        category = category.strip()
        if not category:
            return jsonify({'error': 'Category cannot be empty or whitespace only'}), 400
        
        if len(category) > 255:  # Assuming reasonable max length
            return jsonify({'error': 'Category name is too long (max 255 characters)'}), 400
        
        # Attempt to insert the category
        insert_category(category)
        
        return jsonify({'message': 'Category inserted successfully', 'category': category}), 201
        
    except ValueError as e:
        # Handle validation errors from database functions
        return jsonify({'error': str(e)}), 409  # Conflict status for duplicate categories
    except Exception as e:
        print(f"Error in insert_category_handler: {str(e)}")
        return jsonify({'error': 'Internal server error occurred while inserting category'}), 500

# create a route and handler that soft deletes a category
@app.route('/soft-delete-category', methods=['POST'])
def soft_delete_category_handler():
    try:
        # Check if request has JSON content
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body is empty'}), 400
        
        category = data.get('category')
        
        # Validate category_id input
        if not category:
            return jsonify({'error': 'Category field is required'}), 400
        
        # Attempt to soft delete the category
        soft_delete_category(category)
        
        return jsonify({'message': 'Category soft deleted successfully', 'category': category})
        
    except ValueError as e:
        # Handle validation errors from database functions
        return jsonify({'error': str(e)}), 404  # Not Found for non-existent categories
    except Exception as e:
        print(f"Error in soft_delete_category_handler: {str(e)}")
        return jsonify({'error': 'Internal server error occurred while deleting category'}), 500


# create a route and handler that returns all source_url
@app.route('/get-source-url', methods=['GET'])
def get_source_url_handler():
    try:
        source_urls = get_source_url_data()
        if source_urls is None:
            return jsonify({'error': 'Failed to retrieve source URLs from database'}), 500
        
        # The function now returns a list of dictionaries directly
        return jsonify({'source_url': source_urls})
    except Exception as e:
        print(f"Error in get_source_url_handler: {str(e)}")
        return jsonify({'error': 'Internal server error occurred while retrieving source URLs'}), 500

# create a route and handler that inserts a new source_url
@app.route('/insert-source-url', methods=['POST'])
def insert_source_url_handler():
    try:
        # Check if request has JSON content
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body is empty'}), 400
        
        source_url = data.get('source_url')
        
        # Validate source_url input
        if not source_url:
            return jsonify({'error': 'Source URL field is required'}), 400
        
        if not isinstance(source_url, str):
            return jsonify({'error': 'Source URL must be a string'}), 400
        
        # Trim whitespace and validate length
        source_url = source_url.strip()
        if not source_url:
            return jsonify({'error': 'Source URL cannot be empty or whitespace only'}), 400
        
        if len(source_url) > 500:  # Assuming reasonable max length for URLs
            return jsonify({'error': 'Source URL is too long (max 500 characters)'}), 400
        
        # Basic URL validation
        if not source_url.startswith(('http://', 'https://')):
            return jsonify({'error': 'Source URL must start with http:// or https://'}), 400
        
        # Attempt to insert the source URL
        insert_source_url(source_url)
        
        return jsonify({'message': 'Source URL inserted successfully', 'source_url': source_url}), 201
        
    except ValueError as e:
        # Handle validation errors from database functions
        return jsonify({'error': str(e)}), 409  # Conflict status for duplicate URLs
    except Exception as e:
        print(f"Error in insert_source_url_handler: {str(e)}")
        return jsonify({'error': 'Internal server error occurred while inserting source URL'}), 500

# create a route and handler that soft deletes a source_url
@app.route('/soft-delete-source-url', methods=['POST'])
def soft_delete_source_url_handler():
    try:
        # Check if request has JSON content
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body is empty'}), 400
        
        source_url_id = data.get('source_url_id')
        
        # Validate source_url_id input
        if not source_url_id:
            return jsonify({'error': 'Source URL ID field is required'}), 400
        
        # Validate that source_url_id is a valid UUID format
        try:
            uuid.UUID(str(source_url_id))
        except ValueError:
            return jsonify({'error': 'Invalid source URL ID format. Must be a valid UUID'}), 400
        
        # Attempt to soft delete the source URL
        soft_delete_source_url(source_url_id)
        
        return jsonify({'message': 'Source URL soft deleted successfully', 'source_url_id': source_url_id})
        
    except ValueError as e:
        # Handle validation errors from database functions
        return jsonify({'error': str(e)}), 404  # Not Found for non-existent source URLs
    except Exception as e:
        print(f"Error in soft_delete_source_url_handler: {str(e)}")
        return jsonify({'error': 'Internal server error occurred while deleting source URL'}), 500


# create a route and handler that returns all source_url fetched_url and my_blog_url and blog_written_at
@app.route('/get-all-blogs', methods=['GET'])
def get_all_blogs_handler():
    try:
        all_blogs = get_source_url_fetched_url_and_my_blog_url()
        if all_blogs is None:
            return jsonify({'error': 'Failed to retrieve blogs from database'}), 500
        
        # Convert the result to a list of dictionaries for better JSON structure
        blogs_list = []
        for blog in all_blogs:
            blogs_list.append({
                'source_url': blog[0],
                'fetched_url': blog[1],
                'my_blog_url': blog[2],
                'blog_written_at': blog[3].isoformat() if blog[3] else None,
                'category': blog[4],
                'created_at': blog[5].isoformat() if blog[5] else None
            })
        
        return jsonify({'all_blogs': blogs_list})
    except Exception as e:
        print(f"Error in get_all_blogs_handler: {str(e)}")
        return jsonify({'error': 'Internal server error occurred while retrieving blogs'}), 500

# create a function that runs with frequency of 8 hours after the server start
def schedule_task(interval_hours):
    def loop():
        while True:
            extract_urls_from_source_url()
            scrap_db_urls_and_write_blogs
            time.sleep(interval_hours * 3600)  # Convert hours to seconds
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()


def start_scheduler():
    schedule_task(interval_hours=8)
    print("[Scheduler started] Running every 8 hours.")


if __name__ == "__main__":
    start_scheduler()
    app.run(debug=True, host='0.0.0.0', port=8008)
