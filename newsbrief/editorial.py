"""Conservative fallback classification and cross-section event deduplication."""
import re
from difflib import SequenceMatcher
from urllib.parse import urlparse

from .config import CITIES, SECTION_IDS, SECTIONS, TRUSTED_DOMAINS

FOREIGN = re.compile(r"(?<![가-힣])(?:미국|유럽|일본|중국|영국|프랑스|독일|러시아|우크라이나|이스라엘|이란|대만|인도|호주|캐나다|트럼프|시진핑|도쿄|뉴욕|워싱턴|월가|연준|할리우드|넷플릭스|구글|애플|오픈AI|OpenAI|엔비디아|NASA|테슬라|메타|아마존)", re.I)
DOMESTIC = re.compile(r"(?<![가-힣])(?:한국|국내|우리나라|국산|서울|경기도|부산|인천|대구|광주|울산|대전|세종|강원|충남|충북|전남|전북|경남|경북|제주|고양|파주|삼성|현대차|기아|SK|LG|카이스트|KAIST|네이버|카카오|코스피|코스닥|한은|한국은행|산업부|코트라|방탄|BTS|블랙핑크|동명대)", re.I)
TOPICS = {
    "health": r"건강|의학|질병|치료|예방|의료|환자|백신|당뇨|고혈압|치매|비만|운동|식습관|암환자|항암|임상",
    "entertainment": r"연예|배우|가수|영화|드라마|공연|앨범|콘서트|아이돌|할리우드|팝스타|방탄|BTS|블랙핑크|박스오피스|OTT",
    "science": r"과학|기술|연구|인공지능|반도체|우주|AI|로봇|양자|신약|위성|발사체|실험|챗GPT|OpenAI|생성형",
    "business": r"경제|기업|금융|산업|증시|금리|주가|코스피|코스닥|수출|투자|매출|실적|부동산|물가|환율|주식|상장|연준|은행",
    "society": r"사회|사건|사고|교육|노동|재난|인권|경찰|검찰|법원|화재|지진|홍수|태풍|학교|학생|파업|체포|수사|사망|기후|폭우|범죄|판결",
}
LOCAL_EVENT = re.compile(r"시청|시민|주민|교통|도로|철도|버스|지하철|주택|공원|복지|축제|시의회|예산|개통|행정|개발|지원|모집|공모|마을|정책|행사|교육|안전|문화|운정|문산|덕양|일산")
NON_NEWS = re.compile(r"오늘의 (?:운세|성경)|띠별 운세|별자리 운세|\[(?:부고|인사|광고)\]")
SPAM = re.compile(r"카지노|슬롯|먹튀|꽁머니|토토사이트|바카라|도박 영화|도메인 주소|무료 베팅|소비기한 임박|특별전|특가 판매")
SPORTS = re.compile(r"야구|축구|농구|배구|육상|계주|포디움|골프|동메달|금메달|은메달|월드컵|올림픽|KBO|MLB|EPL|손흥민|투수|타자|홈런|득점")


def normalize(text):
    text = re.sub(r"\[[^\]]+\]|\([^)]*(?:사진|영상|종합|속보)[^)]*\)", "", text)
    return re.sub(r"[^가-힣a-z0-9]", "", text.lower())


def same_event(a, b):
    if a["id"] == b["id"] or a["url"] == b["url"]:
        return True
    if a.get("eventKey") and a.get("eventKey") == b.get("eventKey"):
        return True
    ta, tb = normalize(a["title"]), normalize(b["title"])
    if not ta or not tb:
        return False
    if ta == tb or (min(len(ta), len(tb)) >= 15 and (ta in tb or tb in ta)):
        return True
    matcher = SequenceMatcher(None, ta, tb)
    if matcher.ratio() >= .72:
        return True
    blocks = matcher.get_matching_blocks()
    if max(b.size for b in blocks) >= 12 and sum(b.size for b in blocks if b.size >= 3) >= 17 and matcher.ratio() >= .55:
        return True
    # Word overlap catches reordered headlines without merging on a name alone.
    wa, wb = (set(re.findall(r"[가-힣A-Za-z0-9]{2,}", t.lower())) for t in (a["title"], b["title"]))
    common = wa & wb
    if len(common) >= 4 and len(common) / max(1, min(len(wa), len(wb))) >= .5:
        return True
    ga, gb = {ta[i:i+3] for i in range(len(ta)-2)}, {tb[i:i+3] for i in range(len(tb)-2)}
    return len(ga & gb) / max(1, min(len(ga), len(gb))) >= .72


def fallback_classify(item):
    title = item["title"]
    if NON_NEWS.search(title) or SPORTS.search(title):
        return {"section": None, "city": None, "classification": "rules"}
    city = None
    for name, pattern in [("고양시", r"고양|일산|덕양"), ("파주시", r"파주|운정|문산"), ("서울시", r"서울시|서울특별시|서울시민")]:
        if re.search(pattern, title) and LOCAL_EVENT.search(title):
            city = name
            break
    if city:
        return {"section": "local", "city": city, "classification": "rules"}
    topic = next((key for key, pat in TOPICS.items() if re.search(pat, title, re.I)), None)
    if topic == "health":
        return {"section": "health", "city": None, "classification": "rules"}
    # Mixed or unknown geography is deliberately left unclassified without AI.
    kr, foreign = bool(DOMESTIC.search(title)), bool(FOREIGN.search(title))
    section = f"{topic}_{'kr' if kr else 'world'}" if topic and kr != foreign else None
    return {"section": section, "city": None, "classification": "rules"}


def trusted_candidate(item):
    if NON_NEWS.search(item['title']) or SPAM.search(item['title']):
        return False
    host = (urlparse(item.get('sourceUrl', '')).hostname or '').lower()
    return any(host == root or host.endswith('.' + root) for root in TRUSTED_DOMAINS)


def apply_classification(items, answers):
    lookup = {item["id"]: item for item in items}
    for answer in answers:
        item = lookup.get(answer.get("id"))
        if not item or not isinstance(answer.get("confidence"), (float, int)):
            continue
        section, city = answer.get("section"), answer.get("city")
        if section == "unknown" or answer["confidence"] < .8:
            item.update(section=None, city=None, classification="ai")
            continue
        if answer["confidence"] < .8 or section not in SECTION_IDS - {"top"}:
            continue
        if section == "local" and city not in CITIES:
            continue
        item.update(section=section, city=city if section == "local" else None, classification="ai")
        event_key = answer.get("eventKey")
        if isinstance(event_key, str) and 4 <= len(event_key) <= 100:
            item["eventKey"] = normalize(event_key)


def choose_articles(items):
    items = [i for i in items if not NON_NEWS.search(i["title"])]
    # Similarity is not transitive: A and C can share a report B without
    # matching each other directly. Allocate a whole connected event once.
    parents = list(range(len(items)))
    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    for i, item in enumerate(items):
        for j in range(i):
            if same_event(item, items[j]):
                parents[root(i)] = root(j)
    events = {item["id"]: root(i) for i, item in enumerate(items)}
    used_events = set()
    selected = []
    used = []
    for section in SECTIONS:
        section_id = section["id"]
        slots = list(CITIES) if section_id == "local" else [None] * section["count"]
        eligible = [i for i in items if ("top" in i["feeds"] if section_id == "top" else i.get("section") == section_id)]

        def order(item):
            ranks = item["feeds"]
            rank = ranks.get("top", 999) if section_id == "top" else ranks.get(item.get("city") or section_id, min(ranks.values()) + 5)
            coverage = len({j["publisher"] for j in eligible if same_event(item, j)})
            return rank, -coverage, -__import__("datetime").datetime.fromisoformat(item["publishedAt"]).timestamp(), item["id"]

        eligible.sort(key=order)
        for city in slots:
            match = next((i for i in eligible if (not city or i.get("city") == city) and events[i["id"]] not in used_events), None)
            if match is None:
                continue
            article = {**match, "section": section_id}
            article["related"] = [j for j in items if j["id"] != match["id"] and same_event(match, j)][:2]
            selected.append(article)
            used_events.add(events[match["id"]])
            used.append(match)
    return selected
