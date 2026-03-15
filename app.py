from flask import Flask, request, render_template
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

app = Flask(__name__)

def extract_json_endpoint(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-dev-shm-usage",  # prevents shared memory crashes on Linux
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_function(
                "() => !document.title.includes('Just a moment') && !document.title.includes('Checking')",
                timeout=15000
            )

            # Extra wait to let the real page fully render after redirect
            page.wait_for_load_state("networkidle", timeout=15000)

            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            link_tag = soup.find('link', rel='alternate', type='application/json', title='JSON')
            
            return link_tag['href'] if link_tag else None
        except Exception as e:
            print(f"Page load error: {e}")
            html = page.content()
        finally:
            browser.close()

def parse_json_data(json_url):
    """
    Fetches and parses JSON data from the given URL.
    """

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-dev-shm-usage",  # prevents shared memory crashes on Linux
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        try:
            page.goto(json_url, wait_until="networkidle", timeout=30000)
            page.wait_for_function(
                "() => !document.title.includes('Just a moment') && !document.title.includes('Checking')",
                timeout=15000
            )

            # Extra wait to let the real page fully render after redirect
            page.wait_for_load_state("networkidle", timeout=15000)

            data = page.evaluate("() => JSON.parse(document.body.innerText)")
            return data if data else None
        
        except Exception as e:
            print(f"Page load error: {e}")
        finally:
            browser.close()
    
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
    return render_template('index.html', error="No JSON endpoint found.")
