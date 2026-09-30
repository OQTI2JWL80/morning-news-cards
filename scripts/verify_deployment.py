"""Read published output after deploy, including the first three scheduled mornings."""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from newsbrief.net import fetch
from newsbrief.storage import validate_edition


def main():
    base = sys.argv[1].rstrip('/') + '/'
    expected = json.loads(Path('.github/run-record.json').read_text(encoding='utf-8'))
    error = None
    for attempt in range(4):
        try:
            raw, _ = fetch(base + 'data/index.json', headers={'Cache-Control': 'no-cache'}, retries=0)
            index = json.loads(raw)
            if index['latest'] != expected['edition']:
                raise ValueError('Edition not visible yet')
            raw, _ = fetch(base + 'data/' + index['latest'] + '.json', headers={'Cache-Control': 'no-cache'}, retries=0)
            edition = validate_edition(json.loads(raw))
            if edition['generatedAt'] != expected['generatedAt']:
                raise ValueError('Old deployment still visible')
            report = f"게시 확인: {edition['date']} · 기사 {len(edition['articles'])}/33 · 요약 {edition['summaryCount']}/33 · 상태 {edition['status']}"
            print(report)
            summary = os.getenv('GITHUB_STEP_SUMMARY')
            if summary:
                with open(summary, 'a', encoding='utf-8') as file:
                    file.write('\n' + report + '\n')
                    if edition['status'] == 'partial':
                        file.write('\n일부 제공: 무료 한도, 원문 접근, 분야별 부족 수를 웹페이지에서 확인하세요.\n')
            return
        except Exception as exc:
            error = type(exc).__name__
            if attempt < 3: time.sleep(10)
    raise SystemExit('게시 후 확인 실패: ' + str(error))


if __name__ == '__main__': main()

