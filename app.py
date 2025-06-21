from flask import Flask, jsonify, request
from scraper import scraper_main

app = Flask(__name__)

@app.route('/scrape', methods=['POST'])
def scrape():
    data = request.get_json()
    category = data.get('category', 'General') if data else 'General'  # default to 'General' if missing
    url = data.get('url', 'https://cioafrica.co/meta-moves-to-monetise-whatsapp/') if data else 'https://cioafrica.co/meta-moves-to-monetise-whatsapp/'
    topic, title, url = scraper_main(url, category)
    if topic:
        return jsonify({'topic': topic, 'title': title, 'url': url})
    return jsonify({'error': 'Failed to scrape'}), 500

if __name__ == "__main__":
    app.run(debug=True)
