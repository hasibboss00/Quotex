import yfinance as yf
import requests
import time
import os
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- DUMMY WEB SERVER ---
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Gladiator Engine V15 is Active!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# --- CONFIG ---
TOKEN = "8958179212:AAGRaqegMW4WJS9KTz1MwaU5lh5wtui4HQ0"
GROUP_ID = "-5160285764"
TICKERS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "BTC-USD", "PAXG-USD"]

last_signal_time = {}
last_heartbeat = 0

def send_msg(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": GROUP_ID, "text": msg, "parse_mode": "Markdown"})
    except: pass

def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    global last_heartbeat
    print("🚀 Gladiator Engine Starting...")
    send_msg("⚔️ *Gladiator Engine V15 Online!* \nMode: Aggressive Next-Candle \nStatus: Scanning 20 Pairs...")

    while True:
        try:
            now = datetime.now()
            
            # --- ১৫ মিনিট পর পর হার্টবিট মেসেজ ---
            if time.time() - last_heartbeat > 900:
                send_msg("💓 *System Heartbeat:* All systems operational. Waiting for perfect setup...")
                last_heartbeat = time.time()

            # প্রতি মিনিটের ৫০-৫৫ সেকেন্ডে স্ক্যান করবে
            if 48 <= now.second <= 58:
                data = yf.download(TICKERS, period="1d", interval="1m", progress=False).tail(5)
                
                for ticker in TICKERS:
                    try:
                        c_close = data['Close'][ticker].iloc[-1]
                        c_open = data['Open'][ticker].iloc[-1]
                        c_high = data['High'][ticker].iloc[-1]
                        c_low = data['Low'][ticker].iloc[-1]
                        
                        rng = max(c_high - c_low, 0.00001)
                        l_wick = min(c_open, c_close) - c_low
                        u_wick = c_high - max(c_open, c_close)

                        # --- লজিক শিথিল করা হয়েছে (৩০% উইক) ---
                        is_call = (l_wick / rng) > 0.30 and c_close > c_open
                        is_put = (u_wick / rng) > 0.30 and c_close < c_open

                        if (is_call or is_put) and (time.time() - last_signal_time.get(ticker, 0) > 120):
                            next_m = (now.minute + 1) % 60
                            time_str = f"{now.hour}:{next_m:02d}:00"
                            side = "🟢 CALL" if is_call else "🔴 PUT"
                            pair = ticker.replace('=X','')
                            
                            alert = f"🚨 *GLADIATOR SIGNAL*\n---\n📊 Asset: `{pair}`\n🎯 Action: **{side}**\n⏳ Start: `{time_str}`\n⚠️ 1-Step Martingale\n👑 TB Engine v15"
                            send_msg(alert)
                            last_signal_time[ticker] = time.time()
                    except: continue
                time.sleep(10)
            else:
                time.sleep(1)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
