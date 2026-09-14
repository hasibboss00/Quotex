import yfinance as yf
import requests
import time
import os
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- RENDER WEB SERVER ---
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Target Billionaire Debugger is Active!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# --- CONFIGURATION (এগুলো আবার চেক করো) ---
TOKEN = "8958179212:AAGRaqegMW4WJS9KTz1MwaU5lh5wtui4HQ0"
GROUP_ID = "-5160285764"

def send_msg(text):
    print(f"--- Attempting to send Telegram message: {text[:20]}... ---")
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": GROUP_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
        if r.status_code == 200:
            print("✅ Telegram Message Sent Successfully!")
            return True
        else:
            print(f"❌ Telegram Error: {r.status_code} - {r.text}")
            return False
    except Exception as e:
        print(f"❌ Connection Error to Telegram: {e}")
        return False

def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    
    # এটি বোট রান হওয়ার সাথে সাথে লগে এবং টেলিগ্রামে মেসেজ দেবে
    print("🚀 Script is starting up...")
    send_msg("🧪 *Debug Test:* Bot has just started on Render Cloud!")

    while True:
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Scanning Market...")
            
            # ডাটা ফেচিং (মাত্র ৩টি পেয়ার দিয়ে টেস্ট করছি যাতে ব্লক না করে)
            data = yf.download(["EURUSD=X", "USDJPY=X", "BTC-USD"], period="1d", interval="1m", progress=False).tail(2)
            
            if data.empty:
                print("⚠️ Yahoo Finance returned empty data.")
            else:
                # যদি ডাটা থাকে, তবে একটি টেস্ট সিগন্যাল পাঠিয়ে দেখা
                send_msg("📊 *Market Check:* Data received. Everything is fine!")
                break # একবার মেসেজ গেলে আমরা লুপ থামিয়ে দেব টেস্টের জন্য

            time.sleep(30)
        except Exception as e:
            print(f"Critical Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
