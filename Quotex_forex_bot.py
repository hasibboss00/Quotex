import yfinance as yf
import requests
import time
import os
import threading
import pandas as pd
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- RENDER KEEP-ALIVE SERVER ---
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"TB V23 Result Tracker is Active!")

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

# --- CONFIGURATION ---
TOKEN = "8958179212:AAGRaqegMW4WJS9KTz1MwaU5lh5wtui4HQ0"
GROUP_ID = "-1003927083951" 

TICKERS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X",
    "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "EURGBP=X", "USDCHF=X"
]

last_signal_time = {}
pending_results = []

# --- TELEGRAM SEND FUNCTION ---
def send_tg(text, reply_to=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": GROUP_ID, "text": text, "parse_mode": "Markdown"}
    if reply_to:
        payload["reply_to_message_id"] = reply_to
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            return r.json()["result"]["message_id"]
        return None
    except:
        return None

# --- WIN/LOSS CHECKER (Updated & Robust) ---
def check_results():
    global pending_results
    now = time.time()
    still_pending = []

    for item in pending_results:
        # ৮৫ সেকেন্ড অপেক্ষা করব যেন ইয়াহু ডাটা আপডেট হয়
        if now - item["sent_at"] < 85:
            still_pending.append(item)
            continue

        try:
            # ডাটা ফেচিং
            df = yf.download(item["ticker"], period="1d", interval="1m", progress=False).tail(5)
            if df.empty: continue

            # Multi-index হ্যান্ডলিং
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # ক্যান্ডেল অ্যানালাইসিস
            c_open = float(df["Open"].iloc[-2])
            c_close = float(df["Close"].iloc[-2])

            actual_direction = "CALL" if c_close > c_open else "PUT"
            is_win = (actual_direction == item["direction"])

            if is_win:
                status_text = f"✅ *WIN* \nAsset: {item['pair']}\nResult: {actual_direction} ✔️"
            else:
                status_text = f"❌ *LOSS* \nAsset: {item['pair']}\nResult: {actual_direction} ❌"

            send_tg(status_text, reply_to=item["msg_id"])
            print(f"Result Sent: {item['pair']} -> {'WIN' if is_win else 'LOSS'}")

        except Exception as e:
            print(f"Error checking result for {item['pair']}: {e}")

    pending_results = still_pending

# --- MARKET SCANNER ---
def scan_market():
    try:
        data = yf.download(TICKERS, period="1d", interval="1m", progress=False).tail(5)
        now = datetime.now()
        
        # টাইম ক্যালকুলেশন
        next_min = (now.minute + 1) % 60
        next_hour = now.hour if next_min != 0 else (now.hour + 1) % 24
        next_time = f"{next_hour:02d}:{next_min:02d}:00 UTC"

        for ticker in TICKERS:
            try:
                # ডাটা এক্সট্রাকশন
                c = data["Close"][ticker]
                o = data["Open"][ticker]
                h = data["High"][ticker]
                l = data["Low"][ticker]

                c0, o0 = float(c.iloc[-1]), float(o.iloc[-1])
                c1, o1 = float(c.iloc[-2]), float(o.iloc[-2])
                hi, lo = float(h.iloc[-1]), float(l.iloc[-1])

                rng = max(hi - lo, 0.00001)
                lw, uw = (min(o0, c0) - lo), (hi - max(o0, c0))

                direction, logic = None, ""

                # --- প্যাটান লজিক ---
                if c0 < o0 and (lw / rng) > 0.35: direction, logic = "CALL", "Buyer Rejection"
                elif c0 > o0 and (uw / rng) > 0.35: direction, logic = "PUT", "Seller Rejection"
                elif c1 < o1 and c0 > o0 and c0 > o1: direction, logic = "CALL", "Bullish Flip"
                elif c1 > o1 and c0 < o0 and c0 < o1: direction, logic = "PUT", "Bearish Flip"

                if direction and (time.time() - last_signal_time.get(ticker, 0) > 120):
                    pair = ticker.replace("=X", "")
                    emoji = "🟢 CALL" if direction == "CALL" else "🔴 PUT"
                    
                    msg_text = f"""🚨 *NEXT CANDLE PREDICTION*
---------------------------
📊 Asset: `{pair}`
🎯 Next Candle: **{emoji}**
⏳ Start: `{next_time}`
💡 Logic: `{logic}`
---------------------------
👑 TB Master V23 Pro"""

                    msg_id = send_tg(msg_text)
                    if msg_id:
                        pending_results.append({
                            "ticker": ticker,
                            "pair": pair,
                            "direction": direction,
                            "msg_id": msg_id,
                            "sent_at": time.time()
                        })
                        last_signal_time[ticker] = time.time()

            except: continue
    except: pass

# --- MAIN ENGINE ---
def main():
    threading.Thread(target=keep_alive, daemon=True).start()
    send_tg("🔮 *TB V23 Tracker Online!* \nBot will now reply WIN/LOSS after every candle.")

    while True:
        scan_market()
        check_results()
        time.sleep(10)

if __name__ == "__main__":
    main()
