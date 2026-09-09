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
    text = re.sub(r"\[\d+\]|\[편집\]", "", text)
    text = re.sub(r"[\r\t]+", " ", text)
    return text.strip()


def split_cell_by_lines(td_node):
    """td 셀 내부의 <br> 및 개행문자를 기준으로 줄(Line) 단위로 쪼개어 (텍스트, 위키링크) 리스트 반환"""
    if not td_node:
        return []

    html_content = td_node.decode_contents()
    chunks = re.split(r"<br\s*/?>|\n", html_content)

    lines = []
    for chunk in chunks:
        soup = BeautifulSoup(chunk, "html.parser")
        text = clean_text(soup.get_text())
        link = soup.find("a", href=re.compile(r"^/wiki/"))
        if link and link.get("href", "").startswith("/wiki/%ED%8C%8C%EC%9D%BC:"):
            link = None
        lines.append({"text": text, "link": link})
    return lines


def match_year_and_events(year_td, event_td):
    """연대 셀과 사건 셀의 줄바꿈을 맞추어 (연도, 사건텍스트, 링크) 튜플 리스트 생성"""
    year_lines = split_cell_by_lines(year_td)
    event_lines = split_cell_by_lines(event_td)

    # 유효한 사건만 필터링
    valid_events = [e for e in event_lines if e["text"] and len(e["text"]) >= 2 and e["text"] != "공란"]
    if not valid_events:
        return []

    results = []
    curr_year = ""
    valid_years = [y["text"] for y in year_lines if y["text"] and any(c.isdigit() for c in y["text"])]

    # 1. 연대 줄 수와 사건 줄 수가 비슷하게 배치된 경우 (Forward-fill 방식)
    if len(year_lines) > 1 and abs(len(year_lines) - len(event_lines)) <= 4:
        curr_year = valid_years[0] if valid_years else "연대 미상"
        for idx, ev in enumerate(event_lines):
            if idx < len(year_lines):
                y_txt = year_lines[idx]["text"]
                if y_txt and any(c.isdigit() for c in y_txt):
                    curr_year = y_txt
            if ev["text"] and len(ev["text"]) >= 2 and ev["text"] != "공란":
                results.append((curr_year, ev["text"], ev["link"]))

    # 2. 유효 연도 수와 유효 사건 수가 1:1로 일치하는 경우
    elif len(valid_years) == len(valid_events):
        for y_str, ev in zip(valid_years, valid_events):
            results.append((y_str, ev["text"], ev["link"]))

    # 3. 그 외 (연도는 소수이고 사건이 여러 개 나열된 경우)
    else:
        curr_year = valid_years[0] if valid_years else "연대 미상"
        y_idx = 0
        for ev in valid_events:
            ev_text = ev["text"]
            # 사건 텍스트 앞부분에 자체 연도가 적혀 있는 경우 우선 추출
            m = re.match(r"^(\d{1,4}\s*년?)\s*[\:\-\–\—\.]?\s*(.+)$", ev_text)
            if m and any(c.isdigit() for c in m.group(1)):
                year_val = m.group(1).strip()
                event_val = m.group(2).strip()
                results.append((year_val, event_val if event_val else ev_text, ev["link"]))
                curr_year = year_val
            else:
                if y_idx < len(valid_years):
                    curr_year = valid_years[y_idx]
                    y_idx += 1
                results.append((curr_year, ev_text, ev["link"]))

    return results


def parse_wikipedia_history():
    parsed_items = []
    seen_keys = set()

    print(f"위키백과 세계사 연표 정밀 수집 시작: {TARGET_URL}")
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
        return parsed_items

    current_era = "세계사 연표"
    current_anchor = ""

    # H2, H3 및 테이블 순회
    for elem in content.find_all(["h2", "h3", "table"]):
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

        if elem.name == "table":
            rows = elem.find_all("tr")
            for tr in rows:
                tds = tr.find_all("td")
                pairs_to_process = []

                # 4열 구조: [0]세계연대, [1]세계사건, [2]한국연대, [3]한국사건
                if len(tds) >= 4:
                    pairs_to_process.append((tds[0], tds[1], "세계"))
                    pairs_to_process.append((tds[2], tds[3], "한국"))
                # 2열 구조: [0]연대, [1]사건
                elif len(tds) >= 2:
                    pairs_to_process.append((tds[0], tds[1], "세계"))

                for y_td, e_td, region in pairs_to_process:
                    matched = match_year_and_events(y_td, e_td)
                    for year_val, event_val, link_node in matched:
                        # 중복 및 노이즈 제거
                        event_clean = clean_text(event_val)
                        if not event_clean or len(event_clean) < 2 or event_clean == "공란":
                            continue

                        # 연도 표기 보정 (숫자만 있는 경우 '년' 부착)
                        year_clean = clean_text(year_val)
                        if year_clean.isdigit():
                            display_year = f"{year_clean}년"
                        else:
                            display_year = year_clean

                        dedup_key = f"{region}_{display_year}_{event_clean[:30]}"
                        if dedup_key in seen_keys:
                            continue
                        seen_keys.add(dedup_key)

                        # 위키백과 직접 스크롤 URL 생성
                        anchor_enc = urllib.parse.quote(current_anchor) if current_anchor else ""
                        # 연도 숫자 부분만 추출하여 텍스트 프래그먼트로 지정
                        year_nums = re.findall(r"\d+", display_year)
                        target_kw = year_nums[0] if year_nums else display_year
                        kw_enc = urllib.parse.quote(target_kw)

                        if anchor_enc:
                            ref_url = f"{TARGET_URL}#{anchor_enc}:~:text={kw_enc}"
                        else:
                            ref_url = f"{TARGET_URL}#:~:text={kw_enc}"

                        ref_title = f"위키백과 세계사 연표: {current_era} ({display_year})"

                        # 지역별 인사이트 분기
                        if region == "한국":
                            insight_text = (
                                f"{display_year} 한국사의 전개는 한반도 내부 정세와 동아시아 대외 관계의 "
                                "흐름을 결정지은 핵심 분기점입니다."
                            )
                        else:
                            insight_text = (
                                f"{display_year}의 글로벌 사건은 당시 지역 경제와 문명 교류의 네트워크 "
                                "구조를 변화시킨 중요한 분기점입니다."
                            )

                        parsed_items.append({
                            "era": f"{current_era} ({display_year})",
                            "region": region,
                            "year": display_year,
                            "title": f"[{display_year}] [{region}] {event_clean[:45]}",
                            "summary": f"{display_year} - {event_clean}",
                            "bullets": [
                                f"발생 연대: {display_year} ({region}사)",
                                event_clean[:90] + ("..." if len(event_clean) > 90 else ""),
                                "당대 세력 균형 및 정치·경제적 제도 변화 반영",
                            ],
                            "insight": insight_text,
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

    wiki_history = parse_wikipedia_history()
    print(f"총 {len(wiki_history)}건의 연도별 1:1 매핑 연표 데이터(한국사 포함) 파싱 완료!")

    if wiki_history:
        existing_pool["history_pool"] = wiki_history

        with open(pool_file, "w", encoding="utf-8") as f:
            json.dump(existing_pool, f, ensure_ascii=False, indent=2)

        print(f"'{pool_file}'에 저장 완료.")
    else:
        print("수집된 데이터가 없어 파일을 덮어쓰지 않았습니다.")


if __name__ == "__main__":
    main()
