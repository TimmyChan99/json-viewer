from flask import Flask, request, render_template
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

def extract_json_endpoint(url):
    """
    Extracts the JSON endpoint from a given URL.
    """
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        link_tag = soup.find('link', rel='alternate', type='application/json', title='JSON')
        return link_tag['href'] if link_tag else None
    return None

def parse_json_data(json_url):
    """
    Fetches and parses JSON data from the given URL.
    """
    response = requests.get(json_url)
    if response.status_code == 200:
        return response.json()
    return None
    
@app.route('/', methods=['GET', 'POST'])
def scrape():
    """
    Flask route to fetch JSON data from a specified URL.
    """
    url = request.form.get('url')

    if not url:
        return render_template('index.html')
        
    json_url = extract_json_endpoint(url)
    if json_url:
        parsed_data = parse_json_data(json_url)
        data = {
            "title": parsed_data.get("title")['rendered'],
            "chapter": parsed_data.get("content")['rendered'],
            "chapter_number": parsed_data.get("slug")
        }
        return render_template('index.html', data=data)
    return render_template('index.html')

