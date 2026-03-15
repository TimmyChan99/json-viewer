from flask import Flask, request, render_template
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Browser, Page
from contextlib import contextmanager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BROWSER_ARGS = [
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-setuid-sandbox",
]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

CHALLENGE_CHECK = (
    "() => !document.title.includes('Just a moment') "
    "&& !document.title.includes('Checking')"
)


@contextmanager
def get_page():
    """
    Context manager that spins up a single Playwright browser and yields
    a ready-to-use Page. Guarantees the browser is closed on exit even
    if an exception is raised, and reuses the same browser instance for
    both calls instead of launching two separate ones.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=BROWSER_ARGS)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()
        try:
            yield page
        finally:
            browser.close()


def wait_for_challenge(page: Page, timeout: int = 15000):
    """
    Blocks until the JS bot-challenge screen is gone.
    Extracted into its own function so both helpers share
    identical waiting logic without copy-pasting.
    """
    page.wait_for_function(CHALLENGE_CHECK, timeout=timeout)
    page.wait_for_load_state("networkidle", timeout=timeout)


def navigate(page: Page, url: str):
    """
    Navigates to a URL and waits through any JS challenge.
    Raises on timeout so callers can handle it explicitly.
    """
    page.goto(url, wait_until="networkidle", timeout=10000)
    wait_for_challenge(page)


def extract_json_endpoint(url: str) -> str | None:
    """
    Visits the chapter page and pulls the JSON API URL from the
    <link rel="alternate" type="application/json"> tag in the <head>.
    Returns the href string or None if not found.
    """
    with get_page() as page:
        navigate(page, url)
        html = page.content()

    soup = BeautifulSoup(html, "html.parser")
    link_tag = soup.find("link", rel="alternate", type="application/json", title="JSON")
    if not link_tag:
        logger.warning("No JSON endpoint found on %s", url)
        return None

    return link_tag["href"]


def parse_json_data(json_url: str) -> dict | None:
    """
    Fetches the JSON API endpoint in the browser (so the challenge
    cookie obtained on the first visit is reused) and parses the
    response body as JSON.
    Returns a dict or None on failure.
    """
    with get_page() as page:
        navigate(page, json_url)
        try:
            return page.evaluate("() => JSON.parse(document.body.innerText)")
        except Exception as e:
            logger.error("JSON parse failed for %s: %s", json_url, e)
            return None


def extract_chapter(parsed_data: dict) -> dict:
    """
    Pulls only the fields we care about out of the raw API response.
    Separating this from the HTTP logic makes it easy to unit-test
    without a browser.
    """
    return {
        "title":          parsed_data["title"]["rendered"],
        "chapter":        parsed_data["content"]["rendered"],
        "chapter_number": parsed_data["slug"],
    }


@app.route("/", methods=["GET", "POST"])
def scrape():
    if request.method == "GET":
        return render_template("index.html")

    url = request.form.get("url", "").strip()
    if not url:
        return render_template("index.html", error="Please provide a URL.")

    try:
        json_url = extract_json_endpoint(url)
        if not json_url:
            return render_template("index.html", error="No JSON endpoint found.")

        parsed_data = parse_json_data(json_url)
        if not parsed_data:
            return render_template("index.html", error="Failed to fetch JSON data.")

        return render_template("index.html", data=extract_chapter(parsed_data))

    except Exception as e:
        logger.exception("Scrape failed for %s", url)
        return render_template("index.html", error=f"Unexpected error: {e}")