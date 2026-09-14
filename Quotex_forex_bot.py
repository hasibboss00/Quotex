import yfinance as yf
import requests
import time
import os
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- RENDER KEEP-ALIVE WEB SERVER ---
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Target Billionaire High-Frequency V16 Engine Active!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# --- CONFIGURATION ---
TOKEN = "8958179212:AAGRaqegMW4WJS9KTz1MwaU5lh5wtui4HQ0"
GROUP_ID = "-5160285764"

# সবচেয়ে ভলিউম থাকা ১০টি পেয়ার (Rate Limit এড়াতে সেফ পেয়ার লিস্ট)
PAIRS = {
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X",
    "AUD/USD": "AUDUSD=X", "USD/CAD": "USDCAD=X", "EUR/JPY": "EURJPY=X",
    "GBP/JPY": "GBPJPY=X", "AUD/JPY": "AUDJPY=X", "BTC/USD": "BTC-USD"
}

last_signal_time = {}

def send_telegram_signal(pair_name, direction, reason):
    now = datetime.now().strftime("%H:%M:%S")
    emoji = "🟢 CALL (BUY)" if direction == "CALL" else "🔴 PUT (SELL)"
    
    msg = f"""
🚨 *QUOTEX HIGH-ACCURACY SIGNAL* 🚨
-----------------------------------------
📊 *Asset:* `{pair_name}`
⏰ *Expiry:* 1 MINUTE
🎯 *Action:* **{emoji}**
💡 *Type:* `{reason}`
-----------------------------------------
⏳ *Execution:* Enter immediately on candle start!
⚠️ Use 1-Step Martingale if needed!
👑 *Target Billionaire V16 Pro*
"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": GROUP_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=5)
        print(f"[{now}] SIGNAL SENT: {pair_name} -> {direction}")
    except Exception as e:
        print(f"Telegram Error: {e}")

def calculate_ema(prices, period):
    if len(prices) < period: return prices[-1]
    multiplier = 2 / (period + 1)
    ema = prices[0]
    for price in prices[1:]:
        ema = (price - ema) * multiplier + ema
    return ema

def analyze_pair(pair_name, ticker):
    try:
        data = yf.download(ticker, period="1d", interval="1m", progress=False).tail(15)
        if len(data) < 10: return

        closes = data['Close'].tolist()
        opens = data['Open'].tolist()

        c_close = closes[-1]
        c_open = opens[-1]
        
        # EMA Calc
        ema_fast = calculate_ema(closes, 3)
        ema_slow = calculate_ema(closes, 10)

        # --- STRATEGY 1: MOMENTUM IMPULSE (TREND FOLLOWING) ---
        mom_call = (ema_fast > ema_slow) and (c_close > c_open) and (closes[-2] > opens[-2])
        mom_put = (ema_fast < ema_slow) and (c_close < c_open) and (closes[-2] < opens[-2])

        # --- STRATEGY 2: 3-CANDLE EXHAUSTION (REVERSAL) ---
        exh_put = (closes[-1] > opens[-1]) and (closes[-2] > opens[-2]) and (closes[-3] > opens[-3]) # 3 Green -> PUT
        exh_call = (closes[-1] < opens[-1]) and (closes[-2] < opens[-2]) and (closes[-3] < opens[-3]) # 3 Red -> CALL

        curr_t = time.time()
        direction = None
        reason = ""

        if mom_call:
            direction, reason = "CALL", "Momentum Trend Push 🚀"
        elif mom_put:
            direction, reason = "PUT", "Momentum Trend Push 📉"
        elif exh_put:
            direction, reason = "PUT", "Exhaustion Reversal 🔄"
        elif exh_call:
            direction, reason = "CALL", "Exhaustion Reversal 🔄"

        if direction and (curr_t - last_signal_time.get(pair_name, 0) > 120):
            send_telegram_signal(pair_name, direction, reason)
            last_signal_time[pair_name] = curr_t

    except Exception as e:
        pass

def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    print("🚀 V16 High-Frequency Engine Active...")
    
    # বোট চালু হওয়ামাত্রই কনফার্মেশন মেসেজ
    send_telegram_signal("SYSTEM TEST", "CALL", "V16 Engine Booted Successfully!")

    while True:
        for pair_name, ticker in PAIRS.items():
            analyze_pair(pair_name, ticker)
            time.sleep(0.5)
        time.sleep(3)

if __name__ == "__main__":
    main()
