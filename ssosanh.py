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
        self.setGeometry(300, 200, 720, 600)
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

        h2 = QtWidgets.QHBoxLayout()
        self.check_btn = QtWidgets.QPushButton("Decode Ginfo Response")
        self.check_btn.clicked.connect(self.on_decode_ginfo)
        self.check_btn.setEnabled(False)
        h2.addWidget(self.check_btn)

        self.decode_req_btn = QtWidgets.QPushButton("Decode REQUEST Params")
        self.decode_req_btn.clicked.connect(self.on_decode_request_params)
        self.decode_req_btn.setEnabled(False)
        h2.addWidget(self.decode_req_btn)
        layout.addLayout(h2)

        layout.addWidget(QtWidgets.QLabel("So sánh 2 request params (mỗi dòng 1 params):"))
        self.compare_input = QtWidgets.QTextEdit()
        self.compare_input.setPlaceholderText("Dán 2 params từ Network tab (mỗi dòng 1 params)")
        self.compare_input.setMaximumHeight(80)
        layout.addWidget(self.compare_input)

        self.compare_btn = QtWidgets.QPushButton("So sánh 2 Request Params")
        self.compare_btn.clicked.connect(self.on_compare_params)
        self.compare_btn.setEnabled(False)
        layout.addWidget(self.compare_btn)

        layout.addWidget(QtWidgets.QLabel("━" * 80))
        layout.addWidget(QtWidgets.QLabel("🚀 AUTO-PAGINATION (Lấy toàn bộ members):"))
        
        h3 = QtWidgets.QHBoxLayout()
        self.group_link_input = QtWidgets.QLineEdit()
        self.group_link_input.setPlaceholderText("Nhập link nhóm (https://zalo.me/g/xxx)")
        h3.addWidget(self.group_link_input)
        
        self.fetch_all_btn = QtWidgets.QPushButton("Lấy TẤT CẢ Members")
        self.fetch_all_btn.clicked.connect(self.on_fetch_all_members)
        self.fetch_all_btn.setEnabled(False)
        h3.addWidget(self.fetch_all_btn)
        layout.addLayout(h3)

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
        self.decode_req_btn.setEnabled(bool(self.secret_key))
        self.compare_btn.setEnabled(bool(self.secret_key))
        self.fetch_all_btn.setEnabled(bool(self.secret_key))
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
                    self.decode_req_btn.setEnabled(True)
                    self.compare_btn.setEnabled(True)
                    self.fetch_all_btn.setEnabled(True)
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

    # --- Decode REQUEST params (client → server) ---
    def decode_request_params(self, params_value):
        """
        Decode params TRƯỚC KHI gửi lên server (REQUEST payload).
        Input: params value từ URL (đã URL-encoded)
        Output: dict chứa request payload gốc
        """
        try:
            if not self.secret_key:
                self.log("Chưa có secret_key. Quét QR trước.")
                return None

            # URL decode
            decoded_url = urllib.parse.unquote(params_value)
            self.log(f"URL-decoded params: {decoded_url[:100]}...")

            # Decode bằng zlapi._decode() với secret_key
            try:
                self.client._state._config["secret_key"] = self.secret_key
                decoded_payload = self.client._decode(decoded_url)
                self.log("✅ Decoded REQUEST payload bằng zlapi:")
                self.log(json.dumps(decoded_payload, ensure_ascii=False, indent=2))
                return decoded_payload
            except Exception as e:
                self.log(f"zlapi._decode() lỗi: {e}")
                
                # Fallback: AES-ECB decrypt
                from base64 import b64decode
                from Crypto.Cipher import AES
                import hashlib
                
                raw = b64decode(decoded_url)
                key = hashlib.md5(self.secret_key.encode()).digest()
                cipher = AES.new(key, AES.MODE_ECB)
                dec = cipher.decrypt(raw)
                pad = dec[-1]
                payload = dec[:-pad].decode(errors="ignore")
                decoded_payload = json.loads(payload)
                self.log("✅ Decoded REQUEST payload bằng AES-ECB:")
                self.log(json.dumps(decoded_payload, ensure_ascii=False, indent=2))
                return decoded_payload

        except Exception as e:
            self.log("Lỗi decode request params:", e, traceback.format_exc())
            return None

    def on_decode_request_params(self):
        """Decode 1 request params từ ginfo_input"""
        params_input = self.ginfo_input.text().strip()
        if not params_input:
            self.log("Paste params hoặc URL vào ô input")
            return

        # Extract params nếu là URL
        if params_input.startswith("http"):
            from urllib.parse import urlparse, parse_qs
            qd = parse_qs(urlparse(params_input).query)
            params_value = qd.get("params", [None])[0]
            if not params_value:
                self.log("URL không có params")
                return
        else:
            params_value = params_input

        self.log("\n=== DECODE REQUEST PARAMS ===")
        self.decode_request_params(params_value)

    def on_compare_params(self):
        """So sánh 2 request params để tìm pagination token"""
        text = self.compare_input.toPlainText().strip()
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        
        if len(lines) < 2:
            self.log("Cần ít nhất 2 params để so sánh (mỗi dòng 1 params)")
            return

        self.log("\n=== SO SÁNH 2 REQUEST PARAMS ===")
        
        # Decode cả 2
        params1 = lines[0]
        params2 = lines[1]
        
        # Extract nếu là URL
        for i, p in enumerate([params1, params2], 1):
            if p.startswith("http"):
                from urllib.parse import urlparse, parse_qs
                qd = parse_qs(urlparse(p).query)
                extracted = qd.get("params", [None])[0]
                if extracted:
                    if i == 1:
                        params1 = extracted
                    else:
                        params2 = extracted

        self.log(f"Params 1: {params1[:50]}...")
        decoded1 = self.decode_request_params(params1)
        
        self.log(f"\nParams 2: {params2[:50]}...")
        decoded2 = self.decode_request_params(params2)

        if not decoded1 or not decoded2:
            self.log("Không decode được 1 trong 2 params")
            return

        # So sánh các field
        self.log("\n=== PHÂN TÍCH SỰ KHÁC BIỆT ===")
        all_keys = set(decoded1.keys()) | set(decoded2.keys())
        
        differences = []
        for key in sorted(all_keys):
            val1 = decoded1.get(key)
            val2 = decoded2.get(key)
            if val1 != val2:
                differences.append(key)
                self.log(f"❌ Field '{key}' KHÁC NHAU:")
                self.log(f"   Request 1: {val1}")
                self.log(f"   Request 2: {val2}")
            else:
                self.log(f"✅ Field '{key}': {val1}")

        if differences:
            self.log(f"\n🎯 CÁC FIELD KHÁC NHAU (có thể là pagination token): {differences}")
        else:
            self.log("\n⚠️ Không tìm thấy sự khác biệt giữa 2 request")

    # --- Decode ginfo từ request URL hoặc params (RESPONSE) ---
    def decode_ginfo_from_request(self, ginfo_url_or_params):
        """
        Nhận URL full của request /ginfo hoặc value của 'params' đã encode.
        GỌI API và decode RESPONSE trả về.
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
                self.log("Decoded RESPONSE bằng zlapi:", decoded)
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
                self.log("Decoded RESPONSE fallback AES-ECB:", decoded)
                return decoded

        except Exception as e:
            self.log("Lỗi decode ginfo từ request:", e, traceback.format_exc())
            return None

    def on_decode_ginfo(self):
        """Decode RESPONSE từ ginfo API"""
        ginfo_input = self.ginfo_input.text().strip()
        if not ginfo_input:
            self.log("Paste URL /ginfo?params=xxx hoặc chỉ params")
            return
        
        self.log("\n=== DECODE GINFO RESPONSE ===")
        decoded = self.decode_ginfo_from_request(ginfo_input)
        if decoded:
            gid = decoded.get("group_id") or decoded.get("id") or decoded.get("groupId")
            self.log("✅ Group decoded. Group ID:", gid)
            self.log(json.dumps(decoded, ensure_ascii=False, indent=2))
        else:
            self.log("Không decode được dữ liệu trả về.")

    # --- AUTO-PAGINATION: Lấy toàn bộ members ---
    def fetch_all_members_from_link(self, group_link):
        """
        Tự động lấy toàn bộ members từ link nhóm bằng pagination với mpage.
        Returns: list of all members
        """
        all_members = []
        mpage = 1
        max_pages = 100  # Safety limit
        
        try:
            while mpage <= max_pages:
                self.log(f"\n📄 Đang lấy trang {mpage}...")
                
                # Build request payload
                payload = {
                    "link": group_link,
                    "avatar_size": 120,
                    "member_avatar_size": 120,
                    "mpage": mpage
                }
                
                # Encode payload bằng zlapi
                try:
                    self.client._state._config["secret_key"] = self.secret_key
                    encoded_params = self.client._encode(payload)
                except Exception as e:
                    self.log(f"Lỗi encode payload: {e}")
                    # Fallback: AES-ECB encrypt
                    from base64 import b64encode
                    from Crypto.Cipher import AES
                    import hashlib
                    
                    payload_json = json.dumps(payload, separators=(',', ':'))
                    key = hashlib.md5(self.secret_key.encode()).digest()
                    cipher = AES.new(key, AES.MODE_ECB)
                    
                    # Add PKCS7 padding
                    pad_len = 16 - (len(payload_json) % 16)
                    padded = payload_json.encode() + bytes([pad_len] * pad_len)
                    encrypted = cipher.encrypt(padded)
                    encoded_params = b64encode(encrypted).decode()
                
                # Gọi API
                url = "https://tt-group-wpa.chat.zalo.me/api/group/link/ginfo"
                headers = {
                    "User-Agent": self.user_agent,
                    "Accept": "application/json",
                    "Referer": "https://chat.zalo.me/",
                    "Origin": "https://chat.zalo.me"
                }
                
                r = requests.get(
                    url,
                    params={"zpw_ver": 670, "zpw_type": 30, "params": encoded_params},
                    headers=headers,
                    cookies=self.session_cookies,
                    timeout=12
                )
                
                try:
                    response_json = r.json()
                except Exception:
                    self.log(f"Không parse JSON response: {r.text[:500]}")
                    break
                
                # Decode response
                enc = response_json.get("data") or response_json.get("payload")
                if not enc:
                    self.log(f"Không có data trong response: {response_json}")
                    break
                
                try:
                    decoded = self.client._decode(enc)
                except Exception as e:
                    self.log(f"Lỗi decode response: {e}")
                    # Fallback AES-ECB
                    from base64 import b64decode
                    from Crypto.Cipher import AES
                    import hashlib
                    
                    raw = b64decode(enc)
                    key = hashlib.md5(self.secret_key.encode()).digest()
                    cipher = AES.new(key, AES.MODE_ECB)
                    dec = cipher.decrypt(raw)
                    pad = dec[-1]
                    payload_str = dec[:-pad].decode(errors="ignore")
                    decoded = json.loads(payload_str)
                
                # Check nested wrapper (như scan_link)
                if isinstance(decoded, dict) and "data" in decoded and isinstance(decoded["data"], str):
                    try:
                        decoded = self.client._decode(decoded["data"])
                    except Exception:
                        pass
                
                # Check if response has error
                if decoded.get("error_code") != 0:
                    self.log(f"❌ API trả lỗi: {decoded.get('error_message')}")
                    break
                
                # Extract data object (contains group info + members)
                data = decoded.get("data", {})
                if not isinstance(data, dict):
                    self.log(f"⚠️ 'data' không phải dict: {type(data)}")
                    break
                
                # Extract members from 'currentMems' field
                members = data.get("currentMems", [])
                if not members:
                    self.log(f"⚠️ Trang {mpage}: Không có currentMems (hết)")
                    break
                
                self.log(f"✅ Trang {mpage}: Lấy được {len(members)} members")
                all_members.extend(members)
                
                # Check hasMoreMember (có thể ở data level)
                has_more = data.get("hasMoreMember", 0) or data.get("hasMore", 0)
                total_count = data.get("totalMembers", 0) or data.get("totalCount", 0)
                
                if total_count > 0:
                    self.log(f"   📊 Progress: {len(all_members)}/{total_count} members")
                
                if has_more == 0:
                    self.log("✅ Đã lấy hết (hasMoreMember = 0)")
                    break
                
                mpage += 1
                time.sleep(0.5)  # Rate limiting
            
            return all_members
            
        except Exception as e:
            self.log(f"Lỗi fetch_all_members: {e}")
            self.log(traceback.format_exc())
            return all_members

    def on_fetch_all_members(self):
        """Handler cho nút Lấy TẤT CẢ Members"""
        group_link = self.group_link_input.text().strip()
        if not group_link:
            self.log("Nhập link nhóm (https://zalo.me/g/xxx)")
            return
        
        if not self.secret_key or not self.session_cookies:
            self.log("Chưa có session/secret_key. Quét QR trước.")
            return
        
        self.log(f"\n{'='*60}")
        self.log(f"🚀 BẮT ĐẦU LẤY TOÀN BỘ MEMBERS: {group_link}")
        self.log(f"{'='*60}")
        
        all_members = self.fetch_all_members_from_link(group_link)
        
        self.log(f"\n{'='*60}")
        self.log(f"✅ HOÀN THÀNH! Tổng cộng: {len(all_members)} members")
        self.log(f"{'='*60}")
        
        if all_members:
            # Hiển thị sample
            self.log("\n📋 Sample 5 members đầu tiên:")
            for i, member in enumerate(all_members[:5], 1):
                name = member.get("dName") or member.get("zaloName") or member.get("name") or "Unknown"
                uid = member.get("id") or member.get("uid") or "N/A"
                self.log(f"  {i}. {name} (ID: {uid})")
            
            if len(all_members) > 5:
                self.log(f"  ... và {len(all_members) - 5} members khác")
        else:
            self.log("⚠️ Không lấy được members nào!")

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = ZaloGroupGUI()
    w.show()
    sys.exit(app.exec())
