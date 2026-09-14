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
        self.wfile.write(b"TB V27 Advance 3-Min-Ahead Predictor Engine Live")

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

# --- CONFIGURATION ---
TOKEN = "8958179212:AAGRaqegMW4WJS9KTz1MwaU5lh5wtui4HQ0"
GROUP_ID = "-1003927083951"

# ১২টি সেরা হাই-ভলিউম পেয়ার (সিগন্যাল ফ্রিকোয়েন্সি বাড়ানোর জন্য)
TICKERS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X",
    "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "EURGBP=X", "USDCHF=X",
    "CADJPY=X", "BTC-USD"
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
    now_epoch = time.time()
    still_pending = []

    for item in pending_results:
        # টার্গেট ১-মিনিটের ক্যান্ডেলটি ক্লোজ হওয়া পর্যন্ত অপেক্ষা করবে (Target Time + 75 Seconds)
        if now_epoch < item["target_epoch"] + 75:
            still_pending.append(item)
            continue

        try:
            # ১ মিনিটের ক্যান্ডেল ডাটা লোড
            df = yf.download(item["ticker"], period="1d", interval="1m", progress=False).tail(10)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # টার্গেট ক্যান্ডেলের ওপেন এবং ক্লোজ প্রাইস চেক (iloc[-2] বা আসল টার্গেট ক্যান্ডেল)
            c_open = float(df["Open"].iloc[-2])
            c_close = float(df["Close"].iloc[-2])

            actual_color = "CALL" if c_close > c_open else "PUT"
            is_win = (actual_color == item["direction"])

            actual_str = "GREEN 🟢" if actual_color == "CALL" else "RED 🔴"

            if is_win:
                reply = f"✅ *WIN (1-MIN TRADE)*\nAsset: `{item['pair']}`\nTarget Candle Result: `{actual_str}` ✔️\nPrediction was 100% Correct!"
            else:
                reply = f"❌ *LOSS (1-MIN TRADE)*\nAsset: `{item['pair']}`\nTarget Candle Result: `{actual_str}` ❌\nUse 1-Step Martingale on Next Candle!"

            tg_send(reply, reply_to=item["msg_id"])
            print(f"Result Verified for {item['pair']} Target Candle: {'WIN' if is_win else 'LOSS'}")

        except Exception as e:
            print(f"Result Check Error for {item['pair']}: {e}")

    pending_results = still_pending

def scan_market():
    now_dt = datetime.utcnow()
    
    # ৩ মিনিট পরের টার্গেট ১-মিনিটের ক্যান্ডেল সময় হিসাব (যেমন: ১১:১৪ এ সিগন্যাল দিলে টার্গেট ১১:১৭:০০)
    target_dt = (now_dt + timedelta(minutes=3)).replace(second=0, microsecond=0)
    target_str = target_dt.strftime("%H:%M:00 UTC")
    target_epoch = target_dt.timestamp()

    try:
        data = yf.download(TICKERS, period="1d", interval="1m", progress=False).tail(20)
        
        for ticker in TICKERS:
            try:
                closes = [float(x) for x in data["Close"][ticker].tolist()]
                opens = [float(x) for x in data["Open"][ticker].tolist()]
                highs = [float(x) for x in data["High"][ticker].tolist()]
                lows = [float(x) for x in data["Low"][ticker].tolist()]

                c0_c, c0_o = closes[-1], opens[-1]
                c1_c, c1_o = closes[-2], opens[-2]
                c2_c, c2_o = closes[-3], opens[-3]
                c0_h, c0_l = highs[-1], lows[-1]

                # --- 3-MIN-AHEAD ADVANCE PREDICTION LOGIC ---
                
                # Moving Average Trend
                sma5 = sum(closes[-5:]) / 5
                sma15 = sum(closes[-15:]) / 15

                rng0 = max(c0_h - c0_l, 0.00001)
                lw0 = min(c0_o, c0_c) - c0_l
                uw0 = c0_h - max(c0_o, c0_c)

                direction, logic = None, ""

                # 1. Trend Projection (৩ মিনিট পর ট্রেন্ড ধাক্কা দেবে)
                if sma5 > sma15 and c0_c > c0_o and c1_c > c1_o:
                    direction, logic = "CALL", "3-Min Advance Trend Push 🚀"
                elif sma5 < sma15 and c0_c < c0_o and c1_c < c1_o:
                    direction, logic = "PUT", "3-Min Advance Trend Drop 📉"

                # 2. Reversal Reaction Reach (৩ মিনিট পর রিভার্সাল স্পর্শ করবে)
                elif (lw0 / rng0) > 0.35 and c0_c > c0_o:
                    direction, logic = "CALL", "Buyer Rejection Wave Projection 🟢"
                elif (uw0 / rng0) > 0.35 and c0_c < c0_o:
                    direction, logic = "PUT", "Seller Rejection Wave Projection 🔴"

                # 3. Pattern Color Flip Sequence
                elif c1_c < c1_o and c0_c > c0_o and c0_c > c1_o:
                    direction, logic = "CALL", "Bullish Engulfing Sequence 🟢"
                elif c1_c > c1_o and c0_c < c0_o and c0_c < c1_o:
                    direction, logic = "PUT", "Bearish Engulfing Sequence 🔴"

                # একই পেয়ারে ২.৫ মিনিটের গ্যাপ রাখা হচ্ছে
                if direction and (time.time() - last_signal_time.get(ticker, 0) > 150):
                    pair = ticker.replace("=X", "")
                    emoji = "🟢 CALL (BUY)" if direction == "CALL" else "🔴 PUT (SELL)"

                    text = f"""🚨 *3-MIN ADVANCE PREDICTIVE SIGNAL* 🚨
-----------------------------------------
📊 *Asset:* `{pair}`
🎯 *Target Candle:* **{emoji}**
⏳ *Trade Start:* `{target_str}` (Exact 00s)
⏰ *Expiry:* **1 MINUTE** (Single Candle)
💡 *Logic:* `{logic}`
-----------------------------------------
⚠️ *Instructions:*
1. Open Quotex & set Asset: `{pair}`
2. Set Expiry to **1 MINUTE**
3. Click **{emoji}** exactly at `{target_str}`
👑 *TB V27 Advance Engine*"""

                    msg_id = tg_send(text)
                    if msg_id:
                        pending_results.append({
                            "ticker": ticker,
                            "pair": pair,
                            "direction": direction,
                            "msg_id": msg_id,
                            "target_epoch": target_epoch,
                            "sent_at": time.time()
                        })
                        last_signal_time[ticker] = time.time()
                        print(f"Advance Signal Sent: {pair} -> {direction} for Target: {target_str}")

            except Exception as e:
                continue

    except Exception as e:
        print(f"Market Scan Error: {e}")

def main():
    threading.Thread(target=keep_alive, daemon=True).start()
    tg_send("🔮 *TB V27 Advance Predictor Online!*\nSending signals 3 minutes in advance for 1-Minute Expiry trades. WIN/LOSS tracker active.")

    while True:
        scan_market()
        check_results()
        time.sleep(5) # প্রতি ৫ সেকেন্ডে স্ক্যান

if __name__ == "__main__":
    main()
