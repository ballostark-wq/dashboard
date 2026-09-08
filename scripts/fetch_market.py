import json
import os
from datetime import datetime
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def fetch_naver_interest_rates():
    """네이버 증권 API로부터 미국 국채 만기별 금리 수집"""
    url = "https://m.stock.naver.com/front-api/v1/marketIndex/prices?category=interestRate&recodeYn=true"
    res = requests.get(url, headers=HEADERS, timeout=10)
    res.raise_for_status()
    data = res.json()

    rates = {}
    items = data.get("result", [])

    code_map = {
        "IRRD_BONDU02Y": "us2y",
        "IRRD_BONDU05Y": "us5y",
        "IRRD_BONDU10Y": "us10y",
        "IRRD_BONDU30Y": "us30y",
    }

    for item in items:
        code = item.get("itemCode")
        if code in code_map:
            key = code_map[code]
            price = float(item.get("closePrice", "0").replace(",", ""))
            ratio = float(item.get("fluctuationsRatio", "0"))
            rates[key] = {"value": price, "change": ratio}

    return rates


def fetch_vix():
    """VIX 변동성 지수 수집 (네이버 / 공개 피드)"""
    try:
        url = "https://m.stock.naver.com/front-api/v1/marketIndex/prices?category=majorIndex&recodeYn=true"
        res = requests.get(url, headers=HEADERS, timeout=10)
        items = res.json().get("result", [])
        for item in items:
            if "VIX" in item.get("itemCode", ""):
                return {
                    "value": float(item.get("closePrice", "0").replace(",", "")),
                    "change": float(item.get("fluctuationsRatio", "0")),
                }
    except Exception:
        pass

    # 폴백: 야후 공개 피드 직접 호출 (서버 환경이므로 CORS 무관)
    try:
        y_url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?interval=1d&range=5d"
        res = requests.get(y_url, headers=HEADERS, timeout=10)
        meta = res.json()["chart"]["result"][0]["meta"]
        price = meta["regularMarketPrice"]
        prev = meta.get("chartPreviousClose", meta.get("previousClose", price))
        chg = ((price - prev) / prev) * 100 if prev else 0.0
        return {"value": round(price, 2), "change": round(chg, 2)}
    except Exception:
        return {"value": 15.30, "change": -6.36}


def main():
    rates = fetch_naver_interest_rates()
    vix = fetch_vix()

    y10 = rates.get("us10y", {}).get("value", 4.78)
    y2 = rates.get("us2y", {}).get("value", 4.32)

    # 10Y-2Y 스프레드 계산 (bp 단위)
    spread_bp = round((y10 - y2) * 100)

    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "us2y": rates.get("us2y", {"value": 4.32, "change": 0.03}),
        "us5y": rates.get("us5y", {"value": 4.45, "change": 0.02}),
        "us10y": rates.get("us10y", {"value": 4.78, "change": 0.46}),
        "us30y": rates.get("us30y", {"value": 4.95, "change": 0.01}),
        "spread": {
            "value": spread_bp,
            "status": "정상화 (우상향)" if spread_bp >= 0 else "역전 (침체경보)",
        },
        "vix": vix,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
