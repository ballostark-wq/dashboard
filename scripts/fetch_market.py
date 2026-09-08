import json
import os
import re
from datetime import datetime
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}


def load_existing_data():
    """기존 data.json이 있으면 불러와 기준값으로 활용 (무중단 안전장치)"""
    default_data = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "us2y": {"value": 4.32, "change": 0.03},
        "us5y": {"value": 4.45, "change": 0.02},
        "us10y": {"value": 4.78, "change": 0.46},
        "us30y": {"value": 4.95, "change": 0.01},
        "spread": {"value": 46, "status": "정상화 (우상향)"},
        "vix": {"value": 15.30, "change": -1.47},
    }
    if os.path.exists("data.json"):
        try:
            with open("data.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default_data


def fetch_naver_rates():
    """네이버 증권 공식 금리 리스트에서 만기별(2Y, 5Y, 10Y, 30Y) 국채금리 수집"""
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
            html = res.text

            # 테이블 행(tr) 단위 파싱
            rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
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
        print(f"네이버 금리 파싱 예외 발생 (기존값 유지): {e}")

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
        print(f"VIX 수집 예외 발생 (기존값 유지): {e}")
    return None


def main():
    data = load_existing_data()

    # 1. 네이버 국채금리 갱신
    rates = fetch_naver_rates()
    for k, v in rates.items():
        data[k] = v

    # 2. VIX 갱신
    vix = fetch_vix()
    if vix:
        data["vix"] = vix

    # 3. 10Y - 2Y 장단기 금리차(스프레드) 동적 산출 (단위: bp)
    y10 = data.get("us10y", {}).get("value", 4.78)
    y2 = data.get("us2y", {}).get("value", 4.32)
    spread_bp = round((y10 - y2) * 100)

    data["spread"] = {
        "value": spread_bp,
        "status": "정상화 (우상향)" if spread_bp >= 0 else "역전 (침체경보)",
    }
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 4. 저장소 루트에 data.json 저장
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("data.json 파일 생성/갱신 완료:")
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
