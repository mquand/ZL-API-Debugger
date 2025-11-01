# zalo_gui_group_qr_auto_fixed_request_mode.py
import sys, time, json, traceback, urllib.parse
from PyQt6 import QtWidgets, QtCore
import requests

# zlapi import
from zlapi.simple import ZaloAPI

from webdriver_manager.chrome import ChromeDriverManager
import undetected_chromedriver as uc

def browser_builder():
    return uc.Chrome(driver_executable_path=ChromeDriverManager().install())


# --- Config ---
REQUIRED_COOKIE_KEYS = ["__zi", "zpsid", "zpw_sek", "_zlang", "app.event.zalo.me"]
POLL_INTERVAL = 1.0
POLL_TIMEOUT = 180  # seconds waiting for cookies + localStorage

# --- GUI / Logic ---
class ZaloGroupGUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Zalo Group ID (QR → auto secret_key → decode ginfo)")
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

        self.ginfo_input = QtWidgets.QLineEdit()
        self.ginfo_input.setPlaceholderText("Paste URL /ginfo?params=xxx hoặc chỉ params")
        layout.addWidget(self.ginfo_input)

        self.check_btn = QtWidgets.QPushButton("Decode Ginfo")
        self.check_btn.clicked.connect(self.on_decode_ginfo)
        self.check_btn.setEnabled(False)
        layout.addWidget(self.check_btn)

        self.output_box = QtWidgets.QTextEdit()
        self.output_box.setReadOnly(True)
        layout.addWidget(self.output_box)

        # state
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

    # --- Browser QR Login ---
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

    # --- Decode ginfo từ request URL hoặc params ---
    def decode_ginfo_from_request(self, ginfo_url_or_params):
        """
        Nhận URL full của request /ginfo hoặc value của 'params' đã encode.
        Trả về dict decoded.
        """
        try:
            if not self.secret_key or not self.session_cookies:
                self.log("Chưa có session/secret_key. Quét QR trước.")
                return None

            # Lấy params nếu input là URL
            if ginfo_url_or_params.startswith("http"):
                from urllib.parse import urlparse, parse_qs
                qd = parse_qs(urlparse(ginfo_url_or_params).query)
                params_value = qd.get("params", [None])[0]
                if not params_value:
                    self.log("URL không có params")
                    return None
            else:
                params_value = ginfo_url_or_params

            # Gọi API
            url = "https://tt-group-wpa.chat.zalo.me/api/group/link/ginfo"
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "Referer": "https://chat.zalo.me/",
                "Origin": "https://chat.zalo.me"
            }
            r = requests.get(url, params={"zpw_ver": 669, "zpw_type": 30, "params": params_value},
                             headers=headers, cookies=self.session_cookies, timeout=12)
            try:
                j = r.json()
            except Exception:
                self.log("Không parse JSON:", r.text[:500])
                return None

            enc = j.get("data") or j.get("payload") or j.get("enc")
            if not enc:
                self.log("ginfo trả data trực tiếp:", j.get("data"))
                return j.get("data")

            # Decode bằng zlapi
            try:
                self.client._state._cookies = self.session_cookies
                self.client._state._config["secret_key"] = self.secret_key
                decoded = self.client._decode(enc)
                self.log("Decoded bằng zlapi:", decoded)
                return decoded
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
                self.log("Decoded fallback AES-ECB:", decoded)
                return decoded

        except Exception as e:
            self.log("Lỗi decode ginfo từ request:", e, traceback.format_exc())
            return None

    def on_decode_ginfo(self):
        ginfo_input = self.ginfo_input.text().strip()
        if not ginfo_input:
            self.log("Paste URL /ginfo?params=xxx hoặc chỉ params")
            return
        decoded = self.decode_ginfo_from_request(ginfo_input)
        if decoded:
            gid = decoded.get("group_id") or decoded.get("id") or decoded.get("groupId")
            self.log("✅ Group decoded. Group ID:", gid)
            self.log(json.dumps(decoded, ensure_ascii=False, indent=2))
        else:
            self.log("Không decode được dữ liệu trả về.")

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = ZaloGroupGUI()
    w.show()
    sys.exit(app.exec())
