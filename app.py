from flask import Flask, jsonify, request
from flask_cors import CORS
from scraper import scraper_main
import threading
import time
import uuid
from datetime import datetime

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

if __name__ == "__main__":
    app.run(debug=True, port=8008)
