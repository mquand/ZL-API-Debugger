# zalo_gui_group_qr_auto_fixed.py
import sys, time, json, traceback, urllib.parse, re, threading
from PyQt6 import QtWidgets, QtCore
import requests

# zlapi import
from zlapi.simple import ZaloAPI

# browser control
# browser control
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
        self.setWindowTitle("Zalo API Tools - Công cụ Zalo toàn diện")
        self.setGeometry(300, 200, 900, 750)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)

        # === Status Bar ===
        self.status_label = QtWidgets.QLabel("⏸ Trạng thái: Chưa đăng nhập")
        self.status_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 8px; border-radius: 4px; font-weight: bold; }")
        layout.addWidget(self.status_label)

        # === Login Section (Always visible) ===
        login_group = QtWidgets.QGroupBox("📱 Đăng nhập Zalo")
        login_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 14px; }")
        login_layout = QtWidgets.QHBoxLayout()
        
        self.open_btn = QtWidgets.QPushButton("🌐 Mở trình duyệt (Scan QR)")
        self.open_btn.clicked.connect(self.open_browser)
        self.open_btn.setStyleSheet("QPushButton { padding: 8px; font-size: 13px; }")
        login_layout.addWidget(self.open_btn)

        self.close_btn = QtWidgets.QPushButton("❌ Đóng trình duyệt")
        self.close_btn.clicked.connect(self.close_browser)
        self.close_btn.setEnabled(False)
        self.close_btn.setStyleSheet("QPushButton { padding: 8px; font-size: 13px; }")
        login_layout.addWidget(self.close_btn)
        
        login_group.setLayout(login_layout)
        layout.addWidget(login_group)

        # === Tab Widget ===
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet("QTabWidget::pane { border: 1px solid #ccc; } QTabBar::tab { padding: 10px 20px; font-size: 13px; }")
        
        # TAB 1: Quét nhóm
        self.tab_scan_group = QtWidgets.QWidget()
        self.setup_scan_group_tab()
        self.tabs.addTab(self.tab_scan_group, "🔍 Quét nhóm")
        
        # TAB 2: Decode Friend Request
        self.tab_friend_request = QtWidgets.QWidget()
        self.setup_friend_request_tab()
        self.tabs.addTab(self.tab_friend_request, "👥 Friend Request")
        
        # TAB 3: Log/Kết quả
        self.tab_log = QtWidgets.QWidget()
        self.setup_log_tab()
        self.tabs.addTab(self.tab_log, "📊 Kết quả & Log")
        
        layout.addWidget(self.tabs)

        self.driver = None
        self.client = ZaloAPI(phone=None, password=None, imei="gui-imei-xyz", auto_login=False)
        self.session_cookies = None
        self.local_storage = None
        self.secret_key = None
        self.user_agent = "Mozilla/5.0"
    
    def setup_scan_group_tab(self):
        """Setup tab quét nhóm"""
        layout = QtWidgets.QVBoxLayout(self.tab_scan_group)
        layout.setSpacing(15)
        
        # Quét link nhóm tự động
        scan_group = QtWidgets.QGroupBox("🔍 Quét link nhóm (Phân trang tự động)")
        scan_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 14px; }")
        scan_layout = QtWidgets.QVBoxLayout()
        
        scan_desc = QtWidgets.QLabel("Nhập link nhóm để tự động lấy toàn bộ danh sách thành viên (phân trang mpage)")
        scan_desc.setStyleSheet("QLabel { color: #666; font-style: italic; }")
        scan_layout.addWidget(scan_desc)
        
        self.group_input = QtWidgets.QLineEdit()
        self.group_input.setPlaceholderText("🔗 Nhập link nhóm: https://zalo.me/g/xxx hoặc mã nhóm")
        self.group_input.setStyleSheet("QLineEdit { padding: 8px; font-size: 13px; }")
        scan_layout.addWidget(self.group_input)

        self.check_btn = QtWidgets.QPushButton("▶ Bắt đầu quét nhóm")
        self.check_btn.clicked.connect(self.on_check_group)
        self.check_btn.setEnabled(False)
        self.check_btn.setStyleSheet("QPushButton { padding: 12px; font-size: 14px; font-weight: bold; background-color: #0084ff; color: white; } QPushButton:disabled { background-color: #cccccc; }")
        scan_layout.addWidget(self.check_btn)
        
        scan_group.setLayout(scan_layout)
        layout.addWidget(scan_group)
        
        # Dán params thủ công
        manual_group = QtWidgets.QGroupBox("📋 Dán params thủ công (Tùy chọn)")
        manual_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 14px; }")
        manual_layout = QtWidgets.QVBoxLayout()
        
        manual_desc = QtWidgets.QLabel("Nếu quét tự động không đủ, có thể dán các params từ DevTools (mỗi dòng 1 token)")
        manual_desc.setStyleSheet("QLabel { color: #666; font-style: italic; }")
        manual_layout.addWidget(manual_desc)
        
        self.params_input = QtWidgets.QTextEdit()
        self.params_input.setPlaceholderText("Dán các giá trị params từ Network tab (DevTools) vào đây, mỗi token trên một dòng...")
        self.params_input.setFixedHeight(100)
        self.params_input.setStyleSheet("QTextEdit { padding: 6px; font-size: 12px; font-family: 'Consolas', monospace; }")
        manual_layout.addWidget(self.params_input)

        self.paste_params_btn = QtWidgets.QPushButton("📥 Dán & Giải mã params")
        self.paste_params_btn.clicked.connect(self.on_paste_params)
        self.paste_params_btn.setEnabled(False)
        self.paste_params_btn.setStyleSheet("QPushButton { padding: 10px; font-size: 13px; }")
        manual_layout.addWidget(self.paste_params_btn)
        
        manual_group.setLayout(manual_layout)
        layout.addWidget(manual_group)
        
        layout.addStretch()
    
    def setup_friend_request_tab(self):
        """Setup tab Friend Request"""
        layout = QtWidgets.QVBoxLayout(self.tab_friend_request)
        layout.setSpacing(15)
        
        friend_group = QtWidgets.QGroupBox("👥 Decode Friend Request Params")
        friend_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 14px; }")
        friend_layout = QtWidgets.QVBoxLayout()
        
        friend_desc = QtWidgets.QLabel("Dán params từ API sendreq (gửi kết bạn) để decode thông tin User ID, Message...")
        friend_desc.setStyleSheet("QLabel { color: #666; font-style: italic; }")
        friend_layout.addWidget(friend_desc)
        
        self.friend_params_input = QtWidgets.QTextEdit()
        self.friend_params_input.setPlaceholderText("Dán params từ Network tab (DevTools) vào đây...\nVí dụ: từ request https://tt-friend-wpa.chat.zalo.me/api/friend/sendreq")
        self.friend_params_input.setFixedHeight(120)
        self.friend_params_input.setStyleSheet("QTextEdit { padding: 8px; font-size: 12px; font-family: 'Consolas', monospace; }")
        friend_layout.addWidget(self.friend_params_input)
        
        self.decode_friend_btn = QtWidgets.QPushButton("🔓 Decode params")
        self.decode_friend_btn.clicked.connect(self.on_decode_friend_request_with_effect)
        self.decode_friend_btn.setEnabled(False)
        self.decode_friend_btn.setStyleSheet("""
            QPushButton { 
                padding: 12px; 
                font-size: 14px; 
                font-weight: bold; 
                background-color: #28a745; 
                color: white; 
                border-radius: 5px;
            } 
            QPushButton:hover { 
                background-color: #218838; 
            }
            QPushButton:pressed { 
                background-color: #1e7e34; 
            }
            QPushButton:disabled { 
                background-color: #cccccc; 
            }
        """)
        friend_layout.addWidget(self.decode_friend_btn)
        
        friend_group.setLayout(friend_layout)
        layout.addWidget(friend_group)
        
        layout.addStretch()
    
    def setup_log_tab(self):
        """Setup tab Log/Kết quả"""
        layout = QtWidgets.QVBoxLayout(self.tab_log)
        
        # Nút xóa log
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        
        self.clear_log_btn = QtWidgets.QPushButton("🗑️ Xóa log")
        self.clear_log_btn.clicked.connect(self.clear_log)
        self.clear_log_btn.setStyleSheet("QPushButton { padding: 8px 15px; font-size: 12px; background-color: #dc3545; color: white; } QPushButton:hover { background-color: #c82333; }")
        btn_layout.addWidget(self.clear_log_btn)
        
        layout.addLayout(btn_layout)
        
        self.output_box = QtWidgets.QTextEdit()
        self.output_box.setReadOnly(True)
        self.output_box.setStyleSheet("QTextEdit { font-family: 'Consolas', monospace; font-size: 12px; }")
        layout.addWidget(self.output_box)
    
    def clear_log(self):
        """Xóa tất cả log"""
        self.output_box.clear()
        self.log("✅ Đã xóa log")

    def log(self, *args):
        txt = " ".join(str(a) for a in args)
        self.output_box.append(txt)
        self.output_box.ensureCursorVisible()

    def open_browser(self):
        try:
            self.status_label.setText("⏳ Đang mở trình duyệt...")
            self.status_label.setStyleSheet("QLabel { background-color: #fff3cd; padding: 8px; border-radius: 4px; font-weight: bold; color: #856404; }")
            self.log("🌐 Mở trình duyệt. Hãy quét QR trong cửa sổ trình duyệt vừa bật.")
            self.driver = browser_builder()
            self.driver.get("https://chat.zalo.me/")
            # try enable CDP Network logging so we can capture all requests (works across frames/workers)
            try:
                # enable network events
                try:
                    self.driver.execute_cdp_cmd("Network.enable", {})
                except Exception:
                    # undetected_chromedriver / some drivers may expose as execute_cdp_cmd
                    try:
                        self.driver.execute_script("window.__cdp_network_enabled = true")
                    except Exception:
                        pass
                # optionally disable cache to see fresh requests
                try:
                    self.driver.execute_cdp_cmd("Network.setCacheDisabled", {"cacheDisabled": True})
                except Exception:
                    pass
                self.log("✅ CDP network logging enabled.")
            except Exception:
                self.log("⚠ Không thể bật CDP network logging trên driver này.")
            self.open_btn.setEnabled(False)
            self.close_btn.setEnabled(True)
            self.start_time = time.time()
            QtCore.QTimer.singleShot(1000, self.poll_for_session)
        except Exception as e:
            self.status_label.setText(f"❌ Không mở được browser: {e}")
            self.status_label.setStyleSheet("QLabel { background-color: #f8d7da; padding: 8px; border-radius: 4px; font-weight: bold; color: #721c24; }")
            self.log("❌ Lỗi mở browser:", e, traceback.format_exc())

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
        self.status_label.setText("⏸ Trình duyệt đã đóng")
        self.status_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 8px; border-radius: 4px; font-weight: bold; }")
        self.log("🚪 Trình duyệt đã đóng.")

    def poll_for_session(self):
        if not self.driver:
            return
        elapsed = time.time() - getattr(self, "start_time", 0)
        if elapsed > POLL_TIMEOUT:
            self.status_label.setText("⏱ Timeout chờ login (QR). Hãy thử lại.")
            self.status_label.setStyleSheet("QLabel { background-color: #f8d7da; padding: 8px; border-radius: 4px; font-weight: bold; color: #721c24; }")
            self.log("⏱ Timeout chờ cookies/localStorage.")
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
            status = f"🔍 Đợi QR... Cookies: {len(present)}/{len(REQUIRED_COOKIE_KEYS)} | z_uuid: {'✓' if z_uuid else '✗'}"
            self.status_label.setText(status)
            self.status_label.setStyleSheet("QLabel { background-color: #d1ecf1; padding: 8px; border-radius: 4px; font-weight: bold; color: #0c5460; }")
            self.log(status)

            if all(k in cookies for k in REQUIRED_COOKIE_KEYS) and z_uuid:
                self.session_cookies = cookies
                self.local_storage = local
                self.user_agent = self.driver.execute_script("return navigator.userAgent;")
                self.log("✅ Cookies + localStorage thu thập xong. Đang lấy secret_key...")
                got = self.obtain_secret_key(cookies, z_uuid)
                if got:
                    self.status_label.setText(f"✅ Đã đăng nhập | Secret key: {self.secret_key[:20]}...")
                    self.status_label.setStyleSheet("QLabel { background-color: #d4edda; padding: 8px; border-radius: 4px; font-weight: bold; color: #155724; }")
                    self.log(f"✅ Secret key thu được: {self.secret_key}")
                    try:
                        self.client._state._cookies = cookies
                        self.client._state._config["secret_key"] = self.secret_key
                    except Exception as e:
                        self.log("⚠ Không set state zlapi:", e)
                    # inject a small JS hook into the page to capture client-side /ginfo requests
                    try:
                        self.inject_request_hook()
                        self.log("🔗 Đã inject request hook vào browser để capture params.")
                    except Exception as e:
                        self.log("⚠ Không thể inject request hook:", e)
                        self.check_btn.setEnabled(True)
                    # enable paste-decode button when logged in
                    try:
                        self.paste_params_btn.setEnabled(True)
                        self.decode_friend_btn.setEnabled(True)
                    except Exception:
                        pass
                    return
                else:
                    self.log("❌ Không lấy được secret_key. Thử chờ thêm hoặc refresh QR.")
                    self.status_label.setText("❌ Không lấy được secret_key")
                    self.status_label.setStyleSheet("QLabel { background-color: #f8d7da; padding: 8px; border-radius: 4px; font-weight: bold; color: #721c24; }")
                    return
        except Exception as e:
            self.log("⚠ Lỗi poll:", e)

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

    def on_paste_params(self):
        """Read tokens from the params_input, run them in background and aggregate results."""
        text = self.params_input.toPlainText().strip()
        if not text:
            self.log("⚠ Bạn chưa dán bất kỳ params nào.")
            return
        if not self.session_cookies or not self.secret_key:
            self.log("⚠ Chưa có session/secret_key. Quét QR trước.")
            return

        # split lines and whitespace
        tokens = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            # tokens may be space or comma separated in a line
            for part in re.split(r"[\s,]+", line):
                if part:
                    tokens.append(part)

        if not tokens:
            self.log("⚠ Không tìm thấy token hợp lệ trong input.")
            return

        self.log(f"\n{'='*60}")
        self.log(f"📥 BẮT ĐẦU XỬ LÝ {len(tokens)} PARAMS THỦ CÔNG")
        self.log(f"{'='*60}\n")

        def worker(tok_list):
            try:
                all_members = []
                gid = None
                followed = 0
                for t in tok_list:
                    followed += 1
                    self.log(f"📄 Đang xử lý params #{followed}/{len(tok_list)}: {t[:60]}...")
                    dec = self.get_group_info_by_params(t)
                    if not dec:
                        self.log(f"⚠ Không decode được token #{followed} (bỏ qua).")
                        continue
                    # try extract gid
                    try:
                        if isinstance(dec, dict):
                            g = dec.get("groupId") or dec.get("group_id") or (dec.get("data") or {}).get("groupId")
                            if g:
                                gid = gid or g
                    except Exception:
                        pass

                    # extract members
                    try:
                        ms = self.extract_members_from_decoded(dec)
                        if ms:
                            all_members.extend(ms)
                            self.log(f"✅ Thêm {len(ms)} member; Tổng: {len(all_members)}")
                    except Exception:
                        pass

                    # scan for embedded candidates in this batch
                    try:
                        cands = self.find_candidate_params_in_obj(dec) or []
                        for c in cands:
                            if c and c not in tok_list:
                                # naive: try them as well
                                self.log(f"🔍 Tự động thử candidate token: {c[:40]}...")
                                tok_list.append(c)
                    except Exception:
                        pass

                # save result
                try:
                    fname = f"group_{gid or 'paste'}_members_from_paste.json"
                    with open(fname, 'w', encoding='utf-8') as fp:
                        json.dump(all_members, fp, ensure_ascii=False, indent=2)
                    self.log(f"\n{'='*60}")
                    self.log(f"✅ HOÀN TẤT: {len(all_members)} members từ {followed} params")
                    self.log(f"💾 Lưu vào: {fname}")
                    self.log(f"{'='*60}\n")
                except Exception as e:
                    self.log("❌ Lỗi khi lưu file kết quả:", e)
            except Exception as e:
                self.log("❌ Lỗi trong worker:", e, traceback.format_exc())

        # run in background
        t = threading.Thread(target=worker, args=(tokens,))
        t.daemon = True
        t.start()

    def extract_members_from_decoded(self, decoded):
        """Return list of members from a decoded payload. Handles wrapper with 'data'."""
        try:
            if not decoded:
                return []
            d = decoded
            # if wrapper
            if isinstance(d, dict) and isinstance(d.get("data"), dict):
                d = d.get("data")

            # common keys
            for k in ("currentMems", "members", "membersList", "members_list"):
                v = d.get(k) if isinstance(d, dict) else None
                if isinstance(v, list):
                    return v

            # sometimes payload is nested
            if isinstance(d, dict):
                # try to find first list value that looks like members
                for val in d.values():
                    if isinstance(val, list):
                        return val

            return []
        except Exception:
            return []

    def find_candidate_params_in_obj(self, obj):
        """Recursively scan a decoded JSON-like object (or string) and return
        a list of candidate 'params' strings that look like base64/url-safe tokens.
        This helps when the server embeds next-page tokens inside the encoded
        payload rather than issuing separate requests the browser makes.
        """
        found = []
        try:
            # quick helper to test a string for base64-like token
            def scan_str(s):
                if not s or not isinstance(s, str):
                    return []
                # common token characters in these params: A-Za-z0-9 - _ + / =
                # enforce a reasonable minimum length to avoid false positives
                matches = re.findall(r"[A-Za-z0-9\-_\+/=]{24,300}", s)
                return matches

            if isinstance(obj, str):
                return scan_str(obj)

            if isinstance(obj, dict):
                for k, v in obj.items():
                    # prefer obvious fields
                    if isinstance(v, str):
                        # direct param field
                        if k.lower() in ("params", "param", "enc", "payload", "data", "token", "next", "nextparam", "next_param"):
                            found.extend(scan_str(v))
                        else:
                            found.extend(self.find_candidate_params_in_obj(v))
                    else:
                        found.extend(self.find_candidate_params_in_obj(v))
                return list(dict.fromkeys(found))

            if isinstance(obj, list):
                for item in obj:
                    found.extend(self.find_candidate_params_in_obj(item))
                return list(dict.fromkeys(found))

            return []
        except Exception:
            return []

    def extract_params_from_performance(self, timeout=6):
        """
        Đọc performance logs từ Selenium, tìm request chứa '/ginfo?'
        Trả về một danh sách các tham số params (URL-decoded).
        """
        if not self.driver:
            return None
        end = time.time() + timeout
        seen_urls = set()
        found_params = []
        while time.time() < end:
            try:
                logs = []
                try:
                    logs = self.driver.get_log("performance")
                except Exception:
                    # uc driver or environment may not support performance logs
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
                        # parse query
                        try:
                            q = urllib.parse.urlparse(url).query
                            qd = dict(urllib.parse.parse_qsl(q, keep_blank_values=True))
                            params_val = qd.get("params")
                            if params_val and params_val not in found_params:
                                found_params.append(params_val)
                        except Exception:
                            continue
            except Exception:
                pass
            time.sleep(0.5)

        return found_params

    def read_captured_params_from_localstorage(self):
        """Read captured /ginfo params recorded by the injected JS hook in localStorage.
        Returns a list of params (strings) or empty list.
        """
        try:
            if not self.driver:
                return []
            script = "return window.localStorage.getItem('zlapi_ginfo_params');"
            val = self.driver.execute_script(script)
            if not val:
                return []
            try:
                arr = json.loads(val)
                if isinstance(arr, list):
                    # clear after reading to avoid duplicate processing
                    try:
                        self.driver.execute_script("window.localStorage.removeItem('zlapi_ginfo_params')")
                    except Exception:
                        pass
                    return [str(x) for x in arr if x]
                return []
            except Exception:
                # if it's a single string
                return [val]
        except Exception:
            return []

    def inject_request_hook(self):
        """Inject a JS hook into the page that intercepts fetch/XHR and records
        any requests to /api/group/link/ginfo by storing their params into
        localStorage['zlapi_ginfo_params'] as a JSON array.

        This is best-effort and should be injected after login when the main
        window is available.
        """
        if not self.driver:
            return

        js = r"""
        (function(){
            try{
                if(!window.__zlapi_hook_installed){
                    window.__zlapi_hook_installed = true;
                    function pushParam(p){
                        try{
                            var key = 'zlapi_ginfo_params';
                            var cur = window.localStorage.getItem(key);
                            var arr = [];
                            if(cur){
                                try{ arr = JSON.parse(cur) }catch(e){}
                            }
                            if(!p) return;
                            if(arr.indexOf(p) === -1){ arr.push(p); window.localStorage.setItem(key, JSON.stringify(arr)); }
                        }catch(e){}
                    }

                    // hook fetch
                    var _fetch = window.fetch;
                    window.fetch = function(input, init){
                        try{
                            var url = (typeof input === 'string') ? input : (input && input.url) || '';
                            if(url && url.indexOf('/api/group/link/ginfo')!==-1){
                                // try to get params from query
                                try{
                                    var u = new URL(url, location.origin);
                                    var p = u.searchParams.get('params');
                                    if(p) pushParam(p);
                                }catch(e){}
                                // try to get params from body
                                try{
                                    if(init && init.body){
                                        var b = init.body;
                                        if(typeof b === 'string'){
                                            var m = b.match(/params=([^&]+)/);
                                            if(m && m[1]) pushParam(decodeURIComponent(m[1]));
                                        }
                                    }
                                }catch(e){}
                            }
                        }catch(e){}
                        return _fetch.apply(this, arguments);
                    };

                    // hook XMLHttpRequest
                    var origOpen = XMLHttpRequest.prototype.open;
                    var origSend = XMLHttpRequest.prototype.send;
                    XMLHttpRequest.prototype.open = function(method, url){
                        this.__zlapi_hook_url = url;
                        return origOpen.apply(this, arguments);
                    };
                    XMLHttpRequest.prototype.send = function(body){
                        try{
                            var url = this.__zlapi_hook_url || '';
                            if(url.indexOf('/api/group/link/ginfo')!==-1){
                                try{
                                    var u = new URL(url, location.origin);
                                    var p = u.searchParams.get('params');
                                    if(p) pushParam(p);
                                }catch(e){}
                                try{
                                    if(body){
                                        if(typeof body === 'string'){
                                            var m = body.match(/params=([^&]+)/);
                                            if(m && m[1]) pushParam(decodeURIComponent(m[1]));
                                        }
                                    }
                                }catch(e){}
                            }
                        }catch(e){}
                        return origSend.apply(this, arguments);
                    };
                }
            }catch(e){console.log('zlapi hook err',e)}
        })();
        """

        # execute the script in page context
        try:
            self.driver.execute_script(js)
        except Exception:
            # some drivers may require wrapping in setTimeout
            try:
                self.driver.execute_script("setTimeout(function(){%s},0)" % js)
            except Exception:
                pass


    def on_check_group(self):
        link = self.group_input.text().strip()
        if not link:
            self.log("⚠ Nhập link nhóm trước.")
            return
        if not self.secret_key or not self.session_cookies:
            self.log("⚠ Chưa có session hợp lệ. Quét QR trước.")
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
        self.log(f"\n{'='*60}")
        self.log(f"🔍 BẮT ĐẦU QUÉT NHÓM: {cleaned_link}")
        self.log(f"{'='*60}\n")

        try:
            # --- PHÂN TRANG với mpage ---
            self.client._state._cookies = self.session_cookies
            self.client._state._config["secret_key"] = self.secret_key
            
            all_members = []
            seen_member_ids = set()
            mpage = 1
            max_pages = 100  # giới hạn an toàn
            pages_fetched = 0
            gid = None
            
            while mpage <= max_pages:
                self.log(f"📄 Đang lấy trang {mpage}...")
                
                # Build payload với mpage
                payload_obj = {
                    "link": str(cleaned_link),
                    "clientLang": "vi",
                    "avatar_size": 120,
                    "member_avatar_size": 120,
                    "mpage": mpage
                }
                encoded_params = self.client._encode(payload_obj)

                # --- Gọi ginfo endpoint ---
                url = "https://tt-group-wpa.chat.zalo.me/api/group/link/ginfo"
                params = {"zpw_type": 30, "zpw_ver": 670, "params": encoded_params}
                headers = {
                    "User-Agent": self.user_agent,
                    "Accept": "application/json, text/plain, */*",
                    "Referer": "https://chat.zalo.me/",
                    "Origin": "https://chat.zalo.me"
                }

                self.log(f"Gọi ginfo trang {mpage}...")
                r = requests.get(url, params=params, cookies=self.session_cookies, headers=headers, timeout=12)
                self.log(f"Gọi ginfo trang {mpage}...")
                r = requests.get(url, params=params, cookies=self.session_cookies, headers=headers, timeout=12)
                try:
                    j = r.json()
                except Exception:
                    self.log(f"⚠️ Trang {mpage}: Không parse JSON:", r.text[:800])
                    break

                if j.get("error_code") != 0:
                    self.log(f"❌ Trang {mpage}: ginfo trả lỗi:", json.dumps(j, ensure_ascii=False))
                    break

                enc = j.get("data") or j.get("payload") or j.get("enc")
                if not enc:
                    self.log(f"⚠️ Trang {mpage}: ginfo trả data trực tiếp (không mã hóa)")
                    # Có thể data đã decode sẵn
                    decoded = j.get("data")
                    if not decoded:
                        break
                else:
                    # --- Decode data ---
                    decoded = None
                    try:
                        decoded = self.client._decode(enc)
                        self.log(f"✅ Trang {mpage}: ginfo decoded bằng zlapi.")
                    except Exception:
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
                            self.log(f"✅ Trang {mpage}: Fallback AES decode thành công.")
                        except Exception as e:
                            self.log(f"❌ Trang {mpage}: Decode thất bại:", e)
                            break

                if not decoded:
                    self.log(f"⚠️ Trang {mpage}: Không decode được dữ liệu.")
                    break
                
                # Handle wrapper {error_code, data: {...}}
                if isinstance(decoded, dict) and decoded.get("error_code") == 0 and "data" in decoded:
                    decoded = decoded.get("data")
                
                # Extract group ID từ trang đầu
                if mpage == 1:
                    try:
                        if isinstance(decoded, dict):
                            gid = decoded.get("group_id") or decoded.get("id") or decoded.get("groupId") or decoded.get("gid")
                            if not gid and isinstance(decoded.get("data"), dict):
                                d = decoded.get("data")
                                gid = d.get("groupId") or d.get("group_id") or d.get("id") or d.get("gid")
                            self.log(f"✅ Group ID: {gid}")
                    except Exception:
                        pass
                
                # Extract members từ currentMems
                try:
                    members = self.extract_members_from_decoded(decoded)
                    if not members:
                        self.log(f"⚠️ Trang {mpage}: Không có member (hết).")
                        break
                    
                    # Loại bỏ trùng lặp
                    new_count = 0
                    for m in members:
                        mid = m.get("id") or m.get("userId") or m.get("uid")
                        if mid and mid not in seen_member_ids:
                            seen_member_ids.add(mid)
                            all_members.append(m)
                            new_count += 1
                    
                    self.log(f"✅ Trang {mpage}: Thêm {new_count} members mới; tổng: {len(all_members)}")
                    pages_fetched += 1
                    
                except Exception as e:
                    self.log(f"⚠️ Trang {mpage}: Lỗi extract members:", e)
                    break
                
                # Check hasMoreMember
                has_more = decoded.get("hasMoreMember", 0) if isinstance(decoded, dict) else 0
                total_members = decoded.get("totalMember", 0) if isinstance(decoded, dict) else 0
                
                if total_members > 0:
                    self.log(f"   📊 Tiến độ: {len(all_members)}/{total_members} members")
                
                if has_more == 0:
                    self.log(f"✅ Đã lấy hết (hasMoreMember = 0)")
                    break
                
                # Tăng mpage cho lần tiếp theo
                mpage += 1
                time.sleep(0.2)  # delay nhỏ giữa các trang
            
            # Kết thúc phân trang
            self.log(f"\n{'='*60}")
            self.log(f"✅ HOÀN THÀNH: {len(all_members)} members từ {pages_fetched} trang")
            self.log(f"{'='*60}\n")
            
            # Lưu kết quả
            try:
                fname = f"group_{gid or 'unknown'}_members.json"
                with open(fname, 'w', encoding='utf-8') as fp:
                    json.dump(all_members, fp, ensure_ascii=False, indent=2)
                self.log(f"Danh sách member đã lưu vào: {fname}")
            except Exception as e:
                self.log("Không lưu được file members:", e)

        except Exception as e:
            self.log("Lỗi khi xử lý on_check_group:", e, traceback.format_exc())


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

    def on_decode_friend_request_with_effect(self):
        """Decode với hiệu ứng button"""
        # Hiệu ứng: Disable button và đổi text
        self.decode_friend_btn.setText("⏳ Đang decode...")
        self.decode_friend_btn.setEnabled(False)
        self.decode_friend_btn.setStyleSheet("""
            QPushButton { 
                padding: 12px; 
                font-size: 14px; 
                font-weight: bold; 
                background-color: #ffc107; 
                color: white; 
                border-radius: 5px;
            }
        """)
        
        # Chuyển sang tab log
        self.tabs.setCurrentIndex(2)
        
        # Xử lý decode
        QtCore.QTimer.singleShot(100, self._do_decode_friend_request)
    
    def _do_decode_friend_request(self):
        """Thực hiện decode thực sự"""
        try:
            self.on_decode_friend_request()
        finally:
            # Reset button về trạng thái ban đầu
            self.decode_friend_btn.setText("🔓 Decode params")
            self.decode_friend_btn.setEnabled(True)
            self.decode_friend_btn.setStyleSheet("""
                QPushButton { 
                    padding: 12px; 
                    font-size: 14px; 
                    font-weight: bold; 
                    background-color: #28a745; 
                    color: white; 
                    border-radius: 5px;
                } 
                QPushButton:hover { 
                    background-color: #218838; 
                }
                QPushButton:pressed { 
                    background-color: #1e7e34; 
                }
                QPushButton:disabled { 
                    background-color: #cccccc; 
                }
            """)

    def on_decode_friend_request(self):
        """Decode params từ API sendreq - giống như decode ginfo"""
        try:
            if not self.secret_key or not self.session_cookies:
                self.log("⚠️ Chưa có session/secret_key. Quét QR trước.")
                return
            
            # Lấy params từ text box
            params_text = self.friend_params_input.toPlainText().strip()
            
            if not params_text:
                self.log("⚠️ Vui lòng nhập params cần decode vào ô trên")
                return
            
            # Lấy dòng đầu tiên nếu có nhiều dòng
            lines = params_text.split('\n')
            encoded_params = lines[0].strip()
            
            self.log(f"\n{'='*60}")
            self.log(f"🔓 DECODE FRIEND REQUEST PARAMS")
            self.log(f"{'='*60}")
            self.log(f"📋 Params (cắt ngắn): {encoded_params[:80]}...")
            
            # Decode giống như ginfo - dùng get_group_info_by_params logic
            decoded = None
            try:
                # Cập nhật state cho zlapi
                self.client._state._cookies = self.session_cookies
                self.client._state._config["secret_key"] = self.secret_key
                
                # Thử decode bằng zlapi trước
                decoded = self.client._decode(encoded_params)
                self.log("✅ Decode bằng zlapi thành công!")
            except Exception as e:
                self.log(f"⚠️ Zlapi decode failed: {e}")
                # Fallback to AES-ECB
                try:
                    from base64 import b64decode
                    from Crypto.Cipher import AES
                    import hashlib
                    
                    raw = b64decode(encoded_params)
                    key = hashlib.md5(self.secret_key.encode()).digest()
                    cipher = AES.new(key, AES.MODE_ECB)
                    dec = cipher.decrypt(raw)
                    pad = dec[-1]
                    payload = dec[:-pad].decode(errors="ignore")
                    decoded = json.loads(payload)
                    self.log("✅ Decode bằng AES-ECB fallback thành công!")
                except Exception as e2:
                    self.log(f"❌ Decode thất bại hoàn toàn: {e2}")
                    self.log(traceback.format_exc())
                    return
            
            if decoded:
                self.log(f"\n{'='*60}")
                self.log(f"✅ KẾT QUẢ DECODE:")
                self.log(f"{'='*60}")
                self.log(json.dumps(decoded, ensure_ascii=False, indent=2))
                self.log(f"{'='*60}\n")
                
                # Tự động fill thông tin vào ô encode nếu có
                if isinstance(decoded, dict):
                    user_id = decoded.get("toid")
                    msg = decoded.get("msg")
                    
                    if user_id:
                        self.friend_userid_input.setText(str(user_id))
                        self.log(f"📝 User ID: {user_id}")
                    
                    if msg:
                        self.friend_msg_input.setText(msg)
                        self.log(f"� Message: {msg}")
                    
                    # Hiển thị thêm thông tin khác
                    if decoded.get("reqsrc"):
                        self.log(f"📍 Request Source: {decoded.get('reqsrc')}")
                    if decoded.get("imei"):
                        self.log(f"📱 IMEI: {decoded.get('imei')}")
                    if decoded.get("language"):
                        self.log(f"🌐 Language: {decoded.get('language')}")
                    if decoded.get("srcParams"):
                        self.log(f"🔗 Source Params: {decoded.get('srcParams')}")
                        
        except Exception as e:
            self.log(f"❌ Lỗi khi decode: {e}")
            self.log(traceback.format_exc())


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = ZaloGroupGUI()
    w.show()
    sys.exit(app.exec())