# capture_requests.py (fixed for Selenium ≥ 4.11)
import time, json, threading
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

OUT_FILE = "captured_requests.jsonl"

def build_driver(headless=False):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--auto-open-devtools-for-tabs")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    service = Service()
    driver = webdriver.Chrome(service=service, options=opts)
    return driver

def parse_perf_log_entry(entry):
    try:
        j = json.loads(entry["message"])["message"]
        return j
    except Exception:
        return None

def capture_loop(driver, stop_event):
    seen_ids = set()
    with open(OUT_FILE, "a", encoding="utf-8") as fh:
        while not stop_event.is_set():
            for entry in driver.get_log("performance"):
                ev = parse_perf_log_entry(entry)
                if not ev:
                    continue
                method = ev.get("method")
                params = ev.get("params", {})
                if method in (
                    "Network.requestWillBeSent",
                    "Network.responseReceived",
                    "Network.loadingFinished",
                    "Network.webSocketCreated",
                    "Network.webSocketFrameReceived",
                    "Network.webSocketFrameSent",
                ):
                    rid = (params.get("requestId") or params.get("url"), method)
                    if rid in seen_ids:
                        continue
                    seen_ids.add(rid)
                    fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
                    fh.flush()
                    print(method, params.get("request", {}).get("url") or params.get("url") or "")
            time.sleep(0.5)

def main():
    driver = build_driver(headless=False)
    stop_event = threading.Event()
    t = threading.Thread(target=capture_loop, args=(driver, stop_event), daemon=True)
    t.start()

    print("Browser opened. Hãy quét QR trong cửa sổ trình duyệt vừa bật.")
    driver.get("https://chat.zalo.me/")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping capture...")
    finally:
        stop_event.set()
        t.join(timeout=5)
        driver.quit()
        print(f"Saved events to {OUT_FILE}")

if __name__ == "__main__":
    main()
