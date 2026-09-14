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
        self.wfile.write(b"Target Billionaire Predictor V14 is Live!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# --- CONFIGURATION ---
TOKEN = "8958179212:AAGRaqegMW4WJS9KTz1MwaU5lh5wtui4HQ0"
GROUP_ID = "-5160285764"

# ২০টি পেয়ারের লিস্ট
TICKERS = [
    "USDJPY=X", "EURJPY=X", "EURUSD=X", "GBPJPY=X", "AUDJPY=X",
    "CADJPY=X", "GBPUSD=X", "USDCAD=X", "AUDUSD=X", "EURGBP=X",
    "CHFJPY=X", "EURAUD=X", "AUDCAD=X", "AUDCHF=X", "EURCAD=X",
    "EURCHF=X", "GBPAUD=X", "GBPCAD=X", "GBPCHF=X", "USDCHF=X"
]

last_signal_time = {}

def send_telegram_signal(pair, direction, next_min):
    emoji = "🟢 CALL" if direction == "CALL" else "🔴 PUT"
    msg = f"🚨 *VIP PREDICTION*\n---\n📊 Asset: {pair.replace('=X','')}\n🎯 Action: **{emoji}**\n⏳ Start: `{next_min}`\n⚠️ 1-Step Martingale\n👑 TB Engine v14.0"
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": GROUP_ID, "text": msg, "parse_mode": "Markdown"})

def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    print("🚀 Mass Fetch Engine Starting...")
    
    # শুরুতে একটি স্টার্টআপ মেসেজ
    requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={GROUP_ID}&text=🧠 *Predictor V14 Online!* \nMonitoring 20 Pairs with Anti-Block Tech.")

    while True:
        try:
            now = datetime.now()
            # শুধু প্রতি মিনিটের ৪৫-৫৫ সেকেন্ডের মধ্যে ডাটা নেবে (Next-Candle Logic)
            if 45 <= now.second <= 55:
                # একবারে সব পেয়ারের ডাটা নামানো (ম্যাসিভ অপ্টিমাইজেশন)
                data = yf.download(TICKERS, period="1d", interval="1m", progress=False).tail(5)
                
                for ticker in TICKERS:
                    try:
                        # ডাটা এক্সট্রাকশন
                        df = data['Close'][ticker]
                        df_high = data['High'][ticker]
                        df_low = data['Low'][ticker]
                        df_open = data['Open'][ticker]
                        
                        c_close, c_open = df.iloc[-1], df_open.iloc[-1]
                        c_high, c_low = df_high.iloc[-1], df_low.iloc[-1]
                        
                        candle_rng = max(c_high - c_low, 0.00001)
                        l_wick = min(c_open, c_close) - c_low
                        u_wick = c_high - max(c_open, c_close)

                        # --- লজিক: Wick Rejection ---
                        is_call = (l_wick / candle_rng) > 0.45 and c_close > c_open
                        is_put = (u_wick / candle_rng) > 0.45 and c_close < c_open

                        if (is_call or is_put) and (time.time() - last_signal_time.get(ticker, 0) > 180):
                            next_min = (now.minute + 1) % 60
                            next_time_str = f"{now.hour}:{next_min:02d}:00"
                            send_telegram_signal(ticker, "CALL" if is_call else "PUT", next_time_str)
                            last_signal_time[ticker] = time.time()
                    except: continue
                time.sleep(10) # এক মিনিট পজ
            else:
                time.sleep(2)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
