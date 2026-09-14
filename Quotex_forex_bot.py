import yfinance as yf
import requests
import time
import os
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Target Billionaire Turbo Engine V16.2 is Active!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

TOKEN = "8958179212:AAGRaqegMW4WJS9KTz1MwaU5lh5wtui4HQ0"
GROUP_ID = "-5160285764"

# ২০টি পেয়ার যাতে সিগন্যাল অনেক বেশি আসে
TICKERS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", 
    "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "CADJPY=X", "CHFJPY=X"
]

last_signal_time = {}

def send_telegram_signal(pair, direction, reason):
    emoji = "🟢 CALL" if direction == "CALL" else "🔴 PUT"
    pair_name = pair.replace('=X', '')
    msg = f"🚨 *QUOTEX VIP SIGNAL*\n---\n📊 Asset: `{pair_name}`\n🎯 Action: **{emoji}**\n⏰ Time: 1 MIN\n💡 Logic: `{reason}`\n👑 TB v16.2 Turbo"
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": GROUP_ID, "text": msg, "parse_mode": "Markdown"}, timeout=5)
    except: pass

def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    # স্টার্টআপ মেসেজ
    requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={GROUP_ID}&text=🚀 *Turbo Engine Online!* \nScanning 10 pairs for High-Frequency signals...")

    while True:
        try:
            data = yf.download(TICKERS, period="1d", interval="1m", progress=False).tail(5)
            for ticker in TICKERS:
                try:
                    c_close = data['Close'][ticker].iloc[-1]
                    c_open = data['Open'][ticker].iloc[-1]
                    p_close = data['Close'][ticker].iloc[-2]
                    p_open = data['Open'][ticker].iloc[-2]

                    direction = None
                    reason = ""

                    # --- ১. শক্তিশালী কালার প্যাটার্ন (৩টি ক্যান্ডেল) ---
                    if c_close > c_open and p_close > p_open and data['Close'][ticker].iloc[-3] > data['Open'][ticker].iloc[-3]:
                        direction, reason = "PUT", "3-Candle Reversal 🔄"
                    elif c_close < c_open and p_close < p_open and data['Close'][ticker].iloc[-3] < data['Open'][ticker].iloc[-3]:
                        direction, reason = "CALL", "3-Candle Reversal 🔄"
                    
                    # --- ২. মোমেন্টাম ব্রেকআউট ---
                    elif (c_close > c_open) and (c_close > data['High'][ticker].iloc[-2]):
                        direction, reason = "CALL", "Momentum Breakout 🚀"
                    elif (c_close < c_open) and (c_close < data['Low'][ticker].iloc[-2]):
                        direction, reason = "PUT", "Momentum Breakout 📉"

                    # ৩ মিনিটের গ্যাপে সিগন্যাল (একই পেয়ারে)
                    if direction and (time.time() - last_signal_time.get(ticker, 0) > 120):
                        send_telegram_signal(ticker, direction, reason)
                        last_signal_time[ticker] = time.time()
                except: continue
            time.sleep(5)
        except: time.sleep(10)

if __name__ == "__main__":
    main()
