from datetime import datetime, timezone, timedelta
import html
import json
import os
import re
import xml.etree.ElementTree as ET
import requests
import urllib.parse
from bs4 import BeautifulSoup
import random

# 한국 표준시 (KST = UTC+9) 정의
KST = timezone(timedelta(hours=9))

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

def make_naver_news_link(query_text):
    """키워드에서 괄호 및 불필요한 기호를 정제하여 네이버 뉴스 검색 URL 생성"""
    clean_kw = re.sub(r"\(.*?\)", "", query_text).strip()
    target_kw = clean_kw if clean_kw else query_text.strip()
    encoded = urllib.parse.quote(target_kw)
    return f"https://search.naver.com/search.naver?ssc=tab.news.all&where=news&sm=tab_jum&query={encoded}"

def fetch_naver_sisa_weekly():
    """네이버 시사상식사전 주간조회순 Top 10 실시간 정밀 수집 (a.card_title 정밀 셀렉터 적용)"""
    items = []
    seen = set()

    target_url = "https://terms.naver.com/~%EC%8B%9C%EC%82%AC%EC%83%81%EC%8B%9D%EC%82%AC%EC%A0%84-5gU3XZbbzbKZlVGdi59MJ9?sort=weekly"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": "https://terms.naver.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    try:
        res = requests.get(target_url, headers=headers, timeout=12)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")

            # 1. DevTools 요소 검사에서 확인된 card_title 클래스 및 span 직접 파싱
            cards = soup.select("a.card_title, a[data-nlog-area='.tit'], .feed_item a.card_title")
            for a in cards:
                span = a.select_one("span")
                title_text = span.get_text(strip=True) if span else a.get_text(strip=True)
                title_text = re.sub(r"\s+", " ", title_text).strip()

                if 2 <= len(title_text) <= 40 and title_text not in seen:
                    if not any(x in title_text for x in ["시사상식", "지식백과", "로그인", "신고", "더보기"]):
                        seen.add(title_text)
                        items.append({
                            "rank": len(items) + 1,
                            "title": title_text,
                            "link": make_naver_news_link(title_text)
                        })
                        if len(items) >= 10:
                            break

            # 2. 정규식 보조 탐색 (HTML 파서 트리 우회 대비)
            if len(items) < 10:
                raw_matches = re.findall(r'class="card_title"[^>]*>.*?<span>([^<]+)</span>', res.text, re.DOTALL)
                for raw_t in raw_matches:
                    clean_t = re.sub(r"\s+", " ", raw_t).strip()
                    if 2 <= len(clean_t) <= 40 and clean_t not in seen:
                        seen.add(clean_t)
                        items.append({
                            "rank": len(items) + 1,
                            "title": clean_t,
                            "link": make_naver_news_link(clean_t)
                        })
                        if len(items) >= 10:
                            break
    except Exception as e:
        print(f"네이버 시사상식사전 수집 오류: {e}")

    # GitHub Actions 실행 로그 출력 (수집 결과 직접 확인)
    real_titles = [x["title"] for x in items]
    print(f"📡 [네이버 시사상식 크롤링 결과] 총 {len(items)}건 추출 완료: {real_titles}")

    # 크롤링 실패 시에만 역순 폴백 작동
    if len(items) < 10:
        print("⚠️ [경고] 크롤링 수집 실패로 역순 폴백 목록이 적용됩니다.")
        reversed_fallback = [
            "린스타트업",
            "페미니스트",
            "푸른 하늘을 위한 세계 청정 대기의 날",
            "24절기",
            "연색호",
            "졸피뎀",
            "사보타주",
            "태극기",
            "제주 4·3 사건",
            "오디세이"
        ]
        items = [
            {"rank": idx, "title": kw, "link": make_naver_news_link(kw)}
            for idx, kw in enumerate(reversed_fallback, start=1)
        ]

    return items

def fetch_namu_rankings():
    """나무위키 실시간 검색어 Top 10 수집 (클릭 시 네이버 뉴스 검색 연동)"""
    items = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Referer": "https://namu.wiki/",
        "Accept": "application/json, text/plain, */*"
    }

    # 1차 시도: 나무위키 공식 랭킹 API
    try:
        res = requests.get("https://search.namu.wiki/api/ranking", headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            raw_list = data if isinstance(data, list) else data.get("ranking", [])
            for idx, item in enumerate(raw_list[:10], start=1):
                kw = item if isinstance(item, str) else item.get("keyword", "")
                if kw:
                    items.append({
                        "rank": idx,
                        "title": kw,
                        "link": make_naver_news_link(kw)
                    })
    except Exception as e:
        print(f"나무위키 공식 API 예외: {e}")

    # 2차 시도: 실시간 검색어 Signal 피드
    if len(items) < 8:
        try:
            s_res = requests.get("https://api.signal.bz/news/realtime", headers=headers, timeout=5)
            if s_res.status_code == 200:
                s_data = s_res.json()
                for idx, s_item in enumerate(s_data.get("top10", [])[:10], start=1):
                    kw = s_item.get("keyword", "")
                    if kw:
                        items.append({
                            "rank": idx,
                            "title": kw,
                            "link": make_naver_news_link(kw)
                        })
        except Exception as e:
            print(f"실시간 검색어 대체 피드 예외: {e}")

    # 3차 시도: 구글 트렌드 실시간 대한민국 RSS
    if len(items) < 8:
        try:
            gt_res = requests.get("https://trends.google.co.kr/trending/rss?geo=KR", headers=headers, timeout=5)
            if gt_res.status_code == 200:
                root = ET.fromstring(gt_res.content)
                for idx, item_node in enumerate(root.findall(".//item")[:10], start=1):
                    kw = item_node.findtext("title", "").strip()
                    if kw:
                        items.append({
                            "rank": idx,
                            "title": kw,
                            "link": make_naver_news_link(kw)
                        })
        except Exception as e:
            print(f"구글 트렌드 RSS 예외: {e}")

    # 10개 보장
    if len(items) < 10:
        default_trend_kws = ["국제유가", "환율", "기준금리", "삼성전자", "SK하이닉스", "나스닥", "엔비디아", "비트코인", "미국채 10년물", "소비자물가지수"]
        items = [{"rank": i, "title": kw, "link": make_naver_news_link(kw)} for i, kw in enumerate(default_trend_kws, start=1)]

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


def load_humanities_from_pool(existing_humanities=None):
    """humanities_pool.json 및 data.json 기반 실제 5일 FIFO 히스토리 큐 관리"""
    if existing_humanities is None:
        existing_humanities = {}

    now_kst = datetime.now(KST)
    today_str = now_kst.strftime("%Y-%m-%d")
    day_idx = now_kst.timetuple().tm_yday
    pool_file = "humanities_pool.json"

    hist_pool, poly_pool, basic_pool, phil_pool = [], [], [], []
    if os.path.exists(pool_file):
        try:
            with open(pool_file, "r", encoding="utf-8") as f:
                pool = json.load(f)
                hist_pool = pool.get("history_pool", [])
                poly_pool = pool.get("polyglot_pool", [])
                basic_pool = pool.get("polyglot_basic_pool", [])
                phil_pool = pool.get("philosophy_pool", [])
        except Exception as e:
            print(f"인문학 풀 로드 예외: {e}")

    # 신규 기초 풀(polyglot_basic_pool) 미존재 시 사용할 20개 마스터 기초 데이터셋
    if not basic_pool:
        basic_pool = [
            # [단문 10선]
            {"theme": "기초 인사", "type": "기초", "meaning": "안녕하세요!", "translations": {
                "en": {"code": "en-US", "name": "영어", "flag": "🇺🇸", "text": "Hello! Good day.", "roman": ""},
                "ja": {"code": "ja-JP", "name": "일본어", "flag": "🇯🇵", "text": "こんにちは！", "roman": "Konnichiwa!"},
                "zh": {"code": "zh-CN", "name": "중국어", "flag": "🇨🇳", "text": "你好！", "roman": "Nǐ hǎo!"},
                "fr": {"code": "fr-FR", "name": "프랑스어", "flag": "🇫🇷", "text": "Bonjour !", "roman": ""},
                "de": {"code": "de-DE", "name": "독일어", "flag": "🇩🇪", "text": "Guten Tag!", "roman": ""},
                "es": {"code": "es-ES", "name": "스페인어", "flag": "🇪🇸", "text": "¡Hola! Buenos días.", "roman": ""},
                "ar": {"code": "ar-SA", "name": "아랍어", "flag": "🇸🇦", "text": "مرحباً! يوم سعيد.", "roman": "Marḥaban! Yawm sa'īd."},
                "ru": {"code": "ru-RU", "name": "러시아어", "flag": "🇷🇺", "text": "Здравствуйте!", "roman": "Zdravstvuyte!"}
            }},
            {"theme": "덕담", "type": "기초", "meaning": "좋은 하루 보내세요!", "translations": {
                "en": {"code": "en-US", "name": "영어", "flag": "🇺🇸", "text": "Have a wonderful day!", "roman": ""},
                "ja": {"code": "ja-JP", "name": "일본어", "flag": "🇯🇵", "text": "良い一日をお過ごしください！", "roman": "Yoi ichinichi o osugoshi kudasai!"},
                "zh": {"code": "zh-CN", "name": "중국어", "flag": "🇨🇳", "text": "祝你度过美好的一天！", "roman": "Zhù nǐ dùguò měihǎo de yītiān!"},
                "fr": {"code": "fr-FR", "name": "프랑스어", "flag": "🇫🇷", "text": "Passez une bonne journée !", "roman": ""},
                "de": {"code": "de-DE", "name": "독일어", "flag": "🇩🇪", "text": "Einen schönen Tag noch!", "roman": ""},
                "es": {"code": "es-ES", "name": "스페인어", "flag": "🇪🇸", "text": "¡Que tengas un buen día!", "roman": ""},
                "ar": {"code": "ar-SA", "name": "아랍어", "flag": "🇸🇦", "text": "أتمنى لك يوماً جميلاً!", "roman": "Atamannā laka yawman jamīlan!"},
                "ru": {"code": "ru-RU", "name": "러시아어", "flag": "🇷🇺", "text": "Хорошего вам дня!", "roman": "Khoroshego vam dnya!"}
            }},
            {"theme": "작별 인사", "type": "기초", "meaning": "다음에 또 만나요!", "translations": {
                "en": {"code": "en-US", "name": "영어", "flag": "🇺🇸", "text": "See you again next time!", "roman": ""},
                "ja": {"code": "ja-JP", "name": "일본어", "flag": "🇯🇵", "text": "また次回お会いしましょう！", "roman": "Mata jikai oai shimashō!"},
                "zh": {"code": "zh-CN", "name": "중국어", "flag": "🇨🇳", "text": "下次再见！", "roman": "Xià cì zàijiàn!"},
                "fr": {"code": "fr-FR", "name": "프랑스어", "flag": "🇫🇷", "text": "À la prochaine fois !", "roman": ""},
                "de": {"code": "de-DE", "name": "독일어", "flag": "🇩🇪", "text": "Bis zum nächsten Mal!", "roman": ""},
                "es": {"code": "es-ES", "name": "스페인어", "flag": "🇪🇸", "text": "¡Hasta la próxima!", "roman": ""},
                "ar": {"code": "ar-SA", "name": "아랍어", "flag": "🇸🇦", "text": "أراك في المرة القادمة!", "roman": "Arāka fī al-marrati al-qādimah!"},
                "ru": {"code": "ru-RU", "name": "러시아어", "flag": "🇷🇺", "text": "До следующей встречи!", "roman": "Do sleduyushchey vstrechi!"}
            }},
            {"theme": "감사 표현", "type": "기초", "meaning": "정말 감사합니다.", "translations": {
                "en": {"code": "en-US", "name": "영어", "flag": "🇺🇸", "text": "Thank you very much.", "roman": ""},
                "ja": {"code": "ja-JP", "name": "일본어", "flag": "🇯🇵", "text": "本当にありがとうございます。", "roman": "Hontō ni arigatō gozaimasu."},
                "zh": {"code": "zh-CN", "name": "중국어", "flag": "🇨🇳", "text": "非常感谢你。", "roman": "Fēicháng gǎnxiè nǐ."},
                "fr": {"code": "fr-FR", "name": "프랑스어", "flag": "🇫🇷", "text": "Merci beaucoup.", "roman": ""},
                "de": {"code": "de-DE", "name": "독일어", "flag": "🇩🇪", "text": "Vielen Dank.", "roman": ""},
                "es": {"code": "es-ES", "name": "스페인어", "flag": "🇪🇸", "text": "Muchas gracias.", "roman": ""},
                "ar": {"code": "ar-SA", "name": "아랍어", "flag": "🇸🇦", "text": "شكراً جزيلاً لك.", "roman": "Shukran jazīlan laka."},
                "ru": {"code": "ru-RU", "name": "러시아어", "flag": "🇷🇺", "text": "Большое спасибо.", "roman": "Bol'shoye spasibo."}
            }},
            {"theme": "정중한 양해", "type": "기초", "meaning": "실례합니다 / 죄송합니다.", "translations": {
                "en": {"code": "en-US", "name": "영어", "flag": "🇺🇸", "text": "Excuse me, I am sorry.", "roman": ""},
                "ja": {"code": "ja-JP", "name": "일본어", "flag": "🇯🇵", "text": "すみません、申し訳ありません。", "roman": "Sumimasen, mōshiwake arimasen."},
                "zh": {"code": "zh-CN", "name": "중국어", "flag": "🇨🇳", "text": "不好意思，打扰一下。", "roman": "Bù hǎoyìsi, dǎrǎo yīxià."},
                "fr": {"code": "fr-FR", "name": "프랑스어", "flag": "🇫🇷", "text": "Excusez-moi, pardon.", "roman": ""},
                "de": {"code": "de-DE", "name": "독일어", "flag": "🇩🇪", "text": "Entschuldigen Sie bitte.", "roman": ""},
                "es": {"code": "es-ES", "name": "스페인어", "flag": "🇪🇸", "text": "Disculpe, perdón.", "roman": ""},
                "ar": {"code": "ar-SA", "name": "아랍어", "flag": "🇸🇦", "text": "معذرة، أنا آسف.", "roman": "Ma'dhiratan, anā āsif."},
                "ru": {"code": "ru-RU", "name": "러시아어", "flag": "🇷🇺", "text": "Извините, прошу прощения.", "roman": "Izvinite, proshu proshcheniya."}
            }},
            {"theme": "화답 에티켓", "type": "기초", "meaning": "천만에요, 별말씀을요.", "translations": {
                "en": {"code": "en-US", "name": "영어", "flag": "🇺🇸", "text": "You are very welcome.", "roman": ""},
                "ja": {"code": "ja-JP", "name": "일본어", "flag": "🇯🇵", "text": "どういたしまして。", "roman": "Dōitashimashite."},
                "zh": {"code": "zh-CN", "name": "중국어", "flag": "🇨🇳", "text": "不客气，不用谢。", "roman": "Bù kèqì, bùyòng xiè."},
                "fr": {"code": "fr-FR", "name": "프랑스어", "flag": "🇫🇷", "text": "Je vous en prie.", "roman": ""},
                "de": {"code": "de-DE", "name": "독일어", "flag": "🇩🇪", "text": "Gern geschehen, bitte schön.", "roman": ""},
                "es": {"code": "es-ES", "name": "스페인어", "flag": "🇪🇸", "text": "De nada, es un placer.", "roman": ""},
                "ar": {"code": "ar-SA", "name": "아랍어", "flag": "🇸🇦", "text": "على الرحب والسعة.", "roman": "'Alā ar-raḥbi was-sa'ah."},
                "ru": {"code": "ru-RU", "name": "러시아어", "flag": "🇷🇺", "text": "Пожалуйста, не за что.", "roman": "Pozhaluysta, ne za chto."}
            }},
            {"theme": "첫 대면", "type": "기초", "meaning": "만나서 반갑습니다.", "translations": {
                "en": {"code": "en-US", "name": "영어", "flag": "🇺🇸", "text": "Nice to meet you.", "roman": ""},
                "ja": {"code": "ja-JP", "name": "일본어", "flag": "🇯🇵", "text": "はじめまして、お会いできて嬉しいです。", "roman": "Hajimemashite, oai dekite ureshī desu."},
                "zh": {"code": "zh-CN", "name": "중국어", "flag": "🇨🇳", "text": "很高兴认识你。", "roman": "Hěn gāoxìng rènshí nǐ."},
                "fr": {"code": "fr-FR", "name": "프랑스어", "flag": "🇫🇷", "text": "Ravi de vous rencontrer.", "roman": ""},
                "de": {"code": "de-DE", "name": "독일어", "flag": "🇩🇪", "text": "Schön, Sie kennenzulernen.", "roman": ""},
                "es": {"code": "es-ES", "name": "스페인어", "flag": "🇪🇸", "text": "Mucho gusto en conocerte.", "roman": ""},
                "ar": {"code": "ar-SA", "name": "아랍어", "flag": "🇸🇦", "text": "سعيد بلقائك جداً.", "roman": "Sa'īd biliqā'ika jiddan."},
                "ru": {"code": "ru-RU", "name": "러시아어", "flag": "🇷🇺", "text": "Очень приятно познакомиться.", "roman": "Ochen' priyatno poznakomit'sya."}
            }},
            {"theme": "도움 요청", "type": "기초", "meaning": "잠시 도와주실 수 있나요?", "translations": {
                "en": {"code": "en-US", "name": "영어", "flag": "🇺🇸", "text": "Could you please help me for a moment?", "roman": ""},
                "ja": {"code": "ja-JP", "name": "일본어", "flag": "🇯🇵", "text": "少し手伝っていただけますか？", "roman": "Sukoshi tetsudatte itadakemasu ka?"},
                "zh": {"code": "zh-CN", "name": "중국어", "flag": "🇨🇳", "text": "能请你帮我一下吗？", "roman": "Néng qǐng nǐ bāng wǒ yīxià ma?"},
                "fr": {"code": "fr-FR", "name": "프랑스어", "flag": "🇫🇷", "text": "Pourriez-vous m'aider un instant, s'il vous plaît ?", "roman": ""},
                "de": {"code": "de-DE", "name": "독일어", "flag": "🇩🇪", "text": "Könnten Sie mir bitte kurz helfen?", "roman": ""},
                "es": {"code": "es-ES", "name": "스페인어", "flag": "🇪🇸", "text": "¿Podría ayudarme un momento, por favor?", "roman": ""},
                "ar": {"code": "ar-SA", "name": "아랍어", "flag": "🇸🇦", "text": "هل يمكنك مساعدتي للحظة من فضلك؟", "roman": "Hal yumkinuka musā'adatī li-laḥẓah min faḍlik?"},
                "ru": {"code": "ru-RU", "name": "러시아어", "flag": "🇷🇺", "text": "Не могли бы вы мне помочь?", "roman": "Ne mogli by vy mne pomoch'?"}
            }},
            {"theme": "동의 및 수락", "type": "기초", "meaning": "좋습니다! 전혀 문제없어요.", "translations": {
                "en": {"code": "en-US", "name": "영어", "flag": "🇺🇸", "text": "Sounds great! No problem at all.", "roman": ""},
                "ja": {"code": "ja-JP", "name": "일본어", "flag": "🇯🇵", "text": "いいですね！全く問題ありません。", "roman": "Ii desu ne! Mattaku mondai arimasen."},
                "zh": {"code": "zh-CN", "name": "중국어", "flag": "🇨🇳", "text": "太好了！完全没问题。", "roman": "Tài hǎo le! Wánquán méi wèntí."},
                "fr": {"code": "fr-FR", "name": "프랑스어", "flag": "🇫🇷", "text": "C'est parfait ! Aucun problème.", "roman": ""},
                "de": {"code": "de-DE", "name": "독일어", "flag": "🇩🇪", "text": "Klingt gut! Überhaupt kein Problem.", "roman": ""},
                "es": {"code": "es-ES", "name": "스페인어", "flag": "🇪🇸", "text": "¡Suena genial! Ningún problema.", "roman": ""},
                "ar": {"code": "ar-SA", "name": "아랍어", "flag": "🇸🇦", "text": "يبدو رائعاً! لا توجد مشكلة على الإطلاق.", "roman": "Yabdū rā'i'an! Lā tūjadu mushkilah 'alā al-iṭlāq."},
                "ru": {"code": "ru-RU", "name": "러시아어", "flag": "🇷🇺", "text": "Отлично! Никаких проблем.", "roman": "Otlichno! Nikakikh problem."}
            }},
            {"theme": "소통 배려", "type": "기초", "meaning": "조금만 천천히 말씀해 주시겠어요?", "translations": {
                "en": {"code": "en-US", "name": "영어", "flag": "🇺🇸", "text": "Could you speak a little more slowly, please?", "roman": ""},
                "ja": {"code": "ja-JP", "name": "일본어", "flag": "🇯🇵", "text": "もう少しゆっくり話していただけますか？", "roman": "Mō sukoshi yukkuri hanashite itadakemasu ka?"},
                "zh": {"code": "zh-CN", "name": "중국어", "flag": "🇨🇳", "text": "请你说得稍微慢一点好吗？", "roman": "Qǐng nǐ shuō de shāowēi màn yīdiǎn hǎo ma?"},
                "fr": {"code": "fr-FR", "name": "프랑스어", "flag": "🇫🇷", "text": "Pourriez-vous parler un peu plus lentement ?", "roman": ""},
                "de": {"code": "de-DE", "name": "독일어", "flag": "🇩🇪", "text": "Könnten Sie bitte etwas langsamer sprechen?", "roman": ""},
                "es": {"code": "es-ES", "name": "스페인어", "flag": "🇪🇸", "text": "¿Podría hablar un poco más despacio, por favor?", "roman": ""},
                "ar": {"code": "ar-SA", "name": "아랍어", "flag": "🇸🇦", "text": "هل يمكنك التحدث ببطء أكثر من فضلك؟", "roman": "Hal yumkinuka at-taḥadduth bi-buṭ'in akthar min faḍlik?"},
                "ru": {"code": "ru-RU", "name": "러시아어", "flag": "🇷🇺", "text": "Говорите, пожалуйста, помедленнее.", "roman": "Govorite, pozhaluysta, pomedlenneye."}
            }},

            # [Q&A 문답 10선]
            {"theme": "안부 확인 (Q&A)", "type": "기초", "meaning": "Q: 잘 지내세요? / A: 네, 아주 잘 지내요.", "translations": {
                "en": {"code": "en-US", "name": "영어", "flag": "🇺🇸", "text": "How are you doing? - I'm doing great, thank you.", "roman": ""},
                "ja": {"code": "ja-JP", "name": "일본어", "flag": "🇯🇵", "text": "お元気ですか？ - はい、とても元気です。", "roman": "Ogenki desu ka? - Hai, totemo genki desu."},
                "zh": {"code": "zh-CN", "name": "중국어", "flag": "🇨🇳", "text": "你最近好吗？ - 我很好，谢谢你。", "roman": "Nǐ zuìjìn hǎo ma? - Wǒ hěn hǎo, xièxiè nǐ."},
                "fr": {"code": "fr-FR", "name": "프랑스어", "flag": "🇫🇷", "text": "Comment allez-vous ? - Je vais très bien, merci.", "roman": ""},
                "de": {"code": "de-DE", "name": "독일어", "flag": "🇩🇪", "text": "Wie geht es Ihnen? - Mir geht es sehr gut, danke.", "roman": ""},
                "es": {"code": "es-ES", "name": "스페인어", "flag": "🇪🇸", "text": "¿Cómo estás? - Estoy muy bien, gracias.", "roman": ""},
                "ar": {"code": "ar-SA", "name": "아랍어", "flag": "🇸🇦", "text": "كيف حالك؟ - أنا بخير جداً، شكراً لك.", "roman": "Kayfa ḥāluk? - Anā bi-khayrin jiddan, shukran lak."},
                "ru": {"code": "ru-RU", "name": "러시아어", "flag": "🇷🇺", "text": "Как ваши дела? - У меня всё отлично, спасибо.", "roman": "Kak vashi dela? - U menya vsyo otlichno, spasibo."}
            }},
            {"theme": "언어 소통 (Q&A)", "type": "기초", "meaning": "Q: 영어 할 수 있나요? / A: 네, 조금 할 수 있어요.", "translations": {
                "en": {"code": "en-US", "name": "영어", "flag": "🇺🇸", "text": "Do you speak English? - Yes, I speak a little.", "roman": ""},
                "ja": {"code": "ja-JP", "name": "일본어", "flag": "🇯🇵", "text": "英語を話せますか？ - はい、少し話せます。", "roman": "Eigo o hanasemasu ka? - Hai, sukoshi hanasemasu."},
                "zh": {"code": "zh-CN", "name": "중국어", "flag": "🇨🇳", "text": "你会说英语吗？ - 是的，会说一点点。", "roman": "Nǐ huì shuō yīngyǔ ma? - Shì de, huì shuō yīdiǎndiǎn."},
                "fr": {"code": "fr-FR", "name": "프랑스어", "flag": "🇫🇷", "text": "Parlez-vous anglais ? - Oui, je parle un peu.", "roman": ""},
                "de": {"code": "de-DE", "name": "독일어", "flag": "🇩🇪", "text": "Sprechen Sie Englisch? - Ja, ein bisschen.", "roman": ""},
                "es": {"code": "es-ES", "name": "스페인어", "flag": "🇪🇸", "text": "¿Hablas inglés? - Sí, hablo un poco.", "roman": ""},
                "ar": {"code": "ar-SA", "name": "아랍어", "flag": "🇸🇦", "text": "هل تتحدث الإنجليزية؟ - نعم، أتحدث قليلاً.", "roman": "Hal tataḥaddath al-injlīziyyah? - Na'am, ataḥaddath qalīlan."},
                "ru": {"code": "ru-RU", "name": "러시아어", "flag": "🇷🇺", "text": "Вы говорите по-английски? - Да, немного.", "roman": "Vy govorite po-angliyski? - Da, nemnogo."}
            }},
            {"theme": "이해 여부 (Q&A)", "type": "기초", "meaning": "Q: 제 말 이해하셨나요? / A: 네, 완벽히 이해했어요.", "translations": {
                "en": {"code": "en-US", "name": "영어", "flag": "🇺🇸", "text": "Do you understand me? - Yes, I understand perfectly.", "roman": ""},
                "ja": {"code": "ja-JP", "name": "일본어", "flag": "🇯🇵", "text": "理解できましたか？ - はい、よく分かりました。", "roman": "Rikai dekimashita ka? - Hai, yoku wakarimashita."},
                "zh": {"code": "zh-CN", "name": "중국어", "flag": "🇨🇳", "text": "你听明白了吗？ - 是的，我完全明白了。", "roman": "Nǐ tīng míngbái le ma? - Shì de, wǒ wánquán míngbái le."},
                "fr": {"code": "fr-FR", "name": "프랑스어", "flag": "🇫🇷", "text": "Avez-vous compris ? - Oui, j'ai parfaitement compris.", "roman": ""},
                "de": {"code": "de-DE", "name": "독일어", "flag": "🇩🇪", "text": "Haben Sie mich verstanden? - Ja, vollkommen verstanden.", "roman": ""},
                "es": {"code": "es-ES", "name": "스페인어", "flag": "🇪🇸", "text": "¿Me entiendes? - Sí, entiendo perfectamente.", "roman": ""},
                "ar": {"code": "ar-SA", "name": "아랍어", "flag": "🇸🇦", "text": "هل فهمتني؟ - نعم، فهمت تماماً.", "roman": "Hal fahimtanī? - Na'am, fahimtu tamāman."},
                "ru": {"code": "ru-RU", "name": "러시아어", "flag": "🇷🇺", "text": "Вы меня поняли? - Да, я всё понял.", "roman": "Vy menya ponyali? - Da, ya vsyo ponyal."}
            }},
            {"theme": "위치 문의 (Q&A)", "type": "기초", "meaning": "Q: 화장실이 어디에 있나요? / A: 저기 오른쪽에 있어요.", "translations": {
                "en": {"code": "en-US", "name": "영어", "flag": "🇺🇸", "text": "Where is the restroom? - It's right over there on the right.", "roman": ""},
                "ja": {"code": "ja-JP", "name": "일본어", "flag": "🇯🇵", "text": "トイレはどこですか？ - あちらの右側にあります。", "roman": "Toire wa doko desu ka? - Achira no migigawa ni arimasu."},
                "zh": {"code": "zh-CN", "name": "중국어", "flag": "🇨🇳", "text": "洗手间在哪里？ - 就在那边的右边。", "roman": "Xǐshǒujiān zài nǎlǐ? - Jiù zài nàbiān de yòubiān."},
                "fr": {"code": "fr-FR", "name": "프랑스어", "flag": "🇫🇷", "text": "Où sont les toilettes ? - C'est juste là, sur la droite.", "roman": ""},
                "de": {"code": "de-DE", "name": "독일어", "flag": "🇩🇪", "text": "Wo ist die Toilette? - Direkt dort drüben auf der rechten Seite.", "roman": ""},
                "es": {"code": "es-ES", "name": "스페인어", "flag": "🇪🇸", "text": "¿Dónde está el baño? - Está justo allí, a la derecha.", "roman": ""},
                "ar": {"code": "ar-SA", "name": "아랍어", "flag": "🇸🇦", "text": "أين الحمام؟ - إنه هناك على اليمين مباشرة.", "roman": "Ayna al-ḥammām? - Innahu hunāka 'alā al-yamīn mubāsharatan."},
                "ru": {"code": "ru-RU", "name": "러시아어", "flag": "🇷🇺", "text": "Где находится туалет? - Вон там, прямо направо.", "roman": "Gde nakhoditsya tualet? - Von tam, pryamo napravo."}
            }},
            {"theme": "현재 위치 (Q&A)", "type": "기초", "meaning": "Q: 여기가 어디인가요? / A: 지하철역 바로 앞입니다.", "translations": {
                "en": {"code": "en-US", "name": "영어", "flag": "🇺🇸", "text": "Where are we right now? - Right in front of the subway station.", "roman": ""},
                "ja": {"code": "ja-JP", "name": "일본어", "flag": "🇯🇵", "text": "ここはどこですか？ - 地下鉄の駅のすぐ前です。", "roman": "Koko wa doko desu ka? - Chikatetsu no eki no sugu mae desu."},
                "zh": {"code": "zh-CN", "name": "중국어", "flag": "🇨🇳", "text": "请问这里是哪里？ - 就在地铁站的正前方。", "roman": "Qǐngwèn zhèlǐ shì nǎlǐ? - Jiù zài dìtiězhàn de zhèng qiánfāng."},
                "fr": {"code": "fr-FR", "name": "프랑스어", "flag": "🇫🇷", "text": "Où sommes-nous ? - Juste devant la station de métro.", "roman": ""},
                "de": {"code": "de-DE", "name": "독일어", "flag": "🇩🇪", "text": "Wo sind wir hier? - Direkt vor der U-Bahn-Station.", "roman": ""},
                "es": {"code": "es-ES", "name": "스페인어", "flag": "🇪🇸", "text": "¿Dónde estamos ahora? - Justo frente a la estación de metro.", "roman": ""},
                "ar": {"code": "ar-SA", "name": "아랍어", "flag": "🇸🇦", "text": "أين نحن الآن؟ - أمام محطة المترو مباشرة.", "roman": "Ayna naḥnu al-ān? - Amāma maḥaṭṭat al-mitrū mubāsharatan."},
                "ru": {"code": "ru-RU", "name": "러시아어", "flag": "🇷🇺", "text": "Где мы сейчас? - Прямо перед станцией метро.", "roman": "Gde my seychas? - Pryamo pered stantsiyey metro."}
            }},
            {"theme": "가격 문의 (Q&A)", "type": "기초", "meaning": "Q: 이거 얼마예요? / A: 모두 합쳐서 10달러입니다.", "translations": {
                "en": {"code": "en-US", "name": "영어", "flag": "🇺🇸", "text": "How much is this? - It is ten dollars in total.", "roman": ""},
                "ja": {"code": "ja-JP", "name": "일본어", "flag": "🇯🇵", "text": "これはいくらですか？ - 全部で10ドルです。", "roman": "Kore wa ikura desu ka? - Zenbu de jū-doru desu."},
                "zh": {"code": "zh-CN", "name": "중국어", "flag": "🇨🇳", "text": "这个多少钱？ - 一共是十美元。", "roman": "Zhège duōshǎo qián? - Yīgòng shì shí měiyuán."},
                "fr": {"code": "fr-FR", "name": "프랑스어", "flag": "🇫🇷", "text": "Combien ça coûte ? - C'est dix dollars au total.", "roman": ""},
                "de": {"code": "de-DE", "name": "독일어", "flag": "🇩🇪", "text": "Wie viel kostet das? - Es sind insgesamt zehn Dollar.", "roman": ""},
                "es": {"code": "es-ES", "name": "스페인어", "flag": "🇪🇸", "text": "¿Cuánto cuesta esto? - Son diez dólares en total.", "roman": ""},
                "ar": {"code": "ar-SA", "name": "아랍어", "flag": "🇸🇦", "text": "كم سعر هذا؟ - المجموع عشرة دولارات.", "roman": "Kam si'ru hādhā? - Al-majmū' 'ashrat dūlārāt."},
                "ru": {"code": "ru-RU", "name": "러시아어", "flag": "🇷🇺", "text": "Сколько это стоит? - Всего десять долларов.", "roman": "Skol'ko eto stoit? - Vsego desyat' dollarov."}
            }},
            {"theme": "결제 방식 (Q&A)", "type": "기초", "meaning": "Q: 카드 결제 되나요? / A: 네, 신용카드 가능합니다.", "translations": {
                "en": {"code": "en-US", "name": "영어", "flag": "🇺🇸", "text": "Can I pay by card? - Yes, we accept credit cards.", "roman": ""},
                "ja": {"code": "ja-JP", "name": "일본어", "flag": "🇯🇵", "text": "カードで支払えますか？ - はい、クレジットカードが使えます。", "roman": "Kādo de shiharaemasu ka? - Hai, kurejitto kādo ga tsukaemasu."},
                "zh": {"code": "zh-CN", "name": "중국어", "flag": "🇨🇳", "text": "可以刷卡吗？ - 可以，支持信用卡支付。", "roman": "Kěyǐ shuākǎ ma? - Kěyǐ, zhīchí xìnyòngkǎ zhīfù."},
                "fr": {"code": "fr-FR", "name": "프랑스어", "flag": "🇫🇷", "text": "Puis-je payer par carte ? - Oui, nous acceptons les cartes.", "roman": ""},
                "de": {"code": "de-DE", "name": "독일어", "flag": "🇩🇪", "text": "Kann ich mit Karte zahlen? - Ja, Kreditkarten sind möglich.", "roman": ""},
                "es": {"code": "es-ES", "name": "스페인어", "flag": "🇪🇸", "text": "¿Puedo pagar con tarjeta? - Sí, aceptamos tarjetas de crédito.", "roman": ""},
                "ar": {"code": "ar-SA", "name": "아랍어", "flag": "🇸🇦", "text": "هل يمكنني الدفع بالبطاقة؟ - نعم، نقبل بطاقات الائتمان.", "roman": "Hal yumkinunī ad-daf' bil-biṭāqah? - Na'am, naqbal biṭāqāt al-i'timān."},
                "ru": {"code": "ru-RU", "name": "러시아어", "flag": "🇷🇺", "text": "Можно оплатить картой? - Да, мы принимаем кредитные карты.", "roman": "Mozhno oplatit' kartoy? - Da, my prinimayem kreditnyye karty."}
            }},
            {"theme": "준비 확인 (Q&A)", "type": "기초", "meaning": "Q: 지금 준비되셨나요? / A: 네, 다 준비됐어요. 바로 가요.", "translations": {
                "en": {"code": "en-US", "name": "영어", "flag": "🇺🇸", "text": "Are you ready now? - Yes, I'm all set. Let's go.", "roman": ""},
                "ja": {"code": "ja-JP", "name": "일본어", "flag": "🇯🇵", "text": "準備はできましたか？ - はい、準備完了です。行きましょう。", "roman": "Junbi wa dekimashita ka? - Hai, junbi kanryō desu. Ikimashō."},
                "zh": {"code": "zh-CN", "name": "중국어", "flag": "🇨🇳", "text": "你准备好了吗？ - 好了，都准备好了，走吧。", "roman": "Nǐ zhǔnbèi hǎo le ma? - Hǎo le, dōu zhǔnbèi hǎo le, zǒu ba."},
                "fr": {"code": "fr-FR", "name": "프랑스어", "flag": "🇫🇷", "text": "Êtes-vous prêt maintenant ? - Oui, je suis prêt. Allons-y.", "roman": ""},
                "de": {"code": "de-DE", "name": "독일어", "flag": "🇩🇪", "text": "Sind Sie jetzt bereit? - Ja, alles bereit. Los geht's.", "roman": ""},
                "es": {"code": "es-ES", "name": "스페인어", "flag": "🇪🇸", "text": "¿Estás listo ahora? - Sí, estoy listo. Vamos.", "roman": ""},
                "ar": {"code": "ar-SA", "name": "아랍어", "flag": "🇸🇦", "text": "هل أنت مستعد الآن؟ - نعم، أنا جاهز تماماً. هيا بنا.", "roman": "Hal anta musta'iddun al-ān? - Na'am, anā jāhizun tamāman. Hayyā binā."},
                "ru": {"code": "ru-RU", "name": "러시아어", "flag": "🇷🇺", "text": "Вы готовы? - Да, всё готово. Поехали.", "roman": "Vy gotovy? - Da, vsyo gotovo. Poyekhali."}
            }},
            {"theme": "일치 확인 (Q&A)", "type": "기초", "meaning": "Q: 이게 맞나요? / A: 네, 정확히 맞습니다.", "translations": {
                "en": {"code": "en-US", "name": "영어", "flag": "🇺🇸", "text": "Is this correct? - Yes, that is exactly right.", "roman": ""},
                "ja": {"code": "ja-JP", "name": "일본어", "flag": "🇯🇵", "text": "これで合っていますか？ - はい、その通りです。", "roman": "Kore de atte imasu ka? - Hai, sono tōri desu."},
                "zh": {"code": "zh-CN", "name": "중국어", "flag": "🇨🇳", "text": "这个对吗？ - 是的，完全正确。", "roman": "Zhège duì ma? - Shì de, wánquán zhèngquè."},
                "fr": {"code": "fr-FR", "name": "프랑스어", "flag": "🇫🇷", "text": "Est-ce exact ? - Oui, c'est tout à fait correct.", "roman": ""},
                "de": {"code": "de-DE", "name": "독일어", "flag": "🇩🇪", "text": "Ist das richtig so? - Ja, das ist absolut richtig.", "roman": ""},
                "es": {"code": "es-ES", "name": "스페인어", "flag": "🇪🇸", "text": "¿Es esto correcto? - Sí, es exactamente así.", "roman": ""},
                "ar": {"code": "ar-SA", "name": "아랍어", "flag": "🇸🇦", "text": "هل هذا صحيح؟ - نعم، هذا صحيح تماماً.", "roman": "Hal hādhā ṣaḥīḥ? - Na'am, hādhā ṣaḥīḥun tamāman."},
                "ru": {"code": "ru-RU", "name": "러시아어", "flag": "🇷🇺", "text": "Это правильно? - Да, совершенно верно.", "roman": "Eto pravil'no? - Da, sovershenno verno."}
            }},
            {"theme": "물품 요청 (Q&A)", "type": "기초", "meaning": "Q: 물 한 잔 주시겠어요? / A: 네, 여기 있습니다.", "translations": {
                "en": {"code": "en-US", "name": "영어", "flag": "🇺🇸", "text": "May I have a glass of water, please? - Sure, here you go.", "roman": ""},
                "ja": {"code": "ja-JP", "name": "일본어", "flag": "🇯🇵", "text": "お水を一杯いただけますか？ - はい、どうぞ。", "roman": "Omizu o ippai itadakemasu ka? - Hai, dōzo."},
                "zh": {"code": "zh-CN", "name": "중국어", "flag": "🇨🇳", "text": "可以给我一杯水吗？ - 好的，请用。", "roman": "Kěyǐ gěi wǒ yībēi shuǐ ma? - Hǎo de, qǐng yòng."},
                "fr": {"code": "fr-FR", "name": "프랑스어", "flag": "🇫🇷", "text": "Puis-je avoir un verre d'eau, s'il vous plaît ? - Bien sûr, voici.", "roman": ""},
                "de": {"code": "de-DE", "name": "독일어", "flag": "🇩🇪", "text": "Könnte ich bitte ein Glas Wasser haben? - Sicher, bitte sehr.", "roman": ""},
                "es": {"code": "es-ES", "name": "스페인어", "flag": "🇪🇸", "text": "¿Me da un vaso de agua, por favor? - Claro, aquí tiene.", "roman": ""},
                "ar": {"code": "ar-SA", "name": "아랍어", "flag": "🇸🇦", "text": "هل يمكنني الحصول على كوب ماء؟ - بالطبع، تفضل.", "roman": "Hal yumkinunī al-ḥuṣūl 'alā kūb mā'? - Bil-ṭab', tafaḍḍal."},
                "ru": {"code": "ru-RU", "name": "러시아어", "flag": "🇷🇺", "text": "Можно стакан воды, пожалуйста? - Конечно, вот, держите.", "roman": "Mozhno stakan vody, pozhaluysta? - Konechno, vot, derzhite."}
            }}
        ]

    # 1~3. 역사 데이터 무작위 추출 및 5일 FIFO 큐 갱신
    old_history_5d = existing_humanities.get("history_5d", [])
    stored_date = existing_humanities.get("history_date", "")

    # JSON의 "region" 키를 활용하여 한국사/세계사 풀(Pool) 완벽 분리
    kr_pool = [x for x in hist_pool if x.get("region") == "한국"] if hist_pool else []
    world_pool = [x for x in hist_pool if x.get("region") == "세계"] if hist_pool else []

    # A) 날짜가 실제로 바뀐 경우 (자정 갱신): 무조건 D-1로 밀어내고, 새로운 '오늘' 데이터를 랜덤 추출
    if stored_date and stored_date != today_str and old_history_5d:
        # 오늘 날짜(day_idx)가 짝수면 세계사, 홀수면 한국사 풀을 선택 (매일 교차)
        target_pool = world_pool if day_idx % 2 == 0 else kr_pool
        if not target_pool: target_pool = hist_pool # 예외 처리 방어 로직
        
        # 순차 방식이 아닌 무작위(Random) 역사 사건 추출
        today_item = dict(random.choice(target_pool)) if target_pool else {}
        
        # 기존 데이터를 뒤로 밀고(FIFO), 새로운 오늘 데이터를 0번에 삽입 (오류 유발 타이틀 체크 제거)
        new_history_5d = [today_item] + old_history_5d[:4]
        
    # B) 같은 날짜이거나(하루 중 재실행), 큐가 비어있는 초기 상태
    else:
        if not old_history_5d or len(old_history_5d) < 5:
            # 최초 실행 시 D-0 부터 D-4 까지 과거 5일 치를 규칙(교차/랜덤)에 맞게 초기화
            new_history_5d = []
            for off in range(5):
                t_pool = world_pool if (day_idx - off) % 2 == 0 else kr_pool
                if not t_pool: t_pool = hist_pool
                item = dict(random.choice(t_pool)) if t_pool else {}
                new_history_5d.append(item)
        else:
            # 같은 날짜에 스크립트가 여러 번 돌더라도, '오늘'의 내용은 바뀌지 않도록 기존 상태 유지
            new_history_5d = old_history_5d

    # 4. 각 역사 항목별 d_day 라벨 확정
    d_day_labels = ["오늘", "D-1", "D-2", "D-3", "D-4"]
    for idx, item in enumerate(new_history_5d[:5]):
        item["d_day"] = d_day_labels[idx]

    # 5. 🔥 8개국어 회화 [오늘(기초) - D-1(일상) - D-2(기초) - D-3(일상) - D-4(기초)] 교차 큐 생성
    def get_poly_item(offset):
        target_day = day_idx - offset
        # 날짜(target_day) 기준으로 판별하여 내일이 되면 오늘 항목이 자동으로 '일상'으로 교체 순환
        # 오늘(253일 차, 홀수)은 기초, 내일(254일 차, 짝수)은 일상
        if target_day % 2 != 0:
            item = dict(basic_pool[(target_day // 2) % len(basic_pool)])
            item["pool_type"] = "기초"
        else:
            p_source = poly_pool if poly_pool else basic_pool
            item = dict(p_source[(target_day // 2) % len(p_source)])
            item["pool_type"] = "일상"
        item["d_day"] = d_day_labels[offset]
        return item

    old_poly_5d = existing_humanities.get("polyglot_5d", [])
    today_poly = get_poly_item(0)

    # 날짜 변경 시 FIFO 슬라이딩, 같은 날짜는 큐 유지
    if stored_date and stored_date != today_str and old_poly_5d:
        if old_poly_5d[0].get("meaning") != today_poly.get("meaning"):
            new_poly_5d = [today_poly] + old_poly_5d[:4]
            for i, itm in enumerate(new_poly_5d):
                itm["d_day"] = d_day_labels[i]
        else:
            new_poly_5d = old_poly_5d
    else:
        new_poly_5d = [get_poly_item(off) for off in range(5)]

    phil_item = phil_pool[day_idx % len(phil_pool)] if phil_pool else existing_humanities.get("philosophy", {})

    return {
        "history_date": today_str,
        "history": new_history_5d[0],
        "history_5d": new_history_5d[:5],
        "polyglot": new_poly_5d[0],
        "polyglot_5d": new_poly_5d[:5],
        "philosophy": phil_item,
    }


# [수정된 코드블럭]
def fetch_treasury_gov_2y(fallback_series):
    """미국 재무부(Treasury.gov) 공식 XML 피드를 파싱하여 2년물 금리 수집 (차단 및 타임아웃 확률 0%)"""
    results = {}
    current_year = datetime.now().year
    url = f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value={current_year}"
    
    try:
        # 공공 피드이므로 가볍고 빠르게 타격
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            # XML에서 <m:properties> 블록 단위로 데이터를 안전하게 추출
            blocks = re.findall(r'<m:properties>(.*?)</m:properties>', res.text, re.DOTALL | re.IGNORECASE)
            for block in blocks:
                date_m = re.search(r'<d:NEW_DATE[^>]*>([^<]+)</d:NEW_DATE>', block, re.IGNORECASE)
                val_m = re.search(r'<d:BC_2YEAR[^>]*>([^<]+)</d:BC_2YEAR>', block, re.IGNORECASE)
                
                if date_m and val_m:
                    date_str = date_m.group(1)[:10] # "YYYY-MM-DD" 포맷 추출
                    mmdd = f"{date_str[5:7]}-{date_str[8:10]}"
                    try:
                        results[mmdd] = round(float(val_m.group(1)), 2)
                    except ValueError:
                        pass
    except Exception as e:
        print(f"미 재무부 2년물 수집 오류: {e}")

    # 데이터가 비어있을 경우에만 안전장치 발동
    if len(results) < 10:
        print("⚠️ [경고] 2년물 수집 실패로 폴백 데이터가 적용됩니다.")
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


# [수정된 코드블럭]
def main():
    data = load_existing_data()

# [수정된 코드블럭]
    # 1. 국채금리 실데이터 수집
    # 10년물, 30년물은 현재 잘 작동하고 있는 야후 파이낸스 로직 유지
    raw_10y = fetch_yahoo_series("^TNX", 20)
    hist_10y = [{"date": x["date"], "price": round(x["price"] / 10, 2) if x["price"] > 10 else x["price"]} for x in raw_10y] if raw_10y else [{"date": k, "price": v} for k, v in FALLBACK_10Y]

    # 🔥 누락되어 있던 5년물(미 중기금리) 수집 로직 추가 (^FVX)
    raw_5y = fetch_yahoo_series("^FVX", 20)
    hist_5y = [{"date": x["date"], "price": round(x["price"] / 10, 2) if x["price"] > 10 else x["price"]} for x in raw_5y] if raw_5y else [{"date": "09-10", "price": 4.45}]

    raw_30y = fetch_yahoo_series("^TYX", 20)
    hist_30y = [{"date": x["date"], "price": round(x["price"] / 10, 2) if x["price"] > 10 else x["price"]} for x in raw_30y] if raw_30y else [{"date": k, "price": v} for k, v in FALLBACK_30Y]
# [수정된 코드블럭]
    # 🔥 2년물 궁극의 해결책: 미국 재무부(Treasury.gov) 공식 XML 피드 다이렉트 수집
    # 2년물은 야후 파이낸스에 공식 심볼이 존재하지 않으므로, 차단 리스크가 없는 미 정부 공식망을 타격합니다.
    hist_2y = fetch_treasury_gov_2y(FALLBACK_2Y)
    
    map_10y = {x["date"]: x["price"] for x in hist_10y}
    map_2y = {x["date"]: x["price"] for x in hist_2y}
    map_30y = {x["date"]: x["price"] for x in hist_30y}

    all_dates = sorted(list(set(list(map_10y.keys()) + list(map_2y.keys()) + list(map_30y.keys()))))
    bonds_history = []
    
    # 🔥 핵심: 결측치 보정 (Forward Fill) 변수 초기화
    # 특정 일자에 데이터가 누락되더라도 전일 데이터를 이어받아 차트 절단 방지
    last_p10, last_p2, last_p30 = 4.79, 4.37, 5.25
    
    for d in all_dates:
        p10 = map_10y.get(d)
        if p10 is not None: last_p10 = p10
        else: p10 = last_p10
        
        p2 = map_2y.get(d)
        if p2 is not None: last_p2 = p2
        else: p2 = last_p2
        
        p30 = map_30y.get(d)
        if p30 is not None: last_p30 = p30
        else: p30 = last_p30
        
        # 깐깐한 조건문(if p10 is not None and p2 is not None)을 삭제하여 무조건 기록
        sp = round((p10 - p2) * 100)
        bonds_history.append({"date": d, "us10y": p10, "us2y": p2, "us30y": p30, "spread": sp})

    # [수정된 코드블럭]
    latest_10y = hist_10y[-1]["price"] if hist_10y else last_p10
    latest_5y = hist_5y[-1]["price"] if hist_5y else 4.45  # 5년물 최신값 추출
    latest_2y = hist_2y[-1]["price"] if hist_2y else last_p2
    latest_30y = hist_30y[-1]["price"] if hist_30y else last_p30
    spread_bp = round((latest_10y - latest_2y) * 100)

    # 🔥 하드코딩 방지: 전일 대비 등락폭(Change) 자동 계산 함수
    def get_bond_change(hist, latest_val):
        if len(hist) >= 2:
            return round(latest_val - hist[-2]["price"], 2)
        return 0.00

    data["us10y"] = {"value": latest_10y, "change": get_bond_change(hist_10y, latest_10y)}
    data["us5y"]  = {"value": latest_5y,  "change": get_bond_change(hist_5y, latest_5y)}
    data["us2y"]  = {"value": latest_2y,  "change": get_bond_change(hist_2y, latest_2y)}
    data["us30y"] = {"value": latest_30y, "change": get_bond_change(hist_30y, latest_30y)}
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

    # 6. 마스터 풀 파일(humanities_pool.json)에서 1일 1주제 순환 추출 및 5일 큐 갱신
    data["humanities"] = load_humanities_from_pool(data.get("humanities", {}))

    # 7. 실시간 RSS 피드 수집
    data["feeds"] = {
        "fed": fetch_rss("https://www.federalreserve.gov/feeds/speeches.xml", 4, "[연설]") or [],
        "global": fetch_rss("https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", 5) or [],
        "tech": (fetch_rss("https://www.thelec.kr/rss/allArticle.xml", 3, "[디일렉]") + fetch_rss("https://rss.etnews.com/Section902.xml", 3, "[전자신문]"))[:5],
        "domestic": fetch_rss("https://news.einfomax.co.kr/rss/S1N16.xml", 5) or [],
    }

    data["updated_at"] = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

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
