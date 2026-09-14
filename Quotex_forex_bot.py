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
        self.wfile.write(b"TB V25 Precise Multi-Strategy Engine Live")

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

def tg_send(text, reply_to=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": GROUP_ID, "text": text, "parse_mode": "Markdown"}
    if reply_to: payload["reply_to_message_id"] = reply_to
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            return r.json()["result"]["message_id"]
    except Exception as e:
        print(f"TG Send Error: {e}")
    return None

def check_results():
    global pending_results
    now = time.time()
    still_pending = []

    for item in pending_results:
        # ট্রেডের পরের ক্যান্ডেল ক্লোজ হতে অন্তত ১২০ সেকেন্ড সময় লাগে
        if now - item["sent_at"] < 115:
            still_pending.append(item)
            continue

        try:
            df = yf.download(item["ticker"], period="1d", interval="1m", progress=False).tail(4)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # প্রেডিক্ট করা ক্যান্ডেলের ওপেন ও ক্লোজ (iloc[-2] হলো প্রেডিক্ট করা ক্লোজড ক্যান্ডেল)
            c_open = float(df["Open"].iloc[-2])
            c_close = float(df["Close"].iloc[-2])

            actual = "CALL" if c_close > c_open else "PUT"
            is_win = (actual == item["direction"])

            if is_win:
                reply = f"✅ *WIN* \nAsset: `{item['pair']}`\nPredicted: `{item['direction']}` | Result: `{actual}` ✔️"
            else:
                reply = f"❌ *LOSS* \nAsset: `{item['pair']}`\nPredicted: `{item['direction']}` | Result: `{actual}` ❌"

            tg_send(reply, reply_to=item["msg_id"])
            print(f"Result Verified: {item['pair']} -> {'WIN' if is_win else 'LOSS'}")

        except Exception as e:
            print(f"Result Check Error for {item['pair']}: {e}")

    pending_results = still_pending

def scan_market():
    now_dt = datetime.utcnow()
    # ৫০ থেকে ৫৮ সেকেন্ডের মধ্যে প্রেডিকশন চালাবে
    if not (45 <= now_dt.second <= 58):
        return

    # পরবর্তী ক্যান্ডেল শুরুর সময় (যেমন: ১২:৩০:০০)
    next_candle = (now_dt + timedelta(minutes=1)).replace(second=0, microsecond=0)
    next_time_str = next_candle.strftime("%H:%M:%S UTC")

    try:
        data = yf.download(TICKERS, period="1d", interval="1m", progress=False).tail(6)
        
        for ticker in TICKERS:
            try:
                closes = [float(x) for x in data["Close"][ticker].tolist()]
                opens = [float(x) for x in data["Open"][ticker].tolist()]
                highs = [float(x) for x in data["High"][ticker].tolist()]
                lows = [float(x) for x in data["Low"][ticker].tolist()]

                c0_c, c0_o = closes[-1], opens[-1] # বর্তমান ক্যান্ডেল
                c1_c, c1_o = closes[-2], opens[-2] # আগের ক্যান্ডেল
                c2_c, c2_o = closes[-3], opens[-3] # ২ ক্যান্ডেল আগে

                c0_h, c0_l = highs[-1], lows[-1]
                rng0 = max(c0_h - c0_l, 0.00001)
                lw0 = min(c0_o, c0_c) - c0_l
                uw0 = c0_h - max(c0_o, c0_c)

                direction, logic = None, ""

                # --- MULTI-STRATEGY CONFLUENCE LOGIC ---
                
                # 1. SMC Engulfing Flip
                if c1_c < c1_o and c0_c > c0_o and c0_c > c1_o:
                    direction, logic = "CALL", "SMC Bullish Engulfing Flip 🟢"
                elif c1_c > c1_o and c0_c < c0_o and c0_c < c1_o:
                    direction, logic = "PUT", "SMC Bearish Engulfing Flip 🔴"

                # 2. Wick Rejection Pressure
                elif (lw0 / rng0) > 0.38 and c0_c > c0_o:
                    direction, logic = "CALL", "Buyer Rejection Pressure 🚀"
                elif (uw0 / rng0) > 0.38 and c0_c < c0_o:
                    direction, logic = "PUT", "Seller Rejection Pressure 📉"

                # 3. 3-Candle Exhaustion
                elif c0_c > c0_o and c1_c > c1_o and c2_c > c2_o:
                    direction, logic = "PUT", "3-Green Exhaustion Reversal 🔄"
                elif c0_c < c0_o and c1_c < c1_o and c2_c < c2_o:
                    direction, logic = "CALL", "3-Red Exhaustion Reversal 🔄"

                # 4. Momentum Push
                elif c0_c > c0_o and c1_c > c1_o and (uw0 / rng0) < 0.15:
                    direction, logic = "CALL", "Strong Bullish Momentum Push ⚡"
                elif c0_c < c0_o and c1_c < c1_o and (lw0 / rng0) < 0.15:
                    direction, logic = "PUT", "Strong Bearish Momentum Push ⚡"

                if direction and (time.time() - last_signal_time.get(ticker, 0) > 120):
                    pair = ticker.replace("=X", "")
                    emoji = "🟢 CALL (BUY)" if direction == "CALL" else "🔴 PUT (SELL)"

                    text = f"""🚨 *PREDICTIVE NEXT-CANDLE SIGNAL* 🚨
-----------------------------------------
📊 *Asset:* `{pair}`
🎯 *Next Candle:* **{emoji}**
⏳ *Trade Start:* `{next_time_str}` (Exact 00s)
⏰ *Expiry:* 1 MINUTE
💡 *Strategy:* `{logic}`
-----------------------------------------
⚠️ *Rule:* Enter exactly at 00-second of next candle!
💡 Use 1-Step Martingale if needed!
👑 *TB V25 Master Engine*"""

                    msg_id = tg_send(text)
                    if msg_id:
                        pending_results.append({
                            "ticker": ticker,
                            "pair": pair,
                            "direction": direction,
                            "msg_id": msg_id,
                            "sent_at": time.time()
                        })
                        last_signal_time[ticker] = time.time()
                        print(f"Prediction Sent: {pair} -> {direction} for {next_time_str}")

            except Exception as e:
                continue

    except Exception as e:
        print(f"Market Scan Error: {e}")

def main():
    threading.Thread(target=keep_alive, daemon=True).start()
    tg_send("🔮 *TB V25 Precise Engine Online!*\nPredicting upcoming 1m candles. WIN/LOSS verification active.")

    while True:
        scan_market()
        check_results()
        time.sleep(3)

if __name__ == "__main__":
    main()
