import time
import re
from collections import Counter
from flask import Flask, jsonify, request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = Flask(__name__)

REGISTRATION = "FA23-BAI-064"
NEWS_SOURCE = "Ars Technica"

STOPWORDS = set([
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "dare",
    "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
    "from", "as", "into", "through", "during", "before", "after", "above",
    "below", "between", "under", "and", "but", "or", "yet", "so", "if",
    "because", "although", "though", "while", "where", "when", "that",
    "which", "who", "whom", "whose", "what", "this", "these", "those",
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you",
    "your", "yours", "yourself", "yourselves", "he", "him", "his", "himself",
    "she", "her", "hers", "herself", "it", "its", "itself", "they", "them",
    "their", "theirs", "themselves", "am", "having", "doing", "until",
    "about", "against", "up", "down", "out", "off", "over", "under", "again",
    "further", "then", "once", "here", "there", "why", "how", "all",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "than", "too", "very", "just",
    "don", "now", "s", "t", "said", "also", "one", "two", "three",
    "first", "last", "new", "like", "get", "make", "go", "know", "take",
    "see", "come", "think", "look", "want", "give", "use", "find", "tell",
    "ask", "work", "seem", "feel", "try", "leave", "call", "good", "great",
    "right", "old", "different", "big", "next", "early", "young", "important",
    "public", "able", "us"
])


def get_chrome_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)
    return driver


def is_valid_article_url(url):
    """Reject homepage, categories, tags, authors, search pages."""
    if not url:
        return False
    url = url.strip()
    if url in ("https://arstechnica.com", "https://arstechnica.com/"):
        return False
    if "/search/" in url or "/tag/" in url or "/author/" in url:
        return False
    if "/category/" in url or "/topics/" in url:
        return False
    # Ars Technica articles have /YYYY/MM/ in URL
    if not re.search(r'/20\d\d/', url):
        return False
    return True


def summarize_text(text, num_sentences=3):
    if not text or len(text.strip()) < 50:
        return text.strip() if text else "No content available."

    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 15]

    if len(sentences) <= num_sentences:
        return " ".join(sentences)

    word_freq = Counter()
    for sentence in sentences:
        words = re.findall(r'\b[a-zA-Z]{3,}\b', sentence.lower())
        for word in words:
            if word not in STOPWORDS:
                word_freq[word] += 1

    sentence_scores = []
    for sentence in sentences:
        words = re.findall(r'\b[a-zA-Z]{3,}\b', sentence.lower())
        if not words:
            continue
        score = sum(word_freq.get(word, 0) for word in words if word not in STOPWORDS)
        sentence_scores.append((score / len(words), sentence))

    if not sentence_scores:
        return " ".join(sentences[:num_sentences])

    sentence_scores.sort(key=lambda x: x[0], reverse=True)
    top_sentences = set(s[1] for s in sentence_scores[:num_sentences])
    ordered = [s for s in sentences if s in top_sentences]
    return " ".join(ordered)


def find_first_article(driver, search_url):
    """Try multiple selectors to find the first real article link."""
    wait = WebDriverWait(driver, 20)

    # Wait for any article or result to appear
    time.sleep(4)

    # Strategy 1: Common Ars Technica search/article selectors
    selectors = [
        "article h2 a",
        "article h3 a",
        ".result h2 a",
        ".result h3 a",
        ".search-result h2 a",
        ".search-result h3 a",
        ".teaser h2 a",
        ".teaser h3 a",
        "h2 a[href*='arstechnica.com']",
        "h3 a[href*='arstechnica.com']",
        "article a[href]",
        "li a[href*='arstechnica.com']",
        "a[href*='arstechnica.com']",
    ]

    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for el in elements:
                href = el.get_attribute("href")
                if is_valid_article_url(href):
                    return href.strip()
        except Exception:
            continue

    # Strategy 2: Scan all links as last resort
    links = driver.find_elements(By.TAG_NAME, "a")
    for link in links:
        try:
            href = link.get_attribute("href")
            if is_valid_article_url(href):
                return href.strip()
        except Exception:
            continue

    return None


def scrape_ars_technica(keyword):
    driver = get_chrome_driver()
    result_url = ""
    summary = ""

    try:
        query = keyword.replace(" ", "+")

        # Try Ars Technica search page first
        search_url = f"https://arstechnica.com/search/?query={query}"
        driver.get(search_url)

        article_url = find_first_article(driver, search_url)

        # Fallback: try WordPress search format if first fails
        if not article_url:
            wp_search = f"https://arstechnica.com/?s={query}"
            driver.get(wp_search)
            article_url = find_first_article(driver, wp_search)

        if not article_url:
            return "", "No article found for the given keyword."

        result_url = article_url.strip().strip()

        # Visit the article
        driver.get(article_url)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(2)

        article_text = ""
        content_selectors = [
            "article",
            "[itemprop='articleBody']",
            ".article-content",
            ".post-content",
            "main article",
            "main"
        ]

        for selector in content_selectors:
            try:
                elem = driver.find_element(By.CSS_SELECTOR, selector)
                text = elem.text
                if len(text) > 200:
                    article_text = text
                    break
            except Exception:
                continue

        if not article_text:
            try:
                article_text = driver.find_element(By.TAG_NAME, "body").text
            except Exception:
                article_text = ""

        # Clean text
        lines = [line.strip() for line in article_text.split("\n")
                 if len(line.strip()) > 25 and not line.strip().startswith("©")]
        article_text = " ".join(lines[:80])

        summary = summarize_text(article_text)

    except Exception as e:
        summary = f"Error during scraping: {str(e)}"
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    return result_url, summary


@app.route("/get", methods=["GET"])
def get_news():
    keyword = request.args.get("keyword", "").strip()
    if not keyword:
        return jsonify({
            "registration": REGISTRATION,
            "newssource": NEWS_SOURCE,
            "keyword": "",
            "url": "",
            "summary": "Error: 'keyword' query parameter is required."
        }), 400

    url, summary = scrape_ars_technica(keyword)

    return jsonify({
        "registration": REGISTRATION,
        "newssource": NEWS_SOURCE,
        "keyword": keyword,
        "url": url,
        "summary": summary,
    })


@app.route("/", methods=["GET"])
def index():
    return (
        "<h1>Ars Technica News Scraper API</h1>"
        "<p><strong>Registration Number:</strong> " + REGISTRATION + "</p>"
        "<p><strong>News Source:</strong> " + NEWS_SOURCE + "</p>"
        "<p>API Endpoint: <code>GET /get?keyword=YOUR_KEYWORD</code></p>"
        "<p>Port: 7000</p>"
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7000, debug=False)
