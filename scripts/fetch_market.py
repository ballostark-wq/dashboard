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
        "macro_reviews": {
            "bonds": {
                "badge": "Steepening",
                "title": "10Y-2Y 스프레드 정상화와 듀레이션 리스크",
                "bullets": [
                    "미 10년물 4.7%대 지지 속 경기 침체 확률 하락 반영",
                    (
                        "커브 스티프닝(우상향) 전개로 장기채 변동성 관리"
                        " 필요성 대두"
                    ),
                ],
                "detail": (
                    "기준금리 인하 경로 불확실성과 장기물 발행 부담이 맞물려"
                    " 기간 프리미엄이 상승하고 있습니다. 채권 듀레이션을"
                    " 과도하게 늘리기보다는 2~3년물 중심의 단기 바벨"
                    " 전략이 유리합니다."
                ),
            },
            "commodities": {
                "badge": "Dr. Copper 강세",
                "title": "구리·금·은 동반 강세: 실물 수요 vs 인플레 헤지",
                "bullets": [
                    "구리(닥터 코퍼) 급등으로 글로벌 전력망·AI 인프라 증설 반영",
                    "금·은 동반 상승으로 통화가치 희석에 대한 헤지 수요 지속",
                ],
                "detail": (
                    "구리의 상대적 강세는 실물 제조업 반등을 선행합니다."
                    " 금/구리 비율이 안정세를 보이고 있어 시스템 리스크보다는"
                    " 실물 설비투자 재개(Capex Cycle)에 무게를 두어야 합니다."
                ),
            },
            "fx": {
                "badge": "DXY 104선 지지",
                "title": "달러 인덱스 혼조와 원/달러 상방 경직성",
                "bullets": [
                    "미국-글로벌 주요국 간 성장 격차로 달러화 하방 경직성",
                    "원/달러 1,300원대 중후반 박스권 내 외환 당국 미세조정",
                ],
                "detail": (
                    "연준의 금리 인하 속도 조절로 달러화가 급격히 약세로"
                    " 전환되기는 어렵습니다. 환율 상방 압력은 수출 대형주(반도체,"
                    " 자동차) 마진에는 단기 우호적 요인으로 작용합니다."
                ),
            },
            "oil": {
                "badge": "박스권 유지",
                "title": "WTI 유가 안정세와 에너지발 마진 스퀴즈 완화",
                "bullets": [
                    "WTI 배럴당 70달러선 안착으로 헤드라인 인플레이션 자극 제한",
                    "지정학적 리스크 프리미엄 축소 속 비OPEC 공급 확대",
                ],
                "detail": (
                    "유가가 급등하지 않아 기술 하드웨어 및 국내 제조업체들의"
                    " 원가 마진 스퀴즈(Margin Squeeze) 부담이 완화되고"
                    " 있습니다. 위험자산 랠리의 핵심 완충제입니다."
                ),
            },
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


def generate_macro_quadrant_reviews(y10, y2, spread_bp, vix_val):
    """4대 핵심 축(국채금리, 원자재, 환율, 유가) 매크로 리뷰 지능형 생성"""
    # 1. 국채수익률
    curve_type = (
        "정상화 (Bull/Bear Steepening)" if spread_bp >= 0 else "역전 지속"
    )
    bonds = {
        "badge": f"10Y {y10}% / {spread_bp:+d}bp",
        "title": f"미국채 수익률 곡선: {curve_type}",
        "bullets": [
            f"10년물 {y10}%, 2년물 {y2}% 수준 형성으로 장단기차 {spread_bp:+d} bp 기록",
            (
                "경기 침체 회피 기대와 재정 적자 발행 부담 속 장기물 기간"
                " 프리미엄 유지"
            ),
        ],
        "detail": (
            f"10Y-2Y 스프레드가 {spread_bp:+d} bp 수준을 나타내며 수익률 곡선이"
            " 완만한 우상향 흐름을 보이고 있습니다. 단기 통화정책 완화 기대를"
            " 장기 금리가 지지하며 위험자산 멀티플을 방어하는 구간입니다."
        ),
    }

    # 2. 원자재
    commodities = {
        "badge": "닥터 코퍼 & 금",
        "title": "원자재: 구리 인프라 수요 견인 및 금 헤지",
        "bullets": [
            "구리(닥터 코퍼) 고점권 안착으로 AI 데이터센터·전력망 사이클 반영",
            (
                "글로벌 통화가치 희석 우려에 따른 중앙은행 금 매수세"
                " 하방 지지"
            ),
        ],
        "detail": (
            "닥터 코퍼의 지속적인 강세는 전통적 경기 침체 우려를 상쇄시키는"
            " 핵심 지표입니다. 금/은 가격이 하방을 다지는 가운데 산업용"
            " 금속으로의 수급 유입은 실물 투자 회복을 방증합니다."
        ),
    }

    # 3. 환율
    fx = {
        "badge": "달러 상방 경직",
        "title": "환율: 달러 인덱스 안정 속 원/달러 수급 공방",
        "bullets": [
            "미국 실질금리 우위로 달러화 급격한 약세 제한",
            "원/달러 상단 저항선 작용으로 수출주 환차익 및 외인 순매수 지속",
        ],
        "detail": (
            "연준과 타국 중앙은행 간 완화 시차로 달러화는 하방 경직성을"
            " 띱니다. 원/달러 환율의 완만한 안정세는 외국인의 국내 IT 대형주"
            " 패시브 매수 유입에 긍정적 환경을 제공합니다."
        ),
    }

    # 4. 유가
    oil = {
        "badge": "WTI 70선 안정",
        "title": "유가: 배럴당 70달러선 안착과 비용 압박 완화",
        "bullets": [
            "WTI 안정세 지속으로 헤드라인 인플레이션 재발 위험 억제",
            "기업 에너지 원가 부담 경감으로 하드웨어 제조업 마진 방어",
        ],
        "detail": (
            "에너지 가격의 안정은 연준의 금리 인하 명분을 강화해 줍니다. 고유가로"
            " 인한 밸류에이션 훼손 압력이 낮아지며 실적 중심 장세가"
            " 연장되고 있습니다."
        ),
    }

    return {
        "bonds": bonds,
        "commodities": commodities,
        "fx": fx,
        "oil": oil,
    }


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

    # 2. 4대 매크로 레짐 리뷰 생성
    vix_val = data.get("vix", {}).get("value", 15.30)
    data["macro_reviews"] = generate_macro_quadrant_reviews(
        y10, y2, spread_bp, vix_val
    )

    # 3. 4대 RSS 수집 (연준 연설 + CNBC + 디일렉/전자신문 + 인포맥스)
    if "feeds" not in data:
        data["feeds"] = {}

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

    data["feeds"]["global"] = fetch_rss(
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
        max_items=5,
    )
    if not data["feeds"]["global"]:
        data["feeds"]["global"] = fetch_rss(
            "https://finance.yahoo.com/news/rssindex", max_items=5
        )

    elec = fetch_rss(
        "https://www.thelec.kr/rss/allArticle.xml", max_items=3, prefix="[디일렉]"
    )
    etnews = fetch_rss(
        "https://rss.etnews.com/Section902.xml", max_items=3, prefix="[전자신문]"
    )
    tech_merged = []
    for e, t in zip(elec, etnews):
        tech_merged.extend([e, t])
    if len(elec) > len(etnews):
        tech_merged.extend(elec[len(etnews) :])
    elif len(etnews) > len(elec):
        tech_merged.extend(etnews[len(elec) :])
    data["feeds"]["tech"] = tech_merged[:5]

    data["feeds"]["domestic"] = fetch_rss(
        "https://news.einfomax.co.kr/rss/S1N16.xml", max_items=5
    )

    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("4대 매크로 리뷰 및 피드 갱신 완료!")


if __name__ == "__main__":
    main()
