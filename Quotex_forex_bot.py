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
        self.wfile.write(b"TB V17.1 Predictive Engine is Alive!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# --- CONFIGURATION ---
TOKEN = "8958179212:AAGRaqegMW4WJS9KTz1MwaU5lh5wtui4HQ0"
GROUP_ID = "-5160285764"

# ডাটা ফেচিং সহজ করার জন্য ৫টি প্রধান পেয়ার (সিগন্যাল স্পিড বাড়বে)
TICKERS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "BTC-USD"]

last_signal_time = {}

def send_msg(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": GROUP_ID, "text": text, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except:
        return False

def main():
    # ১. ওয়েব সার্ভার স্টার্ট
    threading.Thread(target=run_web_server, daemon=True).start()
    
    # ২. ইমিডিয়েট স্টার্টআপ মেসেজ (এটি না আসলে বুঝবে টোকেন/আইডি ভুল)
    print("Sending startup message...")
    startup_ok = send_msg("🚀 *TB V17.1 Master Predictor Online!* \nChecking market data now...")
    if not startup_ok:
        print("❌ Error: Could not send Telegram message. Check Token/ID.")

    while True:
        try:
            now = datetime.now()
            # ডাটা ডাউনলোড (৫টি পেয়ার একবারে)
            data = yf.download(TICKERS, period="1d", interval="1m", progress=False).tail(5)
            
            # টাইম প্রেডিকশন
            next_min = (now.minute + 1) % 60
            next_hour = now.hour if next_min != 0 else (now.hour + 1) % 24
            next_time = f"{next_hour:02d}:{next_min:02d}:00 UTC"

            for ticker in TICKERS:
                try:
                    # ওটিসি/ফরেক্স ডাটা হ্যান্ডলিং
                    prices = data['Close'][ticker]
                    opens = data['Open'][ticker]
                    highs = data['High'][ticker]
                    lows = data['Low'][ticker]

                    c0_close, c0_open = prices.iloc[-1], opens.iloc[-1]
                    c1_close, c1_open = prices.iloc[-2], opens.iloc[-2]
                    c0_high, c0_low = highs.iloc[-1], lows.iloc[-1]

                    rng = max(c0_high - c0_low, 0.00001)
                    l_wick = min(c0_open, c0_close) - c0_low
                    u_wick = c0_high - max(c0_open, c0_close)

                    direction, pattern = None, ""

                    # --- লজিক ফিল্টার ---
                    # ১. রিজেকশন (৩৫% উইক)
                    if (l_wick / rng) > 0.35 and c0_close > c0_open:
                        direction, pattern = "CALL", "Buyer Rejection 🚀"
                    elif (u_wick / rng) > 0.35 and c0_close < c0_open:
                        direction, pattern = "PUT", "Seller Rejection 📉"
                    # ২. কালার ফ্লিপ (Engulfing-ish)
                    elif c1_close < c1_open and c0_close > c0_open and c0_close > c1_open:
                        direction, pattern = "CALL", "Bullish Flip 🟢"
                    elif c1_close > c1_open and c0_close < c0_open and c0_close < c1_open:
                        direction, pattern = "PUT", "Bearish Flip 🔴"

                    if direction and (time.time() - last_signal_time.get(ticker, 0) > 120):
                        pair = ticker.replace('=X','')
                        emoji = "🟢 CALL (BUY)" if direction == "CALL" else "🔴 PUT (SELL)"
                        
                        alert = f"""
🚨 *PREDICTIVE SIGNAL* 🚨
--------------------------
📊 Asset: `{pair}`
🎯 Action: **{emoji}**
⏳ Start: `{next_time}`
⏰ Expiry: 1 MINUTE
💡 Logic: `{pattern}`
--------------------------
👑 *TB Master Engine*
"""
                        send_msg(alert)
                        last_signal_time[ticker] = time.time()
                except: continue

            time.sleep(10)
        except Exception as e:
            print(f"Main Loop Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
