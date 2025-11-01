# zalo_gui_group_qr_auto_fixed.py
import sys, time, json, traceback, urllib.parse
from PyQt6 import QtWidgets, QtCore
import requests

# zlapi import
from zlapi.simple import ZaloAPI

# browser control
try:
    import undetected_chromedriver as uc
    def browser_builder():
        from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
        caps = DesiredCapabilities.CHROME.copy()
        caps["goog:loggingPrefs"] = {"performance": "ALL"}  # 🔥 Bật performance log
        options = uc.ChromeOptions()
        options.add_argument("--start-maximized")
        return uc.Chrome(options=options, desired_capabilities=caps)
except Exception:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
    def browser_builder():
        caps = DesiredCapabilities.CHROME.copy()
        caps["goog:loggingPrefs"] = {"performance": "ALL"}  # 🔥 Bật performance log
        opts = Options()
        opts.add_argument("--start-maximized")
        return webdriver.Chrome(options=opts, desired_capabilities=caps)


# --- Config ---
REQUIRED_COOKIE_KEYS = ["__zi", "zpsid", "zpw_sek", "_zlang", "app.event.zalo.me"]
POLL_INTERVAL = 1.0
POLL_TIMEOUT = 180  # seconds waiting for cookies + localStorage

# --- GUI / Logic ---
class ZaloGroupGUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Zalo Group ID (QR → auto secret_key)")
        self.setGeometry(300, 200, 720, 520)
        layout = QtWidgets.QVBoxLayout(self)

        self.status_label = QtWidgets.QLabel("Trạng thái: Chưa mở trình duyệt")
        layout.addWidget(self.status_label)

        h = QtWidgets.QHBoxLayout()
        self.open_btn = QtWidgets.QPushButton("Mở trình duyệt (Scan QR)")
        self.open_btn.clicked.connect(self.open_browser)
        h.addWidget(self.open_btn)

        self.close_btn = QtWidgets.QPushButton("Đóng trình duyệt")
        self.close_btn.clicked.connect(self.close_browser)
        self.close_btn.setEnabled(False)
        h.addWidget(self.close_btn)
        layout.addLayout(h)

        self.group_input = QtWidgets.QLineEdit()
        self.group_input.setPlaceholderText("Nhập link nhóm https://zalo.me/g/xxx hoặc group_code")
        layout.addWidget(self.group_input)

        self.check_btn = QtWidgets.QPushButton("Lấy Group ID")
        self.check_btn.clicked.connect(self.on_check_group)
        self.check_btn.setEnabled(False)
        layout.addWidget(self.check_btn)

        self.output_box = QtWidgets.QTextEdit()
        self.output_box.setReadOnly(True)
        layout.addWidget(self.output_box)

        self.driver = None
        self.client = ZaloAPI(phone=None, password=None, imei="gui-imei-xyz", auto_login=False)
        self.session_cookies = None
        self.local_storage = None
        self.secret_key = None
        self.user_agent = "Mozilla/5.0"

    def log(self, *args):
        txt = " ".join(str(a) for a in args)
        self.output_box.append(txt)
        self.output_box.ensureCursorVisible()

    def open_browser(self):
        try:
            self.status_label.setText("Mở trình duyệt... (đợi)")
            self.log("Mở trình duyệt. Hãy quét QR trong cửa sổ trình duyệt vừa bật.")
            self.driver = browser_builder()
            self.driver.get("https://chat.zalo.me/")
            self.open_btn.setEnabled(False)
            self.close_btn.setEnabled(True)
            self.start_time = time.time()
            QtCore.QTimer.singleShot(1000, self.poll_for_session)
        except Exception as e:
            self.status_label.setText(f"Không mở được browser: {e}")
            self.log("Lỗi mở browser:", e, traceback.format_exc())

    def close_browser(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
        self.driver = None
        self.open_btn.setEnabled(True)
        self.close_btn.setEnabled(False)
        self.check_btn.setEnabled(bool(self.secret_key))
        self.status_label.setText("Trình duyệt đã đóng")
        self.log("Trình duyệt đóng.")

    def poll_for_session(self):
        if not self.driver:
            return
        elapsed = time.time() - getattr(self, "start_time", 0)
        if elapsed > POLL_TIMEOUT:
            self.status_label.setText("Timeout chờ login (QR). Hãy thử lại.")
            self.log("Timeout chờ cookies/localStorage.")
            return

        try:
            cookies_list = self.driver.get_cookies()
            cookies = {c["name"]: c["value"] for c in cookies_list}
            try:
                local_json = self.driver.execute_script("return JSON.stringify(window.localStorage);")
                local = json.loads(local_json or "{}")
            except Exception:
                local = {}

            present = [k for k in REQUIRED_COOKIE_KEYS if k in cookies]
            z_uuid = local.get("z_uuid") or local.get("z_uuid_")
            status = f"Cookies: {present} | z_uuid: {'yes' if z_uuid else 'no'}"
            self.status_label.setText(status)
            self.log(status)

            if all(k in cookies for k in REQUIRED_COOKIE_KEYS) and z_uuid:
                self.session_cookies = cookies
                self.local_storage = local
                self.user_agent = self.driver.execute_script("return navigator.userAgent;")
                self.log("Cookies + localStorage thu thập xong. Gọi getLoginInfo để lấy secret_key...")
                got = self.obtain_secret_key(cookies, z_uuid)
                if got:
                    self.status_label.setText(f"✅ Đã login, secret_key thu được: {self.secret_key}")
                    self.log(f"✅ secret_key thu được: {self.secret_key}")
                    try:
                        self.client._state._cookies = cookies
                        self.client._state._config["secret_key"] = self.secret_key
                    except Exception as e:
                        self.log("Không set state zlapi:", e)
                    self.check_btn.setEnabled(True)
                    return
                else:
                    self.log("Không lấy được secret_key. Có thể thử chờ thêm hoặc refresh QR.")
                    return
        except Exception as e:
            self.log("Lỗi poll:", e)

        QtCore.QTimer.singleShot(int(POLL_INTERVAL * 1000), self.poll_for_session)

    def obtain_secret_key(self, cookies, z_uuid):
        try:
            ua = self.driver.execute_script("return navigator.userAgent;")
            imei = z_uuid
            ts = int(time.time())
            url = f"https://wpa.chat.zalo.me/api/login/getLoginInfo?imei={imei}&type=30&client_version=645&computer_name=Web&ts={ts}"
            headers = {
                "User-Agent": ua,
                "Accept": "application/json",
                "Referer": "https://chat.zalo.me/",
                "Origin": "https://chat.zalo.me"
            }

            r = requests.get(url, headers=headers, cookies=cookies, timeout=12)
            try:
                j = r.json()
            except Exception:
                self.log("getLoginInfo: không parse JSON:", r.text[:300])
                return False

            if j.get("error_code") == 0 and j.get("data"):
                zpw_enk = j["data"].get("zpw_enk")
                if zpw_enk:
                    self.secret_key = zpw_enk
                    self.log("getLoginInfo trả zpw_enk (secret_key).")
                    return True

            elif j.get("error_code") == 602:
                self.log("getLoginInfo báo lỗi 602 → thử lại với zpw_type=30")
                time.sleep(2)
                retry_url = url.replace("type=30", "zpw_type=30")
                r2 = requests.get(retry_url, headers=headers, cookies=cookies, timeout=12)
                try:
                    j2 = r2.json()
                except Exception:
                    self.log("Retry không parse JSON:", r2.text[:300])
                    return False
                zpw_enk = j2.get("data", {}).get("zpw_enk")
                if zpw_enk:
                    self.secret_key = zpw_enk
                    self.log("Retry thành công → secret_key:", zpw_enk)
                    return True
                self.log("Retry vẫn lỗi:", j2)
                return False

            else:
                self.log("getLoginInfo trả lỗi:", j)
                return False

        except Exception as e:
            self.log("Lỗi gọi getLoginInfo:", e, traceback.format_exc())
            return False

    def get_group_info_by_params(self, params_value):
        try:
            if not self.session_cookies or not self.secret_key:
                self.log("Chưa có session/secret_key. Quét QR trước.")
                return None

            url = "https://tt-group-wpa.chat.zalo.me/api/group/link/ginfo"
            params = {"zpw_ver": 669, "zpw_type": 30, "params": params_value}
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://chat.zalo.me/",
                "Origin": "https://chat.zalo.me"
            }

            self.log("Gọi ginfo với params (cắt ngắn):", params_value[:60] + "..." if len(params_value) > 60 else params_value)
            r = requests.get(url, params=params, cookies=self.session_cookies, headers=headers, timeout=15)
            try:
                j = r.json()
            except Exception:
                self.log("ginfo: không parse JSON, raw:", r.text[:800])
                return None

            if j.get("error_code") != 0:
                self.log("ginfo trả lỗi:", json.dumps(j, ensure_ascii=False))
                return None

            enc = j.get("data") or j.get("payload") or j.get("enc")
            if not enc:
                self.log("ginfo trả data trực tiếp:", json.dumps(j.get("data"), ensure_ascii=False))
                return j.get("data")

            # try zlapi decode
            try:
                self.client._state._cookies = self.session_cookies
                self.client._state._config["secret_key"] = self.secret_key
                decoded = self.client._decode(enc)
                if decoded:
                    self.log("ginfo decoded bằng zlapi.")
                    return decoded
            except Exception as e:
                self.log("Không decode bằng zlapi:", e)

            # fallback AES-ECB
            try:
                from base64 import b64decode
                from Crypto.Cipher import AES
                import hashlib
                raw = b64decode(enc)
                key = hashlib.md5(self.secret_key.encode()).digest()
                cipher = AES.new(key, AES.MODE_ECB)
                dec = cipher.decrypt(raw)
                pad = dec[-1]
                payload = dec[:-pad].decode(errors="ignore")
                decoded = json.loads(payload)
                self.log("ginfo decoded bằng AES-ECB fallback.")
                return decoded
            except Exception as e:
                self.log("Fallback decode ginfo thất bại:", e)
                return None

        except Exception as e:
            self.log("Lỗi khi gọi get_group_info_by_params:", e, traceback.format_exc())
            return None

    def extract_all_ginfo_params(self, timeout=8):
        """
        Đọc performance log và lấy *tất cả* params của /ginfo
        Trả về list params_value (chuỗi base64)
        """
        if not self.driver:
            return []
        end = time.time() + timeout
        seen_urls = set()
        found_params = []
        while time.time() < end:
            try:
                logs = []
                try:
                    logs = self.driver.get_log("performance")
                except Exception:
                    pass
                for entry in logs:
                    try:
                        msg = json.loads(entry["message"])["message"]
                    except Exception:
                        continue
                    if msg.get("method") != "Network.requestWillBeSent":
                        continue
                    req = msg.get("params", {}).get("request", {})
                    url = req.get("url", "")
                    if "/api/group/link/ginfo" in url and url not in seen_urls:
                        seen_urls.add(url)
                        q = urllib.parse.urlparse(url).query
                        qd = dict(urllib.parse.parse_qsl(q, keep_blank_values=True))
                        params_val = qd.get("params")
                        if params_val:
                            found_params.append(params_val)
            except Exception:
                pass
            time.sleep(0.5)
        return found_params


    def on_check_group(self):
        link = self.group_input.text().strip()
        if not link:
            self.log("Nhập link nhóm.")
            return
        if not self.secret_key or not self.session_cookies:
            self.log("Chưa có session hợp lệ. Quét QR trước.")
            return

        from urllib.parse import urlparse, unquote
        def clean_link(url):
            p = urlparse(url)
            path = unquote(p.path)
            parts = [seg for seg in path.split('/') if seg]
            if len(parts) >= 2 and parts[-2] == 'g':
                return f"https://zalo.me/g/{parts[-1]}"
            return url.strip()

        cleaned_link = clean_link(link)
        self.log(f"Link đã làm sạch: {cleaned_link}")

        # --- Bắt tất cả ginfo từ performance logs ---
        self.log("⏳ Đang quét tất cả request /ginfo trong performance log...")
        all_params = self.extract_all_ginfo_params(timeout=10)
        if not all_params:
            self.log("❌ Không thấy request /ginfo nào trong performance log.")
            return
        self.log(f"Tìm thấy {len(all_params)} params ginfo.")

        all_members = []
        for i, params_val in enumerate(all_params, start=1):
            self.log(f"\n--- 🔹 GINFO #{i}/{len(all_params)} ---")
            decoded = self.get_group_info_by_params(params_val)
            if decoded:
                self.log("✅ Giải mã thành công:")
                self.log(json.dumps(decoded, ensure_ascii=False, indent=2))
                # nếu có members
                members = decoded.get("members") or decoded.get("participant_list") or []
                all_members.extend(members)
            else:
                self.log("⚠️ Không giải mã được ginfo này.")

        if all_members:
            self.log(f"\n=== 🧩 Tổng cộng lấy được {len(all_members)} thành viên ===")
            try:
                uniq = {m.get('uid') or m.get('userId'): m for m in all_members if m.get('uid') or m.get('userId')}
                self.log(f"🧠 Sau khi lọc trùng: {len(uniq)} thành viên duy nhất")
            except Exception:
                pass
        else:
            self.log("Không lấy được danh sách thành viên nào.")


    def join_group_via_link(self, link):
        try:
            if not self.session_cookies or not self.secret_key:
                self.log("Chưa có session/secret_key. Quét QR trước.")
                return None

            try:
                self.client._state._cookies = self.session_cookies
                self.client._state._config["secret_key"] = self.secret_key
            except Exception as e:
                self.log("Không thể set state cho zlapi:", e)

            payload_obj = {"link": str(link), "clientLang": "vi"}
            try:
                encoded = self.client._encode(payload_obj)
            except Exception as e:
                self.log("Lỗi encode payload bằng zlapi, abort:", e)
                return None

            url = "https://tt-group-wpa.chat.zalo.me/api/group/link/join"
            params = {"zpw_type": 30, "zpw_ver": 669}
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "Referer": "https://chat.zalo.me/",
                "Origin": "https://chat.zalo.me"
            }
            data = {"params": encoded}

            self.log("Gửi yêu cầu join group...")
            r = requests.post(url, params=params, data=data, cookies=self.session_cookies, headers=headers, timeout=15)
            try:
                j = r.json()
            except Exception:
                self.log("Không parse JSON trả về khi join:", r.text[:500])
                return None

            if j.get("error_code") == 0 and j.get("data"):
                enc = j["data"]
                try:
                    decoded = self.client._decode(enc)
                except Exception:
                    # fallback AES-ECB
                    from base64 import b64decode
                    from Crypto.Cipher import AES
                    import hashlib
                    raw = b64decode(enc)
                    key = hashlib.md5(self.secret_key.encode()).digest()
                    cipher = AES.new(key, AES.MODE_ECB)
                    dec = cipher.decrypt(raw)
                    pad = dec[-1]
                    payload = dec[:-pad].decode(errors="ignore")
                    decoded = json.loads(payload)
                    self.log("Fallback decode thành công (AES-ECB).")

                self.log("Join API trả:", json.dumps(decoded, ensure_ascii=False, indent=2))
                return decoded

            self.log("Join API trả lỗi:", json.dumps(j, ensure_ascii=False))
            return None

        except Exception as e:
            self.log("Lỗi khi gọi join_group_via_link:", e, traceback.format_exc())
            return None


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = ZaloGroupGUI()
    w.show()
    sys.exit(app.exec())