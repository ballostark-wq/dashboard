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
    """기존 data.json 안전장치"""
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
            html_text = res.text
            rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html_text, re.DOTALL)
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
        print(f"네이버 금리 파싱 예외: {e}")
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
    """다양한 RSS 날짜 포맷을 간결한 MM-DD HH:MM 형식으로 정규화"""
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


def fetch_rss_feed(url, max_items=5, encoding=None):
    """범용 XML RSS 파서 (오류 발생 시에도 안전하게 빈 배열 반환)"""
    items = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            if encoding:
                res.encoding = encoding
            # XML 루트 파싱
            root = ET.fromstring(res.content)
            for item in root.findall(".//item")[:max_items]:
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                pub_date = item.findtext("pubDate", "")

                title = re.sub(r"<[^>]+>", "", title)
                title = html.unescape(title).strip()

                if title and link:
                    items.append({
                        "title": title,
                        "link": link.strip(),
                        "date": clean_date_str(pub_date),
                    })
    except Exception as e:
        print(f"RSS 수집 예외 ({url}): {e}")
    return items


def generate_macro_briefing(y10, y2, spread_bp, vix_val):
    """지표 기반 매크로 레짐 브리핑 합성"""
    if vix_val < 16.0:
        regime = "Risk-on 우위"
        vix_status = "VIX 안정세로 시스템 리스크가 통제된 우호적 환경"
    elif vix_val < 20.0:
        regime = "중립 / 경계"
        vix_status = "변동성 확대로 섹터별 차별화 심화 구간"
    else:
        regime = "Risk-off 경보"
        vix_status = "VIX 급등으로 방어적 헤지 수요 급증 국면"

    curve_status = (
        "장단기 금리차 정상화(Steepening)"
        if spread_bp >= 0
        else "수익률 곡선 역전 지속"
    )
    title = f"10Y {y10}%선 공방과 VIX({vix_val}) 안정: {regime} 차별화 장세"

    bullets = [
        (
            f"미 10년물 {y10}% 수준 지속 속에서도 {vix_status}이 유지되며 하방"
            " 경직성 확보"
        ),
        (
            f"10Y-2Y 스프레드({spread_bp:+d} bp) {curve_status}로 경기 침체"
            " 공포보다 실적 모멘텀에 시장 초점"
        ),
        (
            "실물 원자재(구리) 추세 및 반도체 밸류체인으로의 자금 집중 현상 지속"
            " 관측"
        ),
    ]

    trading_strategy = (
        f"현재 레짐은 '{regime}' 국면입니다. 금리 상방 압력으로 인해 밸류에이션"
        " 부담이 큰 비기술 성장주는 변동성에 노출될 수 있습니다. AI 반도체"
        " 독점 벤더 및 수주 가시성이 확보된 인프라·소부장 중심의 압축 대응이"
        " 유효합니다."
    )

    return {
        "title": title,
        "regime": regime,
        "bullets": bullets,
        "trading_strategy": trading_strategy,
    }


def main():
    data = load_existing_data()

    # 1. 국채금리 갱신
    rates = fetch_naver_rates()
    for k, v in rates.items():
        data[k] = v

    # 2. VIX 갱신
    vix = fetch_vix()
    if vix:
        data["vix"] = vix

    # 3. 장단기 스프레드
    y10 = data.get("us10y", {}).get("value", 4.78)
    y2 = data.get("us2y", {}).get("value", 4.32)
    spread_bp = round((y10 - y2) * 100)
    data["spread"] = {
        "value": spread_bp,
        "status": "정상화 (우상향)" if spread_bp >= 0 else "역전 (침체경보)",
    }

    # 4. 4대 트레이딩 RSS 피드 수집
    if "feeds" not in data:
        data["feeds"] = {}

    # 4-1. 미 연준(FRB) 보도자료/성명
    fed_items = fetch_rss_feed(
        "https://www.federalreserve.gov/feeds/press_all.xml", max_items=5
    )
    if fed_items:
        data["feeds"]["fed"] = fed_items

    # 4-2. 마켓워치(MarketWatch) 실시간 글로벌 속보
    global_items = fetch_rss_feed(
        "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines",
        max_items=5,
    )
    if global_items:
        data["feeds"]["global"] = global_items

    # 4-3. 전자신문(ETNews) 테크/반도체
    tech_items = fetch_rss_feed(
        "https://rss.etnews.com/Section902.xml", max_items=5
    )
    if tech_items:
        data["feeds"]["tech"] = tech_items

    # 4-4. 연합인포맥스 채권/외환
    infomax_items = fetch_rss_feed(
        "https://news.einfomax.co.kr/rss/S1N16.xml", max_items=5
    )
    if infomax_items:
        data["feeds"]["domestic"] = infomax_items

    # 5. 매크로 브리핑 합성
    vix_val = data.get("vix", {}).get("value", 15.30)
    data["macro_briefing"] = generate_macro_briefing(
        y10, y2, spread_bp, vix_val
    )

    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("4대 RSS 피드 및 매크로 브리핑 동기화 완료!")


if __name__ == "__main__":
    main()
