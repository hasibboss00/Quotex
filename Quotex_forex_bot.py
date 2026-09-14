import yfinance as yf
import requests
import time
import pandas as pd
from datetime import datetime
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- DUMMY WEB SERVER FOR RENDER FREE TIER ---
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Target Billionaire Engine is Running 24/7 Free!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    print(f"Web server running on port {port}")
    server.serve_forever()

# --- CONFIGURATION ---
TOKEN = "8958179212:AAGRaqegMW4WJS9KTz1MwaU5lh5wtui4HQ0"
GROUP_ID = "-5160285764"

PAIRS = {
    "USD/JPY": "USDJPY=X", "EUR/JPY": "EURJPY=X", "EUR/USD": "EURUSD=X",
    "GBP/JPY": "GBPJPY=X", "AUD/JPY": "AUDJPY=X", "CAD/JPY": "CADJPY=X",
    "CHF/JPY": "CHFJPY=X", "EUR/AUD": "EURAUD=X", "AUD/CAD": "AUDCAD=X",
    "GBP/USD": "GBPUSD=X", "USD/CAD": "USDCAD=X", "AUD/USD": "AUDUSD=X"
}

last_signal_time = {}

def send_telegram_signal(pair_name, direction, price):
    now = datetime.now().strftime("%H:%M:%S")
    emoji = "🟢 CALL (BUY)" if direction == "CALL" else "🔴 PUT (SELL)"
    
    msg = f"""
🚨 *QUOTEX 1-MIN VIP SIGNAL* 🚨
-----------------------------------------
📊 *Asset:* `{pair_name}`
⏰ *Timeframe:* 1 MINUTE
🎯 *Action:* **{emoji}**
📍 *Entry Price:* `{price:.5f}`
⏳ *Time:* `{now} UTC`
-----------------------------------------
💡 *Strategy:* Bollinger Stretch + Reversal
⚠️ *Rule:* Use 1-Step Martingale if needed!
👑 *Target Billionaire Engine v11.0*
"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": GROUP_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=5)
        print(f"[{now}] SIGNAL SENT: {pair_name} -> {direction}")
    except Exception as e:
        print(f"Telegram Error: {e}")

def calculate_bollinger_bands(df, window=20, num_sd=2.2):
    sma = df['Close'].rolling(window=window).mean()
    std = df['Close'].rolling(window=window).std()
    upper_band = sma + (std * num_sd)
    lower_band = sma - (std * num_sd)
    return upper_band, lower_band

def analyze_pair(pair_name, ticker):
    try:
        df = yf.download(ticker, period="1d", interval="1m", progress=False).tail(30)
        if len(df) < 22: return

        if isinstance(df.columns, pd.MultiIndex): 
            df.columns = df.columns.get_level_values(0)

        df['Upper'], df['Lower'] = calculate_bollinger_bands(df)
        
        c = df.iloc[-1]
        prev = df.iloc[-2]

        c_open, c_close = c['Open'], c['Close']
        c_high, c_low = c['High'], c['Low']
        
        call_cond = (c_low < c['Lower'] or prev['Low'] < prev['Lower']) and (c_close > c_open)
        put_cond = (c_high > c['Upper'] or prev['High'] > prev['Upper']) and (c_close < c_open)

        curr_t = time.time()
        if (call_cond or put_cond) and (curr_t - last_signal_time.get(pair_name, 0) > 180):
            direction = "CALL" if call_cond else "PUT"
            send_telegram_signal(pair_name, direction, c_close)
            last_signal_time[pair_name] = curr_t

    except Exception as e:
        print(f"Scan Error {pair_name}: {e}")

def main():
    # Start Keep-Alive Web Server Thread
    threading.Thread(target=run_web_server, daemon=True).start()
    print("🚀 1-Min Cloud Engine Active...")
    
    while True:
        for pair_name, ticker in PAIRS.items():
            analyze_pair(pair_name, ticker)
            time.sleep(0.5)
        time.sleep(5)

if __name__ == "__main__":
    main()
