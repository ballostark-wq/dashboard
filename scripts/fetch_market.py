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
    """기존 data.json 안전장치 및 백업 데이터 유지"""
    default_data = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "us2y": {"value": 4.32, "change": 0.03},
        "us5y": {"value": 4.45, "change": 0.02},
        "us10y": {"value": 4.78, "change": 0.46},
        "us30y": {"value": 4.95, "change": 0.01},
        "spread": {"value": 46, "status": "정상화 (우상향)"},
        "vix": {"value": 15.30, "change": -1.47},
        "indicators": {
            "copper": {"price": 4.62, "change": 0.85},
            "gold": {"price": 2685.40, "change": 0.32},
            "silver": {"price": 31.75, "change": -0.45},
            "wti": {"price": 75.80, "change": -0.65},
            "usdkrw": {"price": 1382.50, "change": 0.25},
            "dxy": {"price": 103.85, "change": -0.12},
        },
        "macro_reviews": {},
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


def fetch_yahoo_quote(symbol):
    """야후 파이낸스 공개 차트 API에서 실시간 시세 및 전일대비 등락률 수집"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            meta = res.json()["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice")
            prev = meta.get(
                "chartPreviousClose", meta.get("previousClose", price)
            )
            if price is not None and prev and prev > 0:
                chg = ((price - prev) / prev) * 100
                return {"price": round(float(price), 2), "change": round(chg, 2)}
    except Exception as e:
        print(f"야후 시세 수집 예외 ({symbol}): {e}")
    return None


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


def generate_realtime_macro_reviews(y10_data, y2_data, spread_bp, ind):
    """실제 수집된 실시간 수치에 기반한 지능형 매크로 분석 생성"""
    y10 = y10_data.get("value", 4.78)
    y10_chg = y10_data.get("change", 0.0)
    y2 = y2_data.get("value", 4.32)
    y2_chg = y2_data.get("change", 0.0)

    cop = ind.get("copper", {"price": 4.62, "change": 0.85})
    gold = ind.get("gold", {"price": 2685.4, "change": 0.32})
    silver = ind.get("silver", {"price": 31.75, "change": -0.45})
    wti = ind.get("wti", {"price": 75.80, "change": -0.65})
    krw = ind.get("usdkrw", {"price": 1382.50, "change": 0.25})
    dxy = ind.get("dxy", {"price": 103.85, "change": -0.12})

    # 1. 국채 수익률 곡선 동적 리뷰
    curve_state = "커브 스티프닝(정상화)" if spread_bp >= 0 else "커브 역전(침체경보)"
    bonds = {
        "badge": f"10Y {y10}% ({y10_chg:+.2f}%) | {spread_bp:+d}bp",
        "title": f"미 국채 10년물 {y10}%선 공방과 {curve_state}",
        "bullets": [
            (
                f"10년물 {y10}%({y10_chg:+.2f}%), 2년물"
                f" {y2}%({y2_chg:+.2f}%)로 스프레드 {spread_bp:+d} bp 형성"
            ),
            (
                "통화정책 민감 구간인 2년물 안정세 속 장기물 기간"
                " 프리미엄(Term Premium) 유지"
            ),
        ],
        "detail": (
            f"현재 장단기 금리차는 {spread_bp:+d} bp로, 장기 금리가 단기 금리를"
            " 상회하며 경기 침체 리스크 완화 국면을 가리킵니다. 발행 물량 소화에"
            " 따른 장기채 변동성 구간이므로 듀레이션 과확대보다는 단기 바벨"
            " 전략이 안정적입니다."
        ),
    }

    # 2. 원자재 동적 리뷰 (실제 가격 삽입)
    cop_dir = "강세" if cop["change"] >= 0 else "조정"
    gold_dir = "상승" if gold["change"] >= 0 else "하락"
    commodities = {
        "badge": f"구리 ${cop['price']} ({cop['change']:+.1f}%) | 금 ${gold['price']:,.0f}",
        "title": f"닥터 코퍼 ${cop['price']}/lb {cop_dir}와 금·은의 인플레 헤지",
        "bullets": [
            (
                f"구리(Copper): ${cop['price']}/lb ({cop['change']:+.2f}%) -"
                f" 글로벌 인프라·AI 전력망 설비 수요 반영 ({cop_dir})"
            ),
            (
                f"금: ${gold['price']:,.1f}/oz ({gold['change']:+.2f}%), 은:"
                f" ${silver['price']}/oz ({silver['change']:+.2f}%) - 통화가치"
                f" 헤지 {gold_dir}"
            ),
        ],
        "detail": (
            f"실물 경기의 바로미터인 구리가 ${cop['price']}선에서"
            f" {cop['change']:+.2f}% 움직이며 인프라 사이클 기대감을"
            " 유지하고 있습니다. 금·은의 하방 지지력은 시스템적 위험보다 글로벌"
            " 부채와 유동성 공급에 따른 화폐가치 방어 수요가 유입되고 있음을"
            " 시사합니다."
        ),
    }

    # 3. 환율 동적 리뷰 (실제 원/달러 및 DXY 삽입)
    dxy_dir = "상승" if dxy["change"] >= 0 else "약세"
    krw_dir = "원화 약세" if krw["change"] >= 0 else "원화 강세"
    fx = {
        "badge": f"원/달러 {krw['price']:,.1f}원 | DXY {dxy['price']}",
        "title": f"달러 인덱스 {dxy['price']}pt {dxy_dir}와 원/달러 {krw['price']:,.0f}원선 공방",
        "bullets": [
            (
                f"달러 인덱스(DXY): {dxy['price']}pt ({dxy['change']:+.2f}%) -"
                " 주요국 대비 미국 상대성장 우위 반영"
            ),
            (
                f"원/달러 환율: {krw['price']:,.1f}원 ({krw['change']:+.2f}%) -"
                f" {krw_dir} 구간 속 외국인 증시 수급 민감도 점검"
            ),
        ],
        "detail": (
            f"달러 인덱스가 {dxy['price']}선에서 등락하며 급격한 약세 전환은"
            f" 제한되는 모습입니다. 원/달러 환율 {krw['price']:,.1f}원선은 수출"
            " 대형주(반도체, 자동차)의 원화 환산 마진을 지지하는 반면 외국인의"
            " 지수 추종 패시브 자금 유출입의 임계선으로 작용합니다."
        ),
    }

    # 4. 유가 동적 리뷰 (실제 WTI 가격 삽입)
    oil_status = (
        "박스권 안정"
        if wti["price"] < 80.0
        else "상방 압력 경계"
    )
    oil = {
        "badge": f"WTI ${wti['price']} ({wti['change']:+.2f}%)",
        "title": f"WTI 배럴당 ${wti['price']}선 등락과 {oil_status}",
        "bullets": [
            (
                f"WTI 원유 선물: ${wti['price']}/배럴 ({wti['change']:+.2f}%) -"
                " 에너지발 공급망 비용 부담 완화 추세"
            ),
            (
                f"지정학적 리스크 프리미엄 축소 속 ${wti['price']}선 안착으로"
                " 헤드라인 CPI 자극 제한"
            ),
        ],
        "detail": (
            f"유가가 배럴당 ${wti['price']} 수준을 기록함에 따라 하드웨어"
            " 제조업체들의 원가 마진 스퀴즈(Margin Squeeze) 우려가"
            " 제한적입니다. 원자재발 인플레이션 충격이 낮아진 환경은 테크주의"
            " 실적 중심 랠리를 지탱하는 핵심 배경입니다."
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

    # 1. 네이버 국채금리 갱신
    rates = fetch_naver_rates()
    for k, v in rates.items():
        data[k] = v

    y10_data = data.get("us10y", {"value": 4.78, "change": 0.46})
    y2_data = data.get("us2y", {"value": 4.32, "change": 0.03})
    spread_bp = round((y10_data["value"] - y2_data["value"]) * 100)
    data["spread"] = {
        "value": spread_bp,
        "status": "정상화 (우상향)" if spread_bp >= 0 else "역전 (침체경보)",
    }

    # 2. VIX 및 실시간 글로벌 지표 수집
    vix = fetch_yahoo_quote("^VIX")
    if vix:
        data["vix"] = vix

    if "indicators" not in data:
        data["indicators"] = {}

    indicators_map = {
        "copper": "HG=F",  # 구리 선물 ($/lb)
        "gold": "GC=F",  # 금 선물 ($/oz)
        "silver": "SI=F",  # 은 선물 ($/oz)
        "wti": "CL=F",  # WTI 원유 ($/배럴)
        "usdkrw": "KRW=X",  # 원/달러 환율
        "dxy": "DX-Y.NYB",  # 달러 인덱스
    }

    for key, symbol in indicators_map.items():
        quote = fetch_yahoo_quote(symbol)
        if quote:
            data["indicators"][key] = quote

    # 3. 실제 지표 기반 4대 매크로 리뷰 동적 생성
    data["macro_reviews"] = generate_realtime_macro_reviews(
        y10_data, y2_data, spread_bp, data["indicators"]
    )

    # 4. 4대 RSS 피드 수집 (연준 연설 + CNBC + 디일렉/전자신문 + 인포맥스)
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

    print("실시간 시세 기반 매크로 리뷰 및 데이터 동기화 완료!")


if __name__ == "__main__":
    main()
