import yfinance as yf
import requests
import time
import os
import threading
import pandas as pd
import numpy as np
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- DATABASE LOCK FIX ---
try:
    yf.set_tz_cache_location("/tmp/yf_tz")
except:
    pass

# =============================================
# --- RENDER KEEP-ALIVE ---
# =============================================
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"TB V24 Price Action Sniper Online!")
    def log_message(self, *a): pass

def run_server():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()

# =============================================
# --- CONFIG ---
# =============================================
TOKEN = "8958179212:AAGRaqegMW4WJS9KTz1MwaU5lh5wtui4HQ0"
GROUP_ID = "-1003927083951"

TICKERS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X",
    "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "EURGBP=X", "USDCHF=X"
]

last_signal_time = {}
pending_results = []
scoreboard = {"wins": 0, "losses": 0, "doji": 0}

def send_tg(text, reply_to=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": GROUP_ID, "text": text, "parse_mode": "Markdown"}
    if reply_to: payload["reply_to_message_id"] = reply_to
    try: r = requests.post(url, json=payload, timeout=10)
    except: pass

# =============================================
# --- PURE PRICE ACTION LOGIC (The Pro Way) ---
# =============================================

def analyze_price_action(df):
    """
    একজন ৩০ বছরের ট্রেডারের অভিজ্ঞতায় ১ মিনিটের সেরা ৩টি লজিক
    """
    cl = df["Close"].tolist()
    op = df["Open"].tolist()
    hi = df["High"].tolist()
    lo = df["Low"].tolist()

    # ১. সাপোর্ট এবং রেজিস্ট্যান্স লেভেল বের করা (গত ৩০ ক্যান্ডেলের)
    res_level = max(hi[-30:-1])
    sup_level = min(lo[-30:-1])
    
    curr_hi = hi[-1]
    curr_lo = lo[-1]
    curr_cl = cl[-1]
    curr_op = op[-1]
    
    # ২. রাউন্ড নাম্বার চেক (যেমন .500, .000)
    def is_round_number(price):
        p_str = f"{price:.5f}"
        return p_str.endswith("00") or p_str.endswith("50")

    # ৩. ক্যান্ডেল বডি এবং উইক এনালাইসিস
    body = abs(curr_cl - curr_op)
    u_wick = curr_hi - max(curr_cl, curr_op)
    l_wick = min(curr_cl, curr_op) - curr_lo
    
    direction, logic = None, ""

    # --- STRATEGY 1: SNR REJECTION (সবথেকে শক্তিশালী) ---
    if curr_hi >= res_level and u_wick > body:
        direction, logic = "PUT", "Strong Resistance Rejection 🏰"
    elif curr_lo <= sup_level and l_wick > body:
        direction, logic = "CALL", "Strong Support Rejection 🛡️"

    # --- STRATEGY 2: ROUND NUMBER REJECTION ---
    elif is_round_number(curr_hi) and u_wick > (body * 0.5):
        direction, logic = "PUT", "Psychological Round Number Reject 🎯"
    elif is_round_number(curr_lo) and l_wick > (body * 0.5):
        direction, logic = "CALL", "Psychological Round Number Reject 🎯"

    # --- STRATEGY 3: CANDLE EXHAUSTION (V-Shape Reversal) ---
    else:
        avg_body = np.mean([abs(cl[i]-op[i]) for i in range(-10, -1)])
        if body > (avg_body * 2.5): # হঠাৎ অস্বাভাবিক বড় ক্যান্ডেল
            if curr_cl > curr_op:
                direction, logic = "PUT", "Bullish Exhaustion (Over-Extended) 🎈"
            else:
                direction, logic = "CALL", "Bearish Exhaustion (Over-Extended) 🎈"

    return direction, logic

# =============================================
# --- CORE ENGINE ---
# =============================================
def main_process():
    try:
        now = datetime.now()
        entry_time = f"{(now.hour if (now.minute+1)<60 else (now.hour+1)%24):02d}:{(now.minute+1)%60:02d}:00"
        
        for ticker in TICKERS:
            # Yahoo Block এড়াতে সিকোয়েন্সিয়াল ডাউনলোড
            df = yf.download(ticker, period="1d", interval="1m", progress=False)
            if df is None or len(df) < 35: continue
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            direction, logic = analyze_price_action(df)
            
            # সিগন্যাল পাঠানোর শর্ত (৩ মিনিট কুলডাউন)
            if direction and (time.time() - last_signal_time.get(ticker, 0) > 180):
                pair = ticker.replace("=X", "")
                
                # Rule description
                if direction == "CALL":
                    rule = "Next Candle: 🟢 GREEN (BUY)"
                else:
                    rule = "Next Candle: 🔴 RED (SELL)"

                text = f"""🔥 *SNR PRICE ACTION SNIPER* 🔥
━━━━━━━━━━━━━━━━━━━━━━
📊 *Asset:* `{pair}`
🎯 *Action:* **{direction}**
💡 *Logic:* `{logic}`
⏳ *Entry:* `{entry_time}` (Exact 00s)
⏰ *Duration:* 1 MINUTE
━━━━━━━━━━━━━━━━━━━━━━
✅ {rule}
⚠️ Wait for the candle to close!
👑 *TB V24 EXPERT BOT*"""

                msg_id = send_tg(text)
                last_signal_time[ticker] = time.time()
                
                pending_results.append({
                    "ticker": ticker,
                    "direction": direction,
                    "msg_id": msg_id,
                    "expiry": time.time() + (60 - now.second) + 60,
                    "retries": 0
                })
                print(f"🎯 Signal: {pair} {direction}")
            
            time.sleep(0.5) # Anti-block delay

    except Exception as e:
        print(f"Error: {e}")

def check_results():
    global pending_results, scoreboard
    now = time.time()
    still_pending = []

    for item in pending_results:
        if now < item["expiry"] + 12:
            still_pending.append(item)
            continue
        
        try:
            df = yf.download(item["ticker"], period="1d", interval="1m", progress=False)
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            
            c_open = float(df["Open"].iloc[-2])
            c_close = float(df["Close"].iloc[-2])
            
            res = "CALL" if c_close > c_open else "PUT" if c_close < c_open else "DOJI"
            pair = item["ticker"].replace("=X", "")
            
            if res == "DOJI":
                scoreboard["doji"] += 1
                msg = f"⚖️ *RESULT: DOJI (REFUND)*\nAsset: {pair}\nLevel held the price."
            elif res == item["direction"]:
                scoreboard["wins"] += 1
                wr = (scoreboard["wins"] / (scoreboard["wins"] + scoreboard["losses"])) * 100
                msg = f"✅ *WINNING SNIPE!* 💰\nAsset: {pair}\nOutcome: {res}\nWin Rate: {wr:.1f}%"
            else:
                scoreboard["losses"] += 1
                wr = (scoreboard["wins"] / (scoreboard["wins"] + scoreboard["losses"])) * 100
                msg = f"❌ *LOSS (MTG 1 Needed)*\nAsset: {pair}\nOutcome: {res}\nWin Rate: {wr:.1f}%"
            
            send_tg(msg, reply_to=item["msg_id"])
        except:
            pass

    pending_results = still_pending

def main():
    threading.Thread(target=run_server, daemon=True).start()
    send_tg("🚀 *TB V24 Price Action Sniper Online!*\nNo Indicators, Only Levels & Rejection.")
    
    while True:
        main_process()
        check_results()
        time.sleep(10)

if __name__ == "__main__":
    main()
