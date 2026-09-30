import hashlib
import html
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

from .config import KST, QUERIES
from .net import FetchError, fetch, public_url


def edition_cutoff(now=None, edition_date=None):
    now = (now or datetime.now(KST)).astimezone(KST)
    if edition_date:
        cutoff = datetime.strptime(edition_date, "%Y-%m-%d").replace(hour=7, tzinfo=KST)
        if cutoff > now:
            raise ValueError("미래 날짜 또는 아직 마감되지 않은 날짜는 생성할 수 없습니다.")
        return cutoff
    cutoff = now.replace(hour=7, minute=0, second=0, microsecond=0)
    return cutoff if now >= cutoff else cutoff - timedelta(days=1)


def clean_text(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def parse_feed(raw, feed_key, cutoff):
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("Unsafe XML")
    root = ET.fromstring(raw)
    start = cutoff - timedelta(days=1)
    items = []
    for rank, node in enumerate(root.findall("./channel/item")):
        title = clean_text(node.findtext("title"))
        url = node.findtext("link", "").strip()
        publisher = clean_text(node.findtext("source"))
        source = node.find("source")
        try:
            published = parsedate_to_datetime(node.findtext("pubDate", ""))
            if published.tzinfo is None:
                continue
            published = published.astimezone(KST)
        except (ValueError, TypeError, OverflowError):
            continue
        if not start < published <= cutoff or not public_url(url) or not title:
            continue
        suffix = f" - {publisher}"
        if publisher and title.endswith(suffix):
            title = title[:-len(suffix)]
        identifier = hashlib.sha256(url.encode()).hexdigest()[:16]
        items.append({
            "id": identifier, "title": title[:250], "url": url,
            "publisher": publisher or "출처 확인", "sourceUrl": source.get("url", "") if source is not None else "",
            "publishedAt": published.isoformat(), "feeds": {feed_key: rank},
        })
    return items


def feed_urls(cutoff):
    locale = {"hl": "ko", "gl": "KR", "ceid": "KR:ko"}
    urls = {"top": "https://news.google.com/rss?" + urlencode(locale)}
    # Search date operators are broad; exact timestamp filtering above owns the cutoff.
    after = (cutoff - timedelta(days=2)).strftime("%Y-%m-%d")
    before = (cutoff + timedelta(days=1)).strftime("%Y-%m-%d")
    for key, query in QUERIES.items():
        urls[key] = "https://news.google.com/rss/search?" + urlencode({
            "q": f"{query} after:{after} before:{before}", **locale,
        })
    for topic, key in [("BUSINESS", "business"), ("TECHNOLOGY", "science"), ("SCIENCE", "science"), ("ENTERTAINMENT", "entertainment"), ("HEALTH", "health")]:
        urls[f"topic_{topic.lower()}"] = f"https://news.google.com/rss/headlines/section/topic/{topic}?" + urlencode(locale)
    return urls


def collect(cutoff):
    def read(pair):
        key, url = pair
        try:
            raw, _ = fetch(url, limit=2_000_000, timeout=12)
            return key, parse_feed(raw, key, cutoff), None
        except (FetchError, ValueError, ET.ParseError):
            return key, [], "feed_unavailable"

    combined, reports = {}, []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for key, items, error in pool.map(read, feed_urls(cutoff).items()):
            reports.append({"feed": key, "count": len(items), "status": error or "ok"})
            # Bound classification cost while preserving top candidates per feed.
            for item in items[:18]:
                if item["id"] in combined:
                    combined[item["id"]]["feeds"].update(item["feeds"])
                else:
                    combined[item["id"]] = item
    return list(combined.values()), reports

