import yfinance as yf
import requests
import time
import os
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# ================== RENDER KEEP-ALIVE ==================
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"TB V22 WIN-LOSS Tracker Live")

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

# ================== CONFIG ==================
TOKEN = "8958179212:AAGRaqegMW4WJS9KTz1MwaU5lh5wtui4HQ0"
GROUP_ID = "-1003927083951"   # তোমার SuperGroup ID

TICKERS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X",
    "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "EURGBP=X", "USDCHF=X"
]

last_signal = {}
pending = []   # সিগন্যাল সেভ করে WIN/LOSS চেকের জন্য

# ================== TELEGRAM ==================
def tg_send(text, reply_to=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": GROUP_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_to:
        data["reply_to_message_id"] = reply_to
    try:
        r = requests.post(url, json=data, timeout=10)
        if r.status_code == 200:
            return r.json()["result"]["message_id"]
        print("TG Error:", r.text)
        return None
    except Exception as e:
        print("TG Exception:", e)
        return None

# ================== WIN / LOSS CHECKER ==================
def check_results():
    global pending
    now = time.time()
    keep = []

    for p in pending:
        # 70 সেকেন্ডের আগে চেক করব না
        if now - p["time"] < 70:
            keep.append(p)
            continue

        try:
            df = yf.download(p["ticker"], period="1d", interval="1m", progress=False).tail(3)
            
            # multi-index fix
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            open_price = float(df["Open"].iloc[-2])
            close_price = float(df["Close"].iloc[-2])

            actual = "CALL" if close_price > open_price else "PUT"
            win = (actual == p["direction"])

            if win:
                reply = f"✅ *WIN*\nResult: `{actual}`\nPrediction was correct!"
            else:
                reply = f"❌ *LOSS*\nResult: `{actual}`\nPrediction was wrong."

            tg_send(reply, reply_to=p["msg_id"])
            print(f"Result → {p['ticker']} → {'WIN' if win else 'LOSS'}")

        except Exception as e:
            print("Result check error:", e)

    pending = keep

# ================== SIGNAL LOGIC ==================
def scan():
    try:
        data = yf.download(TICKERS, period="1d", interval="1m", progress=False).tail(5)
        now = datetime.now()

        next_m = (now.minute + 1) % 60
        next_h = now.hour if next_m != 0 else (now.hour + 1) % 24
        next_time = f"{next_h:02d}:{next_m:02d}:00"

        for ticker in TICKERS:
            try:
                c = data["Close"][ticker]
                o = data["Open"][ticker]
                h = data["High"][ticker]
                l = data["Low"][ticker]

                c0, o0 = float(c.iloc[-1]), float(o.iloc[-1])
                c1, o1 = float(c.iloc[-2]), float(o.iloc[-2])
                hi, lo = float(h.iloc[-1]), float(l.iloc[-1])

                rng = max(hi - lo, 0.00001)
                lw = min(o0, c0) - lo
                uw = hi - max(o0, c0)

                direction = None
                logic = ""

                # 1. Red Reversal → Next Green (CALL)
                if c0 < o0 and (lw / rng) > 0.35:
                    direction, logic = "CALL", "Red Reversal → Next Green"

                # 2. Green Reversal → Next Red (PUT)
                elif c0 > o0 and (uw / rng) > 0.35:
                    direction, logic = "PUT", "Green Reversal → Next Red"

                # 3. Red → Green Flip
                elif c1 < o1 and c0 > o0 and c0 > o1:
                    direction, logic = "CALL", "Red-to-Green Flip"

                # 4. Green → Red Flip
                elif c1 > o1 and c0 < o0 and c0 < o1:
                    direction, logic = "PUT", "Green-to-Red Flip"

                # 5. Green Continuation
                elif c0 > o0 and c1 > o1 and (uw / rng) < 0.15:
                    direction, logic = "CALL", "Green Continuation"

                # 6. Red Continuation
                elif c0 < o0 and c1 < o1 and (lw / rng) < 0.15:
                    direction, logic = "PUT", "Red Continuation"

                if direction and (time.time() - last_signal.get(ticker, 0) > 90):
                    pair = ticker.replace("=X", "")
                    emoji = "🟢 CALL" if direction == "CALL" else "🔴 PUT"

                    text = f"""🚨 *NEXT CANDLE SIGNAL*
---------------------------
📊 Asset: `{pair}`
🎯 Next Candle: **{emoji}**
⏳ Start: `{next_time}`
⏰ Expiry: 1 MIN
💡 Logic: `{logic}`
---------------------------
⚠️ Enter at 00 second
💡 1-Step Martingale if needed
👑 TB V22"""

                    msg_id = tg_send(text)
                    if msg_id:
                        pending.append({
                            "ticker": ticker,
                            "direction": direction,
                            "msg_id": msg_id,
                            "time": time.time()
                        })
                        last_signal[ticker] = time.time()
                        print(f"Signal sent: {pair} → {direction}")

            except:
                continue
    except Exception as e:
        print("Scan error:", e)

# ================== MAIN ==================
def main():
    threading.Thread(target=keep_alive, daemon=True).start()
    tg_send("🔮 *TB V22 WIN-LOSS Tracker Online!*\nBot will now reply WIN or LOSS under every signal.")

    while True:
        scan()
        check_results()
        time.sleep(8)

if __name__ == "__main__":
    main()
