# zalo_gui_group_qr_auto_optimized.py
import sys, time, json, traceback, urllib.parse, re, threading
from PyQt6 import QtWidgets, QtCore
import requests

# zlapi import
from zlapi.simple import ZaloAPI

# browser control
from webdriver_manager.chrome import ChromeDriverManager
import undetected_chromedriver as uc

try:
    # Cần cài đặt pycryptodome để fallback AES-ECB hoạt động
    from base64 import b64decode
    from Crypto.Cipher import AES
    import hashlib
    CRYPTO_ENABLED = True
except ImportError:
    print("WARNING: pycryptodome not installed. Fallback AES-ECB decode may fail. Install with: pip install pycryptodome")
    CRYPTO_ENABLED = False


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
        
        # TAB 2: Decode Params (Universal)
        self.tab_decode_universal = QtWidgets.QWidget()
        self.setup_decode_universal_tab()
        self.tabs.addTab(self.tab_decode_universal, "🔓 Decode Params")
        
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
    
    # NEW UTILITY: Extract params from raw input (URL or raw string)
    def _extract_params_from_input(self, raw_input):
        """Phân tích chuỗi input (có thể là URL, query string, hoặc raw params) 
        để trích xuất giá trị params đã mã hóa."""
        raw_input = raw_input.strip()
        
        if not raw_input:
            return None
        
        encoded_params = raw_input

        try:
            # Kiểm tra nếu input là URL hoàn chỉnh hoặc có chứa query
            if "params=" in raw_input and (raw_input.startswith("http") or "?" in raw_input or raw_input.startswith("params=")):
                # Phân tích chuỗi query
                if not raw_input.startswith("http"):
                    # Xử lý trường hợp chỉ dán query string (ví dụ: ?a=1&params=xyz)
                    if not raw_input.startswith("?"):
                        raw_input = "?" + raw_input
                    parsed_url = urllib.parse.urlparse("http://dummy.com/" + raw_input)
                else:
                    parsed_url = urllib.parse.urlparse(raw_input)
                
                query_params = urllib.parse.parse_qs(parsed_url.query)
                
                if 'params' in query_params:
                    # Lấy giá trị đầu tiên của 'params' và URL-decode nó
                    encoded_params = query_params['params'][0]
                    encoded_params = urllib.parse.unquote(encoded_params)
                    # self.log("✅ Đã trích xuất params từ URL thành công.") # Bỏ log này để tránh spam
                    return encoded_params

            # Nếu không phải URL, giả định là chuỗi params đã mã hóa
            return encoded_params
            
        except Exception:
            # Nếu phân tích thất bại, trả về chuỗi gốc
            return raw_input


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
        self.check_btn.clicked.connect(self.on_check_group_with_effect)
        self.check_btn.setEnabled(False)
        self.check_btn.setStyleSheet("""
            QPushButton { 
                padding: 12px; 
                font-size: 14px; 
                font-weight: bold; 
                background-color: #0084ff; 
                color: white; 
                border-radius: 5px;
            } 
            QPushButton:hover { 
                background-color: #006dd1; 
            }
            QPushButton:pressed { 
                background-color: #0056b3; 
            }
            QPushButton:disabled { 
                background-color: #cccccc; 
            }
        """)
        scan_layout.addWidget(self.check_btn)
        
        # Nút decode nhanh từ link (chỉ decode trang 1, không phân trang)
        self.decode_link_btn = QtWidgets.QPushButton("🔎 Decode link (1 trang)")
        self.decode_link_btn.clicked.connect(self.on_decode_group_link_with_effect)
        self.decode_link_btn.setEnabled(False)
        self.decode_link_btn.setStyleSheet("""
            QPushButton { 
                padding: 10px; 
                font-size: 13px; 
                background-color: #17a2b8; 
                color: white; 
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #138496; }
            QPushButton:pressed { background-color: #117a8b; }
            QPushButton:disabled { background-color: #cccccc; }
        """)
        scan_layout.addWidget(self.decode_link_btn)
        
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
    
    def setup_decode_universal_tab(self):
        """Setup tab Decode Params (Universal)"""
        layout = QtWidgets.QVBoxLayout(self.tab_decode_universal)
        layout.setSpacing(15)
        
        decode_group = QtWidgets.QGroupBox("🔓 Decode Universal Params (Bất kỳ API nào)")
        decode_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 14px; }")
        decode_layout = QtWidgets.QVBoxLayout()
        
        decode_desc = QtWidgets.QLabel("Dán params (hoặc URL hoàn chỉnh) từ bất kỳ API mã hóa nào (sendreq, alias, convlabel, deliveredv2...) để decode.")
        decode_desc.setStyleSheet("QLabel { color: #666; font-style: italic; }")
        decode_layout.addWidget(decode_desc)
        
        self.universal_params_input = QtWidgets.QTextEdit()
        self.universal_params_input.setPlaceholderText("Dán params (hoặc URL hoàn chỉnh) vào đây...\nVí dụ: https://tt-group-wpa.chat.zalo.me/.../deliveredv2?params=xxxx")
        self.universal_params_input.setFixedHeight(200)
        self.universal_params_input.setStyleSheet("QTextEdit { padding: 8px; font-size: 12px; font-family: 'Consolas', monospace; }")
        decode_layout.addWidget(self.universal_params_input)
        
        self.decode_universal_btn = QtWidgets.QPushButton("🔑 Bắt đầu Decode")
        self.decode_universal_btn.clicked.connect(self.on_decode_universal_params_with_effect)
        self.decode_universal_btn.setEnabled(False)
        self.decode_universal_btn.setStyleSheet("""
            QPushButton { 
                padding: 12px; 
                font-size: 14px; 
                font-weight: bold; 
                background-color: #3f51b5; 
                color: white; 
                border-radius: 5px;
            } 
            QPushButton:hover { 
                background-color: #303f9f; 
            }
            QPushButton:pressed { 
                background-color: #283593; 
            }
            QPushButton:disabled { 
                background-color: #cccccc; 
            }
        """)
        decode_layout.addWidget(self.decode_universal_btn)
        
        decode_group.setLayout(decode_layout)
        layout.addWidget(decode_group)
        
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
                        # NOTE: inject_request_hook definition is removed in this version for simplicity, 
                        # relying on manual paste/scan flow.
                        # self.inject_request_hook()
                        self.log("🔗 Bỏ qua inject request hook (theo yêu cầu tối ưu).")
                        self.check_btn.setEnabled(True)
                    except Exception as e:
                        self.log("⚠ Không thể bật chức năng quét tự động:", e)
                        self.check_btn.setEnabled(True)
                    # enable paste-decode buttons when logged in
                    try:
                        self.paste_params_btn.setEnabled(True)
                        self.decode_link_btn.setEnabled(True)
                        self.decode_universal_btn.setEnabled(True)
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
        """Hàm decode chính, được sử dụng cho cả Group Info và Universal Decode nếu cần fallback"""
        try:
            if not self.session_cookies or not self.secret_key:
                self.log("Chưa có session/secret_key. Quét QR trước.")
                return None

            # Cập nhật state cho zlapi trước
            self.client._state._cookies = self.session_cookies
            self.client._state._config["secret_key"] = self.secret_key

            # 1. Thử decode trực tiếp bằng zlapi (thường cho universal params)
            try:
                decoded = self.client._decode(params_value)
                self.log("✅ Decode bằng zlapi (Mode 1: Raw params) thành công.")
                return decoded
            except Exception:
                # 2. Thử gọi API ginfo (thường cho quét nhóm/link)
                url = "https://tt-group-wpa.chat.zalo.me/api/group/link/ginfo"
                params = {"zpw_ver": 669, "zpw_type": 30, "params": params_value}
                headers = {
                    "User-Agent": self.user_agent,
                    "Accept": "application/json, text/plain, */*",
                    "Referer": "https://chat.zalo.me/",
                    "Origin": "https://chat.zalo.me"
                }

                self.log("Gọi ginfo (Mode 2) với params (cắt ngắn):", params_value[:60] + "..." if len(params_value) > 60 else params_value)
                r = requests.get(url, params=params, cookies=self.session_cookies, headers=headers, timeout=15)
                try:
                    j = r.json()
                except Exception:
                    self.log("ginfo: không parse JSON, raw:", r.text[:800])
                    return None

                enc = j.get("data") or j.get("payload") or j.get("enc") or j.get("response")

                if j.get("error_code") != 0:
                    self.log("ginfo trả lỗi:", json.dumps(j, ensure_ascii=False))
                    # Nếu có enc, cố gắng decode enc
                    if enc:
                        params_value = enc
                    else:
                        return None
                
                if enc:
                    # 3. Thử decode enc (từ response API)
                    try:
                        decoded = self.client._decode(enc)
                        self.log("✅ Decode bằng zlapi (Mode 3: API Response) thành công.")
                        return decoded
                    except Exception as e:
                        self.log(f"Không decode được API Response bằng zlapi ({e}). Thử Fallback AES-ECB...")

                # 4. Fallback AES-ECB (cho cả raw params và enc từ API response)
                if CRYPTO_ENABLED:
                    try:
                        raw = b64decode(params_value)
                        key = hashlib.md5(self.secret_key.encode()).digest()
                        cipher = AES.new(key, AES.MODE_ECB)
                        dec = cipher.decrypt(raw)
                        pad = dec[-1]
                        payload = dec[:-pad].decode(errors="ignore")
                        decoded = json.loads(payload)
                        self.log("✅ Decode bằng AES-ECB fallback thành công.")
                        return decoded
                    except Exception as e:
                        self.log("Fallback decode AES-ECB thất bại:", e)
                        return None
                else:
                    self.log("⚠️ Fallback AES-ECB không hoạt động (thiếu pycryptodome).")
                    return None

        except Exception as e:
            self.log("❌ Lỗi khi gọi get_group_info_by_params (wrapper):", e, traceback.format_exc())
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
                    # Try to extract params if it's a URL in manual paste
                    extracted = self._extract_params_from_input(part)
                    if extracted:
                        tokens.append(extracted)
                    else:
                        tokens.append(part) # Fallback to raw part

        if not tokens:
            self.log("⚠ Không tìm thấy token hợp lệ trong input.")
            return

        # Filter out duplicates after extraction attempt
        tokens = list(dict.fromkeys(tokens))
        
        self.log(f"\n{'='*60}")
        self.log(f"📥 BẮT ĐẦU XỬ LÝ {len(tokens)} PARAMS THỦ CÔNG")
        self.log(f"{'='*60}\n")
        self.tabs.setCurrentIndex(2) # Chuyển sang Log

        def worker(tok_list):
            try:
                all_members = []
                gid = None
                followed = 0
                for t in tok_list:
                    followed += 1
                    self.log(f"📄 Đang xử lý params #{followed}/{len(tok_list)}: {t[:60]}...")
                    # Sử dụng hàm decode chính
                    dec = self.get_group_info_by_params(t)
                    if not dec:
                        self.log(f"⚠ Không decode được token #{followed} (bỏ qua).")
                        continue
                    
                    # Log kết quả decode thủ công
                    self.log(">>> Kết quả Decode:")
                    self.log(json.dumps(dec, ensure_ascii=False, indent=2))
                    self.log("<<< Kết quả Decode")
                    
                    # try extract gid (giữ lại logic này cho group info)
                    try:
                        if isinstance(dec, dict):
                            g = dec.get("groupId") or dec.get("group_id") or (dec.get("data") or {}).get("groupId")
                            if g:
                                gid = gid or g
                    except Exception:
                        pass

                    # extract members (giữ lại logic này cho group info)
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
                            extracted_cand = self._extract_params_from_input(c)
                            if extracted_cand and extracted_cand not in tok_list:
                                self.log(f"🔍 Tự động thử candidate token: {extracted_cand[:40]}...")
                                tok_list.append(extracted_cand)
                    except Exception:
                        pass

                # save result (chỉ lưu nếu có members)
                if all_members:
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
                else:
                    self.log(f"\n{'='*60}")
                    self.log(f"✅ HOÀN TẤT: Không tìm thấy members nào để lưu file.")
                    self.log(f"{'='*60}\n")

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
        """
        found = []
        try:
            # quick helper to test a string for base64-like token
            def scan_str(s):
                if not s or not isinstance(s, str):
                    return []
                # common token characters in these params: A-Za-z0-9 - _ + / =
                matches = re.findall(r"[A-Za-z0-9\-\._\+/=]{24,300}", s)
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

    def on_check_group_with_effect(self):
        """Wrapper cho on_check_group với hiệu ứng button"""
        link = self.group_input.text().strip()
        if not link:
            self.log("⚠ Nhập link nhóm trước.")
            return
        if not self.secret_key or not self.session_cookies:
            self.log("⚠ Chưa có session hợp lệ. Quét QR trước.")
            return
        
        # Hiệu ứng: Disable button và đổi màu
        self.check_btn.setText("⏳ Đang quét...")
        self.check_btn.setEnabled(False)
        self.check_btn.setStyleSheet("""
            QPushButton { 
                padding: 12px; 
                font-size: 14px; 
                font-weight: bold; 
                background-color: #ffc107; 
                color: white; 
                border-radius: 5px;
            }
        """)
        
        # Chuyển sang tab Log ngay lập tức (Tab 3, index 2)
        self.tabs.setCurrentIndex(2)
        self.log("🔄 Đã nhận lệnh quét nhóm, đang xử lý...")
        
        # Xử lý trong background thread
        def worker():
            try:
                self.on_check_group()
            finally:
                # Reset button về trạng thái ban đầu
                self.check_btn.setText("▶ Bắt đầu quét nhóm")
                self.check_btn.setEnabled(True)
                self.check_btn.setStyleSheet("""
                    QPushButton { 
                        padding: 12px; 
                        font-size: 14px; 
                        font-weight: bold; 
                        background-color: #0084ff; 
                        color: white; 
                        border-radius: 5px;
                    } 
                    QPushButton:hover { 
                        background-color: #006dd1; 
                    }
                    QPushButton:pressed { 
                        background-color: #0056b3; 
                    }
                    QPushButton:disabled { 
                        background-color: #cccccc; 
                    }
                """)
        
        # Chạy trong thread riêng để không block UI
        t = threading.Thread(target=worker)
        t.daemon = True
        t.start()

    def on_decode_group_link_with_effect(self):
        """Wrapper to decode a single-page group info from the provided link with button effect."""
        link = self.group_input.text().strip()
        if not link:
            self.log("⚠ Nhập link nhóm trước.")
            return
        if not self.secret_key or not self.session_cookies:
            self.log("⚠ Chưa có session hợp lệ. Quét QR trước.")
            return

        # UI effect
        self.decode_link_btn.setText("⏳ Đang decode...")
        self.decode_link_btn.setEnabled(False)
        self.decode_link_btn.setStyleSheet("""
            QPushButton { padding: 10px; font-size: 13px; background-color: #ffc107; color: white; border-radius: 5px; }
        """)
        self.tabs.setCurrentIndex(2) # Log là Tab 3, index 2
        self.log("🔄 Đã nhận lệnh decode link, đang xử lý...")

        def worker():
            try:
                self._do_decode_group_link()
            finally:
                self.decode_link_btn.setText("🔎 Decode link (1 trang)")
                self.decode_link_btn.setEnabled(True)
                self.decode_link_btn.setStyleSheet("""
                    QPushButton { 
                        padding: 10px; 
                        font-size: 13px; 
                        background-color: #17a2b8; 
                        color: white; 
                        border-radius: 5px;
                    }
                    QPushButton:hover { background-color: #138496; }
                    QPushButton:pressed { background-color: #117a8b; }
                    QPushButton:disabled { background-color: #cccccc; }
                """)

        t = threading.Thread(target=worker)
        t.daemon = True
        t.start()

    def _do_decode_group_link(self):
        """Perform a single ginfo request for the provided link (mpage=1) and log decoded result."""
        try:
            link = self.group_input.text().strip()
            if not link:
                self.log("⚠ Nhập link nhóm trước.")
                return

            from urllib.parse import urlparse, unquote
            def clean_link(url):
                p = urlparse(url)
                path = unquote(p.path)
                parts = [seg for seg in path.split('/') if seg]
                if len(parts) >= 2 and parts[-2] == 'g':
                    return f"https://zalo.me/g/{parts[-1]}"
                return url.strip()

            cleaned = clean_link(link)
            self.log(f"🔎 Decoding link (1 trang): {cleaned}")

            # Build payload for page 1
            payload_obj = {
                "link": str(cleaned),
                "clientLang": "vi",
                "avatar_size": 120,
                "member_avatar_size": 120,
                "mpage": 1
            }

            try:
                encoded = self.client._encode(payload_obj)
            except Exception as e:
                self.log("❌ Lỗi encode payload bằng zlapi:", e)
                return

            # Use existing helper to call ginfo and decode
            decoded = self.get_group_info_by_params(encoded)
            if not decoded:
                self.log("⚠️ Không decode được link (ginfo trả lỗi hoặc không có data).")
                return

            self.log("✅ Kết quả decode (trang 1):")
            try:
                self.log(json.dumps(decoded, ensure_ascii=False, indent=2))
            except Exception:
                self.log(str(decoded))

            # Save a quick file
            try:
                gid = None
                if isinstance(decoded, dict):
                    gid = decoded.get("group_id") or decoded.get("groupId") or decoded.get("id")
                    if not gid and isinstance(decoded.get("data"), dict):
                        gid = decoded.get("data", {}).get("groupId")
                fname = f"group_{gid or 'link'}_info.json"
                with open(fname, 'w', encoding='utf-8') as fp:
                    json.dump(decoded, fp, ensure_ascii=False, indent=2)
                self.log(f"💾 Lưu kết quả vào: {fname}")
            except Exception as e:
                self.log("⚠ Không lưu được file kết quả:", e)

        except Exception as e:
            self.log("❌ Lỗi khi decode link:", e, traceback.format_exc())

    def on_check_group(self):
        link = self.group_input.text().strip()
        if not link:
            self.log("⚠ Nhập link nhóm trước.")
            return
        if not self.secret_key or not self.session_cookies:
            self.log("⚠ Chưa có session hợp lệ. Quét QR trước.")
            return

        # Chuyển sang tab Log để hiển thị kết quả (Tab 3, index 2)
        self.tabs.setCurrentIndex(2)

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
                # NOTE: Gọi trực tiếp API và decode response
                decoded = self.get_group_info_by_params(encoded_params)
                
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

    def on_decode_universal_params_with_effect(self):
        """Wrapper cho on_decode_universal_params với hiệu ứng button"""
        params_text = self.universal_params_input.toPlainText().strip()
        if not params_text:
            self.log("⚠ Vui lòng nhập params hoặc URL trước.")
            return
        if not self.secret_key or not self.session_cookies:
            self.log("⚠ Chưa có session hợp lệ. Quét QR trước.")
            return

        # UI effect
        self.decode_universal_btn.setText("⏳ Đang decode...")
        self.decode_universal_btn.setEnabled(False)
        self.decode_universal_btn.setStyleSheet("""
            QPushButton { 
                padding: 12px; 
                font-size: 14px; 
                font-weight: bold; 
                background-color: #ffc107; 
                color: white; 
                border-radius: 5px;
            }
        """)
        self.tabs.setCurrentIndex(2) # Log là Tab 3, index 2
        self.log("🔄 Đã nhận lệnh Decode Universal, đang xử lý...")

        # Xử lý trong background thread
        def worker():
            try:
                self._do_decode_universal_params()
            finally:
                # Reset button
                self.decode_universal_btn.setText("🔑 Bắt đầu Decode")
                self.decode_universal_btn.setEnabled(True)
                self.decode_universal_btn.setStyleSheet("""
                    QPushButton { 
                        padding: 12px; 
                        font-size: 14px; 
                        font-weight: bold; 
                        background-color: #3f51b5; 
                        color: white; 
                        border-radius: 5px;
                    } 
                    QPushButton:hover { 
                        background-color: #303f9f; 
                    }
                    QPushButton:pressed { 
                        background-color: #283593; 
                    }
                    QPushButton:disabled { 
                        background-color: #cccccc; 
                    }
                """)
        
        t = threading.Thread(target=worker)
        t.daemon = True
        t.start()

    def _do_decode_universal_params(self):
        """Thực hiện decode bất kỳ params nào được dán vào."""
        try:
            params_text = self.universal_params_input.toPlainText()
            encoded_params = self._extract_params_from_input(params_text)
            
            if not encoded_params:
                self.log("⚠️ Vui lòng nhập params hoặc URL hợp lệ.")
                return

            self.log(f"\n{'='*60}")
            self.log(f"🔓 DECODE UNIVERSAL PARAMS")
            self.log(f"{'='*60}")
            self.log(f"📋 Params (cắt ngắn): {encoded_params[:80]}...")
            
            # Sử dụng hàm decode chính
            decoded = self.get_group_info_by_params(encoded_params)
            
            if decoded:
                self.log(f"\n{'='*60}")
                self.log(f"✅ KẾT QUẢ DECODE CUỐI CÙNG:")
                self.log(f"{'='*60}")
                self.log(json.dumps(decoded, ensure_ascii=False, indent=2))
                self.log(f"{'='*60}\n")
                
                # Lưu kết quả
                try:
                    fname = f"universal_decode_{time.time()}.json"
                    with open(fname, 'w', encoding='utf-8') as fp:
                        json.dump(decoded, fp, ensure_ascii=False, indent=2)
                    self.log(f"💾 Lưu kết quả Decode Universal vào: {fname}")
                except Exception as e:
                    self.log("⚠ Không lưu được file kết quả:", e)
            else:
                self.log(f"\n{'='*60}")
                self.log(f"❌ DECODE THẤT BẠI: Không thể giải mã chuỗi này với Secret Key hiện tại.")
                self.log(f"{'='*60}\n")
                
        except Exception as e:
            self.log(f"❌ Lỗi khi decode universal: {e}")
            self.log(traceback.format_exc())


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = ZaloGroupGUI()
    w.show()
    sys.exit(app.exec())