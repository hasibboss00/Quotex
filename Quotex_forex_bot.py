import yfinance as yf
import requests
import time
import os
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- RENDER KEEP-ALIVE SERVER ---
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Target Billionaire Master V19 is Online!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# --- CONFIGURATION ---
TOKEN = "8958179212:AAGRaqegMW4WJS9KTz1MwaU5lh5wtui4HQ0"
GROUP_ID = "-1003927083951" # তোমার নতুন সুপারগ্রুপ আইডি আপডেট করা হয়েছে ✅

TICKERS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "EURGBP=X", "USDCHF=X"]

last_signal_time = {}

def send_telegram_signal(pair, direction, logic_name, next_candle_time):
    emoji = "🟢 CALL (BUY)" if direction == "CALL" else "🔴 PUT (SELL)"
    pair_name = pair.replace('=X', '')
    
    msg = f"""
🚨 *NEXT-CANDLE PREDICTION* 🚨
-----------------------------------------
📊 *Asset:* `{pair_name}`
🎯 *Predictive Action:* **{emoji}**
⏳ *Trade Start:* `{next_candle_time}` (Exact 00s)
⏰ *Expiry:* 1 MINUTE
💡 *Pattern:* `{logic_name}`
-----------------------------------------
⚠️ *Rule:* Enter exactly at 00-second of next candle!
💡 Use 1-Step Martingale if needed!
👑 *TB Master Engine V19*
"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": GROUP_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    
    # বোট অনলাইন হওয়ার সাথে সাথে মেসেজ
    requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={GROUP_ID}&text=🔮 *Target Billionaire Master V19 Online!* \nNext-Candle Prediction Engine Active.")

    while True:
        try:
            # একবারে সব পেয়ারের ডাটা ফেচ
            data = yf.download(TICKERS, period="1d", interval="1m", progress=False).tail(5)
            now = datetime.now()

            # পরবর্তী মিনিটের সময় (যেমন: ১২:৩৫:০০)
            next_min = (now.minute + 1) % 60
            next_hour = now.hour if next_min != 0 else (now.hour + 1) % 24
            next_candle_time = f"{next_hour:02d}:{next_min:02d}:00 UTC"

            for ticker in TICKERS:
                try:
                    closes = data['Close'][ticker].tolist()
                    opens = data['Open'][ticker].tolist()
                    highs = data['High'][ticker].tolist()
                    lows = data['Low'][ticker].tolist()

                    c0_close, c0_open = closes[-1], opens[-1]
                    c1_close, c1_open = closes[-2], opens[-2]
                    c0_high, c0_low = highs[-1], lows[-1]
                    
                    rng = max(c0_high - c0_low, 0.00001)
                    l_wick = min(c0_open, c0_close) - c0_low
                    u_wick = c0_high - max(c0_open, c0_close)

                    direction, pattern = None, ""

                    # --- লজিক ১: উইক রিজেকশন (৩৫% প্রেসার) ---
                    if (l_wick / rng) > 0.35 and c0_close > c0_open:
                        direction, pattern = "CALL", "Buyer Pressure 🚀"
                    elif (u_wick / rng) > 0.35 and c0_close < c0_open:
                        direction, pattern = "PUT", "Seller Pressure 📉"
                    
                    # --- লজিক ২: কালার ফ্লিপ (Engulfing) ---
                    elif c1_close < c1_open and c0_close > c0_open and c0_close > c1_open:
                        direction, pattern = "CALL", "Bullish Color Flip 🟢"
                    elif c1_close > c1_open and c0_close < c0_open and c0_close < c1_open:
                        direction, pattern = "PUT", "Bearish Color Flip 🔴"

                    if direction and (time.time() - last_signal_time.get(ticker, 0) > 120):
                        send_telegram_signal(ticker, direction, pattern, next_candle_time)
                        last_signal_time[ticker] = time.time()
                except: continue

            time.sleep(10) # প্রতি ১০ সেকেন্ডে স্ক্যান
        except:
            time.sleep(10)

if __name__ == "__main__":
    main()
