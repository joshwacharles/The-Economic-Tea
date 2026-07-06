"""
The Ledger - Combined Market Data Fetcher
Pulls US markets, gold, crude, and USD/INR from Alpha Vantage (free),
and Nifty 50 / Sensex / all 50 Nifty stocks from Yahoo Finance (free).

Saves everything into one market-data.json file, meant to run automatically
via GitHub Actions (hourly recommended).

Install requirements first:
    pip install requests yfinance --break-system-packages
"""

import os
import json
import time
import requests
from datetime import datetime, timezone

API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY")

if not API_KEY:
    raise ValueError(
        "No API key found. Set ALPHA_VANTAGE_API_KEY as an environment variable "
        "(locally in a .env file, or as a GitHub Secret when deployed)."
    )

BASE_URL = "https://www.alphavantage.co/query"


def fetch_quote(symbol):
    params = {"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": API_KEY}
    r = requests.get(BASE_URL, params=params, timeout=15)
    quote = r.json().get("Global Quote", {})
    return {
        "price": quote.get("05. price"),
        "change": quote.get("09. change"),
        "change_percent": quote.get("10. change percent"),
    }


def fetch_commodity(function_name):
    params = {"function": function_name,
              "interval": "daily", "apikey": API_KEY}
    r = requests.get(BASE_URL, params=params, timeout=15)
    series = r.json().get("data", [])
    if series:
        latest = series[0]
        return {"date": latest.get("date"), "value": latest.get("value")}
    return {"date": None, "value": None}


def fetch_forex(from_symbol, to_symbol):
    params = {
        "function": "CURRENCY_EXCHANGE_RATE",
        "from_currency": from_symbol,
        "to_currency": to_symbol,
        "apikey": API_KEY,
    }
    r = requests.get(BASE_URL, params=params, timeout=15)
    data = r.json().get("Realtime Currency Exchange Rate", {})
    return {"rate": data.get("5. Exchange Rate"), "last_refreshed": data.get("6. Last Refreshed")}


def fetch_nifty_sensex():
    result = {}
    try:
        import yfinance as yf
        nifty = yf.Ticker("^NSEI")
        hist = nifty.history(period="1d")
        if not hist.empty:
            last_close = hist["Close"].iloc[-1]
            result["nifty_50"] = {"price": round(float(last_close), 2)}
        else:
            result["nifty_50"] = {"status": "no_data_returned"}
    except Exception as e:
        result["nifty_50"] = {"status": "fetch_failed", "error": str(e)}

    try:
        import yfinance as yf
        sensex = yf.Ticker("^BSESN")
        hist = sensex.history(period="1d")
        if not hist.empty:
            last_close = hist["Close"].iloc[-1]
            result["sensex"] = {"price": round(float(last_close), 2)}
        else:
            result["sensex"] = {"status": "no_data_returned"}
    except Exception as e:
        result["sensex"] = {"status": "fetch_failed", "error": str(e)}

    return result


NIFTY_50_TICKERS = {
    "RELIANCE.NS": "Reliance Industries",
    "HDFCBANK.NS": "HDFC Bank",
    "BHARTIARTL.NS": "Bharti Airtel",
    "ICICIBANK.NS": "ICICI Bank",
    "SBIN.NS": "State Bank of India",
    "TCS.NS": "Tata Consultancy Services",
    "BAJFINANCE.NS": "Bajaj Finance",
    "LT.NS": "Larsen & Toubro",
    "HINDUNILVR.NS": "Hindustan Unilever",
    "SUNPHARMA.NS": "Sun Pharmaceutical",
    "MARUTI.NS": "Maruti Suzuki",
    "ADANIPORTS.NS": "Adani Ports",
    "INFY.NS": "Infosys",
    "ADANIENT.NS": "Adani Enterprises",
    "AXISBANK.NS": "Axis Bank",
    "TITAN.NS": "Titan Company",
    "KOTAKBANK.NS": "Kotak Mahindra Bank",
    "M&M.NS": "Mahindra & Mahindra",
    "ITC.NS": "ITC",
    "NTPC.NS": "NTPC",
    "ULTRACEMCO.NS": "UltraTech Cement",
    "HCLTECH.NS": "HCL Technologies",
    "BEL.NS": "Bharat Electronics",
    "TATAMOTORS.NS": "Tata Motors",
    "WIPRO.NS": "Wipro",
    "ASIANPAINT.NS": "Asian Paints",
    "BAJAJFINSV.NS": "Bajaj Finserv",
    "POWERGRID.NS": "Power Grid",
    "TATASTEEL.NS": "Tata Steel",
    "ONGC.NS": "ONGC",
    "COALINDIA.NS": "Coal India",
    "NESTLEIND.NS": "Nestle India",
    "JSWSTEEL.NS": "JSW Steel",
    "GRASIM.NS": "Grasim Industries",
    "TECHM.NS": "Tech Mahindra",
    "HINDALCO.NS": "Hindalco Industries",
    "DRREDDY.NS": "Dr Reddy's Labs",
    "CIPLA.NS": "Cipla",
    "SBILIFE.NS": "SBI Life Insurance",
    "HDFCLIFE.NS": "HDFC Life Insurance",
    "APOLLOHOSP.NS": "Apollo Hospitals",
    "DIVISLAB.NS": "Divi's Laboratories",
    "BAJAJ-AUTO.NS": "Bajaj Auto",
    "BRITANNIA.NS": "Britannia Industries",
    "EICHERMOT.NS": "Eicher Motors",
    "HEROMOTOCO.NS": "Hero MotoCorp",
    "SHRIRAMFIN.NS": "Shriram Finance",
    "TATACONSUM.NS": "Tata Consumer Products",
    "TRENT.NS": "Trent",
    "INDUSINDBK.NS": "IndusInd Bank",
    "UPL.NS": "UPL",
}


def fetch_all_nifty50_stocks():
    stocks = {}
    try:
        import yfinance as yf
        tickers = list(NIFTY_50_TICKERS.keys())
        data = yf.download(tickers, period="1d",
                           group_by="ticker", progress=False)

        for symbol, name in NIFTY_50_TICKERS.items():
            try:
                last_close = data[symbol]["Close"].iloc[-1]
                stocks[symbol] = {
                    "name": name,
                    "price": round(float(last_close), 2),
                }
            except Exception:
                stocks[symbol] = {"name": name, "status": "no_data"}
    except Exception as e:
        stocks["_error"] = str(e)

    return stocks


def main():
    now = datetime.now(timezone.utc)

    try:
        with open("market-data.json", "r") as f:
            result = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        result = {"markets": {}}

    result["last_updated_utc"] = now.isoformat()

    ALPHA_VANTAGE_HOURS = {0, 6, 12, 18}

    if now.hour in ALPHA_VANTAGE_HOURS:
        result["markets"]["dow_jones"] = fetch_quote("DIA")
        time.sleep(12)
        result["markets"]["sp500"] = fetch_quote("SPY")
        time.sleep(12)
        result["markets"]["crude_oil_wti"] = fetch_commodity("WTI")
        time.sleep(12)
        result["markets"]["gold_gld_proxy"] = fetch_quote("GLD")
        time.sleep(12)
        result["markets"]["usd_inr"] = fetch_forex("USD", "INR")
    else:
        print(f"Skipping Alpha Vantage calls this hour (UTC {now.hour}:00) "
              f"to stay under the free daily limit. Keeping previous values.")

    result["markets"].update(fetch_nifty_sensex())

    result["nifty_50_stocks"] = fetch_all_nifty50_stocks()

    result["markets"]["india_cpi"] = {"status": "manual_update_monthly_mospi"}
    result["markets"]["india_wpi"] = {"status": "manual_update_monthly_mospi"}

    with open("market-data.json", "w") as f:
        json.dump(result, f, indent=2)

    print("market-data.json updated successfully.")


if __name__ == "__main__":
    main()
