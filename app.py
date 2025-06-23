from flask import Flask, jsonify, request
from flask_cors import CORS
from dbOperations import get_password, update_password
from scraper import scraper_main
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
    receiver_email = "shoaib.waqar665@gmail.com"
    # receiver_email = "linkcrafter@gmail.com"
    
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

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8008)
