import yfinance as yf
import requests
import time
import os
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- RENDER KEEP-ALIVE HTTP SERVER ---
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Target Billionaire Candle Color Predictor V20 Active!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# --- CONFIGURATION ---
TOKEN = "8958179212:AAGRaqegMW4WJS9KTz1MwaU5lh5wtui4HQ0"
GROUP_ID = "-1003927083951" # তোমার সঠিক সুপারগ্রুপ আইডি ✅

TICKERS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X",
    "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "EURGBP=X", "USDCHF=X"
]

last_signal_time = {}

def send_telegram_signal(pair, direction, logic_name, next_candle_time):
    emoji = "🟢 CALL (BUY)" if direction == "CALL" else "🔴 PUT (SELL)"
    pair_name = pair.replace('=X', '')
    
    msg = f"""
🚨 *NEXT-CANDLE COLOR PREDICTION* 🚨
-----------------------------------------
📊 *Asset:* `{pair_name}`
🎯 *Next Candle:* **{emoji}**
⏳ *Trade Start:* `{next_candle_time}` (Exact 00s)
⏰ *Expiry:* 1 MINUTE
💡 *Candle Rule:* `{logic_name}`
-----------------------------------------
⚠️ *Rule:* Enter exactly at 00-second of next candle!
💡 Use 1-Step Martingale if needed!
👑 *Target Billionaire V20 Engine*
"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": GROUP_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] SENT PREDICTION: {pair_name} -> {direction}")
    except Exception as e:
        print(f"Telegram Send Error: {e}")

def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    print("🚀 Candle Color Predictor V20 Engine Online...")
    
    # স্টার্টআপ কনফার্মেশন মেসেজ
    try:
        requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={GROUP_ID}&text=🔮 *V20 Pure Candle Predictor Online!* \nScanning candle close colors for Next-Candle signals...")
    except: pass

    while True:
        try:
            now = datetime.now()
            # ১ মিনিটের ক্যান্ডেল ডাটা ফেচ
            data = yf.download(TICKERS, period="1d", interval="1m", progress=False).tail(5)

            # পরবর্তী মিনিটের নিখুঁত সময় হিসাব (যেমন: ১৩:৫০:০০)
            next_min = (now.minute + 1) % 60
            next_hour = now.hour if next_min != 0 else (now.hour + 1) % 24
            next_candle_time = f"{next_hour:02d}:{next_min:02d}:00 UTC"

            for ticker in TICKERS:
                try:
                    closes = data['Close'][ticker].tolist()
                    opens = data['Open'][ticker].tolist()
                    highs = data['High'][ticker].tolist()
                    lows = data['Low'][ticker].tolist()

                    c0_close, c0_open = closes[-1], opens[-1]  # চলতি ক্যান্ডেল
                    c1_close, c1_open = closes[-2], opens[-2]  # আগের ক্যান্ডেল

                    c0_high, c0_low = highs[-1], lows[-1]
                    rng0 = max(c0_high - c0_low, 0.00001)
                    l_wick0 = min(c0_open, c0_close) - c0_low
                    u_wick0 = c0_high - max(c0_open, c0_close)

                    direction, logic_name = None, ""

                    # --- Rule 1: Red Candle Reversal -> Next Green ---
                    if c0_close < c0_open and (l_wick0 / rng0) > 0.35:
                        direction, logic_name = "CALL", "Red Reversal -> Next Green 🟢"

                    # --- Rule 2: Green Candle Reversal -> Next Red ---
                    elif c0_close > c0_open and (u_wick0 / rng0) > 0.35:
                        direction, logic_name = "PUT", "Green Reversal -> Next Red 🔴"

                    # --- Rule 3: Red to Green Color Flip ---
                    elif c1_close < c1_open and c0_close > c0_open and c0_close > c1_open:
                        direction, logic_name = "CALL", "Red-to-Green Flip -> Next Green 🟢"

                    # --- Rule 4: Green to Red Color Flip ---
                    elif c1_close > c1_open and c0_close < c0_open and c0_close < c1_open:
                        direction, logic_name = "PUT", "Green-to-Red Flip -> Next Red 🔴"

                    # --- Rule 5: Green Push Continuation ---
                    elif c0_close > c0_open and c1_close > c1_open and (u_wick0 / rng0) < 0.15:
                        direction, logic_name = "CALL", "Green Push -> Next Green Continuation 🟢"

                    # --- Rule 6: Red Push Continuation ---
                    elif c0_close < c0_open and c1_close < c1_open and (l_wick0 / rng0) < 0.15:
                        direction, logic_name = "PUT", "Red Push -> Next Red Continuation 🔴"

                    # একই পেয়ারে ২ মিনিটের আগে বারবার দেবে না
                    if direction and (time.time() - last_signal_time.get(ticker, 0) > 90):
                        send_telegram_signal(ticker, direction, logic_name, next_candle_time)
                        last_signal_time[ticker] = time.time()

                except: continue

            time.sleep(5)
        except Exception as e:
            time.sleep(10)

if __name__ == "__main__":
    main()
