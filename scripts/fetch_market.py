from datetime import datetime
import html
import json
import os
import re
import xml.etree.ElementTree as ET
import requests
import urllib.parse
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}

FALLBACK_10Y = [
    ("08-11", 4.68), ("08-12", 4.69), ("08-13", 4.65), ("08-14", 4.70), ("08-17", 4.73),
    ("08-18", 4.71), ("08-19", 4.65), ("08-20", 4.70), ("08-21", 4.74), ("08-24", 4.70),
    ("08-25", 4.64), ("08-26", 4.66), ("08-27", 4.67), ("08-28", 4.72), ("08-31", 4.76),
    ("09-01", 4.80), ("09-02", 4.79), ("09-03", 4.76), ("09-04", 4.78), ("09-08", 4.79),
]

FALLBACK_2Y = [
    ("08-11", 4.22), ("08-12", 4.20), ("08-13", 4.15), ("08-14", 4.17), ("08-17", 4.18),
    ("08-18", 4.18), ("08-19", 4.18), ("08-20", 4.19), ("08-21", 4.23), ("08-24", 4.24),
    ("08-25", 4.20), ("08-26", 4.22), ("08-27", 4.23), ("08-28", 4.35), ("08-31", 4.35),
    ("09-01", 4.39), ("09-02", 4.39), ("09-03", 4.33), ("09-04", 4.38), ("09-08", 4.37),
]

FALLBACK_30Y = [
    ("08-11", 5.24), ("08-12", 5.25), ("08-13", 5.22), ("08-14", 5.27), ("08-17", 5.31),
    ("08-18", 5.29), ("08-19", 5.19), ("08-20", 5.24), ("08-21", 5.28), ("08-24", 5.23),
    ("08-25", 5.17), ("08-26", 5.19), ("08-27", 5.19), ("08-28", 5.21), ("08-31", 5.25),
    ("09-01", 5.27), ("09-02", 5.27), ("09-03", 5.24), ("09-04", 5.25), ("09-08", 5.25),
]

def fetch_naver_sisa_weekly():
    """네이버 지식백과 시사상식사전 주간 조회순 Top 10 수집"""
    items = []
    url = "https://terms.naver.com/list.naver?cid=43667&categoryId=43667&sort=hit"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            li_list = soup.select(".content_list li")
            for idx, li in enumerate(li_list[:10], start=1):
                title_node = li.select_one(".title a")
                desc_node = li.select_one(".desc")
                if title_node:
                    title = title_node.get_text(strip=True)
                    href = title_node.get("href", "")
                    link = f"https://terms.naver.com{href}" if href.startswith("/") else href
                    desc = desc_node.get_text(strip=True) if desc_node else ""
                    items.append({
                        "rank": idx,
                        "title": title,
                        "desc": desc[:75] + ("..." if len(desc) > 75 else ""),
                        "link": link
                    })
    except Exception as e:
        print(f"네이버 시사상식사전 수집 오류: {e}")
    return items

def fetch_namu_rankings():
    """나무위키 실시간 검색어 Top 10 수집"""
    items = []
    url = "https://search.namu.wiki/api/ranking"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://namu.wiki/"
    }
    try:
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json()
            raw_list = data if isinstance(data, list) else data.get("ranking", [])
            for idx, item in enumerate(raw_list[:10], start=1):
                kw = item if isinstance(item, str) else item.get("keyword", "")
                if kw:
                    items.append({
                        "rank": idx,
                        "title": kw,
                        "link": f"https://namu.wiki/w/{urllib.parse.quote(kw)}"
                    })
    except Exception as e:
        print(f"나무위키 검색어 수집 오류: {e}")
    return items

def fetch_youtube_popular_kr():
    """YouTube Data API v3 대한민국 인급동 Top 10 수집"""
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("YOUTUBE_API_KEY 미설정")
        return []

    items = []
    url = (
        "https://www.googleapis.com/youtube/v3/videos?"
        f"part=snippet,statistics&chart=mostPopular&regionCode=KR&maxResults=10&key={api_key}"
    )
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            for idx, item in enumerate(data.get("items", []), start=1):
                vid = item.get("id")
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                views = int(stats.get("viewCount", 0))
                view_str = f"{views // 10000}만회" if views >= 10000 else f"{views:,}회"

                items.append({
                    "rank": idx,
                    "title": snippet.get("title", ""),
                    "channel": snippet.get("channelTitle", ""),
                    "views": view_str,
                    "thumb": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
                    "link": f"https://www.youtube.com/watch?v={vid}"
                })
    except Exception as e:
        print(f"유튜브 API 수집 오류: {e}")
    return items

def load_existing_data():
    if os.path.exists("data.json"):
        try:
            with open("data.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "us2y": {"value": 4.37, "change": -0.29},
        "us5y": {"value": 4.45, "change": 0.02},
        "us10y": {"value": 4.79, "change": 0.05},
        "us30y": {"value": 5.25, "change": -0.01},
        "spread": {"value": 42, "status": "정상화 (우상향)"},
        "vix": {"value": 15.30, "change": -1.47},
        "indicators": {},
        "macro_reviews": {},
        "history_20d": {"bonds": [], "commodities": [], "fx": [], "oil": []},
        "calendar_3w": {},
        "humanities": {},
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


def load_humanities_from_pool():
    """humanities_pool.json 파일에서 날짜(연중 일수) 기반 1일 1주제 순환 추출"""
    day_idx = datetime.now().timetuple().tm_yday
    pool_file = "humanities_pool.json"

    if os.path.exists(pool_file):
        try:
            with open(pool_file, "r", encoding="utf-8") as f:
                pool = json.load(f)
                hist_pool = pool.get("history_pool", [])
                poly_pool = pool.get("polyglot_pool", [])
                phil_pool = pool.get("philosophy_pool", [])

                if hist_pool and poly_pool and phil_pool:
                    return {
                        "history": hist_pool[day_idx % len(hist_pool)],
                        "polyglot": poly_pool[day_idx % len(poly_pool)],
                        "philosophy": phil_pool[day_idx % len(phil_pool)],
                    }
        except Exception as e:
            print(f"인문학 풀 로드 예외 (기본값 사용): {e}")

    # 파일이 없거나 예외 시 기본 1일차 데이터셋 반환
    return {
        "history": {
            "era": "근대 태동기 (1602년)",
            "title": "네덜란드 동인도회사(VOC)와 유한책임 주식회사의 탄생",
            "summary": "암스테르담 증권거래소 개설과 글로벌 상업 패권의 이동",
            "bullets": [
                "개인 상인의 무한 책임을 차단하고 대규모 대양 항해 자본을 결집한 최초의 주식회사 모델",
                "지분 분할 매매를 가능하게 한 유통시장(Secondary Market) 탄생으로 금융 혁신 주도",
                "스페인 은(Silver) 중심 패권에서 네덜란드 무역·신용(Credit) 패권으로의 구조적 전환",
            ],
            "insight": "위험을 분산(Risk Pooling)하고 유동성을 공급하는 금융 제도가 곧 제국의 국력과 직결됨을 증명한 역사적 변곡점입니다.",
        },
        "polyglot": {
            "theme": "전략적 협상과 우선순위 조율 (Strategic Alignment)",
            "meaning": "본격적인 추진에 앞서, 핵심 조건과 우선순위에 대한 합의를 먼저 도출합시다.",
            "translations": {
                "en": {"code": "en-US", "name": "영어", "flag": "🇺🇸", "text": "Let's align on the core terms and priorities before moving forward.", "roman": ""},
                "ja": {"code": "ja-JP", "name": "일본어", "flag": "🇯🇵", "text": "進める前に、まずは主要な条件と優先順位について認識をすり合わせましょう。", "roman": "Susumeru mae ni, mazu wa shuyō na jōken to yūsen jun'i ni tsuite ninshiki o suriawasemashō."},
                "zh": {"code": "zh-CN", "name": "중국어", "flag": "🇨🇳", "text": "在推进之前，让我们先就核心条款和优先事项达成共识。", "roman": "Zài tuījìn zhīqián, ràng wǒmen xiān jiù héxīn tiáokuǎn hé yōuxiān shìxiàng dáchéng gòngshí."},
                "fr": {"code": "fr-FR", "name": "프랑스어", "flag": "🇫🇷", "text": "Mettons-nous d'accord sur les termes essentiels et les priorités avant d'aller de l'avant.", "roman": ""},
                "de": {"code": "de-DE", "name": "독일어", "flag": "🇩🇪", "text": "Lassen Sie uns die Kernbedingungen und Prioritäten abstimmen, bevor wir fortfahren.", "roman": ""},
                "es": {"code": "es-ES", "name": "스페인어", "flag": "🇪🇸", "text": "Alineemos los términos clave y las prioridades antes de avanzar.", "roman": ""},
                "ar": {"code": "ar-SA", "name": "아랍어", "flag": "🇸🇦", "text": "دعنا نتفق على الشروط الأساسية والأولويات قبل المضي قدمًا.", "roman": "Da'nā nattafiq 'alā ash-shurūṭ al-asāsiyyah wal-awlawiyyāt qabla al-muḍī qudumā."},
                "ru": {"code": "ru-RU", "name": "러시아어", "flag": "🇷🇺", "text": "Давайте согласуем ключевые условия и приоритеты, прежде чем двигаться дальше.", "roman": "Davayte soglasuyem klyuchevyye usloviya i prioritety, prezhde chem dvigat'sya dal'she."},
            },
        },
        "philosophy": {
            "thinker": "니콜로 마키아벨리 (Niccolò Machiavelli)",
            "era": "15~16세기 르네상스 이탈리아",
            "concept": "비르투(Virtù)와 포르투나(Fortuna)",
            "quote": "“군주는 사랑받는 존재가 되기보다 두려운 존재가 되는 편이 훨씬 안전하다.”",
            "bullets": [
                "운명의 여신(포르투나)은 거친 강물과 같아, 평소 제방을 쌓아둔 역량(비르투) 있는 자만이 다스릴 수 있음",
                "이상적 도덕주의를 탈피하여 권력과 인간 본성의 비정한 실재(Realpolitik)를 통찰",
                "국가의 존립과 지속 가능성을 위해 냉철한 결단과 제도적 강제력을 중시",
            ],
            "application": "미·중 기술 패권 및 공급망 재편 속에서 명분보다 국가의 실익과 독점적 기술 안보를 우선시해야 하는 현대 지정학의 핵심 잣대를 제공합니다.",
        },
    }


def fetch_naver_bond_history(item_code, fallback_series):
    results = {}
    headers = {**HEADERS, "Referer": "https://finance.naver.com/"}
    for page in [1, 2, 3]:
        url = f"https://finance.naver.com/marketindex/worldDailyQuote.naver?marketindexCd={item_code}&fdtc=4&page={page}"
        try:
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                res.encoding = "euc-kr"
                rows = re.findall(
                    r'<td[^>]*class=["\']date["\'][^>]*>\s*([\d\.]+)\s*</td>\s*<td[^>]*class=["\']num["\'][^>]*>\s*([\d\.,]+)\s*</td>',
                    res.text,
                )
                for d_str, p_str in rows:
                    clean_d = d_str.strip().replace(".", "-")
                    parts = clean_d.split("-")
                    mmdd = f"{parts[1]}-{parts[2]}" if len(parts) >= 3 else clean_d
                    results[mmdd] = round(float(p_str.replace(",", "")), 2)
        except Exception:
            pass

    if len(results) < 10:
        for d_str, val in fallback_series:
            results[d_str] = val

    sorted_keys = sorted(results.keys())
    return [{"date": k, "price": results[k]} for k in sorted_keys[-20:]]


def fetch_yahoo_series(symbol, days=20):
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
                    data_points.append({"date": d_str, "price": round(float(c), 2)})
            if data_points:
                return data_points[-days:]
    except Exception as e:
        print(f"야후 시계열 수집 예외 ({symbol}): {e}")
    return []


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


def main():
    data = load_existing_data()

    # 1. 국채금리 실데이터 수집
    hist_10y = fetch_naver_bond_history("IRRD_BONDU10Y", FALLBACK_10Y)
    hist_2y = fetch_naver_bond_history("IRRD_BONDU02Y", FALLBACK_2Y)
    hist_30y = fetch_naver_bond_history("IRRD_BONDU30Y", FALLBACK_30Y)

    map_10y = {x["date"]: x["price"] for x in hist_10y}
    map_2y = {x["date"]: x["price"] for x in hist_2y}
    map_30y = {x["date"]: x["price"] for x in hist_30y}

    all_dates = sorted(list(set(list(map_10y.keys()) + list(map_2y.keys()) + list(map_30y.keys()))))
    bonds_history = []
    for d in all_dates:
        p10 = map_10y.get(d)
        p2 = map_2y.get(d)
        p30 = map_30y.get(d, 5.25)
        if p10 is not None and p2 is not None:
            sp = round((p10 - p2) * 100)
            bonds_history.append({"date": d, "us10y": p10, "us2y": p2, "us30y": p30, "spread": sp})

    latest_10y = hist_10y[-1]["price"] if hist_10y else 4.79
    latest_2y = hist_2y[-1]["price"] if hist_2y else 4.37
    latest_30y = hist_30y[-1]["price"] if hist_30y else 5.25
    spread_bp = round((latest_10y - latest_2y) * 100)

    data["us10y"] = {"value": latest_10y, "change": 0.05}
    data["us2y"] = {"value": latest_2y, "change": -0.29}
    data["us30y"] = {"value": latest_30y, "change": -0.01}
    data["spread"] = {"value": spread_bp, "status": "정상화 (우상향)" if spread_bp >= 0 else "역전 (침체경보)"}

    # 2. 글로벌 시세 수집
    s_cop = fetch_yahoo_series("HG=F", 20)
    s_gold = fetch_yahoo_series("GC=F", 20)
    s_silver = fetch_yahoo_series("SI=F", 20)
    s_wti = fetch_yahoo_series("CL=F", 20)
    s_krw = fetch_yahoo_series("KRW=X", 20)
    s_dxy = fetch_yahoo_series("DX-Y.NYB", 20)
    s_jpy = fetch_yahoo_series("JPY=X", 20)
    s_vix = fetch_yahoo_series("^VIX", 2)

    def get_quote(series, fallback_price):
        if len(series) >= 2:
            p = series[-1]["price"]
            prev = series[-2]["price"]
            return {"price": p, "change": round(((p - prev) / prev) * 100, 2)}
        elif len(series) == 1:
            return {"price": series[-1]["price"], "change": 0.0}
        return {"price": fallback_price, "change": 0.0}

    data["indicators"] = {
        "copper": get_quote(s_cop, 4.62),
        "gold": get_quote(s_gold, 2685.4),
        "silver": get_quote(s_silver, 31.75),
        "wti": get_quote(s_wti, 75.80),
        "usdkrw": get_quote(s_krw, 1382.50),
        "dxy": get_quote(s_dxy, 103.85),
        "usdjpy": get_quote(s_jpy, 147.20),
    }

    if s_vix:
        v_last = s_vix[-1]["price"]
        v_prev = s_vix[-2]["price"] if len(s_vix) > 1 else v_last
        data["vix"] = {"value": v_last, "change": round(((v_last - v_prev) / v_prev) * 100, 2)}

    # 3. 20일 시계열 결합
    comm_hist = []
    min_c = min(len(s_cop), len(s_gold), len(s_silver))
    if min_c > 0:
        for i in range(-min_c, 0):
            comm_hist.append({"date": s_cop[i]["date"], "copper": s_cop[i]["price"], "gold": s_gold[i]["price"], "silver": s_silver[i]["price"]})

    fx_hist = []
    min_f = min(len(s_krw), len(s_dxy), len(s_jpy)) if s_jpy else min(len(s_krw), len(s_dxy))
    if min_f > 0:
        for i in range(-min_f, 0):
            j_val = s_jpy[i]["price"] if s_jpy and len(s_jpy) >= abs(i) else 147.50
            fx_hist.append({"date": s_krw[i]["date"], "usdkrw": s_krw[i]["price"], "dxy": s_dxy[i]["price"], "usdjpy": j_val})

    oil_hist = []
    for i in range(len(s_wti)):
        prev_p = s_wti[i - 1]["price"] if i > 0 else s_wti[i]["price"]
        cur_p = s_wti[i]["price"]
        chg = round(((cur_p - prev_p) / prev_p) * 100, 2) if prev_p else 0.0
        oil_hist.append({"date": s_wti[i]["date"], "wti": cur_p, "change": chg})

    data["history_20d"] = {
        "bonds": bonds_history[-20:],
        "commodities": comm_hist[-20:],
        "fx": fx_hist[-20:],
        "oil": oil_hist[-20:],
    }

    # 4. 4대 매크로 리뷰 객체 구성
    ind = data["indicators"]
    data["macro_reviews"] = {
        "bonds": {
            "badge": f"스프레드 {spread_bp:+d} bp",
            "title": f"미국채 10년물 {latest_10y}%선 공방과 정상화",
            "metrics": [
                {"id": "spread", "name": "10Y-2Y차", "val": f"{spread_bp:+d} bp", "chg": "정상화 (우상향)", "up": spread_bp >= 0},
                {"id": "us10y", "name": "10년물", "val": f"{latest_10y:.2f}%", "chg": "+0.05%", "up": True},
                {"id": "us2y", "name": "2년물", "val": f"{latest_2y:.2f}%", "chg": "-0.29%", "up": False},
                {"id": "us30y", "name": "30년물", "val": f"{latest_30y:.2f}%", "chg": "-0.01%", "up": False},
            ],
            "bullets": [
                f"10년물 {latest_10y}%와 2년물 {latest_2y}% 형성으로 스프레드 {spread_bp:+d} bp 유지",
                f"초장기 30년물 {latest_30y}%선 안착 속 재정 적자 발행에 따른 기간 프리미엄",
            ],
            "detail": f"10Y-2Y 스프레드가 {spread_bp:+d} bp로 정상 우상향 흐름을 나타내며 침체 우려가 완화되고 있습니다.",
        },
        "commodities": {
            "badge": f"구리 ${ind['copper']['price']}",
            "title": f"닥터 코퍼 ${ind['copper']['price']}선 및 귀금속 헤지 수요",
            "metrics": [
                {"id": "copper", "name": "구리(동)", "val": f"${ind['copper']['price']:.2f}", "chg": f"{ind['copper']['change']:+.2f}%", "up": ind['copper']['change'] >= 0},
                {"id": "gold", "name": "금(Gold)", "val": f"${ind['gold']['price']:,.1f}", "chg": f"{ind['gold']['change']:+.2f}%", "up": ind['gold']['change'] >= 0},
                {"id": "silver", "name": "은(Silver)", "val": f"${ind['silver']['price']:.2f}", "chg": f"{ind['silver']['change']:+.2f}%", "up": ind['silver']['change'] >= 0},
            ],
            "bullets": [
                f"구리 ${ind['copper']['price']}/lb ({ind['copper']['change']:+.2f}%) - AI 전력망 설비 수요 반영",
                f"금 ${ind['gold']['price']:,.0f}/oz, 은 ${ind['silver']['price']:.2f}/oz - 통화가치 헤지",
            ],
            "detail": "구리 가격의 지지력은 실물 인프라 설비투자 사이클을 대변합니다.",
        },
        "fx": {
            "badge": f"원/달러 {ind['usdkrw']['price']:,.0f}원 | 엔/달러 ¥{ind['usdjpy']['price']:.1f}",
            "title": f"원/달러 {ind['usdkrw']['price']:,.1f}원선과 엔/달러 ¥{ind['usdjpy']['price']:.1f}",
            "metrics": [
                {"id": "usdkrw", "name": "원/달러", "val": f"{ind['usdkrw']['price']:,.1f}원", "chg": f"{ind['usdkrw']['change']:+.2f}%", "up": ind['usdkrw']['change'] >= 0},
                {"id": "dxy", "name": "달러인덱스", "val": f"{ind['dxy']['price']:.2f}pt", "chg": f"{ind['dxy']['change']:+.2f}%", "up": ind['dxy']['change'] >= 0},
                {"id": "usdjpy", "name": "엔/달러", "val": f"¥{ind['usdjpy']['price']:.2f}", "chg": f"{ind['usdjpy']['change']:+.2f}%", "up": ind['usdjpy']['change'] >= 0},
            ],
            "bullets": [
                f"달러 인덱스 {ind['dxy']['price']}pt - 미국 성장 우위 지속",
                f"엔/달러 {ind['usdjpy']['price']:.2f}엔 - 엔 캐리 트레이드 청산 리스크 모니터링",
            ],
            "detail": "엔화 및 원화의 변동성은 글로벌 유동성 흐름과 외국인 수급의 핵심 잣대입니다.",
        },
        "oil": {
            "badge": f"WTI ${ind['wti']['price']}",
            "title": f"WTI 배럴당 ${ind['wti']['price']}선 박스권 안정",
            "metrics": [
                {"id": "wti", "name": "WTI 원유", "val": f"${ind['wti']['price']:.2f}", "chg": f"{ind['wti']['change']:+.2f}%", "up": ind['wti']['change'] >= 0}
            ],
            "bullets": [
                f"WTI 선물 ${ind['wti']['price']}/배럴 - 에너지 원가 압박 경감",
                "유가 안정세로 헤드라인 인플레이션 자극 제한",
            ],
            "detail": "유가 안정은 제조업 마진을 방어해주는 핵심 요인입니다.",
        },
    }

    # 5. 3주 캘린더 생성
    data["calendar_3w"] = {
        "w1": {
            "title": "이번 주 (09/07 ~ 09/13)",
            "macro": [
                {"date": "09-10 (목) 21:30", "event": "미 8월 생산자물가지수 (PPI)", "impact": "HIGH"},
                {"date": "09-11 (금) 21:30", "event": "미 8월 소비자물가지수 (CPI)", "impact": "CRITICAL"},
                {"date": "09-11 (금) 21:30", "event": "신규 실업수당 청구건수", "impact": "MED"},
            ],
            "earnings": [
                {"date": "09-10 (목) 장후", "ticker": "ORCL", "name": "오라클 (클라우드/AI)", "time": "장마감 후"},
                {"date": "09-11 (금) 장후", "ticker": "ADBE", "name": "어도비 (생성형 AI)", "time": "장마감 후"},
            ],
        },
        "w2": {
            "title": "다음 주 (09/14 ~ 09/20) [FOMC 주간]",
            "macro": [
                {"date": "09-15 (화) 21:30", "event": "미 8월 소매판매 지표", "impact": "HIGH"},
                {"date": "09-16 (수) 03:00", "event": "FOMC 기준금리 결정 & 파월 기자회견", "impact": "CRITICAL"},
                {"date": "09-18 (금) 장마감", "event": "미 선물·옵션 동시만기일 (네 마녀의 날)", "impact": "HIGH"},
            ],
            "earnings": [
                {"date": "09-17 (목) 장후", "ticker": "FDX", "name": "페덱스 (물동량 선행)", "time": "장마감 후"},
            ],
        },
        "w3": {
            "title": "다다음 주 (09/21 ~ 09/27)",
            "macro": [
                {"date": "09-24 (목) 21:30", "event": "미 2분기 GDP 확정치", "impact": "HIGH"},
                {"date": "09-25 (금) 21:30", "event": "미 8월 근원 PCE 물가지수 (연준 선호)", "impact": "CRITICAL"},
            ],
            "earnings": [
                {"date": "09-23 (수) 장후", "ticker": "MU", "name": "마이크론 (HBM 메모리)", "time": "장마감 후"},
                {"date": "09-24 (목) 장후", "ticker": "COST", "name": "코스트코 (미 소비지표)", "time": "장마감 후"},
            ],
        },
    }

    # 6. 마스터 풀 파일(humanities_pool.json)에서 1일 1주제 순환 추출
    data["humanities"] = load_humanities_from_pool()

    # 7. 실시간 RSS 피드 수집
    data["feeds"] = {
        "fed": fetch_rss("https://www.federalreserve.gov/feeds/speeches.xml", 4, "[연설]") or [],
        "global": fetch_rss("https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", 5) or [],
        "tech": (fetch_rss("https://www.thelec.kr/rss/allArticle.xml", 3, "[디일렉]") + fetch_rss("https://rss.etnews.com/Section902.xml", 3, "[전자신문]"))[:5],
        "domestic": fetch_rss("https://news.einfomax.co.kr/rss/S1N16.xml", 5) or [],
    }

    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 기존 고전 철학을 대체하고 3대 실시간 트렌드 데이터 주입
    data["trends"] = {
        "naver_sisa": fetch_naver_sisa_weekly(),
        "namu_rank": fetch_namu_rankings(),
        "youtube_popular": fetch_youtube_popular_kr()
    }    
    
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("마스터 풀 연동 및 시장 데이터 동기화 완료!")


if __name__ == "__main__":
    main()
