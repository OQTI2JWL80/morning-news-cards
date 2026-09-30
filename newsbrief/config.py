from datetime import timedelta, timezone

KST = timezone(timedelta(hours=9), "Asia/Seoul")
MODEL = "gemini-3.7-flash"
FALLBACK_MODELS = ("gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash",
                   "gemini-3.5-flash-lite", "gemini-3.1-flash-lite")
RETENTION_DAYS = 30
EDITORIAL_VERSION = 4
# Curated publisher roots limit search-result spam. Extend deliberately in source control.
TRUSTED_DOMAINS = {
    "yna.co.kr", "yonhapnewstv.co.kr", "kbs.co.kr", "imbc.com", "sbs.co.kr", "ytn.co.kr", "jtbc.co.kr",
    "hani.co.kr", "khan.co.kr", "chosun.com", "chosunbiz.com", "donga.com", "joongang.co.kr", "joins.com",
    "hankookilbo.com", "seoul.co.kr", "segye.com", "munhwa.com", "kmib.co.kr", "nocutnews.co.kr",
    "newsis.com", "news1.kr", "news1.co.kr", "ohmynews.com", "pressian.com", "hankyung.com", "mk.co.kr",
    "sedaily.com", "edaily.co.kr", "mt.co.kr", "fnnews.com", "heraldcorp.com", "biz.heraldcorp.com", "asiae.co.kr",
    "ajunews.com", "newsway.co.kr", "etnews.com", "zdnet.co.kr", "zdnet.com", "bloter.net", "digitaltoday.co.kr",
    "ddaily.co.kr", "dt.co.kr", "itworld.co.kr", "aitimes.com", "sciencetimes.co.kr", "dongascience.com",
    "hellodd.com", "dailymedi.com", "medicaltimes.com", "medigatenews.com", "docdocdoc.co.kr", "hidoc.co.kr",
    "medicaldaily.co.kr", "kormedi.com", "health.chosun.com", "newsthevoice.com", "healthinnews.co.kr",
    "osen.co.kr", "news.nate.com", "mydaily.co.kr", "starnewskorea.com", "sportschosun.com", "sportsseoul.com",
    "xportsnews.com", "tenasia.hankyung.com", "tvdaily.co.kr", "news.naver.com", "v.daum.net", "bbc.com",
    "reuters.com", "apnews.com", "cnn.com", "lawtimes.co.kr", "hangyo.com", "kookje.co.kr",
    "seoul.go.kr", "gg.go.kr", "goyang.go.kr", "paju.go.kr", "goyangnews.co.kr", "mygoyang.com",
    "atpaju.com", "pajutimes.com", "pajuilbo.com", "idojung.com", "kyeongin.com", "kyeonggi.com",
    "kgnews.co.kr", "incheonilbo.com", "joongboo.com", "gukjenews.com", "newspim.com", "newsfreezone.co.kr",
    "sisafocus.co.kr", "breaknews.com", "goyang1.com", "korea.kr", "scieng.net", "yna.tv",
}
SECTIONS = [
    {"id": "top", "name": "종합 주요 뉴스", "label": "TOP STORIES", "count": 3},
    {"id": "society_kr", "name": "국내 사회", "label": "SOCIETY · KR", "count": 3},
    {"id": "society_world", "name": "해외 사회", "label": "SOCIETY · WORLD", "count": 3},
    {"id": "business_kr", "name": "국내 경제·비즈니스", "label": "BUSINESS · KR", "count": 3},
    {"id": "business_world", "name": "해외 경제·비즈니스", "label": "BUSINESS · WORLD", "count": 3},
    {"id": "science_kr", "name": "국내 과학·기술", "label": "SCIENCE & TECH · KR", "count": 3},
    {"id": "science_world", "name": "해외 과학·기술", "label": "SCIENCE & TECH · WORLD", "count": 3},
    {"id": "entertainment_kr", "name": "국내 엔터테인먼트", "label": "CULTURE · KR", "count": 3},
    {"id": "entertainment_world", "name": "해외 엔터테인먼트", "label": "CULTURE · WORLD", "count": 3},
    {"id": "health", "name": "건강", "label": "HEALTH", "count": 3},
    {"id": "local", "name": "서울·고양·파주", "label": "LOCAL", "count": 3},
]
SECTION_IDS = {s["id"] for s in SECTIONS}
CITIES = ("서울시", "고양시", "파주시")
# Searches nominate candidates; classification and deduplication happen afterwards.
QUERIES = {
    "society_kr": '(사회 OR 사건 OR 사고 OR 교육 OR 노동 OR 재난) (한국 OR 국내)',
    "society_world": '(사회 OR 사건 OR 사고 OR 교육 OR 재난 OR 인권) (해외 OR 국제 OR 미국 OR 유럽 OR 일본 OR 중국)',
    "business_kr": '(경제 OR 기업 OR 금융 OR 산업 OR 증시) (한국 OR 국내)',
    "business_world": '(경제 OR 기업 OR 금융 OR 산업 OR 증시) (해외 OR 미국 OR 유럽 OR 일본 OR 중국)',
    "science_kr": '(과학 OR 기술 OR 연구 OR 인공지능 OR 반도체 OR 우주) (한국 OR 국내)',
    "science_world": '(과학 OR 기술 OR 연구 OR 인공지능 OR 우주) (해외 OR 미국 OR 유럽 OR 일본 OR 중국)',
    "entertainment_kr": '(연예 OR 배우 OR 가수 OR 영화 OR 드라마 OR 공연) (한국 OR 국내)',
    "entertainment_world": '(연예 OR 배우 OR 가수 OR 영화 OR 공연) (해외 OR 할리우드 OR 팝스타 OR 일본)',
    "health": '(건강 OR 의학 OR 질병 OR 치료 OR 예방)',
    "서울시": '(서울시 OR 서울특별시 OR 서울시민)',
    "고양시": '(고양시 OR 일산 OR 덕양구)',
    "파주시": '(파주시 OR 운정 OR 문산)',
}
