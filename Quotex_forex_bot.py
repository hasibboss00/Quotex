import yfinance as yf
import requests
import time
import os
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- FREE RENDER KEEP-ALIVE SERVER ---
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Target Billionaire High-Speed Engine V16.1 is Running!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# --- CONFIGURATION ---
TOKEN = "8958179212:AAGRaqegMW4WJS9KTz1MwaU5lh5wtui4HQ0"
GROUP_ID = "-5160285764"

# সেরা ১০টি পেয়ার (সবচেয়ে বেশি ভলিউম)
TICKERS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "BTC-USD", "PAXG-USD"]

last_signal_time = {}

def send_telegram_signal(pair, direction, reason):
    emoji = "🟢 CALL (BUY)" if direction == "CALL" else "🔴 PUT (SELL)"
    pair_name = pair.replace('=X', '')
    
    msg = f"""
🚨 *QUOTEX VIP SIGNAL* 🚨
-----------------------------------------
📊 *Asset:* `{pair_name}`
⏰ *Expiry:* 1 MINUTE
🎯 *Action:* **{emoji}**
💡 *Type:* `{reason}`
-----------------------------------------
⏳ *Execution:* Enter NOW at candle start!
⚠️ Use 1-Step Martingale if needed!
👑 *Target Billionaire Engine v16.1*
"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": GROUP_ID, "text": msg, "parse_mode": "Markdown"}, timeout=5)
    except: pass

def calculate_ema(prices, period):
    if len(prices) < period: return prices[-1]
    multiplier = 2 / (period + 1)
    ema = prices[0]
    for p in prices[1:]: ema = (p - ema) * multiplier + ema
    return ema

def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    print("🚀 V16.1 High-Speed Engine Active...")
    
    # স্টার্টআপ কনফার্মেশন
    requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={GROUP_ID}&text=🚀 *Signal Engine Online!* \nScanning 10 High-Volume Pairs...")

    while True:
        try:
            # একবারে সব পেয়ারের ডাটা ডাউনলোড (ম্যাসিভ স্পিড বুস্ট)
            data = yf.download(TICKERS, period="1d", interval="1m", progress=False).tail(10)
            
            for ticker in TICKERS:
                try:
                    closes = data['Close'][ticker].tolist()
                    opens = data['Open'][ticker].tolist()
                    
                    c_close, c_open = closes[-1], opens[-1]
                    ema_fast = calculate_ema(closes, 3)
                    ema_slow = calculate_ema(closes, 12)

                    # --- Dual Engine Logic ---
                    mom_call = (ema_fast > ema_slow) and (c_close > c_open) and (closes[-2] > opens[-2])
                    mom_put = (ema_fast < ema_slow) and (c_close < c_open) and (closes[-2] < opens[-2])
                    exh_put = (closes[-1] > opens[-1]) and (closes[-2] > opens[-2]) and (closes[-3] > opens[-3])
                    exh_call = (closes[-1] < opens[-1]) and (closes[-2] < opens[-2]) and (closes[-3] < opens[-3])

                    direction = None
                    reason = ""

                    if exh_put: direction, reason = "PUT", "Exhaustion Reversal 🔄"
                    elif exh_call: direction, reason = "CALL", "Exhaustion Reversal 🔄"
                    elif mom_call: direction, reason = "CALL", "Momentum Push 🚀"
                    elif mom_put: direction, reason = "PUT", "Momentum Push 📉"

                    if direction and (time.time() - last_signal_time.get(ticker, 0) > 180):
                        send_telegram_signal(ticker, direction, reason)
                        last_signal_time[ticker] = time.time()
                except: continue
                
            time.sleep(10) # প্রতি ১০ সেকেন্ডে ফুল মার্কেট স্ক্যান
        except Exception as e:
            time.sleep(10)

if __name__ == "__main__":
    main()
