import yfinance as yf
import requests
import time
import os
import threading
import pandas as pd
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- RENDER KEEP-ALIVE SERVER ---
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"TB V21 Result Tracker Online & Running!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# --- CONFIGURATION ---
TOKEN = "8958179212:AAGRaqegMW4WJS9KTz1MwaU5lh5wtui4HQ0"
GROUP_ID = "-1003927083951"   # আপনার সুপারগ্রুপ আইডি

TICKERS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X",
    "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "EURGBP=X", "USDCHF=X"
]

last_signal_time = {}
pending_results = []

# লাইভ স্কোরবোর্ড কাউন্টার
scoreboard = {
    "wins": 0,
    "losses": 0,
    "doji": 0
}

def send_telegram(text, reply_to=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": GROUP_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_to:
        payload["reply_to_message_id"] = reply_to

    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            return r.json()["result"]["message_id"]
        else:
            print("Telegram API Error:", r.text)
            return None
    except Exception as e:
        print("Send Error:", e)
        return None

def check_pending_results():
    """ট্রেডের মেয়াদ শেষ হলে সঠিক ক্যান্ডেলের রেজাল্ট চেক করে Reply করবে"""
    global pending_results, scoreboard
    now = time.time()
    still_pending = []

    for item in pending_results:
        # ট্রেড এক্সপায়ারির পর ১০ সেকেন্ড অপেক্ষা করবে যেন ব্রোকার/yfinance ডাটা আপডেট করতে পারে
        if now < item["expiry_timestamp"] + 10:
            still_pending.append(item)
            continue

        try:
            # সিঙ্গেল পেয়ারের লেটেস্ট ডাটা ডাউনলোড
            df = yf.download(item["ticker"], period="1d", interval="1m", progress=False)
            
            if df.empty or len(df) < 2:
                # ডাটা না পেলে সর্বোচ্চ ৩ বার ট্রাই করবে
                item["retries"] = item.get("retries", 0) + 1
                if item["retries"] <= 3:
                    still_pending.append(item)
                continue

            # MultiIndex কলাম ফিক্স
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # এক্সপায়ার হওয়া ক্যান্ডেল (শেষের আগের ক্যান্ডেলটি ক্লোজড ক্যান্ডেল)
            c_open = float(df["Open"].iloc[-2])
            c_close = float(df["Close"].iloc[-2])
            diff = c_close - c_open

            # রেজাল্ট নির্ধারণ
            if abs(diff) < 0.00001:
                result_status = "DOJI"
            elif diff > 0:
                result_status = "CALL"
            else:
                result_status = "PUT"

            pair = item["ticker"].replace("=X", "")
            
            # WIN / LOSS চেক
            if result_status == "DOJI":
                scoreboard["doji"] += 1
                reply = f"""⚠️ *TRADE RESULT: TIE / DOJI* ⚖️
━━━━━━━━━━━━━━━━━━
📊 *Asset:* `{pair}`
🎯 *Prediction:* `{item['direction']}`
📈 *Open:* `{c_open:.5f}` | *Close:* `{c_close:.5f}`
💡 *Result:* Refund / No Loss
━━━━━━━━━━━━━━━━━━
👑 *TB V21 Live Tracker*"""

            elif result_status == item["direction"]:
                scoreboard["wins"] += 1
                total_trades = scoreboard["wins"] + scoreboard["losses"]
                win_rate = (scoreboard["wins"] / total_trades) * 100 if total_trades > 0 else 100
                
                reply = f"""🎯 *TRADE RESULT: WIN* ✅
━━━━━━━━━━━━━━━━━━
📊 *Asset:* `{pair}`
🎯 *Prediction:* `{'🟢 CALL' if item['direction'] == 'CALL' else '🔴 PUT'}`
📈 *Open:* `{c_open:.5f}`
📉 *Close:* `{c_close:.5f}`
🏆 *Outcome:* **DIRECT PROFIT!** 💰
━━━━━━━━━━━━━━━━━━
📊 *Bot Score:* {scoreboard['wins']}W - {scoreboard['losses']}L ({win_rate:.1f}% Win Rate)
👑 *TB V21 Official Tracker*"""

            else:
                scoreboard["losses"] += 1
                total_trades = scoreboard["wins"] + scoreboard["losses"]
                win_rate = (scoreboard["wins"] / total_trades) * 100 if total_trades > 0 else 0
                
                reply = f"""❌ *TRADE RESULT: LOSS* 🔴
━━━━━━━━━━━━━━━━━━
📊 *Asset:* `{pair}`
🎯 *Prediction:* `{'🟢 CALL' if item['direction'] == 'CALL' else '🔴 PUT'}`
📈 *Open:* `{c_open:.5f}`
📉 *Close:* `{c_close:.5f}`
💡 *Tip:* Use 1-Step MTG if following strategy.
━━━━━━━━━━━━━━━━━━
📊 *Bot Score:* {scoreboard['wins']}W - {scoreboard['losses']}L ({win_rate:.1f}% Win Rate)
👑 *TB V21 Official Tracker*"""

            # টেলিগ্রামে সিগন্যালের মেসেজে Reply পাঠানো
            send_telegram(reply, reply_to=item["msg_id"])
            print(f"Result replied for {pair}: {result_status}")

        except Exception as e:
            print(f"Error checking result for {item['ticker']}: {e}")
            item["retries"] = item.get("retries", 0) + 1
            if item["retries"] <= 3:
                still_pending.append(item)

    pending_results = still_pending

def analyze_and_signal():
    try:
        data = yf.download(TICKERS, period="1d", interval="1m", progress=False).tail(6)
        if data.empty:
            return

        now = datetime.now()
        next_min = (now.minute + 1) % 60
        next_hour = now.hour if next_min != 0 else (now.hour + 1) % 24
        next_time_str = f"{next_hour:02d}:{next_min:02d}:00"

        # এক্সপায়ারি টাইম ক্যালকুলেশন (পরের ১ মিনিট ক্যান্ডেল ক্লোজ হওয়া পর্যন্ত)
        trade_start_ts = time.time() + (60 - now.second)
        expiry_ts = trade_start_ts + 60

        for ticker in TICKERS:
            try:
                closes = data["Close"][ticker].dropna().tolist()
                opens = data["Open"][ticker].dropna().tolist()
                highs = data["High"][ticker].dropna().tolist()
                lows = data["Low"][ticker].dropna().tolist()

                if len(closes) < 3:
                    continue

                c0_close, c0_open = closes[-1], opens[-1]
                c1_close, c1_open = closes[-2], opens[-2]
                c0_high, c0_low = highs[-1], lows[-1]

                rng = max(c0_high - c0_low, 0.00001)
                l_wick = min(c0_open, c0_close) - c0_low
                u_wick = c0_high - max(c0_open, c0_close)

                direction, logic = None, ""

                # --- সিগন্যাল লজিক ---
                if c0_close < c0_open and (l_wick / rng) > 0.35:
                    direction, logic = "CALL", "Red Reversal → Next Green 🟢"

                elif c0_close > c0_open and (u_wick / rng) > 0.35:
                    direction, logic = "PUT", "Green Reversal → Next Red 🔴"

                elif c1_close < c1_open and c0_close > c0_open and c0_close > c1_open:
                    direction, logic = "CALL", "Red-to-Green Flip → Next Green 🟢"

                elif c1_close > c1_open and c0_close < c0_open and c0_close < c1_open:
                    direction, logic = "PUT", "Green-to-Red Flip → Next Red 🔴"

                elif c0_close > c0_open and c1_close > c1_open and (u_wick / rng) < 0.15:
                    direction, logic = "CALL", "Green Push → Next Green 🟢"

                elif c0_close < c0_open and c1_close < c1_open and (l_wick / rng) < 0.15:
                    direction, logic = "PUT", "Red Push → Next Red 🔴"

                # সিগন্যাল সেন্ডিং
                if direction and (time.time() - last_signal_time.get(ticker, 0) > 120):
                    emoji = "🟢 CALL (BUY)" if direction == "CALL" else "🔴 PUT (SELL)"
                    pair = ticker.replace("=X", "")

                    text = f"""🚨 *NEXT-CANDLE COLOR PREDICTION* 🚨
━━━━━━━━━━━━━━━━━━
📊 *Asset:* `{pair}`
🎯 *Next Candle:* **{emoji}**
⏳ *Trade Start:* `{next_time_str}` (Exact 00s)
⏰ *Expiry:* 1 MINUTE
💡 *Logic:* `{logic}`
━━━━━━━━━━━━━━━━━━
⚠️ *Enter exactly at 00-second!*
💡 *1-Step Martingale (MTG) if needed*
👑 *TB V21 Automated Tracker*"""

                    msg_id = send_telegram(text)
                    if msg_id:
                        pending_results.append({
                            "ticker": ticker,
                            "direction": direction,
                            "msg_id": msg_id,
                            "expiry_timestamp": expiry_ts,
                            "retries": 0
                        })
                        last_signal_time[ticker] = time.time()
                        print(f"Signal sent: {pair} -> {direction}")

            except Exception as e:
                continue

    except Exception as e:
        print("Analyze loop error:", e)

def main():
    # Render Web Server চালু করা
    threading.Thread(target=run_web_server, daemon=True).start()
    
    send_telegram("🚀 *TB V21 Auto Result Tracker Online!*\n\n✅ বটের অটোমেটিক WIN/LOSS রিপ্লাই ট্র্যাকার চালু হয়েছে।")
    print("Bot is running...")

    while True:
        analyze_and_signal()
        check_pending_results()
        time.sleep(5)  # দ্রুত আপডেটের জন্য ৫ সেকেন্ড লুপ

if __name__ == "__main__":
    main()
