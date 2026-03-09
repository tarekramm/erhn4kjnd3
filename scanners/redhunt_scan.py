import requests
import tempfile
import json
import os
import re
import time
import sqlite3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# CONFIG

DOMAINS = [
    "paste2.org", "jsbin.com", "play.golang.org", "paste.debian.net",
    "pastehtml.com", "pastebin.com", "snipplr.com", "snipt.net",
    "heypasteit.com", "pastebin.fr", "slexy.org", "hastebin.com",
    "dumpz.org", "codepad.org", "jsitor.com", "dpaste.org",
    "textsnip.com", "bitpaste.app", "justpaste.it", "jsfiddle.net",
    "dpaste.com", "codepen.io", "dartpad.dartlang.org",
    "ide.codingblocks.com", "dotnetfiddle.net", "ideone.com",
    "paste.fedoraproject.org", "paste.frubar.net", "repl.it",
    "paste.opensuse.org", "rextester.com", "paste.org.ru",
    "paste.ubuntu.com", "paste.pound-python.org", "paste.lisp.org",
    "paste.xinu.at", "try.ceylon-lang.org", "paste.org",
    "phpfiddle.org", "ide.geeksforgeeks.org",
    "controlc.com", "p.ip.fi", "0bin.net", "privatebin.net",
    "paste.ee", "paste.rs", "nekobin.com", "dpaste.com",
    "play.kotlinlang.org", "play.rust-lang.org", "onecompiler.com",
    "runkit.com", "tio.run", "godbolt.org", "trycf.com",
    "pastie.io", "pastebucket.com", "bpaste.net", "notes.io"
]

DB_PATH = "....db"


# HTTP session with retries
def get_retry_session(total_retries=3, backoff_factor=1):
    session = requests.Session()
    retries = Retry(
        total=total_retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 502, 503, 504],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# Extract URLs from page
def extract_urls_from_page(url):
    try:
        session = get_retry_session()
        resp = session.get(url, timeout=10)
        html = resp.text
        urls = re.findall(r'https?://[^\s\'"<>()]+', html)
        return html, list(set(urls))
    except Exception:
        return "", []


# Collect URLs from Wayback Machine
def collect_wayback_urls(domain, limit=50000):
    print("Collecting Wayback URLs for:", domain)

    base_url = "https://web.archive.org/cdx/search/cdx"
    params = {
        "url": f"*.{domain}/*",
        "matchType": "prefix",
        "output": "json",
        "fl": "timestamp,original,statuscode",
        "collapse": "digest",
        "limit": str(limit),
    }

    session = get_retry_session()

    try:
        response = session.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print("Wayback error:", e)
        return []

    filtered_urls = []

    skip_exts = re.compile(
        r"\.(css|js|png|jpg|jpeg|gif|svg|woff|ttf|ico|mp4|mp3|avi|pdf|zip|exe|bin)$",
        re.IGNORECASE,
    )

    for entry in data[1:]:
        try:
            timestamp, original_url, status = entry
        except ValueError:
            continue

        if status != "200":
            continue

        if skip_exts.search(original_url):
            continue

        filtered_urls.append(original_url)

    time.sleep(2)
    return list(set(filtered_urls))


# Filter useful paste-like URLs
def filter_suspect_urls(urls):
    good_urls = []

    allow_extensions = (
        ".js", ".json", ".env", ".php", ".conf", ".sql", ".log", ".txt"
    )

    block_extensions = (
        ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg",
        ".ico", ".woff", ".ttf", ".mp4", ".mp3", ".avi",
        ".zip", ".pdf"
    )

    for url in urls:
        parsed = url.lower()

        if any(parsed.endswith(ext) for ext in block_extensions):
            continue

        if any(parsed.endswith(ext) for ext in allow_extensions):
            good_urls.append(url)
            continue

        if parsed.endswith(("/", ".com", ".net", ".org", ".html")) and "?" not in parsed:
            continue

        if any(x in parsed for x in [
            "paste", "view", "raw", "snippet", "bin",
            "code", "id=", "doc=", "/p/", "/d/", "/show/"
        ]):
            good_urls.append(url)

    return list(set(good_urls))


# Main collection pipeline
def process_all_domains():
    results = []

    for domain in DOMAINS:
        base_url = f"https://{domain}"
        print("Scanning:", base_url)

        base_html, paste_links = extract_urls_from_page(base_url)
        paste_links = filter_suspect_urls(paste_links)

        wayback_links = collect_wayback_urls(domain)
        wayback_links = filter_suspect_urls(wayback_links)

        all_links = list(set(paste_links + wayback_links))

        for url in all_links:
            print("Found:", url)
            results.append({
                "source_domain": domain,
                "url": url
            })

    return results


# Save results to SQLite
def save_results_to_db(records):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_domain TEXT,
            url TEXT UNIQUE
        )
    """)

    saved = 0

    for record in records:
        try:
            c.execute(
                "INSERT OR IGNORE INTO urls (source_domain, url) VALUES (?, ?)",
                (record["source_domain"], record["url"])
            )
            saved += 1
        except Exception as e:
            print("DB insert failed:", e)

    conn.commit()
    conn.close()
    print("Saved", saved, "records to database")


# Entry point
if __name__ == "__main__":
    results = process_all_domains()
    save_results_to_db(results)
