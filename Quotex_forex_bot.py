import yfinance as yf
import requests
import time
import os
import threading
import pandas as pd
import numpy as np
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# =============================================
# --- RENDER KEEP-ALIVE SERVER ---
# =============================================
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"TB V22 Pro Confluence Tracker Online!")
    def log_message(self, format, *args):
        pass  # লগ বন্ধ

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# =============================================
# --- CONFIGURATION ---
# =============================================
TOKEN = "8958179212:AAGRaqegMW4WJS9KTz1MwaU5lh5wtui4HQ0"
GROUP_ID = "-1003927083951"

TICKERS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X",
    "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "EURGBP=X", "USDCHF=X"
]

MIN_CONFLUENCE = 3  # কমপক্ষে ৩টি স্ট্র্যাটেজি মিলতে হবে

last_signal_time = {}
pending_results = []
scoreboard = {"wins": 0, "losses": 0, "doji": 0}

# =============================================
# --- TELEGRAM SENDER ---
# =============================================
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
            print("TG Error:", r.status_code, r.text[:200])
            return None
    except Exception as e:
        print("Send Error:", e)
        return None

# =============================================
# --- ৫টি প্রফেশনাল স্ট্র্যাটেজি ---
# =============================================

def calc_rsi(closes, period=14):
    """Strategy 1: RSI Reversal"""
    if len(closes) < period + 1:
        return None, ""
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100, ""
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    if rsi < 30:
        return rsi, "CALL"
    elif rsi > 70:
        return rsi, "PUT"
    return rsi, ""

def calc_ema_cross(closes):
    """Strategy 2: EMA 9/21 Crossover"""
    if len(closes) < 22:
        return ""
    ema9 = pd.Series(closes).ewm(span=9, adjust=False).mean()
    ema21 = pd.Series(closes).ewm(span=21, adjust=False).mean()

    # বর্তমান এবং আগের ক্রস চেক
    curr_diff = ema9.iloc[-1] - ema21.iloc[-1]
    prev_diff = ema9.iloc[-2] - ema21.iloc[-2]

    if curr_diff > 0 and prev_diff <= 0:
        return "CALL"  # Fresh bullish cross
    elif curr_diff < 0 and prev_diff >= 0:
        return "PUT"   # Fresh bearish cross
    elif curr_diff > 0:
        return "CALL_TREND"
    elif curr_diff < 0:
        return "PUT_TREND"
    return ""

def calc_bollinger(closes, period=20, std_dev=2):
    """Strategy 3: Bollinger Band Bounce"""
    if len(closes) < period:
        return ""
    sma = np.mean(closes[-period:])
    std = np.std(closes[-period:])
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    current = closes[-1]
    prev = closes[-2]

    # প্রাইস Lower Band ছুঁয়ে উপরে উঠছে
    if prev <= lower and current > lower:
        return "CALL"
    # প্রাইস Upper Band ছুঁয়ে নিচে নামছে
    elif prev >= upper and current < upper:
        return "PUT"
    return ""

def calc_engulfing(opens, closes):
    """Strategy 4: Engulfing Candle Pattern"""
    if len(opens) < 2 or len(closes) < 2:
        return ""
    prev_open, prev_close = opens[-2], closes[-2]
    curr_open, curr_close = opens[-1], closes[-1]

    prev_body = prev_close - prev_open
    curr_body = curr_close - curr_open

    # Bullish Engulfing: আগেরটা Red, বর্তমান Green এবং বড়
    if prev_body < 0 and curr_body > 0 and curr_open <= prev_close and curr_close >= prev_open:
        return "CALL"
    # Bearish Engulfing: আগেরটা Green, বর্তমান Red এবং বড়
    elif prev_body > 0 and curr_body < 0 and curr_open >= prev_close and curr_close <= prev_open:
        return "PUT"
    return ""

def calc_pinbar(opens, closes, highs, lows):
    """Strategy 5: Pin Bar / Hammer Reversal"""
    if len(opens) < 1:
        return ""
    o, c, h, l = opens[-1], closes[-1], highs[-1], lows[-1]
    body = abs(c - o)
    rng = h - l
    if rng == 0:
        return ""

    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l

    # Hammer (Bullish Pin Bar): Long lower wick, small body at top
    if lower_wick > body * 2.5 and lower_wick > rng * 0.6 and upper_wick < body * 0.5:
        return "CALL"
    # Shooting Star (Bearish Pin Bar): Long upper wick, small body at bottom
    elif upper_wick > body * 2.5 and upper_wick > rng * 0.6 and lower_wick < body * 0.5:
        return "PUT"
    return ""

# =============================================
# --- MAIN ANALYSIS ENGINE ---
# =============================================
def analyze_and_signal():
    try:
        # বেশি ডাটা দরকার EMA/RSI এর জন্য
        data = yf.download(TICKERS, period="5d", interval="1m", progress=False)
        if data.empty:
            return

        now = datetime.now()
        next_min = (now.minute + 1) % 60
        next_hour = now.hour if next_min != 0 else (now.hour + 1) % 24
        next_time_str = f"{next_hour:02d}:{next_min:02d}:00"

        trade_start_ts = time.time() + (60 - now.second)
        expiry_ts = trade_start_ts + 60

        for ticker in TICKERS:
            try:
                # ডাটা এক্সট্রাক্ট
                if len(TICKERS) > 1 and isinstance(data.columns, pd.MultiIndex):
                    closes = data["Close"][ticker].dropna().tolist()
                    opens = data["Open"][ticker].dropna().tolist()
                    highs = data["High"][ticker].dropna().tolist()
                    lows = data["Low"][ticker].dropna().tolist()
                else:
                    closes = data["Close"].dropna().tolist()
                    opens = data["Open"].dropna().tolist()
                    highs = data["High"].dropna().tolist()
                    lows = data["Low"].dropna().tolist()

                if len(closes) < 25:
                    continue

                # === ৫টি স্ট্র্যাটেজি রান ===
                call_votes = 0
                put_votes = 0
                active_strategies = []

                # 1. RSI
                rsi_val, rsi_dir = calc_rsi(closes)
                if rsi_dir == "CALL":
                    call_votes += 1
                    active_strategies.append(f"RSI({rsi_val:.0f}) Oversold")
                elif rsi_dir == "PUT":
                    put_votes += 1
                    active_strategies.append(f"RSI({rsi_val:.0f}) Overbought")

                # 2. EMA Cross
                ema_dir = calc_ema_cross(closes)
                if ema_dir in ["CALL", "CALL_TREND"]:
                    call_votes += 1
                    active_strategies.append("EMA 9/21 Bullish")
                elif ema_dir in ["PUT", "PUT_TREND"]:
                    put_votes += 1
                    active_strategies.append("EMA 9/21 Bearish")

                # 3. Bollinger
                bb_dir = calc_bollinger(closes)
                if bb_dir == "CALL":
                    call_votes += 1
                    active_strategies.append("BB Lower Bounce")
                elif bb_dir == "PUT":
                    put_votes += 1
                    active_strategies.append("BB Upper Reject")

                # 4. Engulfing
                eng_dir = calc_engulfing(opens, closes)
                if eng_dir == "CALL":
                    call_votes += 1
                    active_strategies.append("Bullish Engulfing")
                elif eng_dir == "PUT":
                    put_votes += 1
                    active_strategies.append("Bearish Engulfing")

                # 5. Pin Bar
                pin_dir = calc_pinbar(opens, closes, highs, lows)
                if pin_dir == "CALL":
                    call_votes += 1
                    active_strategies.append("Hammer Pin Bar")
                elif pin_dir == "PUT":
                    put_votes += 1
                    active_strategies.append("Shooting Star")

                # === CONFLUENCE CHECK ===
                direction = None
                confluence_count = 0

                if call_votes >= MIN_CONFLUENCE and call_votes > put_votes:
                    direction = "CALL"
                    confluence_count = call_votes
                elif put_votes >= MIN_CONFLUENCE and put_votes > call_votes:
                    direction = "PUT"
                    confluence_count = put_votes

                # শুধুমাত্র Strong Confluence হলেই সিগন্যাল
                if direction and (time.time() - last_signal_time.get(ticker, 0) > 180):
                    emoji = "🟢 CALL (BUY)" if direction == "CALL" else "🔴 PUT (SELL)"
                    pair = ticker.replace("=X", "")
                    strength = "🔥🔥🔥" if confluence_count >= 4 else "🔥🔥"

                    strategies_text = "\n".join([f"  ✅ {s}" for s in active_strategies])

                    text = f"""🚨 *PRO CONFLUENCE SIGNAL* 🚨
━━━━━━━━━━━━━━━━━━
📊 *Asset:* `{pair}`
🎯 *Direction:* **{emoji}**
💪 *Strength:* {strength} ({confluence_count}/5 Match)
⏳ *Entry:* `{next_time_str}` (00s)
⏰ *Expiry:* 1 MINUTE
━━━━━━━━━━━━━━━━━━
📋 *Active Confirmations:*
{strategies_text}
━━━━━━━━━━━━━━━━━━
⚠️ Enter at 00-second!
💡 1-Step MTG if needed
👑 *TB V22 Pro Tracker*"""

                    msg_id = send_telegram(text)
                    if msg_id:
                        pending_results.append({
                            "ticker": ticker,
                            "direction": direction,
                            "msg_id": msg_id,
                            "expiry_timestamp": expiry_ts,
                            "confluence": confluence_count,
                            "retries": 0
                        })
                        last_signal_time[ticker] = time.time()
                        print(f"✅ SIGNAL: {pair} -> {direction} ({confluence_count}/5)")

            except Exception as e:
                continue

    except Exception as e:
        print("Analyze error:", e)

# =============================================
# --- RESULT CHECKER (WIN/LOSS REPLY) ---
# =============================================
def check_pending_results():
    global pending_results, scoreboard
    now = time.time()
    still_pending = []

    for item in pending_results:
        if now < item["expiry_timestamp"] + 12:
            still_pending.append(item)
            continue

        try:
            df = yf.download(item["ticker"], period="1d", interval="1m", progress=False)
            if df.empty or len(df) < 2:
                item["retries"] = item.get("retries", 0) + 1
                if item["retries"] <= 3:
                    still_pending.append(item)
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            c_open = float(df["Open"].iloc[-2])
            c_close = float(df["Close"].iloc[-2])
            diff = c_close - c_open

            if abs(diff) < 0.00001:
                result_status = "DOJI"
            elif diff > 0:
                result_status = "CALL"
            else:
                result_status = "PUT"

            pair = item["ticker"].replace("=X", "")
            conf = item.get("confluence", 3)
            stars = "⭐" * conf

            if result_status == "DOJI":
                scoreboard["doji"] += 1
                reply = f"""⚖️ *RESULT: DOJI / TIE*
━━━━━━━━━━━━━━━━━━
📊 `{pair}` | Prediction: `{item['direction']}`
📈 Open: `{c_open:.5f}` → Close: `{c_close:.5f}`
💡 Refund Trade
━━━━━━━━━━━━━━━━━━
👑 *TB V22 Pro Tracker*"""

            elif result_status == item["direction"]:
                scoreboard["wins"] += 1
                total = scoreboard["wins"] + scoreboard["losses"]
                wr = (scoreboard["wins"] / total) * 100 if total > 0 else 100
                reply = f"""✅ *RESULT: WIN!* 🎉
━━━━━━━━━━━━━━━━━━
📊 `{pair}` | {stars}
🎯 Prediction: `{'🟢 CALL' if item['direction'] == 'CALL' else '🔴 PUT'}`
📈 Open: `{c_open:.5f}`
📉 Close: `{c_close:.5f}`
💰 *PROFIT CONFIRMED!*
━━━━━━━━━━━━━━━━━━
📊 Score: *{scoreboard['wins']}W - {scoreboard['losses']}L* ({wr:.1f}%)
👑 *TB V22 Pro Tracker*"""

            else:
                scoreboard["losses"] += 1
                total = scoreboard["wins"] + scoreboard["losses"]
                wr = (scoreboard["wins"] / total) * 100 if total > 0 else 0
                reply = f"""❌ *RESULT: LOSS*
━━━━━━━━━━━━━━━━━━
📊 `{pair}` | {stars}
🎯 Prediction: `{'🟢 CALL' if item['direction'] == 'CALL' else '🔴 PUT'}`
📈 Open: `{c_open:.5f}`
📉 Close: `{c_close:.5f}`
💡 Use 1-Step MTG
━━━━━━━━━━━━━━━━━━
📊 Score: *{scoreboard['wins']}W - {scoreboard['losses']}L* ({wr:.1f}%)
👑 *TB V22 Pro Tracker*"""

            send_telegram(reply, reply_to=item["msg_id"])
            print(f"📩 Result: {pair} -> {result_status} ({'WIN' if result_status == item['direction'] else 'LOSS'})")

        except Exception as e:
            print(f"Result error {item['ticker']}: {e}")
            item["retries"] = item.get("retries", 0) + 1
            if item["retries"] <= 3:
                still_pending.append(item)

    pending_results = still_pending

# =============================================
# --- MAIN LOOP ---
# =============================================
def main():
    threading.Thread(target=run_web_server, daemon=True).start()

    send_telegram(
        "🚀 *TB V22 Pro Confluence Tracker Online!*\n\n"
        "📋 *5 Strategies Active:*\n"
        "1️⃣ RSI Reversal\n"
        "2️⃣ EMA 9/21 Crossover\n"
        "3️⃣ Bollinger Band Bounce\n"
        "4️⃣ Engulfing Pattern\n"
        "5️⃣ Pin Bar / Hammer\n\n"
        f"🎯 *Min Confluence:* {MIN_CONFLUENCE}/5\n"
        "💡 Only signals when 3+ strategies agree!\n"
        "⏳ Auto WIN/LOSS reply enabled."
    )
    print("TB V22 Pro running...")

    while True:
        analyze_and_signal()
        check_pending_results()
        time.sleep(8)

if __name__ == "__main__":
    main()
