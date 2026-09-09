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

# 단일 종합 연표 URL
TARGET_URL = "https://ko.wikipedia.org/wiki/%EC%84%B8%EA%B3%84%EC%82%AC_%EC%97%B0%ED%91%9C"


def clean_text(text):
    if not text:
        return ""
    # 위키 각주 [1], [편집] 등 제거
    cleaned = re.sub(r"\[\d+\]|\[편집\]", "", text)
    return cleaned.strip()


def parse_wikipedia_single_page():
    parsed_items = []
    seen_keys = set()

    print(f"단일 연표 문서 수집 시작: {TARGET_URL}")
    try:
        res = requests.get(TARGET_URL, headers=HEADERS, timeout=20)
        if res.status_code != 200:
            print(f"HTTP 에러 발생: {res.status_code}")
            return parsed_items
    except Exception as e:
        print(f"요청 실패: {e}")
        return parsed_items

    soup = BeautifulSoup(res.text, "html.parser")
    content = soup.find("div", {"class": "mw-parser-output"})
    if not content:
        print("본문 컨테이너(mw-parser-output)를 찾지 못했습니다.")
        return parsed_items

    current_era = "세계사 연표"

    # 본문 내 요소들을 순차적으로 순회
    for elem in content.find_all(["h2", "h3", "li", "tr"]):
        # 1. 시대 섹션 헤더 처리 (시대명 자동 추적)
        if elem.name in ["h2", "h3"]:
            h_text = clean_text(elem.get_text())
            skip_words = ["각주", "참고 문헌", "외부 링크", "같이 보기", "목차"]
            if h_text and not any(w in h_text for w in skip_words):
                current_era = h_text
            continue

        year_part = ""
        desc_part = ""

        # 2. 표 형태 (tr) 처리
        if elem.name == "tr":
            cols = elem.find_all(["td", "th"])
            if len(cols) >= 2:
                col1 = clean_text(cols[0].get_text())
                col2 = clean_text(cols[1].get_text())
                if any(c.isdigit() for c in col1) and len(col2) >= 2:
                    year_part = col1
                    desc_part = col2
            else:
                continue

        # 3. 리스트 형태 (li) 처리
        elif elem.name == "li":
            text = clean_text(elem.get_text())
            if not text or len(text) < 6:
                continue
            match = re.match(r"^([^\:\-\–\—\t]+)[\:\-\–\—\t]\s*(.+)$", text)
            if match:
                year_part = match.group(1).strip()
                desc_part = match.group(2).strip()
            else:
                continue

        # 연도 숫자 검증
        if not any(char.isdigit() for char in year_part):
            continue

        # 내부 위키백과 링크 추출
        first_link = elem.find("a", href=re.compile(r"^/wiki/"))
        if first_link and not first_link.get("href", "").startswith(
            "/wiki/%ED%8C%8C%EC%9D%BC:"
        ):
            raw_title = first_link.get_text().strip()
            wiki_path = first_link["href"]
            title = raw_title if len(raw_title) >= 2 else desc_part[:30]
            ref_url = f"https://ko.wikipedia.org{wiki_path}"
            ref_title = f"위키백과: {raw_title}"
        else:
            title = desc_part[:30].strip()
            ref_url = (
                "https://ko.wikipedia.org/wiki/Special:Search?search="
                f"{urllib.parse.quote(title)}"
            )
            ref_title = f"위키백과 검색: {title}"

        dedup_key = f"{year_part}_{title}"
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        parsed_items.append({
            "era": f"{current_era} ({year_part})",
            "title": f"[{year_part}] {title}",
            "summary": desc_part[:120]
            + ("..." if len(desc_part) > 120 else ""),
            "bullets": [
                f"발생 연대: {year_part}",
                desc_part[:90],
                "당대 유라시아 및 글로벌 지정학적 세력 균형의 변화 반영",
            ],
            "insight": (
                f"{year_part}의 사건은 당시 지역 경제와 문명 교류의 네트워크"
                " 구조를 변화시킨 중요한 분기점입니다."
            ),
            "ref_title": ref_title,
            "ref_url": ref_url,
        })

    return parsed_items


def main():
    pool_file = "humanities_pool.json"
    existing_pool = {}

    if os.path.exists(pool_file):
        try:
            with open(pool_file, "r", encoding="utf-8") as f:
                existing_pool = json.load(f)
        except Exception as e:
            print(f"기존 풀 파일 로드 예외: {e}")

    # 단일 연표 문서 파싱 실행
    wiki_history = parse_wikipedia_single_page()
    print(f"총 {len(wiki_history)}건의 역사 연표 데이터 파싱 완료!")

    if wiki_history:
        # 기존 polyglot_pool과 philosophy_pool은 보존하고 history_pool만 교체
        existing_pool["history_pool"] = wiki_history

        with open(pool_file, "w", encoding="utf-8") as f:
            json.dump(existing_pool, f, ensure_ascii=False, indent=2)

        print(f"'{pool_file}'에 대량 연표 데이터 성공적으로 저장 완료.")
    else:
        print("수집된 데이터가 없어 기존 파일을 덮어쓰지 않았습니다.")


if __name__ == "__main__":
    main()
