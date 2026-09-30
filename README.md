# 아침 일곱 시

매일 한국시간 07시까지 발행된 뉴스를 최대 33장의 가벼운 웹카드로 읽습니다.
GitHub Actions + GitHub Pages + Gemini API Free Tier를 사용합니다. **사용자의 PC가 꺼져 있어도 실행됩니다.**

예정 주소: `https://oqti2jwl80.github.io/morning-news-cards/` (GitHub 게시를 완료해야 열립니다.)

## 처음 한 번 설정

1. GitHub 계정 `OQTI2JWL80`으로 **공개** 저장소 `morning-news-cards`를 만듭니다. 이 프로젝트의 소스만 업로드합니다. `.venv`, `.local`, `build`, 비밀키는 업로드하지 않습니다.
2. 저장소 **Settings → Pages → Build and deployment → Source**를 **GitHub Actions**로 선택합니다.
3. [Google AI Studio 프로젝트](https://aistudio.google.com/projects)에서 과금 계정이 연결되지 않은 **Free Tier** 프로젝트를 확인합니다. 키를 새로 만들 때 결제 설정·유료 전환·자동 충전을 선택하지 않습니다.
4. 그 프로젝트의 API 키를 GitHub 저장소 **Settings → Secrets and variables → Actions → Secrets → New repository secret**에서 이름 **`GEMINI_API_KEY`**로 등록합니다. 키는 채팅, 코드, README에 쓰지 않습니다.
5. 같은 화면의 **Variables → New repository variable**에서 이름 **`GEMINI_FREE_TIER_CONFIRMED`**, 값 **`true`**를 등록합니다. 이것은 사람이 무료 상태를 확인했다는 표시이며 과금 상태를 자동 조회하는 기능은 아닙니다. 이미 과금이 연결된 프로젝트라면 등록하지 마세요.
6. 저장소 **Actions → Morning news cards → Run workflow**를 한 번 실행합니다. `build`, `deploy`, `record`가 성공하면 위 주소로 확인합니다.
7. 휴대폰 브라우저에서 이 주소를 열고 공유/메뉴의 **홈 화면에 추가**를 선택합니다.

계정 연결과 API 키는 최초 설정에만 필요합니다. 일일 아침 알림은 전송하지 않습니다.

## 매일 동작하는 방식

- 예약: UTC 22:00, 즉 한국시간 다음 날 07:00. 공개 목표는 07:05~07:15이며 GitHub 실행이 지연되거나 누락될 수 있습니다.
- 기사 범위: `(전날 07:00, 오늘 07:00]`. 07시 전 수동 실행은 전날 마감판을 만듭니다. 오래된 구글 뉴스 순위를 복원하지는 않습니다.
- 분야: 종합 3개 + 국내/해외 사회·경제·과학기술·엔터 각 3개 + 건강 3개 + 서울·고양·파주 각 1개.
- Google News RSS의 검색·토픽 후보에 출처 확인, 스팸 제외, 분야 분류, 동일 사건 중복 제거를 적용합니다. 종합에 포함된 사건은 다른 분야에 반복하지 않습니다.
- 허용한 매체 도메인은 `newsbrief/config.py`의 `TRUSTED_DOMAINS`에 있습니다. 검색 결과에 섞인 광고성/해킹된 사이트를 줄이기 위한 목록입니다. 유효한 소스가 부족해도 임의의 사이트나 오래된 기사를 넣지 않습니다.
- AI 연결이 있으면 제목을 최대 60개씩 분류하고, 읽을 수 있는 기사 본문은 최대 6개씩 묶어 요약합니다. 모델은 `gemini-3.8-flash`로 고정하고 최대 12회 호출합니다. 유료 Google Search grounding, 유료 Batch API, 모델 자동 변경은 사용하지 않습니다.
- 요약 문장마다 원문에 실제 존재하는 근거를 요구합니다. 새로운 수치, 근거 누락, 잘못된 JSON, 부족한 본문은 요약에서 제외합니다. 이것이 완전한 사실 검증을 보장하지는 않으므로 원문 링크를 함께 제공합니다.
- 07시 이후 수정 시각이 확인된 본문, 유료/로그인 제한 문서, robots 규칙이 허용하지 않는 문서는 요약하지 않습니다. 접근 제한을 우회하지 않습니다.
- AI 키 미등록, 무료 확인 미설정, 429 한도 초과, 모델 미지원이면 제목·출처·원문으로 계속 제공합니다. 분야가 불명확하면 부족한 수를 표시합니다.

## 무료 이용 조건

공개 저장소의 표준 GitHub-hosted Linux runner와 GitHub Pages를 사용합니다. 별도 도메인·유료 runner·유료 AI 기능은 필요 없습니다.

Gemini API는 **무료 프로젝트와 해당 모델의 무료 한도**에서만 사용해야 합니다. 사용자 계정의 한도는 [AI Studio](https://aistudio.google.com/)에서 확인하세요. 무료 호출 한도와 모델 제공은 변경될 수 있습니다. 설정 파일의 확인 플래그만으로 실제 결제를 차단하는 것은 불가능하므로 프로젝트에 과금 계정을 연결하지 않는 것이 중요합니다.

Free Tier의 입력/출력은 Google의 서비스 개선에 사용될 수 있습니다. 이 프로그램은 공개 기사만 전달하고, 로그인 쿠키나 개인 문서는 전달하지 않습니다.

## 저장 용량

- 기본 화면은 HTML/CSS/텍스트 JSON입니다. 뉴스 사진, 웹폰트, AI 생성 이미지를 다운로드하지 않습니다.
- 최근 30일의 게시용 JSON만 웹페이지에 보관합니다. 이전 게시물은 기존 Pages에서 읽어 새 게시물과 함께 배포합니다.
- 기사 원문·중간 결과·AI 근거 인용문은 메모리에서 처리 후 버립니다. 소스 Git 이력에는 저장하지 않습니다.
- 카드 이미지는 사용자가 저장할 때만 브라우저에서 만듭니다. WebP 720×900, 목표 150KB 이하이며 글자 가독성을 우선합니다. WebP 인코딩이 없는 브라우저는 PNG가 나올 수 있고 용량이 더 클 수 있습니다.
- GitHub 배포 산출물 보관은 1일로 설정했습니다. 성공 시 날짜·기사 수·요약 수의 작은 실행 기록만 커밋합니다. 장기 비활동에 따른 예약 중지 위험을 줄이지만 서비스 정책 변경까지 보장하지는 않습니다.

## 문제가 생겼을 때

| 화면 또는 실행 상태 | 확인할 사항 |
|---|---|
| 오늘자 갱신 지연 | Actions의 최근 실행과 GitHub 서비스 상태를 확인하고 Run workflow로 재실행 |
| 본문 요약 없음 / AI 연결 준비 | API Secret과 무료 확인 Variable을 확인 |
| 무료 요약 한도 도달 | 무료 한도가 회복될 때까지 대기. 유료 전환 없이 다음 날 다시 실행 |
| 모델 사용 불가 | 모델 제공 상태 확인. 자동으로 다른 유료 모델을 쓰지 않음 |
| 특정 분야 기사 부족 | 24시간 범위, 출처 허용 목록, 제목의 국내외 분류 여부 확인 |
| workflow disabled | Actions에서 Enable workflow. 기본 브랜치의 예약 설정 확인 |
| deploy 실패 | Pages의 Source=GitHub Actions와 workflow 권한 확인 |

실패한 새 배포는 기존 정상판을 덮어쓰지 않습니다. 같은 날짜의 재실행도 카드를 추가 복제하지 않습니다. 더 완전한 같은 날짜의 결과가 있으면 유지합니다. 최근 3일의 일일 실행에서 `record` 단계가 실제 공개 JSON을 다시 읽어 마감 시각·기사 수·요약 수를 검사하며, 이후에도 같은 검사를 지속합니다.

## 로컬 실행 / 개발

Python 3.12 이상을 권장합니다.

```text
python -m venv .venv
# Windows
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m newsbrief --no-ai
.venv\Scripts\python.exe scripts/check_build.py build
.venv\Scripts\python.exe -m http.server 8765 --bind 127.0.0.1 --directory build
```

그다음 `http://127.0.0.1:8765/`를 엽니다. `.env`는 자동으로 읽지 않으므로 키를 쓸 때는 프로세스 환경변수 또는 GitHub Secrets를 사용합니다.

`python -m newsbrief --skip-content --no-ai`는 RSS·화면 확인용입니다. `--date YYYY-MM-DD`는 과거 마감 테스트용이며 과거 순위를 복원하는 기능은 아닙니다. `--previous-url`로 기존 Pages 자료를 읽을 수 있습니다.

### 파일 구성

- `newsbrief/`: 수집, 출처 확인, 분류, 요약, 원문 추출, 자료 검증
- `site/`: 모바일 웹카드 및 선택 카드 이미지 저장
- `.github/workflows/daily.yml`: 예약 실행, 원자적 Pages 배포, 게시 후 점검
- `tests/`: 시간대·중복·지역·요약 근거·장애·보관 규칙 검증
- `scripts/`: 배포 결과의 용량·비밀키 노출 검사와 게시 후 확인

## 공식 참고

- [Google 뉴스 선정 방식](https://support.google.com/googlenews/answer/9005749?hl=ko)
- [Gemini 무료/유료 구분](https://ai.google.dev/gemini-api/docs/billing)
- [Gemini 모델 가격](https://ai.google.dev/gemini-api/docs/pricing)
- [GitHub Actions 무료 이용](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [예약 지연·비활동 중지 조건](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)

