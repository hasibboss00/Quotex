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
        self.wfile.write(b"TB V32 2-Min Sniper Predictor is Active!")

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

# --- CONFIGURATION ---
TOKEN = "8958179212:AAGRaqegMW4WJS9KTz1MwaU5lh5wtui4HQ0"
GROUP_ID = "-1003927083951" 

TICKERS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "EURGBP=X", "USDCHF=X"]

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
        # টার্গেট ক্যান্ডেল শেষ হওয়ার ১০ সেকেন্ড পর চেক (sent_at + 2 min + 1 min + 10s)
        if now_epoch < (item["sent_at"] + 190): 
            still_pending.append(item)
            continue
        try:
            df = yf.download(item["ticker"], period="1d", interval="1m", progress=False).tail(5)
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            
            # টার্গেট ক্যান্ডেলের ক্লোজড ডাটা (iloc[-2])
            c_open = float(df["Open"].iloc[-2])
            c_close = float(df["Close"].iloc[-2])
            
            actual = "CALL" if c_close > c_open else "PUT"
            is_win = (actual == item["direction"])
            
            status = f"✅ *WIN* \nAsset: {item['pair']}\nResult: {actual} 🎯" if is_win else f"❌ *LOSS* \nAsset: {item['pair']}\nResult: {actual} ❌"
            send_tg(status, reply_to=item["msg_id"])
            print(f"Verified: {item['pair']} -> {'WIN' if is_win else 'LOSS'}")
        except: pass
    pending_results = still_pending

def scan_market():
    try:
        data = yf.download(TICKERS, period="1d", interval="1m", progress=False).tail(20)
        now_dt = datetime.utcnow()
        
        # ২ মিনিট পরের টার্গেট ক্যান্ডেল সময়
        target_dt = (now_dt + timedelta(minutes=2)).replace(second=0, microsecond=0)
        target_str = target_dt.strftime("%H:%M:00 UTC")

        for ticker in TICKERS:
            try:
                closes = data["Close"][ticker].tolist()
                opens = data["Open"][ticker].tolist()
                highs = data["High"][ticker].tolist()
                lows = data["Low"][ticker].tolist()
                
                c0_c, c0_o = closes[-1], opens[-1]
                c0_h, c0_l = highs[-1], lows[-1]
                
                # --- V32 SNIPER LOGIC (2-MIN AHEAD) ---
                # RSI-7 Calc
                diff = pd.Series(closes).diff()
                gain = diff.where(diff > 0, 0).rolling(7).mean().iloc[-1]
                loss = -diff.where(diff < 0, 0).rolling(7).mean().iloc[-1]
                rsi = 100 - (100 / (1 + (gain / (loss if loss != 0 else 0.001))))

                direction, logic = None, ""
                
                # ১. বলিঞ্জার রিজেকশন + RSI কনফ্লুয়েন্স
                if c0_c < c0_o and rsi < 32:
                    direction, logic = "CALL", "2-Min Oversold Surge 🚀"
                elif c0_c > c0_o and rsi > 68:
                    direction, logic = "PUT", "2-Min Overbought Drop 📉"
                # ২. কালার সিকোয়েন্স ফ্লিপ
                elif closes[-2] < opens[-2] and c0_c > c0_o:
                    direction, logic = "CALL", "Pattern Shift Prediction 🔄"
                elif closes[-2] > opens[-2] and c0_c < c0_o:
                    direction, logic = "PUT", "Pattern Shift Prediction 🔄"

                if direction and (time.time() - last_signal_time.get(ticker, 0) > 150):
                    pair = ticker.replace("=X", "")
                    emoji = "🟢 CALL (BUY)" if direction == "CALL" else "🔴 PUT (SELL)"
                    
                    msg = f"""🚨 *2-MIN ADVANCE SNIPER* 🚨
-----------------------------------------
📊 *Asset:* `{pair}`
🎯 *Target Candle:* **{emoji}**
⏳ *Trade Start:* `{target_str}` (Exact 00s)
⏰ *Expiry:* 1 MINUTE
💡 *Logic:* `{logic}`
-----------------------------------------
⚠️ *Rule:* Click exactly at `{target_str}`
👑 TB V32 Sniper Engine"""

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
    send_tg("🔮 *TB V32 2-Min Predictor Online!* \nSignals 2 mins in advance for 1-Min trades. Win/Loss reply enabled.")
    while True:
        scan_market()
        check_results()
        time.sleep(8)

if __name__ == "__main__":
    main()
