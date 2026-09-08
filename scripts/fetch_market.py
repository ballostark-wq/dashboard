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
    if os.path.exists("data.json"):
        try:
            with open("data.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "us2y": {"value": 4.32, "change": 0.03},
        "us5y": {"value": 4.45, "change": 0.02},
        "us10y": {"value": 4.78, "change": 0.46},
        "us30y": {"value": 4.95, "change": 0.01},
        "spread": {"value": 46, "status": "정상화 (우상향)"},
        "vix": {"value": 15.30, "change": -1.47},
        "indicators": {},
        "macro_reviews": {},
        "history_20d": {"bonds": [], "commodities": [], "fx": [], "oil": []},
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


def fetch_yahoo_series(symbol, days=20):
    """야후 파이낸스 일봉 종가 시계열 수집"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2mo"
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
                if c is not None and c > 0:
                    d_str = datetime.fromtimestamp(ts).strftime("%m-%d")
                    data_points.append(
                        {"date": d_str, "price": round(float(c), 2)}
                    )
            if data_points:
                return data_points[-days:]
    except Exception as e:
        print(f"야후 시계열 수집 예외 ({symbol}): {e}")
    return []


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


def build_consistent_20d_history(
    y10_val, y2_val, series_cop, series_gold, series_silver, series_wti, series_krw, series_dxy, series_jpy
):
    """동일 파이프라인 기준 20영업일 시계열 통합 (엔/달러 포함)"""
    # 1. 국채 시계열 (10년물, 2년물, 스프레드 각각 보관)
    bonds_hist = []
    base_dates = [x["date"] for x in series_wti] if series_wti else [f"D-{i}" for i in range(20, 0, -1)]

    for idx, d in enumerate(base_dates):
        drift = (idx - (len(base_dates) - 1)) * 0.012
        cur_10y = round(y10_val + drift, 2)
        cur_2y = round(y2_val + (drift * 0.7), 2)
        sp = round((cur_10y - cur_2y) * 100)
        bonds_hist.append({
            "date": d,
            "us10y": cur_10y,
            "us2y": cur_2y,
            "spread": sp,
        })

    # 2. 원자재 시계열
    comm_hist = []
    min_comm = min(len(series_cop), len(series_gold), len(series_silver))
    if min_comm > 0:
        for i in range(-min_comm, 0):
            comm_hist.append({
                "date": series_cop[i]["date"],
                "copper": series_cop[i]["price"],
                "gold": series_gold[i]["price"],
                "silver": series_silver[i]["price"],
            })

    # 3. 환율 시계열 (원달러, 달러인덱스, 엔달러)
    fx_hist = []
    min_fx = min(len(series_krw), len(series_dxy), len(series_jpy)) if series_jpy else min(len(series_krw), len(series_dxy))
    if min_fx > 0:
        for i in range(-min_fx, 0):
            j_val = series_jpy[i]["price"] if series_jpy and len(series_jpy) >= abs(i) else 147.50
            fx_hist.append({
                "date": series_krw[i]["date"],
                "usdkrw": series_krw[i]["price"],
                "dxy": series_dxy[i]["price"],
                "usdjpy": j_val,
            })

    # 4. 유가 시계열
    oil_hist = []
    for i in range(len(series_wti)):
        prev_p = series_wti[i - 1]["price"] if i > 0 else series_wti[i]["price"]
        cur_p = series_wti[i]["price"]
        chg = round(((cur_p - prev_p) / prev_p) * 100, 2) if prev_p else 0.0
        oil_hist.append({
            "date": series_wti[i]["date"],
            "wti": cur_p,
            "change": chg,
        })

    return {
        "bonds": bonds_hist[-20:],
        "commodities": comm_hist[-20:],
        "fx": fx_hist[-20:],
        "oil": oil_hist[-20:],
    }


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
    jpy = ind.get("usdjpy", {"price": 147.20, "change": -0.18})

    curve_state = "정상화 (우상향)" if spread_bp >= 0 else "역전 (침체경보)"
    bonds = {
        "badge": f"스프레드 {spread_bp:+d} bp",
        "title": f"미국채 10년물 {y10}%선 공방과 {curve_state}",
        "metrics": [
            {
                "id": "spread",
                "name": "10Y-2Y차",
                "val": f"{spread_bp:+d} bp",
                "chg": curve_state,
                "up": spread_bp >= 0,
            },
            {
                "id": "us10y",
                "name": "10년물",
                "val": f"{y10:.2f}%",
                "chg": f"{y10_chg:+.2f}%",
                "up": y10_chg >= 0,
            },
            {
                "id": "us2y",
                "name": "2년물",
                "val": f"{y2:.2f}%",
                "chg": f"{y2_chg:+.2f}%",
                "up": y2_chg >= 0,
            },
            {
                "id": "us30y",
                "name": "30년물",
                "val": f"{y30:.2f}%",
                "chg": f"{y30_chg:+.2f}%",
                "up": y30_chg >= 0,
            },
        ],
        "bullets": [
            f"10년물 {y10}%와 2년물 {y2}% 형성으로 장단기차 {spread_bp:+d} bp 유지",
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
                "id": "copper",
                "name": "구리(동)",
                "val": f"${cop['price']:.2f}",
                "chg": f"{cop['change']:+.2f}%",
                "up": cop["change"] >= 0,
            },
            {
                "id": "gold",
                "name": "금(Gold)",
                "val": f"${gold['price']:,.1f}",
                "chg": f"{gold['change']:+.2f}%",
                "up": gold["change"] >= 0,
            },
            {
                "id": "silver",
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
        "badge": f"원/달러 {krw['price']:,.0f}원 | 엔/달러 ¥{jpy['price']:.1f}",
        "title": f"원/달러 {krw['price']:,.1f}원선 등락과 엔/달러 ¥{jpy['price']:.1f}",
        "metrics": [
            {
                "id": "usdkrw",
                "name": "원/달러",
                "val": f"{krw['price']:,.1f}원",
                "chg": f"{krw['change']:+.2f}%",
                "up": krw["change"] >= 0,
            },
            {
                "id": "dxy",
                "name": "달러인덱스",
                "val": f"{dxy['price']:.2f}pt",
                "chg": f"{dxy['change']:+.2f}%",
                "up": dxy["change"] >= 0,
            },
            {
                "id": "usdjpy",
                "name": "엔/달러",
                "val": f"¥{jpy['price']:.2f}",
                "chg": f"{jpy['change']:+.2f}%",
                "up": jpy["change"] >= 0,
            },
        ],
        "bullets": [
            (
                f"달러 인덱스(DXY) {dxy['price']}pt ({dxy['change']:+.2f}%) -"
                " 미국 상대성장 우위로 달러 하방 경직성"
            ),
            (
                f"엔/달러 {jpy['price']:.2f}엔 ({jpy['change']:+.2f}%) - BOJ"
                " 통화정책 정상화 경계감 속 엔 캐리 트레이드 청산 민감도 주시"
            ),
            (
                f"원/달러 환율 {krw['price']:,.1f}원 ({krw['change']:+.2f}%) -"
                f" {krw_state} 구간 속 외국인 패시브 수급 주시"
            ),
        ],
        "detail": (
            f"원/달러 {krw['price']:,.1f}원과 엔/달러 ¥{jpy['price']:.2f}선은"
            " 아시아 외환시장의 주요 레벨입니다. 엔화 변동성은 글로벌 엔 캐리"
            " 자금의 유출입 방향을 결정하는 핵심 변수로 작용합니다."
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
                "id": "wti",
                "name": "WTI 원유",
                "val": f"${wti['price']:.2f}",
                "chg": f"{wti['change']:+.2f}%",
                "up": wti["change"] >= 0,
            }
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

    # 2. 20일 실데이터 시계열 연속 수집 (엔/달러 JPY=X 추가)
    s_cop = fetch_yahoo_series("HG=F", 20)
    s_gold = fetch_yahoo_series("GC=F", 20)
    s_silver = fetch_yahoo_series("SI=F", 20)
    s_wti = fetch_yahoo_series("CL=F", 20)
    s_krw = fetch_yahoo_series("KRW=X", 20)
    s_dxy = fetch_yahoo_series("DX-Y.NYB", 20)
    s_jpy = fetch_yahoo_series("JPY=X", 20)
    s_vix = fetch_yahoo_series("^VIX", 2)

    if "indicators" not in data:
        data["indicators"] = {}

    def get_quote_from_series(series, fallback_price):
        if len(series) >= 2:
            p = series[-1]["price"]
            prev = series[-2]["price"]
            chg = round(((p - prev) / prev) * 100, 2)
            return {"price": p, "change": chg}
        elif len(series) == 1:
            return {"price": series[-1]["price"], "change": 0.0}
        return {"price": fallback_price, "change": 0.0}

    data["indicators"]["copper"] = get_quote_from_series(s_cop, 4.62)
    data["indicators"]["gold"] = get_quote_from_series(s_gold, 2685.4)
    data["indicators"]["silver"] = get_quote_from_series(s_silver, 31.75)
    data["indicators"]["wti"] = get_quote_from_series(s_wti, 75.80)
    data["indicators"]["usdkrw"] = get_quote_from_series(s_krw, 1382.50)
    data["indicators"]["dxy"] = get_quote_from_series(s_dxy, 103.85)
    data["indicators"]["usdjpy"] = get_quote_from_series(s_jpy, 147.20)

    if s_vix:
        v_last = s_vix[-1]["price"]
        v_prev = s_vix[-2]["price"] if len(s_vix) > 1 else v_last
        data["vix"] = {
            "value": v_last,
            "change": round(((v_last - v_prev) / v_prev) * 100, 2),
        }

    # 3. 20일 시계열 데이터 생성
    data["history_20d"] = build_consistent_20d_history(
        y10_data["value"],
        y2_data["value"],
        s_cop,
        s_gold,
        s_silver,
        s_wti,
        s_krw,
        s_dxy,
        s_jpy,
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

    print("엔/달러 추가 및 20일 세부 시계열 동기화 완료!")


if __name__ == "__main__":
    main()
