import yfinance as yf
import requests
import time
import os
import threading
import pandas as pd
import numpy as np
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- FIX DATABASE LOCKED ERROR ---
# Render/Cloud এ SQLite ডাটাবেজ লক হওয়া বন্ধ করতে ক্যাশ লোকেশন পরিবর্তন
try:
    yf.set_tz_cache_location("/tmp/yf_tz")
except Exception:
    pass

# =============================================
# --- RENDER KEEP-ALIVE WEB SERVER ---
# =============================================
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"TB V23 Pro Candle Predictor Online & Fixed!")
    def log_message(self, *a):
        pass

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

# 🔑 KEY SETTINGS — 5 মিনিটে ১-২টি High Quality Trade এর জন্য
MIN_CONFLUENCE = 4    # ৫টির মধ্যে কমপক্ষে ৪টি মিলতে হবে
COOLDOWN = 240        # ৪ মিনিট কুলডাউন

last_signal_time = {}
pending_results = []
scoreboard = {"wins": 0, "losses": 0, "doji": 0}

# =============================================
# --- TELEGRAM ---
# =============================================
def send_tg(text, reply_to=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": GROUP_ID, "text": text, "parse_mode": "Markdown"}
    if reply_to:
        payload["reply_to_message_id"] = reply_to
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            return r.json()["result"]["message_id"]
    except Exception as e:
        print("TG Send Error:", e)
    return None

# =============================================
# --- SAFE DATA FETCHING (FIX 401 & LOCK) ---
# =============================================
def fetch_safe_data(ticker):
    """Yahoo Block এড়াতে ১টি করে পেয়ার ফেচ করা"""
    try:
        df = yf.download(ticker, period="1d", interval="1m", progress=False)
        if df.empty or len(df) < 20:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        print(f"Fetch Error [{ticker}]: {e}")
        return None

# =============================================
# --- 5 PRO CANDLE STRATEGIES ---
# =============================================

def s1_consecutive_reversal(opens, closes):
    if len(closes) < 4:
        return "", ""
    colors = ["G" if closes[i] > opens[i] else "R" if closes[i] < opens[i] else "D" for i in range(-4, 0)]

    if colors[-1] == colors[-2] == colors[-3] == "G":
        return "PUT", "3x Green Streak → Next Red 🔴"
    elif colors[-1] == colors[-2] == colors[-3] == "R":
        return "CALL", "3x Red Streak → Next Green 🟢"
    return "", ""

def s2_body_exhaustion(opens, closes):
    if len(closes) < 12:
        return "", ""
    bodies = [abs(closes[i] - opens[i]) for i in range(-12, 0)]
    avg_body = np.mean(bodies[:-1])
    last_body = bodies[-1]
    if avg_body == 0:
        return "", ""

    if last_body > avg_body * 2.3:
        if closes[-1] > opens[-1]:
            return "PUT", "Big Green Exhaustion → Next Red 🔴"
        else:
            return "CALL", "Big Red Exhaustion → Next Green 🟢"
    return "", ""

def s3_wick_rejection(opens, closes, highs, lows):
    if len(opens) < 2:
        return "", ""

    def wick_ratio(o, c, h, l):
        rng = h - l
        if rng == 0:
            return 0, 0
        return (h - max(o, c)) / rng, (min(o, c) - l) / rng

    u1, l1 = wick_ratio(opens[-2], closes[-2], highs[-2], lows[-2])
    u2, l2 = wick_ratio(opens[-1], closes[-1], highs[-1], lows[-1])

    if l1 > 0.40 and l2 > 0.40:
        return "CALL", "Double Lower Wick Rejection → Next Green 🟢"
    elif u1 > 0.40 and u2 > 0.40:
        return "PUT", "Double Upper Wick Rejection → Next Red 🔴"
    return "", ""

def s4_rsi_extreme(closes, period=14):
    if len(closes) < period + 2:
        return "", ""
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    ag = np.mean(gains[-period:])
    al = np.mean(losses[-period:])
    rsi = 100 if al == 0 else 100 - (100 / (1 + ag / al))

    if rsi < 28:
        return "CALL", f"RSI({rsi:.0f}) Oversold → Next Green 🟢"
    elif rsi > 72:
        return "PUT", f"RSI({rsi:.0f}) Overbought → Next Red 🔴"
    return "", ""

def s5_engulfing_reversal(opens, closes):
    if len(opens) < 3:
        return "", ""

    p_o, p_c = opens[-2], closes[-2]
    c_o, c_c = opens[-1], closes[-1]
    p_body = abs(p_c - p_o)
    c_body = abs(c_c - c_o)

    if p_c < p_o and c_c > c_o and c_o <= p_c and c_c >= p_o and c_body > p_body * 1.1:
        return "CALL", "Bullish Engulfing → Next Green 🟢"
    elif p_c > p_o and c_c < c_o and c_o >= p_c and c_c <= p_o and c_body > p_body * 1.1:
        return "PUT", "Bearish Engulfing → Next Red 🔴"
    return "", ""

# =============================================
# --- MAIN ANALYSIS ENGINE ---
# =============================================
def analyze():
    try:
        now = datetime.now()
        nxt_m = (now.minute + 1) % 60
        nxt_h = now.hour if nxt_m != 0 else (now.hour + 1) % 24
        entry_time = f"{nxt_h:02d}:{nxt_m:02d}:00"

        trade_start = time.time() + (60 - now.second)
        expiry = trade_start + 60

        for ticker in TICKERS:
            try:
                # 안전ভাবে প্রতি পেয়ারের ডাটা আনা
                df = fetch_safe_data(ticker)
                if df is None:
                    continue

                cl = df["Close"].dropna().tolist()
                op = df["Open"].dropna().tolist()
                hi = df["High"].dropna().tolist()
                lo = df["Low"].dropna().tolist()

                if len(cl) < 20:
                    continue

                call_v, put_v = 0, 0
                reasons = []

                # 1. Consecutive
                d, r = s1_consecutive_reversal(op, cl)
                if d == "CALL": call_v += 1; reasons.append(r)
                elif d == "PUT": put_v += 1; reasons.append(r)

                # 2. Exhaustion
                d, r = s2_body_exhaustion(op, cl)
                if d == "CALL": call_v += 1; reasons.append(r)
                elif d == "PUT": put_v += 1; reasons.append(r)

                # 3. Wick Rejection
                d, r = s3_wick_rejection(op, cl, hi, lo)
                if d == "CALL": call_v += 1; reasons.append(r)
                elif d == "PUT": put_v += 1; reasons.append(r)

                # 4. RSI Extreme
                d, r = s4_rsi_extreme(cl)
                if d == "CALL": call_v += 1; reasons.append(r)
                elif d == "PUT": put_v += 1; reasons.append(r)

                # 5. Engulfing
                d, r = s5_engulfing_reversal(op, cl)
                if d == "CALL": call_v += 1; reasons.append(r)
                elif d == "PUT": put_v += 1; reasons.append(r)

                # ===== CONFLUENCE CHECK =====
                direction = None
                score = 0

                if call_v >= MIN_CONFLUENCE and call_v > put_v:
                    direction = "CALL"
                    score = call_v
                elif put_v >= MIN_CONFLUENCE and put_v > call_v:
                    direction = "PUT"
                    score = put_v

                if direction and (time.time() - last_signal_time.get(ticker, 0) > COOLDOWN):
                    pair = ticker.replace("=X", "")
                    arrow = "🟢 CALL (BUY)" if direction == "CALL" else "🔴 PUT (SELL)"
                    fire = "🔥" * score

                    if direction == "CALL":
                        candle_rule = "এই ক্যান্ডেল 🔴 RED → পরের ক্যান্ডেল 🟢 GREEN"
                    else:
                        candle_rule = "এই ক্যান্ডেল 🟢 GREEN → পরের ক্যান্ডেল 🔴 RED"

                    reason_text = "\n".join([f"  ✅ {r}" for r in reasons])

                    text = f"""🚨 *CANDLE COLOR PREDICTION* 🚨
━━━━━━━━━━━━━━━━━━━━━━
📊 *Pair:* `{pair}`
🎯 *Next Candle:* **{arrow}**
💡 *Rule:* {candle_rule}
💪 *Strength:* {fire} ({score}/5 Confirm)
⏳ *Entry:* `{entry_time}` (Exact 00s)
⏰ *Expiry:* 1 MINUTE
━━━━━━━━━━━━━━━━━━━━━━
📋 *Confirmations:*
{reason_text}
━━━━━━━━━━━━━━━━━━━━━━
⚠️ Enter at 00-second sharp!
💡 1-Step MTG if needed
👑 *TB V23 Pro Predictor*"""

                    msg_id = send_tg(text)
                    if msg_id:
                        pending_results.append({
                            "ticker": ticker,
                            "direction": direction,
                            "msg_id": msg_id,
                            "expiry_ts": expiry,
                            "score": score,
                            "retries": 0
                        })
                        last_signal_time[ticker] = time.time()
                        print(f"✅ SIGNAL: {pair} -> {direction} ({score}/5)")

                # Yahoo Rate limit বাঁচানোর জন্য সামান্য বিরতি
                time.sleep(0.3)

            except Exception as e:
                continue

    except Exception as e:
        print("Analyze loop error:", e)

# =============================================
# --- WIN/LOSS AUTO REPLY ENGINE ---
# =============================================
def check_results():
    global pending_results, scoreboard
    now = time.time()
    keep = []

    for item in pending_results:
        if now < item["expiry_ts"] + 15:
            keep.append(item)
            continue

        try:
            df = fetch_safe_data(item["ticker"])
            if df is None or len(df) < 2:
                item["retries"] = item.get("retries", 0) + 1
                if item["retries"] <= 3:
                    keep.append(item)
                continue

            c_open = float(df["Open"].iloc[-2])
            c_close = float(df["Close"].iloc[-2])
            diff = c_close - c_open

            if abs(diff) < 0.000005:
                actual = "DOJI"
            elif diff > 0:
                actual = "CALL"
            else:
                actual = "PUT"

            pair = item["ticker"].replace("=X", "")
            stars = "⭐" * item.get("score", 4)

            if actual == "DOJI":
                scoreboard["doji"] += 1
                reply = f"""⚖️ *RESULT: DOJI (TIE)*
━━━━━━━━━━━━━━━━━━
📊 `{pair}` | {stars}
🎯 Predicted: `{item['direction']}`
📈 Open: `{c_open:.5f}` → Close: `{c_close:.5f}`
💡 Trade Refund
━━━━━━━━━━━━━━━━━━
👑 *TB V23 Pro*"""

            elif actual == item["direction"]:
                scoreboard["wins"] += 1
                t = scoreboard["wins"] + scoreboard["losses"]
                wr = (scoreboard["wins"] / t) * 100 if t > 0 else 100
                reply = f"""✅ *RESULT: WIN!* 🎉💰
━━━━━━━━━━━━━━━━━━
📊 `{pair}` | {stars}
🎯 Predicted: `{'🟢 GREEN' if item['direction'] == 'CALL' else '🔴 RED'}`
✅ Actual: `{'🟢 GREEN' if actual == 'CALL' else '🔴 RED'}`
📈 Open: `{c_open:.5f}`
📉 Close: `{c_close:.5f}`
💰 *PROFIT CONFIRMED!*
━━━━━━━━━━━━━━━━━━
📊 Score: *{scoreboard['wins']}W / {scoreboard['losses']}L* ({wr:.1f}% WR)
👑 *TB V23 Pro*"""

            else:
                scoreboard["losses"] += 1
                t = scoreboard["wins"] + scoreboard["losses"]
                wr = (scoreboard["wins"] / t) * 100 if t > 0 else 0
                reply = f"""❌ *RESULT: LOSS*
━━━━━━━━━━━━━━━━━━
📊 `{pair}` | {stars}
🎯 Predicted: `{'🟢 GREEN' if item['direction'] == 'CALL' else '🔴 RED'}`
❌ Actual: `{'🟢 GREEN' if actual == 'CALL' else '🔴 RED'}`
📈 Open: `{c_open:.5f}`
📉 Close: `{c_close:.5f}`
💡 Use 1-Step MTG to recover
━━━━━━━━━━━━━━━━━━
📊 Score: *{scoreboard['wins']}W / {scoreboard['losses']}L* ({wr:.1f}% WR)
👑 *TB V23 Pro*"""

            send_tg(reply, reply_to=item["msg_id"])
            print(f"📩 Result: {pair} -> {'WIN ✅' if actual == item['direction'] else 'LOSS ❌'}")

        except Exception as e:
            print(f"Result error {item['ticker']}: {e}")
            item["retries"] = item.get("retries", 0) + 1
            if item["retries"] <= 3:
                keep.append(item)

    pending_results = keep

# =============================================
# --- MAIN LOOP ---
# =============================================
def main():
    threading.Thread(target=run_server, daemon=True).start()

    send_tg(
        "🚀 *TB V23 Pro Candle Predictor Online (Fixed)!*\n\n"
        "✅ Yahoo Finance Block & Database Lock fixed.\n"
        "🎯 *Min Confluence:* 4/5 Confirmations\n"
        "⏳ Auto WIN/LOSS Reply enabled."
    )
    print("TB V23 Pro Running Smoothly...")

    while True:
        analyze()
        check_results()
        time.sleep(8)

if __name__ == "__main__":
    main()
