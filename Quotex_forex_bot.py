import yfinance as yf
import requests
import time
import os
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- KEEP-ALIVE DUMMY WEB SERVER ---
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Target Billionaire Next-Candle Predictor Active!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# --- CONFIGURATION ---
TOKEN = "8958179212:AAGRaqegMW4WJS9KTz1MwaU5lh5wtui4HQ0"
GROUP_ID = "-5160285764"

PAIRS = {
    "USD/JPY": "USDJPY=X", "EUR/JPY": "EURJPY=X", "EUR/USD": "EURUSD=X",
    "GBP/JPY": "GBPJPY=X", "AUD/JPY": "AUDJPY=X", "CAD/JPY": "CADJPY=X",
    "GBP/USD": "GBPUSD=X", "USD/CAD": "USDCAD=X", "AUD/USD": "AUDUSD=X"
}

last_signal_time = {}

def send_telegram_signal(pair_name, direction, next_minute_str):
    emoji = "🟢 CALL (BUY)" if direction == "CALL" else "🔴 PUT (SELL)"
    
    msg = f"""
🚨 *PREDICTIVE VIP SIGNAL* 🚨
-----------------------------------------
📊 *Asset:* `{pair_name}`
⏰ *Expiry:* 1 MINUTE
🎯 *Action:* **{emoji}**
⏳ *Trade Start:* `{next_minute_str}` (Exact)
-----------------------------------------
💡 *Rule:* Enter at 00-second of next candle!
⚠️ Use 1-Step Martingale if needed!
👑 *TB Predictive Engine v13.0*
"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": GROUP_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=5)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] PREDICTION SENT: {pair_name} -> {direction}")
    except Exception as e:
        print(f"Telegram Error: {e}")

def predict_next_candle(pair_name, ticker):
    try:
        # ৫ দিনের ১ মিনিটের ডাটা নেওয়া
        df = yf.download(ticker, period="1d", interval="1m", progress=False).tail(15)
        if len(df) < 10: return

        if isinstance(df.columns, pd.MultiIndex): 
            df.columns = df.columns.get_level_values(0)

        # ক্যান্ডেল তথ্য
        c = df.iloc[-1]
        c_open, c_close = c['Open'], c['Close']
        c_high, c_low = c['High'], c['Low']
        
        candle_rng = max(c_high - c_low, 0.00001)
        l_wick = min(c_open, c_close) - c_low
        u_wick = c_high - max(c_open, c_close)

        # --- PREDICTIVE PRICE ACTION LOGIC ---
        # ১. অতিরিক্ত ডাউন প্রেসার -> পরবর্তী ক্যান্ডেল হবে GREEN (CALL)
        predict_call = (l_wick / candle_rng) > 0.40 and (c_close > c_open)
        
        # ২. অতিরিক্ত আপ প্রেসার -> পরবর্তী ক্যান্ডেল হবে RED (PUT)
        predict_put = (u_wick / candle_rng) > 0.40 and (c_close < c_open)

        now = datetime.now()
        curr_t = time.time()
        
        # পরবর্তী মিনিটের টাইম তৈরি (যেমন: ১১:২৯:০০)
        next_min_time = (now.minute + 1) % 60
        next_hour_time = now.hour if next_min_time != 0 else (now.hour + 1) % 24
        next_min_str = f"{next_hour_time:02d}:{next_min_time:02d}:00 UTC"

        if (predict_call or predict_put) and (curr_t - last_signal_time.get(pair_name, 0) > 180):
            direction = "CALL" if predict_call else "PUT"
            send_telegram_signal(pair_name, direction, next_min_str)
            last_signal_time[pair_name] = curr_t

    except Exception as e:
        print(f"Prediction Error {pair_name}: {e}")

def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    print("🚀 Predictive Next-Candle Engine Active...")
    
    while True:
        # প্রতি মিনিটের ৫০-তম সেকেন্ডে স্ক্যান করবে যেন ৫৫-তম সেকেন্ডে মেসেজ যায়
        now_sec = datetime.now().second
        if now_sec >= 45 and now_sec <= 55:
            for pair_name, ticker in PAIRS.items():
                predict_next_candle(pair_name, ticker)
                time.sleep(0.3)
        time.sleep(2)

if __name__ == "__main__":
    main()
