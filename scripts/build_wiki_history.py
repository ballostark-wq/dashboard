import json
import os
import re
import urllib.parse
from bs4 import BeautifulSoup
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}

# 위키백과 세계사 연표 메인 및 시대별 상세 연표 URL 목록
TIMELINE_URLS = "https://ko.wikipedia.org/wiki/%EC%84%B8%EA%B3%84%EC%82%AC_%EC%97%B0%ED%91%9C"

def clean_text(text):
    if not text:
        return ""
    # 위키 각주 [1], [편집] 등 제거
    cleaned = re.sub(r"\[\d+\]|\[편집\]", "", text)
    return cleaned.strip()

def parse_wikipedia_timelines():
    parsed_items = []
    seen_titles = set()

    for era_label, url in TIMELINE_URLS:
        print(f"수집 중: {era_label} ({url})...")
        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            if res.status_code != 200:
                continue
            soup = BeautifulSoup(res.text, "html.parser")
            content = soup.find("div", {"class": "mw-parser-output"})
            if not content:
                continue

            # li 태그 목록 및 표(tr) 데이터 순회
            for li in content.find_all(["li", "tr"]):
                text = clean_text(li.get_text())
                if not text or len(text) < 10:
                    continue

                # 연도 패턴 매칭 (예: "기원전 776년 - ...", "1492년: ...")
                match = re.match(r"^([^\:\-\–\—\t]+)[\:\-\–\—\t]\s*(.+)$", text)
                if not match:
                    continue

                year_part = match.group(1).strip()
                desc_part = match.group(2).strip()

                # 유효한 연도 형식인지 검증
                if not any(char.isdigit() for char in year_part):
                    continue

                # 첫 번째 내부 링크를 추출해 표제어와 공식 URL 생성
                first_link = li.find("a", href=re.compile(r"^/wiki/"))
                if first_link and not first_link.get("href", "").startswith("/wiki/%ED%8C%8C%EC%9D%BC:"):
                    raw_title = first_link.get_text().strip()
                    wiki_path = first_link["href"]
                    title = raw_title if len(raw_title) >= 2 else desc_part[:30]
                    ref_url = f"https://ko.wikipedia.org{wiki_path}"
                    ref_title = f"위키백과: {raw_title}"
                else:
                    title = desc_part[:30].strip()
                    ref_url = f"https://ko.wikipedia.org/wiki/Special:Search?search={urllib.parse.quote(title)}"
                    ref_title = f"위키백과 검색: {title}"

                if title in seen_titles:
                    continue
                seen_titles.add(title)

                parsed_items.append({
                    "era": f"{era_label} ({year_part})",
                    "title": f"[{year_part}] {title}",
                    "summary": desc_part[:120] + ("..." if len(desc_part) > 120 else ""),
                    "bullets": [
                        f"발생 연대: {year_part}",
                        desc_part[:90],
                        "당대 유라시아 및 글로벌 지정학적 세력 균형의 변화 반영"
                    ],
                    "insight": f"{year_part}의 사건은 당시 지역 경제와 문명 교류의 네트워크 구조를 변화시킨 중요한 분기점입니다.",
                    "ref_title": ref_title,
                    "ref_url": ref_url
                })
        except Exception as e:
            print(f"{era_label} 파싱 중 오류: {e}")

    return parsed_items

def main():
    pool_file = "humanities_pool.json"
    existing_pool = {}

    if os.path.exists(pool_file):
        try:
            with open(pool_file, "r", encoding="utf-8") as f:
                existing_pool = json.load(f)
        except Exception:
            pass

    # 위키백과 연표 파싱
    wiki_history = parse_wikipedia_timelines()
    print(f"총 {len(wiki_history)}건의 역사 연표 데이터 파싱 완료!")

    # 기존 회화 및 철학 풀 유지
    existing_pool["history_pool"] = wiki_history

    with open(pool_file, "w", encoding="utf-8") as f:
        json.dump(existing_pool, f, ensure_ascii=False, indent=2)

    print(f"'{pool_file}'에 대량 연표 데이터 성공적으로 저장 완료.")

if __name__ == "__main__":
    main()
