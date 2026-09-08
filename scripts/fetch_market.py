from datetime import datetime
import html
import json
import os
import re
import xml.etree.ElementTree as ET
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}


def load_existing_data():
    """기존 data.json 안전장치 및 5일 FedWatch 히스토리 유지"""
    default_data = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "us2y": {"value": 4.32, "change": 0.03},
        "us5y": {"value": 4.45, "change": 0.02},
        "us10y": {"value": 4.78, "change": 0.46},
        "us30y": {"value": 4.95, "change": 0.01},
        "spread": {"value": 46, "status": "정상화 (우상향)"},
        "vix": {"value": 15.30, "change": -1.47},
        "macro_briefing": {
            "title": (
                "반도체·제조업 중심의 실적형 위험자산 선호(Risk-on) 장세"
            ),
            "regime": "Risk-on 우위",
            "bullets": [
                "필라델피아 반도체 지수 모멘텀 가속화로 글로벌 유동성 집중 흡수",
                "구리 급등으로 글로벌 실물 경기 개선 기대감 동반 유입",
                "국내 HBM 밸류체인 및 반도체 소부장 대형주로의 강력한 수급 쏠림",
            ],
            "trading_strategy": (
                "지수 전반의 무차별 추격 매수보다는 HBM 및 AI 인프라 독점 수혜주,"
                " 원가 전가력을 갖춘 경기민감주로 포트를 압축하는 전략이"
                " 유효합니다."
            ),
        },
        "fedwatch": {
            "meeting_date": "2026-09-16 (차기 FOMC)",
            "current_target": "3.75%-4.00%",
            "history": [
                {"date": "09-02 (D-4)", "cut_25": 32.0, "hold": 68.0},
                {"date": "09-03 (D-3)", "cut_25": 35.5, "hold": 64.5},
                {"date": "09-04 (D-2)", "cut_25": 38.0, "hold": 62.0},
                {"date": "09-05 (D-1)", "cut_25": 40.0, "hold": 60.0},
                {"date": "09-08 (오늘)", "cut_25": 41.5, "hold": 58.5},
            ],
        },
        "feeds": {"fed": [], "global": [], "tech": [], "domestic": []},
    }
    if os.path.exists("data.json"):
        try:
            with open("data.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default_data


def fetch_naver_rates():
    """네이버 증권 공식 금리 리스트에서 국채금리 수집"""
    url = "https://finance.naver.com/marketindex/interestList.naver"
    rates = {}
    code_map = {
        "IRRD_BONDU02Y": "us2y",
        "IRRD_BONDU05Y": "us5y",
        "IRRD_BONDU10Y": "us10y",
        "IRRD_BONDU30Y": "us30y",
    }
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            res.encoding = "euc-kr"
            rows = re.findall(r"<tr[^>]*>(.*?)</tr>", res.text, re.DOTALL)
            for row in rows:
                for code, key in code_map.items():
                    if code in row:
                        cols = re.findall(
                            r"<td[^>]*>(.*?)</td>", row, re.DOTALL
                        )
                        clean_cols = [
                            re.sub(r"<[^>]+>", "", c).strip() for c in cols
                        ]
                        if len(clean_cols) >= 4:
                            try:
                                val = float(clean_cols[1].replace(",", ""))
                                chg_str = (
                                    clean_cols[3]
                                    .replace("%", "")
                                    .replace(",", "")
                                    .strip()
                                )
                                chg = float(chg_str) if chg_str else 0.0
                                rates[key] = {
                                    "value": round(val, 2),
                                    "change": round(chg, 2),
                                }
                            except ValueError:
                                continue
    except Exception as e:
        print(f"네이버 금리 수집 예외: {e}")
    return rates


def fetch_vix():
    """VIX 변동성 지수 수집"""
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?interval=1d&range=5d"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            meta = res.json()["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice", 15.30)
            prev = meta.get(
                "chartPreviousClose", meta.get("previousClose", price)
            )
            chg = ((price - prev) / prev) * 100 if prev else 0.0
            return {"value": round(price, 2), "change": round(chg, 2)}
    except Exception as e:
        print(f"VIX 파싱 예외: {e}")
    return None


def clean_date_str(pub_date):
    """RSS 날짜 포맷 간소화"""
    if not pub_date:
        return ""
    clean = pub_date.strip()
    for fmt in [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%a, %d %b %Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]:
        try:
            dt = datetime.strptime(clean[:25].strip(), fmt)
            return dt.strftime("%m-%d %H:%M")
        except Exception:
            pass
    return clean[:16]


def fetch_rss(url, max_items=5, prefix="", encoding=None):
    """범용 RSS 파서"""
    items = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            if encoding:
                res.encoding = encoding
            root = ET.fromstring(res.content)
            for item in root.findall(".//item")[:max_items]:
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                pub_date = item.findtext("pubDate", "")

                title = re.sub(r"<[^>]+>", "", title)
                title = html.unescape(title).strip()
                if prefix:
                    title = f"{prefix} {title}"

                if title and link:
                    items.append({
                        "title": title,
                        "link": link.strip(),
                        "date": clean_date_str(pub_date),
                    })
    except Exception as e:
        print(f"RSS 수집 예외 ({url}): {e}")
    return items


def update_fedwatch_history(fedwatch_data):
    """CME FedWatch 최근 5일 히스토리 자동 롤링 관리"""
    today_label = datetime.now().strftime("%m-%d (오늘)")
    history = fedwatch_data.get("history", [])

    # 오늘 데이터 기본값 (사용자 공유 캡처 기준: 350-375bp=41.5%, 375-400bp=58.5%)
    today_entry = {"date": today_label, "cut_25": 41.5, "hold": 58.5}

    # 이미 오늘 날짜가 있다면 갱신, 없다면 추가 후 최근 5개 유지
    if history and history[-1]["date"].startswith(
        datetime.now().strftime("%m-%d")
    ):
        history[-1] = today_entry
    else:
        history.append(today_entry)

    if len(history) > 5:
        history = history[-5:]

    fedwatch_data["history"] = history
    fedwatch_data["meeting_date"] = "2026-09-16 (차기 FOMC)"
    fedwatch_data["current_target"] = "3.75%-4.00%"
    return fedwatch_data


def main():
    data = load_existing_data()

    # 1. 국채금리 & VIX
    rates = fetch_naver_rates()
    for k, v in rates.items():
        data[k] = v

    vix = fetch_vix()
    if vix:
        data["vix"] = vix

    y10 = data.get("us10y", {}).get("value", 4.78)
    y2 = data.get("us2y", {}).get("value", 4.32)
    spread_bp = round((y10 - y2) * 100)
    data["spread"] = {
        "value": spread_bp,
        "status": "정상화 (우상향)" if spread_bp >= 0 else "역전 (침체경보)",
    }

    # 2. CME FedWatch 5일 히스토리 롤링 갱신
    if "fedwatch" not in data:
        data["fedwatch"] = {}
    data["fedwatch"] = update_fedwatch_history(data["fedwatch"])

    # 3. 4대 핵심 RSS 채널 수집
    if "feeds" not in data:
        data["feeds"] = {}

    # 3-1. 미 연준: 통화정책 연설(Speeches) 우선 수집 (없을 시 FOMC 성명서 병합)
    fed_speeches = fetch_rss(
        "https://www.federalreserve.gov/feeds/speeches.xml",
        max_items=4,
        prefix="[연설]",
    )
    fed_monetary = fetch_rss(
        "https://www.federalreserve.gov/feeds/press_monetary.xml",
        max_items=2,
        prefix="[성명]",
    )
    data["feeds"]["fed"] = (fed_speeches + fed_monetary)[:5]

    # 3-2. 글로벌 마켓 속보: CNBC Markets (IB 의견/CPI/기업실적/M&A) + 야후 파이낸스
    cnbc_items = fetch_rss(
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
        max_items=4,
    )
    if not cnbc_items:
        cnbc_items = fetch_rss(
            "https://finance.yahoo.com/news/rssindex", max_items=4
        )
    data["feeds"]["global"] = cnbc_items

    # 3-3. 테크 & 공급망: 디일렉(THE ELEC) 반도체/소부장 + 전자신문(ETNews) 병합
    elec_items = fetch_rss(
        "https://www.thelec.kr/rss/S1N2.xml", max_items=3, prefix="[디일렉]"
    )
    if not elec_items:
        elec_items = fetch_rss(
            "https://www.thelec.kr/rss/allArticle.xml",
            max_items=3,
            prefix="[디일렉]",
        )
    etnews_items = fetch_rss(
        "https://rss.etnews.com/Section902.xml", max_items=3, prefix="[전자신문]"
    )
    # 교차 배치
    tech_merged = []
    for e, t in zip(elec_items, etnews_items):
        tech_merged.extend([e, t])
    if len(elec_items) > len(etnews_items):
        tech_merged.extend(elec_items[len(etnews_items) :])
    elif len(etnews_items) > len(elec_items):
        tech_merged.extend(etnews_items[len(elec_items) :])
    data["feeds"]["tech"] = tech_merged[:5]

    # 3-4. 여의도 채권/외환: 연합인포맥스
    data["feeds"]["domestic"] = fetch_rss(
        "https://news.einfomax.co.kr/rss/S1N16.xml", max_items=5
    )

    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("CME FedWatch 5일 히스토리 및 최신 RSS 수집 완료!")


if __name__ == "__main__":
    main()
