import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

from .config import CITIES, KST, RETENTION_DAYS, SECTIONS
from .net import FetchError, fetch, public_url


def validate_edition(edition):
    if not isinstance(edition, dict) or edition.get("schemaVersion") != 1:
        raise ValueError("Invalid edition schema")
    day = edition.get("date", "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise ValueError("Invalid date")
    cutoff = datetime.fromisoformat(edition["cutoffAt"])
    if cutoff.tzinfo is None or cutoff.astimezone(KST).strftime("%Y-%m-%dT%H:%M:%S") != day + "T07:00:00":
        raise ValueError("Invalid cutoff")
    if datetime.fromisoformat(edition["generatedAt"]).tzinfo is None:
        raise ValueError("Missing generation timezone")
    articles = edition.get("articles")
    if not isinstance(articles, list) or len(articles) > 33:
        raise ValueError("Invalid article count")
    if [s.get("id") for s in edition.get("sections", [])] != [s["id"] for s in SECTIONS]:
        raise ValueError("Invalid section list")
    ids, cities = set(), set()
    counts = {s["id"]: 0 for s in SECTIONS}
    allowed = {"id", "title", "section", "city", "publishedAt", "sources", "bullets", "summaryStatus", "classification"}
    for article in articles:
        if set(article) - allowed:
            raise ValueError("Unexpected or private article field")
        if article["id"] in ids or article["section"] not in counts:
            raise ValueError("Duplicate or invalid article")
        ids.add(article["id"])
        counts[article["section"]] += 1
        if not isinstance(article["title"], str) or not 1 <= len(article["title"]) <= 250:
            raise ValueError("Invalid headline")
        stamp = datetime.fromisoformat(article["publishedAt"])
        if stamp.tzinfo is None or not cutoff - timedelta(days=1) < stamp <= cutoff:
            raise ValueError("Article outside cutoff")
        if article["section"] == "local":
            if article.get("city") not in CITIES or article["city"] in cities:
                raise ValueError("Invalid city allocation")
            cities.add(article["city"])
        if not article.get("sources") or any(not public_url(s["url"]) for s in article["sources"]):
            raise ValueError("Invalid source")
        bullets = article.get("bullets", [])
        if article["summaryStatus"] == "summarized":
            if len(bullets) != 3 or any(not isinstance(b, str) or not 20 <= len(b) <= 130 for b in bullets):
                raise ValueError("Invalid summary")
        elif bullets:
            raise ValueError("Unverified summary")
    if any(counts[s["id"]] > s["count"] for s in SECTIONS):
        raise ValueError("Section over quota")
    for section in edition["sections"]:
        spec = next(s for s in SECTIONS if s["id"] == section["id"])
        if section.get("count") != spec["count"] or section.get("available") != counts[section["id"]]:
            raise ValueError("Invalid section counts")
    if edition.get("summaryCount") != sum(a["summaryStatus"] == "summarized" for a in articles):
        raise ValueError("Invalid summary count")
    encoded = json.dumps(edition, ensure_ascii=False)
    if re.search(r"AIza[0-9A-Za-z_-]{25,}|github_pat_[0-9A-Za-z_]+|gh[pousr]_[0-9A-Za-z]{20,}", encoded):
        raise ValueError("Secret-like content in public output")
    return edition


def load_previous(directory, base_url=None):
    editions = {}
    directory = Path(directory)
    if directory.exists():
        for path in directory.glob("????-??-??.json"):
            try:
                edition = validate_edition(json.loads(path.read_text(encoding="utf-8")))
                editions[edition["date"]] = edition
            except (ValueError, KeyError, TypeError, OSError):
                pass
    if base_url:
        # Previous output is untrusted data, never code. Only this origin and fixed filenames.
        base_url = base_url.rstrip("/") + "/"
        try:
            raw, _ = fetch(urljoin(base_url, "data/index.json"), retries=0, limit=100_000)
            index = json.loads(raw)
            for entry in index.get("editions", [])[:RETENTION_DAYS]:
                day = entry.get("date", "")
                if day in editions or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
                    continue
                raw, _ = fetch(urljoin(base_url, f"data/{day}.json"), retries=0, limit=250_000)
                edition = validate_edition(json.loads(raw))
                if edition["date"] == day:
                    editions[day] = edition
        except FetchError as exc:
            # Only an absent first index is expected. A partial restore must
            # never replace the archive with a silently truncated history.
            if exc.code != "404" or 'index' in locals():
                raise
    return editions


def write_editions(directory, editions, cutoff):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    earliest = (cutoff - timedelta(days=RETENTION_DAYS - 1)).date().isoformat()
    current = cutoff.date().isoformat()
    editions = {day: validate_edition(e) for day, e in editions.items() if earliest <= day <= current}
    if not editions:
        raise ValueError("No valid editions")
    for old in directory.glob("????-??-??.json"):
        if old.stem not in editions:
            old.unlink()  # Fixed generated data directory only; never touches source files.
    for day, edition in editions.items():
        path = directory / f"{day}.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(edition, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        temp.replace(path)
    days = sorted(editions, reverse=True)
    index = {"schemaVersion": 1, "latest": days[0], "editions": [
        {"date": day, "count": len(editions[day]["articles"]), "status": editions[day]["status"]} for day in days
    ]}
    (directory / "index.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
