import yfinance as yf
import requests
import time
import os
import threading
import pandas as pd
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- RENDER KEEP-ALIVE SERVER ---
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"TB V31 Advance Predictor is Active!")

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

# --- CONFIGURATION ---
TOKEN = "8958179212:AAGRaqegMW4WJS9KTz1MwaU5lh5wtui4HQ0"
GROUP_ID = "-1003927083951" 

TICKERS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "EURGBP=X", "BTC-USD"]

last_signal_time = {}
pending_results = []

def send_tg(text, reply_to=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": GROUP_ID, "text": text, "parse_mode": "Markdown"}
    if reply_to: payload["reply_to_message_id"] = reply_to
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200: return r.json()["result"]["message_id"]
    except: pass
    return None

def check_results():
    global pending_results
    now_epoch = time.time()
    still_pending = []
    
    for item in pending_results:
        # টার্গেট ক্যান্ডেল শেষ হওয়ার অন্তত ১০ সেকেন্ড পর চেক (Target + 4 min + 10s)
        if now_epoch < (item["sent_at"] + 250): 
            still_pending.append(item)
            continue
        try:
            # ১ মিনিটের ডাটা নিয়ে টার্গেট ক্যান্ডেল চেক
            df = yf.download(item["ticker"], period="1d", interval="1m", progress=False).tail(10)
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            
            # টার্গেট ক্যান্ডেলের রেজাল্ট (সঠিক ক্যান্ডেল খুঁজে বের করা)
            c_open = float(df["Open"].iloc[-2])
            c_close = float(df["Close"].iloc[-2])
            
            actual = "CALL" if c_close > c_open else "PUT"
            is_win = (actual == item["direction"])
            
            status = f"✅ *WIN* \nAsset: {item['pair']}\nTarget Result: {actual} ✔️" if is_win else f"❌ *LOSS* \nAsset: {item['pair']}\nTarget Result: {actual} ❌"
            send_tg(status, reply_to=item["msg_id"])
        except: pass
    pending_results = still_pending

def scan_market():
    try:
        data = yf.download(TICKERS, period="1d", interval="1m", progress=False).tail(20)
        now_dt = datetime.utcnow()
        
        # ৩ মিনিট পরের টার্গেট সময় (যেমন: ১২:১৫ এ দিলে ১২:১৮:০০)
        target_dt = (now_dt + timedelta(minutes=3)).replace(second=0, microsecond=0)
        target_str = target_dt.strftime("%H:%M:00 UTC")

        for ticker in TICKERS:
            try:
                closes = data["Close"][ticker].tolist()
                opens = data["Open"][ticker].tolist()
                
                c0_c, c0_o = closes[-1], opens[-1]
                c1_c, c1_o = closes[-2], opens[-2]
                
                # --- V31 ADVANCE PREDICTION LOGIC ---
                # লজিক: ট্রেন্ড এবং কালার সিকোয়েন্স এনালাইসিস করে ৩ মিনিট পরের প্রেডিকশন
                direction, logic = None, ""
                
                if c0_c > c0_o and c1_c > c1_o and c0_c > closes[-5]:
                    direction, logic = "CALL", "3-Min Momentum Wave 🚀"
                elif c0_c < c0_o and c1_c < c1_o and c0_c < closes[-5]:
                    direction, logic = "PUT", "3-Min Momentum Wave 📉"
                elif c1_c < c1_o and c0_c > c0_o:
                    direction, logic = "CALL", "Advance Pattern Flip 🔄"
                elif c1_c > c1_o and c0_c < c0_o:
                    direction, logic = "PUT", "Advance Pattern Flip 🔄"

                if direction and (time.time() - last_signal_time.get(ticker, 0) > 180):
                    pair = ticker.replace("=X", "")
                    emoji = "🟢 CALL" if direction == "CALL" else "🔴 PUT"
                    
                    msg = f"""🚨 *3-MIN ADVANCE SIGNAL* 🚨
-----------------------------------------
📊 Asset: `{pair}`
🎯 Prediction: **{emoji}**
⏳ Target Candle: `{target_str}`
⏰ Expiry: 1 MINUTE
💡 Pattern: `{logic}`
-----------------------------------------
⚠️ *Rule:* Prepare now. Click at `{target_str}`
👑 TB V31 Master Engine"""

                    msg_id = send_tg(msg)
                    if msg_id:
                        pending_results.append({
                            "ticker": ticker, "pair": pair, 
                            "direction": direction, "msg_id": msg_id, 
                            "sent_at": time.time()
                        })
                        last_signal_time[ticker] = time.time()
            except: continue
    except: pass

def main():
    threading.Thread(target=keep_alive, daemon=True).start()
    send_tg("🔮 *TB V31 Advance Engine Online!* \nSignals sent 3 mins in advance. Result reply active.")
    while True:
        scan_market()
        check_results()
        time.sleep(10)

if __name__ == "__main__":
    main()
