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
        self.wfile.write(b"TB Master Binary Predictor V17 is Running!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# --- CONFIGURATION ---
TOKEN = "8958179212:AAGRaqegMW4WJS9KTz1MwaU5lh5wtui4HQ0"
GROUP_ID = "-5160285764"

# ১০টি হাই-লিকুইডিটি ফরেক্স পেয়ার
TICKERS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X",
    "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "EURGBP=X", "USDCHF=X"
]

last_signal_time = {}

def send_telegram_signal(pair, direction, logic_name, next_candle_time):
    emoji = "🟢 CALL (BUY)" if direction == "CALL" else "🔴 PUT (SELL)"
    pair_name = pair.replace('=X', '')
    
    msg = f"""
🚨 *NEXT-CANDLE PREDICTIVE SIGNAL* 🚨
-----------------------------------------
📊 *Asset:* `{pair_name}`
🎯 *Predictive Action:* **{emoji}**
⏳ *Trade Start:* `{next_candle_time}` (Exact 00s)
⏰ *Expiry:* 1 MINUTE
💡 *Pattern:* `{logic_name}`
-----------------------------------------
⚠️ *Rule:* Enter exactly at 00-second of next candle!
💡 Use 1-Step Martingale if needed!
👑 *Target Billionaire V17 Master Engine*
"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": GROUP_ID, "text": msg, "parse_mode": "Markdown"}, timeout=5)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] PREDICTION SENT: {pair_name} -> {direction}")
    except Exception as e:
        print(f"Telegram Send Error: {e}")

def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    print("🚀 Master Binary Predictor V17 Active...")
    
    # বোট অনলাইন কনফার্মেশন
    try:
        requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={GROUP_ID}&text=🔮 *Target Billionaire V17 Engine Online!* \nCandle Pattern & Next-Candle Predictor Active.")
    except: pass

    while True:
        try:
            # একবারে সব পেয়ারের ডাটা ফেচ
            data = yf.download(TICKERS, period="1d", interval="1m", progress=False).tail(5)
            now = datetime.now()

            # পরবর্তী মিনিটের সময় নির্ধারণ (যেমন: ১২:৩৫:০০)
            next_min = (now.minute + 1) % 60
            next_hour = now.hour if next_min != 0 else (now.hour + 1) % 24
            next_candle_time = f"{next_hour:02d}:{next_min:02d}:00 UTC"

            for ticker in TICKERS:
                try:
                    closes = data['Close'][ticker].tolist()
                    opens = data['Open'][ticker].tolist()
                    highs = data['High'][ticker].tolist()
                    lows = data['Low'][ticker].tolist()

                    c0_close, c0_open = closes[-1], opens[-1] # বর্তমান ক্যান্ডেল
                    c1_close, c1_open = closes[-2], opens[-2] # আগের ক্যান্ডেল
                    c2_close, c2_open = closes[-3], opens[-3] # ২ ক্যান্ডেল আগের

                    c0_high, c0_low = highs[-1], lows[-1]
                    rng0 = max(c0_high - c0_low, 0.00001)
                    l_wick0 = min(c0_open, c0_close) - c0_low
                    u_wick0 = c0_high - max(c0_open, c0_close)

                    direction = None
                    logic_name = ""

                    # --- 1. PINBAR PRESSURE (WICK REJECTION) ---
                    if (l_wick0 / rng0) > 0.38 and c0_close > c0_open:
                        direction, logic_name = "CALL", "Buyer Wick Pressure 🚀"
                    elif (u_wick0 / rng0) > 0.38 and c0_close < c0_open:
                        direction, logic_name = "PUT", "Seller Wick Pressure 📉"

                    # --- 2. ENGULFING COLOR FLIP ---
                    elif c1_close < c1_open and c0_close > c0_open and c0_close > (c1_open + c1_close)/2:
                        direction, logic_name = "CALL", "Bullish Color Flip 🟢"
                    elif c1_close > c1_open and c0_close < c0_open and c0_close < (c1_open + c1_close)/2:
                        direction, logic_name = "PUT", "Bearish Color Flip 🔴"

                    # --- 3. TWO-CANDLE MOMENTUM PUSH ---
                    elif c0_close > c0_open and c1_close > c1_open and (u_wick0 / rng0) < 0.15:
                        direction, logic_name = "CALL", "Bullish Momentum Push ⚡"
                    elif c0_close < c0_open and c1_close < c1_open and (l_wick0 / rng0) < 0.15:
                        direction, logic_name = "PUT", "Bearish Momentum Push ⚡"

                    # --- 4. ZIG-ZAG ALTERNATING FLIP ---
                    elif c2_close < c2_open and c1_close > c1_open and c0_close < c0_open:
                        direction, logic_name = "CALL", "Zig-Zag Pattern Flip 🔄"
                    elif c2_close > c2_open and c1_close < c1_open and c0_close > c0_open:
                        direction, logic_name = "PUT", "Zig-Zag Pattern Flip 🔄"

                    # কোলডাউন: একই পেয়ারে ২ মিনিটের আগে বারবার দেবে না
                    if direction and (time.time() - last_signal_time.get(ticker, 0) > 90):
                        send_telegram_signal(ticker, direction, logic_name, next_candle_time)
                        last_signal_time[ticker] = time.time()

                except: continue

            time.sleep(6) # প্রতি ৬ সেকেন্ডে স্ক্যান
        except Exception as e:
            time.sleep(10)

if __name__ == "__main__":
    main()
