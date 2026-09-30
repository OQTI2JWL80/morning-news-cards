import argparse
import json
import os
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from .ai import Gemini
from .config import CITIES, EDITORIAL_VERSION, KST, MODEL, SECTIONS
from .content import enrich
from .editorial import apply_classification, choose_articles, fallback_classify, trusted_candidate
from .feeds import collect, edition_cutoff
from .net import FetchError
from .storage import load_previous, validate_edition, write_editions

ROOT = Path(__file__).resolve().parent.parent


def edition_quality(edition):
    # A headline-only edition must not prevent activation of verified summaries.
    return (edition["summaryCount"], len(edition["articles"]), edition["collection"]["feedsOk"])


def public_article(article, reason):
    status = article.get("summaryStatus", "body_unavailable")
    if status == "ready":
        status = reason or "summary_unverified"
    source_url = article.get("originalUrl") or article["url"]
    sources = [{"name": article["publisher"], "url": source_url}]
    for related in article.get("related", []):
        if all(s["name"] != related["publisher"] for s in sources):
            sources.append({"name": related["publisher"], "url": related["url"]})
    return {
        "id": article["id"], "title": article["title"], "section": article["section"],
        "city": article.get("city") if article["section"] == "local" else None,
        "publishedAt": article["publishedAt"], "sources": sources,
        "bullets": article.get("bullets", []) if status == "summarized" else [],
        "summaryStatus": status, "classification": article.get("classification", "rss"),
    }


def make_edition(cutoff, selected, feed_reports, ai):
    articles = [public_article(a, ai.reason) for a in selected]
    counts = Counter(a["section"] for a in articles)
    summaries = sum(a["summaryStatus"] == "summarized" for a in articles)
    return validate_edition({
        "schemaVersion": 1, "editorialVersion": EDITORIAL_VERSION, "date": cutoff.date().isoformat(), "cutoffAt": cutoff.isoformat(),
        "generatedAt": datetime.now(KST).isoformat(timespec="seconds"),
        "status": "complete" if len(articles) == 33 and summaries == 33 and all(f["status"] == "ok" for f in feed_reports) else "partial",
        "sections": [{**s, "available": counts[s["id"]]} for s in SECTIONS],
        "articles": articles, "summaryCount": summaries,
        "collection": {"feedsOk": sum(f["status"] == "ok" for f in feed_reports), "feedsTotal": len(feed_reports), "candidateWindowHours": 24},
        "ai": {"model": MODEL, "calls": ai.calls, "status": ai.reason or "ok"},
    })


def main():
    parser = argparse.ArgumentParser(description="07시 뉴스 카드를 생성합니다.")
    parser.add_argument("--date", help="한국시간 집계 날짜 YYYY-MM-DD (기본: 최근 마감)")
    parser.add_argument("--output", default="build")
    parser.add_argument("--archive", default=".local/archive")
    parser.add_argument("--previous-url", help="이전 GitHub Pages 주소; 최근 30일 자료 복원")
    parser.add_argument("--no-ai", action="store_true")
    parser.add_argument("--skip-content", action="store_true", help="원문 수집을 생략하여 RSS 연결만 점검")
    args = parser.parse_args()
    cutoff = edition_cutoff(edition_date=args.date)
    output = Path(args.output).resolve()
    # All pruning is limited to a designated generated output, never an arbitrary tree.
    if output == ROOT or output in ROOT.parents or output == Path(args.archive).resolve() or ROOT / "site" == output:
        raise ValueError("Output must be a separate generated directory")
    ai = Gemini(key="" if args.no_ai else None)
    print(f"집계 날짜: {cutoff.date()} / 마감: 07:00 KST", flush=True)
    items, reports = collect(cutoff)
    print(f"RSS {sum(r['status'] == 'ok' for r in reports)}/{len(reports)}, 후보 {len(items)}개", flush=True)
    if not items:
        print("유효한 기사가 없습니다. 기존 게시물을 유지합니다.", file=sys.stderr)
        return 2
    items = [item for item in items if trusted_candidate(item)]
    print(f"출처와 뉴스 적합성 확인 후 {len(items)}개 후보", flush=True)
    for item in items:
        item.update(fallback_classify(item))
    apply_classification(items, ai.classify(items))
    selected = choose_articles(items)
    print(f"서로 다른 기사 {len(selected)}개 선정 / AI 상태: {ai.reason or '사용 가능'}", flush=True)
    if not selected:
        print("게시 가능한 기사가 없습니다. 기존 게시물을 유지합니다.", file=sys.stderr)
        return 2
    if not args.skip_content:
        selected = enrich(selected, cutoff)
        print(f"원문 확인: {sum(bool(a.get('body')) for a in selected)}개", flush=True)
        ai.summarize(selected)
    if ai.last_error:
        print(f"AI 응답 진단: {ai.last_error}", flush=True)
    edition = make_edition(cutoff, selected, reports, ai)
    previous = load_previous(args.archive, args.previous_url)
    old = previous.get(edition["date"])
    # A degraded rerun must not replace a more complete same-day edition.
    if old and old.get('editorialVersion') == EDITORIAL_VERSION and edition_quality(old) > edition_quality(edition):
        edition = old
        print("같은 날짜의 기존 결과가 더 완전하여 유지합니다.", flush=True)
    previous[edition["date"]] = edition
    retention_cutoff = edition_cutoff()
    write_editions(args.archive, previous, retention_cutoff)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "site", output, dirs_exist_ok=True)
    write_editions(output / "data", previous, retention_cutoff)
    (output / ".nojekyll").touch()
    record = {"edition": edition["date"], "generatedAt": edition["generatedAt"], "articles": len(edition["articles"]), "summaries": edition["summaryCount"], "status": edition["status"]}
    (output / "run-record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, FetchError) as exc:
        # Deliberately print only the type; raw network/third-party messages may contain credentials.
        print(f"생성을 중단했습니다 ({type(exc).__name__}). 기존 게시물은 유지됩니다.", file=sys.stderr)
        sys.exit(2)
