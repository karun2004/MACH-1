"""
RSS Scraper
Fetches topics from configured RSS sources.
"""
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional
import requests

from utils.logger import get_logger
from utils.database import db

log = get_logger("mach1.rss")

# ── Default RSS sources (11 sources) ─────────────
DEFAULT_SOURCES = [
    ("Hackaday", "https://hackaday.com/feed/", "hardware"),
    ("IEEE Spectrum Robotics", "https://spectrum.ieee.org/feeds/topic/robotics.rss", "robotics"),
    ("ROS Discourse", "https://discourse.ros.org/latest.rss", "robotics"),
    ("Adafruit", "https://blog.adafruit.com/feed/", "hardware"),
    ("Arduino Blog", "https://blog.arduino.cc/feed/", "embedded"),
    ("MIT Tech Review AI", "https://www.technologyreview.com/feed/", "ai"),
    ("Towards Data Science", "https://towardsdatascience.com/feed", "ai"),
    ("The Robot Report", "https://www.therobotreport.com/feed/", "robotics"),
    ("Embedded.com", "https://www.embedded.com/feed/", "embedded"),
    ("Dev.to Embedded", "https://dev.to/feed/tag/embedded", "embedded"),
    ("Hacker News Best", "https://hnrss.org/best", "general"),
]


def init_default_sources():
    """Populate RSS sources table with defaults if empty."""
    existing = db.get_rss_sources(enabled_only=False)
    if existing:
        return len(existing)

    for name, url, category in DEFAULT_SOURCES:
        db.add_rss_source(name, url, category)
    log.info(f"Initialized {len(DEFAULT_SOURCES)} RSS sources")
    return len(DEFAULT_SOURCES)


def fetch_source(source: dict) -> list:
    """Fetch and parse a single RSS source. Returns list of topic dicts."""
    topics = []
    try:
        resp = requests.get(source["url"], timeout=15, headers={
            "User-Agent": "MACH-1/3.0 RSS Reader"
        })
        resp.raise_for_status()

        root = ET.fromstring(resp.content)

        # Handle both RSS 2.0 and Atom feeds
        items = root.findall(".//item")  # RSS 2.0
        if not items:
            # Atom feed
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            items = root.findall(".//atom:entry", ns)

        for item in items[:20]:  # Cap at 20 per source
            title = _get_text(item, "title") or _get_text(item, "atom:title", ns={"atom": "http://www.w3.org/2005/Atom"})
            link = _get_text(item, "link") or _get_attr(item, "atom:link", "href", ns={"atom": "http://www.w3.org/2005/Atom"})
            desc = _get_text(item, "description") or _get_text(item, "atom:summary", ns={"atom": "http://www.w3.org/2005/Atom"})

            if title and link:
                # Clean HTML from description
                if desc:
                    import re
                    desc = re.sub(r"<[^>]+>", "", desc)[:500]

                topics.append({
                    "title": title.strip(),
                    "url": link.strip(),
                    "summary": (desc or "").strip(),
                    "source_id": source["id"],
                })

        # Update last_fetched
        db.update(
            "UPDATE rss_sources SET last_fetched = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), source["id"]),
        )
        log.info(f"Fetched {len(topics)} topics from {source['name']}")

    except Exception as e:
        log.warning(f"Failed to fetch {source['name']}: {e}")

    return topics


def _get_text(element, tag, ns=None):
    """Safely get text from XML element."""
    if ns:
        child = element.find(tag, ns)
    else:
        child = element.find(tag)
    return child.text if child is not None and child.text else None


def _get_attr(element, tag, attr, ns=None):
    """Safely get attribute from XML element."""
    if ns:
        child = element.find(tag, ns)
    else:
        child = element.find(tag)
    return child.get(attr) if child is not None else None


def scrape_all() -> int:
    """Fetch all enabled RSS sources and save new topics. Returns count."""
    sources = db.get_rss_sources(enabled_only=True)
    if not sources:
        init_default_sources()
        sources = db.get_rss_sources(enabled_only=True)

    total = 0
    for source in sources:
        topics = fetch_source(source)
        for t in topics:
            try:
                db.add_topic(
                    title=t["title"],
                    url=t["url"],
                    source_id=t["source_id"],
                    summary=t["summary"],
                )
                total += 1
            except Exception:
                pass  # Duplicate URL, skip

    log.info(f"RSS scrape complete: {total} new topics from {len(sources)} sources")
    return total
