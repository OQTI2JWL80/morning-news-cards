import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from newsbrief.ai import Gemini, validate_summary
from newsbrief.config import KST, SECTIONS
from newsbrief.editorial import apply_classification, choose_articles, fallback_classify, same_event, trusted_candidate
from newsbrief.feeds import edition_cutoff, parse_feed
from newsbrief.net import FetchError, public_url
from newsbrief.storage import validate_edition, write_editions, load_previous
from newsbrief.__main__ import make_edition, public_article

CUTOFF = datetime(2026, 9, 29, 7, tzinfo=KST)


def article(identifier="a", title="한국은행 기준금리 동결 발표", section="business_kr", rank=0, city=None):
    return {"id": identifier, "title": title, "url": f"https://example.com/{identifier}", "publisher": "테스트언론",
            "publishedAt": (CUTOFF-timedelta(hours=1)).isoformat(), "feeds": {section: rank},
            "section": section, "city": city, "classification": "rules"}


def edition(day=CUTOFF, articles=None):
    return make_edition(day, articles or [article()], [{"status": "ok"}], Gemini(key=""))


class CutoffTests(unittest.TestCase):
    def test_before_and_after_seven(self):
        self.assertEqual(edition_cutoff(CUTOFF-timedelta(seconds=1)), CUTOFF-timedelta(days=1))
        self.assertEqual(edition_cutoff(CUTOFF), CUTOFF)
        self.assertEqual(edition_cutoff(CUTOFF+timedelta(hours=3)), CUTOFF)

    def test_year_boundary(self):
        self.assertEqual(edition_cutoff(datetime(2027,1,1,2,tzinfo=KST)).date().isoformat(), "2026-12-31")

    def test_future_refused(self):
        with self.assertRaises(ValueError): edition_cutoff(CUTOFF, "2026-09-30")

    def test_rss_exact_window_missing_time_and_future(self):
        timestamps = ["Mon, 28 Sep 2026 22:00:00 GMT", "Mon, 28 Sep 2026 22:00:01 GMT", "Sun, 27 Sep 2026 22:00:00 GMT", "Sun, 27 Sep 2026 22:00:01 GMT", "bad"]
        raw = '<rss><channel>' + ''.join(f'<item><title>기사 {i} - 매체</title><link>https://example.com/{i}</link><pubDate>{stamp}</pubDate><source url="https://example.com">매체</source></item>' for i,stamp in enumerate(timestamps)) + '</channel></rss>'
        items = parse_feed(raw.encode(), "top", CUTOFF)
        self.assertEqual([i["title"] for i in items], ["기사 0", "기사 3"])

    def test_xml_entity_refused(self):
        with self.assertRaises(ValueError): parse_feed(b'<!DOCTYPE x [<!ENTITY a "x">]><rss/>',"top",CUTOFF)


class EditorialTests(unittest.TestCase):
    def test_ai_rejection_clears_fallback_classification(self):
        item = article()
        apply_classification([item], [{"id": "a", "section": "unknown", "city": "", "confidence": 0}])
        self.assertIsNone(item['section'])

    def test_same_airport_certification_with_different_wording(self):
        a = article('a', "인천공항공사, ICAO 항공전문 국제교육기관 재인증 획득")
        b = article('b', "인천공항 항공교육원, 항공전문 국제교육기관 재인증 통과…2029년까지 자격 유지")
        self.assertTrue(same_event(a, b))

    def test_reordered_news_event_is_not_repeated(self):
        a = article("a", "BTS, 日 오리콘 100만 포인트 싱글 통산 네 번째 해외 가수 신기록", "entertainment_kr")
        b = article("b", "BTS, 日 오리콘 합산 싱글 100만 포인트 추가 해외 가수 최다", "entertainment_kr")
        self.assertEqual(len(choose_articles([a, b])), 1)

    def test_duplicate_event_in_top_is_not_repeated(self):
        a = article("a", "한국은행 기준금리 동결 발표")
        a["feeds"]["top"] = 0
        b = article("b", "한국은행, 기준금리 동결 발표")
        self.assertTrue(same_event(a,b))
        selected = choose_articles([a,b])
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["section"], "top")

    def test_local_one_per_city(self):
        data = [article("s","서울시 공원 시민 행사", "local",city="서울시"),article("g","고양시 일산 버스 개편", "local",city="고양시"),article("p","파주시 운정 도로 개통", "local",city="파주시"),article("p2","파주시 문산 청년 지원", "local",city="파주시")]
        selected = choose_articles(data)
        self.assertEqual([a["city"] for a in selected], ["서울시","고양시","파주시"])

    def test_fewer_candidates_does_not_backfill_with_old_or_other_category(self):
        self.assertEqual(len(choose_articles([article()])),1)

    def test_world_is_not_publisher_country(self):
        item = article(title="미국 연준 기준금리 인하 발표")
        self.assertEqual(fallback_classify(item)["section"],"business_world")

    def test_unclear_geography_not_guessed(self):
        self.assertIsNone(fallback_classify(article(title="새 반도체 기술 연구 성과 발표"))["section"])

    def test_local_requires_local_event(self):
        self.assertEqual(fallback_classify(article(title="고양시 일산 버스 노선 개편 시행"))["city"], "고양시")

    def test_sport_idiom_is_not_a_social_incident(self):
        self.assertIsNone(fallback_classify(article(title="한국 육상, 제대로 사고 쳤다! 계주 동메달"))["section"])

    def test_daily_horoscope_is_not_top_news(self):
        item = article(title="[오늘의 성경말씀·29일] 생명의 근원이 이에서 남이니라")
        item['feeds']['top'] = 0
        self.assertEqual(choose_articles([item]), [])

    def test_korean_substring_and_generic_overseas_word_do_not_set_geography(self):
        self.assertIsNone(fallback_classify(article(title="무서울 수밖에 없는 영화 이야기"))["section"])
        self.assertIsNone(fallback_classify(article(title="해외 인재 영입 연구 계획"))["section"])

    def test_search_spam_and_unknown_sources_are_excluded(self):
        item=article(title='터치 조작과 마우스 조작의 차이, 도박 영화 한국')
        item['sourceUrl']='https://www.yna.co.kr'
        self.assertFalse(trusted_candidate(item))
        item['title']='한국은행 기준금리 동결'
        self.assertTrue(trusted_candidate(item))
        item['sourceUrl']='https://random-website.example'
        self.assertFalse(trusted_candidate(item))


class SummaryTests(unittest.TestCase):
    body = "서울시는 시민들을 위한 새 공원을 다음 달에 개방할 계획이라고 밝혔다. 공원에는 어린이들을 위한 놀이 공간과 산책로를 함께 조성했다. 방문객은 별도의 입장료 없이 시설을 자유롭게 이용할 수 있다."

    def valid(self):
        sentences = self.body.split('. ')
        return [{"text": text, "evidence": text} for text in sentences]

    def test_three_grounded_bullets(self):
        self.assertEqual(len(validate_summary(self.valid(),self.body)),3)

    def test_invented_evidence_and_number_rejected(self):
        bullets=self.valid();bullets[0]["evidence"]="이것은 제공된 기사 본문에 전혀 없는 근거 문장입니다."
        self.assertEqual(validate_summary(bullets,self.body),[])
        bullets=self.valid();bullets[0]["text"]="서울시는 120개의 새 공원을 다음 달에 개방할 계획이라고 밝혔다."
        self.assertEqual(validate_summary(bullets,self.body),[])

    def test_key_and_free_attestation_both_required(self):
        with patch('newsbrief.ai.fetch') as fetch:
            Gemini(key="test",confirmed=False).request("system",[],{})
            Gemini(key="",confirmed=True).request("system",[],{})
            fetch.assert_not_called()

    def test_quota_stops_calls_without_model_switch(self):
        client=Gemini(key="test",confirmed=True,interval=0)
        with patch('newsbrief.ai.fetch',side_effect=FetchError("429")) as fetch:
            self.assertIsNone(client.request("s",[],{}))
            self.assertIsNone(client.request("s",[],{}))
            self.assertEqual(fetch.call_count,1)
            self.assertEqual(client.reason,"quota_exceeded")

    def test_private_body_and_evidence_never_published(self):
        data=article();data.update(body=self.body,evidence="secret snippet",originalUrl="https://example.com/a")
        public=public_article(data,"key_missing")
        self.assertNotIn("body",public);self.assertNotIn("evidence",public)
        self.assertEqual(public["bullets"],[])


class OutputTests(unittest.TestCase):
    def test_archive_outage_does_not_erase_history(self):
        with tempfile.TemporaryDirectory() as path:
            with patch('newsbrief.storage.fetch', side_effect=FetchError('503')):
                with self.assertRaises(FetchError): load_previous(path, 'https://example.com/')
            with patch('newsbrief.storage.fetch', side_effect=FetchError('404')):
                self.assertEqual(load_previous(path, 'https://example.com/'), {})
            with patch('newsbrief.storage.fetch', side_effect=[(b'{"editions":[{"date":"2026-09-29"}]}', {}), FetchError('404')]):
                with self.assertRaises(FetchError): load_previous(path, 'https://example.com/')

    def test_duplicate_ids_invalid(self):
        data=edition();data["articles"].append(copy.deepcopy(data["articles"][0]))
        with self.assertRaises(ValueError):validate_edition(data)

    def test_cutoff_and_city_overallocation_invalid(self):
        data=edition();data["articles"][0]["publishedAt"]=(CUTOFF+timedelta(seconds=1)).isoformat()
        with self.assertRaises(ValueError):validate_edition(data)
        with self.assertRaises(ValueError):edition(articles=[article("a",section="local",city="서울시"),article("b",title="다른 기사",section="local",city="서울시")])

    def test_repeated_write_and_thirty_day_retention(self):
        with tempfile.TemporaryDirectory() as path:
            editions={}
            for delta in range(35):
                day=CUTOFF-timedelta(days=delta)
                a=article();a["publishedAt"]=(day-timedelta(hours=1)).isoformat()
                editions[day.date().isoformat()]=edition(day,[a])
            write_editions(path,editions,CUTOFF);write_editions(path,editions,CUTOFF)
            self.assertEqual(len(list(Path(path).glob('????-??-??.json'))),30)
            self.assertEqual(len(load_previous(path)),30)

    def test_safe_public_urls(self):
        for url in ['file:///etc/passwd','http://127.0.0.1/x','http://192.168.1.1','https://localhost/','javascript:alert(1)','https://user:pass@example.com','http://[::1]/']:
            self.assertFalse(public_url(url),url)
        self.assertTrue(public_url('https://example.com/news'))

    def test_invalid_body_fields_cannot_enter_archive(self):
        data=edition();data['articles'][0]['body']='private raw article'
        with self.assertRaises(ValueError):validate_edition(data)

    def test_missing_summary_is_visible(self):
        data=edition()
        self.assertEqual(data['status'],'partial')
        self.assertEqual(data['summaryCount'],0)


if __name__ == '__main__':unittest.main()
