"""Resolve public article links and extract text without bypassing access controls."""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from .net import FetchError, USER_AGENT, fetch, public_url


def resolve_urls(articles):
    urls = list(dict.fromkeys(a["url"] for a in articles))
    google = [u for u in urls if urlparse(u).hostname == "news.google.com"]
    resolved = {u: u for u in urls if u not in google and public_url(u)}
    if google:
        try:
            from googlenewsdecoder import gnewsdecoder
            results = gnewsdecoder(google, interval=.25, timeout=10)
            if isinstance(results, list):
                for original, result in zip(google, results):
                    target = result.get("decoded_url", "")
                    if result.get("success") and public_url(target):
                        resolved[original] = target
        except Exception:
            # Decoder is an unofficial adapter and may break independently of RSS.
            # Do not log its exceptions: they can contain full third-party payloads.
            pass
    return resolved


def robots_allowed(url, cache):
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in cache:
        try:
            raw, _ = fetch(origin + "/robots.txt", limit=300_000, retries=0, timeout=8)
            parser = RobotFileParser()
            parser.parse(raw.decode("utf-8", errors="replace").splitlines())
            cache[origin] = parser
        except FetchError as exc:
            cache[origin] = True if exc.code == "404" else False
    rule = cache[origin]
    return rule if isinstance(rule, bool) else rule.can_fetch(USER_AGENT, url)


def extract_article(raw, final_url, cutoff):
    from lxml import html as html_parser
    from trafilatura import extract
    try:
        tree = html_parser.fromstring(raw)
        meta = {n.get("property") or n.get("name"): n.get("content", "") for n in tree.xpath("//meta[@content]")}
        modified = meta.get("article:modified_time") or meta.get("og:updated_time")
        if modified:
            try:
                stamp = datetime.fromisoformat(modified.replace("Z", "+00:00"))
                if stamp.tzinfo and stamp > cutoff:
                    return "", "updated_after_cutoff"
            except ValueError:
                pass
        for script in tree.xpath('//script[@type="application/ld+json"]'):
            if re.search(r'"isAccessibleForFree"\s*:\s*(?:false|"false")', script.text or "", re.I):
                return "", "restricted"
        text = extract(raw, url=final_url, include_comments=False, include_tables=False, favor_precision=True) or ""
        if len(text) < 250:
            return "", "body_too_short"
        if re.search(r"구독.{0,10}(필요|전용)|유료\s*회원|로그인.{0,12}(읽|열람)|access denied|verify you are human|just a moment", text, re.I):
            return "", "restricted"
        # Bound input size; never persist raw text, evidence snippets, or HTML.
        return text[:6500], "ready"
    except (ValueError, TypeError):
        return "", "body_parse_failed"


def enrich(articles, cutoff):
    # Only already collected reports directly matched to this event are alternatives.
    # Publication cutoff and event matching are checked again before using a body.
    from .editorial import same_event
    def candidates(article):
        result = [{**article}]
        for related in article.get('related', [])[:2]:
            try:
                stamp = datetime.fromisoformat(related['publishedAt'])
                if stamp.tzinfo and cutoff - timedelta(days=1) < stamp <= cutoff and same_event(article, related):
                    result.append(related)
            except (ValueError, KeyError, TypeError):
                continue
        return result
    resolved = resolve_urls([item for article in articles for item in candidates(article)])
    robots_cache = {}
    for url in dict.fromkeys(resolved.values()):
        robots_allowed(url, robots_cache)

    def read(article):
        attempts = candidates(article)
        article.update(body="", bullets=[], summaryStatus="body_unavailable", originalUrl=None, bodyAttempts=[])
        for candidate in attempts:
            target = resolved.get(candidate['url'])
            final, body, status = target, '', 'link_unresolved'
            if target:
                status = 'robots_blocked'
                if robots_allowed(target, robots_cache):
                    try:
                        raw, final = fetch(target, retries=0, timeout=12)
                        if robots_allowed(final, robots_cache):
                            body, status = extract_article(raw, final, cutoff)
                    except FetchError:
                        status = 'fetch_failed'
                    except ImportError:
                        status = 'extractor_unavailable'
            article['bodyAttempts'].append({'name': candidate['publisher'], 'url': final or candidate['url'], 'status': status})
            article['summaryStatus'] = status
            if body:
                # Keep the headline, publication time and source aligned with the text used.
                # Related sources never inherit a summary of the inaccessible original.
                article.update(body=body, originalUrl=final, title=candidate['title'],
                               publisher=candidate['publisher'], publishedAt=candidate['publishedAt'], url=candidate['url'])
                article['related'] = [i for i in attempts if i is not candidate][:2]
                break
        return article

    with ThreadPoolExecutor(max_workers=3) as pool:
        return list(pool.map(read, articles))
