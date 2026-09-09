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

TARGET_URL = "https://ko.wikipedia.org/wiki/%EC%84%B8%EA%B3%84%EC%82%AC_%EC%97%B0%ED%91%9C"


def clean_text(text):
    if not text:
        return ""
    # 위키 각주 [1] 및 [편집] 태그 제거
    text = re.sub(r"\[\d+\]|\[편집\]", "", text)
    # 줄바꿈(\n, \r), 탭, 연속 공백을 단일 공백으로 치환
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_wikipedia_single_page():
    parsed_items = []
    seen_keys = set()

    print(f"단일 연표 문서 수집 시작: {TARGET_URL}")
    try:
        res = requests.get(TARGET_URL, headers=HEADERS, timeout=20)
        if res.status_code != 200:
            print(f"HTTP 에러: {res.status_code}")
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
    current_anchor = ""

    # 본문 내 요소들을 순차적으로 순회하며 섹션과 연표 항목 매핑
    for elem in content.find_all(["h2", "h3", "li", "tr"]):
        # 1. 시대 섹션 헤더 처리 (ID 추출 및 시대명 갱신)
        if elem.name in ["h2", "h3"]:
            h_text = clean_text(elem.get_text())
            skip_words = ["각주", "참고 문헌", "외부 링크", "같이 보기", "목차", "내용"]
            if h_text and not any(w in h_text for w in skip_words):
                current_era = h_text
                headline = elem.find(class_="mw-headline")
                if headline and headline.get("id"):
                    current_anchor = headline["id"]
                elif elem.get("id"):
                    current_anchor = elem["id"]
                else:
                    current_anchor = re.sub(r"\s+", "_", h_text)
            continue

        year_part = ""
        desc_part = ""

        # 2. 표(tr) 데이터 파싱
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

        # 3. 리스트(li) 데이터 파싱
        elif elem.name == "li":
            text = clean_text(elem.get_text())
            if not text or len(text) < 6:
                continue
            match = re.match(r"^([^\:\-\–\—\t]+)[\:\-\–\—\t]\s*(.+)$", text)
            if match:
                year_part = clean_text(match.group(1))
                desc_part = clean_text(match.group(2))
            else:
                continue

        # 유효한 연도 형식인지 검증
        if not any(char.isdigit() for char in year_part):
            continue

        # 제목 정제: 첫 번째 위키 링크 명칭 사용 또는 설명문의 첫 핵심 구절 발췌
        first_link = elem.find("a", href=re.compile(r"^/wiki/"))
        raw_title = ""
        if first_link and not first_link.get("href", "").startswith("/wiki/%ED%8C%8C%EC%9D%BC:"):
            raw_title = clean_text(first_link.get_text())

        if raw_title and len(raw_title) >= 2 and not any(c.isdigit() for c in raw_title):
            title = raw_title
        else:
            split_desc = re.split(r"[,·\.]", desc_part)
            first_clause = split_desc[0].strip() if split_desc else ""
            title = first_clause if len(first_clause) >= 3 else desc_part[:30].strip()

        # 중복 방지 키
        dedup_key = f"{year_part}_{title}"
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        # 위키백과 세계사 연표 문서 내 해당 섹션 및 연도로 스크롤되는 URL 생성
        anchor_encoded = urllib.parse.quote(current_anchor) if current_anchor else ""
        year_encoded = urllib.parse.quote(year_part)

        if anchor_encoded:
            ref_url = (
                f"https://ko.wikipedia.org/wiki/%EC%84%B8%EA%B3%84%EC%82%AC_%EC%97%B0%ED%91%9C"
                f"#{anchor_encoded}:~:text={year_encoded}"
            )
        else:
            ref_url = (
                f"https://ko.wikipedia.org/wiki/%EC%84%B8%EA%B3%84%EC%82%AC_%EC%97%B0%ED%91%9C"
                f"#:~:text={year_encoded}"
            )

        ref_title = f"위키백과 세계사 연표: {current_era} ({year_part})"

        parsed_items.append({
            "era": f"{current_era} ({year_part})",
            "title": f"[{year_part}] {title}",
            "summary": desc_part[:130] + ("..." if len(desc_part) > 130 else ""),
            "bullets": [
                f"발생 연대: {year_part}",
                desc_part[:90] + ("..." if len(desc_part) > 90 else ""),
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

    wiki_history = parse_wikipedia_single_page()
    print(f"총 {len(wiki_history)}건의 역사 연표 데이터 파싱 완료!")

    if wiki_history:
        existing_pool["history_pool"] = wiki_history

        with open(pool_file, "w", encoding="utf-8") as f:
            json.dump(existing_pool, f, ensure_ascii=False, indent=2)

        print(f"'{pool_file}'에 대량 연표 데이터 저장 완료.")
    else:
        print("수집된 데이터가 없어 파일을 덮어쓰지 않았습니다.")


if __name__ == "__main__":
    main()
