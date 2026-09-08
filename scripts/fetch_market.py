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
    """기존 data.json 안전장치 및 기본 20일 히스토리 시드"""
    default_bonds_hist = [
        {"date": "08-11", "us10y": 4.62, "us2y": 4.25, "spread": 37},
        {"date": "08-12", "us10y": 4.64, "us2y": 4.26, "spread": 38},
        {"date": "08-13", "us10y": 4.65, "us2y": 4.27, "spread": 38},
        {"date": "08-14", "us10y": 4.68, "us2y": 4.28, "spread": 40},
        {"date": "08-17", "us10y": 4.70, "us2y": 4.30, "spread": 40},
        {"date": "08-18", "us10y": 4.69, "us2y": 4.29, "spread": 40},
        {"date": "08-19", "us10y": 4.71, "us2y": 4.30, "spread": 41},
        {"date": "08-20", "us10y": 4.73, "us2y": 4.31, "spread": 42},
        {"date": "08-21", "us10y": 4.72, "us2y": 4.30, "spread": 42},
        {"date": "08-24", "us10y": 4.75, "us2y": 4.32, "spread": 43},
        {"date": "08-25", "us10y": 4.74, "us2y": 4.31, "spread": 43},
        {"date": "08-26", "us10y": 4.76, "us2y": 4.32, "spread": 44},
        {"date": "08-27", "us10y": 4.75, "us2y": 4.31, "spread": 44},
        {"date": "08-28", "us10y": 4.77, "us2y": 4.32, "spread": 45},
        {"date": "08-31", "us10y": 4.76, "us2y": 4.31, "spread": 45},
        {"date": "09-01", "us10y": 4.77, "us2y": 4.32, "spread": 45},
        {"date": "09-02", "us10y": 4.78, "us2y": 4.33, "spread": 45},
        {"date": "09-03", "us10y": 4.76, "us2y": 4.31, "spread": 45},
        {"date": "09-04", "us10y": 4.77, "us2y": 4.32, "spread": 45},
        {"date": "09-08", "us10y": 4.78, "us2y": 4.32, "spread": 46},
    ]

    default_comm_hist = [
        {"date": "08-11", "copper": 4.45, "gold": 2610.5, "silver": 30.2},
        {"date": "08-12", "copper": 4.47, "gold": 2618.0, "silver": 30.5},
        {"date": "08-13", "copper": 4.49, "gold": 2625.4, "silver": 30.6},
        {"date": "08-14", "copper": 4.51, "gold": 2630.0, "silver": 30.8},
        {"date": "08-17", "copper": 4.50, "gold": 2635.2, "silver": 30.7},
        {"date": "08-18", "copper": 4.53, "gold": 2642.0, "silver": 31.0},
        {"date": "08-19", "copper": 4.55, "gold": 2648.5, "silver": 31.1},
        {"date": "08-20", "copper": 4.54, "gold": 2650.0, "silver": 31.0},
        {"date": "08-21", "copper": 4.56, "gold": 2655.4, "silver": 31.2},
        {"date": "08-24", "copper": 4.58, "gold": 2660.1, "silver": 31.4},
        {"date": "08-25", "copper": 4.57, "gold": 2658.0, "silver": 31.3},
        {"date": "08-26", "copper": 4.59, "gold": 2665.2, "silver": 31.5},
        {"date": "08-27", "copper": 4.60, "gold": 2670.0, "silver": 31.6},
        {"date": "08-28", "copper": 4.59, "gold": 2668.5, "silver": 31.5},
        {"date": "08-31", "copper": 4.61, "gold": 2672.4, "silver": 31.6},
        {"date": "09-01", "copper": 4.60, "gold": 2675.0, "silver": 31.7},
        {"date": "09-02", "copper": 4.62, "gold": 2680.5, "silver": 31.8},
        {"date": "09-03", "copper": 4.61, "gold": 2678.0, "silver": 31.6},
        {"date": "09-04", "copper": 4.63, "gold": 2682.4, "silver": 31.8},
        {"date": "09-08", "copper": 4.62, "gold": 2685.4, "silver": 31.75},
    ]

    default_fx_hist = [
        {"date": "08-11", "usdkrw": 1365.2, "dxy": 102.8},
        {"date": "08-12", "usdkrw": 1368.0, "dxy": 103.0},
        {"date": "08-13", "usdkrw": 1370.5, "dxy": 103.1},
        {"date": "08-14", "usdkrw": 1372.0, "dxy": 103.3},
        {"date": "08-17", "usdkrw": 1371.4, "dxy": 103.2},
        {"date": "08-18", "usdkrw": 1374.2, "dxy": 103.4},
        {"date": "08-19", "usdkrw": 1375.8, "dxy": 103.5},
        {"date": "08-20", "usdkrw": 1377.0, "dxy": 103.6},
        {"date": "08-21", "usdkrw": 1376.2, "dxy": 103.5},
        {"date": "08-24", "usdkrw": 1379.0, "dxy": 103.7},
        {"date": "08-25", "usdkrw": 1378.4, "dxy": 103.6},
        {"date": "08-26", "usdkrw": 1380.2, "dxy": 103.8},
        {"date": "08-27", "usdkrw": 1381.5, "dxy": 103.9},
        {"date": "08-28", "usdkrw": 1380.0, "dxy": 103.8},
        {"date": "08-31", "usdkrw": 1382.4, "dxy": 103.9},
        {"date": "09-01", "usdkrw": 1381.0, "dxy": 103.8},
        {"date": "09-02", "usdkrw": 1383.5, "dxy": 104.0},
        {"date": "09-03", "usdkrw": 1382.0, "dxy": 103.9},
        {"date": "09-04", "usdkrw": 1381.8, "dxy": 103.8},
        {"date": "09-08", "usdkrw": 1382.5, "dxy": 103.85},
    ]

    default_oil_hist = [
        {"date": "08-11", "wti": 78.4, "change": 0.5},
        {"date": "08-12", "wti": 78.1, "change": -0.4},
        {"date": "08-13", "wti": 77.8, "change": -0.4},
        {"date": "08-14", "wti": 77.2, "change": -0.8},
        {"date": "08-17", "wti": 76.9, "change": -0.4},
        {"date": "08-18", "wti": 76.5, "change": -0.5},
        {"date": "08-19", "wti": 76.8, "change": 0.4},
        {"date": "08-20", "wti": 76.2, "change": -0.8},
        {"date": "08-21", "wti": 75.9, "change": -0.4},
        {"date": "08-24", "wti": 75.5, "change": -0.5},
        {"date": "08-25", "wti": 75.8, "change": 0.4},
        {"date": "08-26", "wti": 76.1, "change": 0.4},
        {"date": "08-27", "wti": 75.7, "change": -0.5},
        {"date": "08-28", "wti": 75.4, "change": -0.4},
        {"date": "08-31", "wti": 75.1, "change": -0.4},
        {"date": "09-01", "wti": 75.5, "change": 0.5},
        {"date": "09-02", "wti": 76.0, "change": 0.7},
        {"date": "09-03", "wti": 75.9, "change": -0.1},
        {"date": "09-04", "wti": 76.3, "change": 0.5},
        {"date": "09-08", "wti": 75.8, "change": -0.65},
    ]

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
        "history_20d": {
            "bonds": default_bonds_hist,
            "commodities": default_comm_hist,
            "fx": default_fx_hist,
            "oil": default_oil_hist,
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
                saved = json.load(f)
                if "history_20d" not in saved:
                    saved["history_20d"] = default_data["history_20d"]
                return saved
        except Exception:
            pass
    return default_data


def fetch_yahoo_history(symbol, days=20):
    """야후 파이낸스에서 1개월치 일별 종가 히스토리 수집"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1mo"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            result = res.json()["chart"]["result"][0]
            timestamps = result.get("timestamp", [])
            closes = (
                result.get("indicators", {})
                .get("quote", [{}])[0]
                .get("close", [])
            )
            data_points = []
            for ts, c in zip(timestamps, closes):
                if c is not None:
                    d_str = datetime.fromtimestamp(ts).strftime("%m-%d")
                    data_points.append(
                        {"date": d_str, "price": round(float(c), 2)}
                    )
            return data_points[-days:]
    except Exception as e:
        print(f"야후 히스토리 수집 예외 ({symbol}): {e}")
    return []


def fetch_yahoo_quote(symbol):
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


def generate_macro_reviews_with_metrics(
    y10_data, y2_data, spread_bp, ind, naver_rates
):
    y10 = y10_data.get("value", 4.78)
    y10_chg = y10_data.get("change", 0.0)
    y2 = y2_data.get("value", 4.32)
    y2_chg = y2_data.get("change", 0.0)
    y30 = naver_rates.get("us30y", {}).get("value", 4.95)
    y30_chg = naver_rates.get("us30y", {}).get("change", 0.0)

    cop = ind.get("copper", {"price": 4.62, "change": 0.85})
    gold = ind.get("gold", {"price": 2685.4, "change": 0.32})
    silver = ind.get("silver", {"price": 31.75, "change": -0.45})
    wti = ind.get("wti", {"price": 75.80, "change": -0.65})
    krw = ind.get("usdkrw", {"price": 1382.50, "change": 0.25})
    dxy = ind.get("dxy", {"price": 103.85, "change": -0.12})

    curve_state = "정상화 (우상향)" if spread_bp >= 0 else "역전 (침체경보)"
    bonds = {
        "badge": f"스프레드 {spread_bp:+d} bp",
        "title": f"미국채 10년물 {y10}%선 공방과 {curve_state}",
        "metrics": [
            {
                "name": "10년물",
                "val": f"{y10:.2f}%",
                "chg": f"{y10_chg:+.2f}%",
                "up": y10_chg >= 0,
            },
            {
                "name": "2년물",
                "val": f"{y2:.2f}%",
                "chg": f"{y2_chg:+.2f}%",
                "up": y2_chg >= 0,
            },
            {
                "name": "30년물",
                "val": f"{y30:.2f}%",
                "chg": f"{y30_chg:+.2f}%",
                "up": y30_chg >= 0,
            },
            {
                "name": "10Y-2Y차",
                "val": f"{spread_bp:+d} bp",
                "chg": curve_state,
                "up": spread_bp >= 0,
            },
        ],
        "bullets": [
            (
                f"10년물 {y10}%와 2년물 {y2}% 형성으로 장단기차 {spread_bp:+d} bp"
                " 유지"
            ),
            "단기 통화정책 안정세 속 재정 적자 발행에 따른 장기물 기간 프리미엄",
        ],
        "detail": (
            f"10Y-2Y 스프레드가 {spread_bp:+d} bp를 기록하며 채권시장은 경기"
            " 침체 회피에 무게를 두고 있습니다. 무리한 듀레이션 확대보다는 2~3년물"
            " 중심의 바벨 전략이 적합합니다."
        ),
    }

    cop_dir = "강세" if cop["change"] >= 0 else "조정"
    commodities = {
        "badge": f"구리 ${cop['price']}",
        "title": f"닥터 코퍼 ${cop['price']}선 {cop_dir} 및 귀금속 헤지 수요",
        "metrics": [
            {
                "name": "구리(동)",
                "val": f"${cop['price']:.2f}",
                "chg": f"{cop['change']:+.2f}%",
                "up": cop["change"] >= 0,
            },
            {
                "name": "금(Gold)",
                "val": f"${gold['price']:,.1f}",
                "chg": f"{gold['change']:+.2f}%",
                "up": gold["change"] >= 0,
            },
            {
                "name": "은(Silver)",
                "val": f"${silver['price']:.2f}",
                "chg": f"{silver['change']:+.2f}%",
                "up": silver["change"] >= 0,
            },
        ],
        "bullets": [
            (
                f"구리(Copper) ${cop['price']}/lb ({cop['change']:+.2f}%) -"
                f" 글로벌 인프라·AI 전력망 설비 수요 반영 ({cop_dir})"
            ),
            (
                f"금 ${gold['price']:,.0f}/oz, 은 ${silver['price']}/oz - 통화가치"
                " 희석 우려에 대한 헤지 수요 지속"
            ),
        ],
        "detail": (
            f"실물 경기 선행지표인 구리가 ${cop['price']}선에서"
            f" {cop['change']:+.2f}% 흐름을 보이며 인프라 증설 기대를"
            " 견인하고 있습니다. 금·은의 동반 지지력은 유동성 방어 수요가"
            " 유효함을 나타냅니다."
        ),
    }

    krw_state = "원화 약세" if krw["change"] >= 0 else "원화 강세"
    fx = {
        "badge": f"원/달러 {krw['price']:,.0f}원",
        "title": f"원/달러 {krw['price']:,.1f}원선 등락과 DXY {dxy['price']}pt 지지",
        "metrics": [
            {
                "name": "원/달러",
                "val": f"{krw['price']:,.1f}원",
                "chg": f"{krw['change']:+.2f}%",
                "up": krw["change"] >= 0,
            },
            {
                "name": "달러인덱스",
                "val": f"{dxy['price']:.2f}pt",
                "chg": f"{dxy['change']:+.2f}%",
                "up": dxy["change"] >= 0,
            },
        ],
        "bullets": [
            (
                f"달러 인덱스(DXY) {dxy['price']}pt ({dxy['change']:+.2f}%) -"
                " 미국 상대성장 우위로 달러 하방 경직성"
            ),
            (
                f"원/달러 환율 {krw['price']:,.1f}원 ({krw['change']:+.2f}%) -"
                f" {krw_state} 구간 속 외국인 패시브 수급 주시"
            ),
        ],
        "detail": (
            f"원/달러 환율 {krw['price']:,.1f}원선은 반도체 등 수출 대형주의"
            " 원화 환산 실적을 방어하는 완충 역할을 합니다. DXY 103선 지지는"
            " 연준의 신중한 금리 인하 경로를 반영합니다."
        ),
    }

    oil_status = (
        "박스권 안정"
        if wti["price"] < 80.0
        else "상방 압력 경계"
    )
    oil = {
        "badge": f"WTI ${wti['price']}",
        "title": f"WTI 배럴당 ${wti['price']}선과 {oil_status}",
        "metrics": [
            {
                "name": "WTI 원유",
                "val": f"${wti['price']:.2f}",
                "chg": f"{wti['change']:+.2f}%",
                "up": wti["change"] >= 0,
            },
            {
                "name": "유가 국면",
                "val": oil_status,
                "chg": "에너지 마진 안정",
                "up": True,
            },
        ],
        "bullets": [
            (
                f"WTI 원유 선물: ${wti['price']}/배럴 ({wti['change']:+.2f}%) -"
                " 공급망 비용 스퀴즈 압박 경감"
            ),
            "에너지 가격 안정세로 헤드라인 인플레이션 자극 제한",
        ],
        "detail": (
            f"유가가 배럴당 ${wti['price']} 수준으로 안정됨에 따라 제조업체의"
            " 원가 마진 스퀴즈 위험이 축소되었습니다. 이는 IT 하드웨어주 중심의"
            " 실적 장세를 뒷받침하는 핵심 요인입니다."
        ),
    }

    return {
        "bonds": bonds,
        "commodities": commodities,
        "fx": fx,
        "oil": oil,
    }


def update_20d_history(existing_hist, y10, y2, spread_bp, ind):
    """실시간 시세와 1개월 일봉 데이터를 결합해 최근 20일 시계열 갱신"""
    today_label = datetime.now().strftime("%m-%d")

    # 1. 국채 20일 추이 갱신
    b_hist = existing_hist.get("bonds", [])
    today_bond = {
        "date": today_label,
        "us10y": y10,
        "us2y": y2,
        "spread": spread_bp,
    }
    if b_hist and b_hist[-1]["date"] == today_label:
        b_hist[-1] = today_bond
    else:
        b_hist.append(today_bond)
    b_hist = b_hist[-20:]

    # 2. 원자재 20일 추이 갱신
    c_hist = existing_hist.get("commodities", [])
    today_comm = {
        "date": today_label,
        "copper": ind.get("copper", {}).get("price", 4.62),
        "gold": ind.get("gold", {}).get("price", 2685.4),
        "silver": ind.get("silver", {}).get("price", 31.75),
    }
    if c_hist and c_hist[-1]["date"] == today_label:
        c_hist[-1] = today_comm
    else:
        c_hist.append(today_comm)
    c_hist = c_hist[-20:]

    # 3. 환율 20일 추이 갱신
    fx_hist = existing_hist.get("fx", [])
    today_fx = {
        "date": today_label,
        "usdkrw": ind.get("usdkrw", {}).get("price", 1382.5),
        "dxy": ind.get("dxy", {}).get("price", 103.85),
    }
    if fx_hist and fx_hist[-1]["date"] == today_label:
        fx_hist[-1] = today_fx
    else:
        fx_hist.append(today_fx)
    fx_hist = fx_hist[-20:]

    # 4. 유가 20일 추이 갱신
    oil_hist = existing_hist.get("oil", [])
    today_oil = {
        "date": today_label,
        "wti": ind.get("wti", {}).get("price", 75.8),
        "change": ind.get("wti", {}).get("change", -0.65),
    }
    if oil_hist and oil_hist[-1]["date"] == today_label:
        oil_hist[-1] = today_oil
    else:
        oil_hist.append(today_oil)
    oil_hist = oil_hist[-20:]

    return {
        "bonds": b_hist,
        "commodities": c_hist,
        "fx": fx_hist,
        "oil": oil_hist,
    }


def main():
    data = load_existing_data()

    # 1. 네이버 국채금리 수집
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

    # 2. VIX 및 실시간 지표 수집
    vix = fetch_yahoo_quote("^VIX")
    if vix:
        data["vix"] = vix

    if "indicators" not in data:
        data["indicators"] = {}

    indicators_map = {
        "copper": "HG=F",
        "gold": "GC=F",
        "silver": "SI=F",
        "wti": "CL=F",
        "usdkrw": "KRW=X",
        "dxy": "DX-Y.NYB",
    }

    for key, symbol in indicators_map.items():
        quote = fetch_yahoo_quote(symbol)
        if quote:
            data["indicators"][key] = quote

    # 3. 20일 히스토리 롤링 갱신
    data["history_20d"] = update_20d_history(
        data.get("history_20d", {}),
        y10_data["value"],
        y2_data["value"],
        spread_bp,
        data["indicators"],
    )

    # 4. 데이터 우선 매크로 리뷰 생성
    data["macro_reviews"] = generate_macro_reviews_with_metrics(
        y10_data, y2_data, spread_bp, data["indicators"], rates
    )

    # 5. 4대 RSS 피드 수집
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

    print("20영업일 히스토리 및 실시간 데이터 동기화 완료!")


if __name__ == "__main__":
    main()
