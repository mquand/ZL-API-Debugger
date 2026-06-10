import time
import json
import traceback
from PyQt6 import QtWidgets, QtCore, QtGui
from utils import browser_builder, REQUIRED_COOKIE_KEYS, POLL_INTERVAL, POLL_TIMEOUT
from services import ZaloService
from ui.styles import SAAS_STYLING
from ui.log_tab import LogTab
from ui.decode_universal_tab import DecodeUniversalTab

class ZaloGroupGUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Zalo API Tools - Công cụ Zalo toàn diện")
        self.setGeometry(300, 200, 950, 780)
        
        # Thiết lập icon cho cửa sổ ứng dụng và thanh taskbar trên Windows từ tệp icon.png vuông
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base_dir, "resource", "icon.png")
        self.setWindowIcon(QtGui.QIcon(icon_path))
        
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("zalo.api.decoder.v1")
        except Exception:
            pass
            
        self.zalo_service = ZaloService()
        self.driver = None
        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)

        # === Bố cục tiêu đề cùng với Logo ===
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(15)
        
        self.logo_label = QtWidgets.QLabel()
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logo_path = os.path.join(base_dir, "resource", "logo.png")
        logo_pixmap = QtGui.QPixmap(logo_path)
        if not logo_pixmap.isNull():
            self.logo_label.setPixmap(logo_pixmap.scaledToHeight(64, QtCore.Qt.TransformationMode.SmoothTransformation))
        else:
            self.logo_label.setText("[LOGO]")
            self.logo_label.setStyleSheet("font-weight: bold; color: #4F46E5;")
            
        header_layout.addWidget(self.logo_label)
        
        title_layout = QtWidgets.QVBoxLayout()
        app_title = QtWidgets.QLabel("ZALO API TOOLS")
        app_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #4F46E5;")
        app_subtitle = QtWidgets.QLabel("Công cụ Giải mã API Params Zalo toàn diện")
        app_subtitle.setObjectName("subtext")
        app_subtitle.setStyleSheet("font-size: 13px;")
        
        title_layout.addWidget(app_title)
        title_layout.addWidget(app_subtitle)
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)

        # === Thanh trạng thái ===
        self.status_label = QtWidgets.QLabel("Trạng thái: Chưa đăng nhập")
        self.status_label.setObjectName("status_label")
        layout.addWidget(self.status_label)

        # === Phần đăng nhập (Luôn hiển thị) ===
        login_group = QtWidgets.QGroupBox("Đăng nhập Zalo")
        login_layout = QtWidgets.QHBoxLayout()
        
        self.open_btn = QtWidgets.QPushButton("Mở trình duyệt (Quét mã QR)")
        self.open_btn.setObjectName("primary_btn")
        self.open_btn.clicked.connect(self.open_browser)
        login_layout.addWidget(self.open_btn)

        self.close_btn = QtWidgets.QPushButton("Đóng trình duyệt")
        self.close_btn.setObjectName("danger_btn")
        self.close_btn.clicked.connect(self.close_browser)
        self.close_btn.setEnabled(False)
        login_layout.addWidget(self.close_btn)
        
        login_group.setLayout(login_layout)
        layout.addWidget(login_group)

        # === Quản lý các Tab ===
        self.tabs = QtWidgets.QTabWidget()
        self.tab_log_widget = LogTab()
        self.tab_decode_widget = DecodeUniversalTab(
            zalo_service=self.zalo_service,
            log_callback=self.tab_log_widget.log,
            tab_switch_callback=lambda: self.tabs.setCurrentIndex(1)
        )
        self.tabs.addTab(self.tab_decode_widget, "Giải mã Params")
        self.tabs.addTab(self.tab_log_widget, "Kết quả & Log")
        layout.addWidget(self.tabs)

    def apply_styles(self):
        self.setStyleSheet(SAAS_STYLING)

    def log(self, *args):
        self.tab_log_widget.log(*args)

    def open_browser(self):
        try:
            self.status_label.setText("Đang mở trình duyệt...")
            self.status_label.setStyleSheet("QLabel#status_label { color: #0284C7; background-color: #FFFFFF; border-color: #0284C7; }")
            self.log("Mở trình duyệt. Hãy quét mã QR trong cửa sổ trình duyệt vừa mở.")
            self.driver = browser_builder()
            
            self.driver.get("https://chat.zalo.me/")
            self.open_btn.setEnabled(False)
            self.close_btn.setEnabled(True)
            self.start_time = time.time()
            
            # Bắt đầu kiểm tra phiên làm việc (session)
            QtCore.QTimer.singleShot(1000, self.poll_for_session)
        except Exception as e:
            self.status_label.setText(f"Không mở được trình duyệt: {e}")
            self.status_label.setStyleSheet("QLabel#status_label { color: #EF4444; background-color: #FFFFFF; border-color: #EF4444; }")
            self.log("Lỗi mở trình duyệt:", e, traceback.format_exc())

    def close_browser(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
        self.driver = None
        self.open_btn.setEnabled(True)
        self.close_btn.setEnabled(False)
        has_auth = bool(self.zalo_service.secret_key)
        self.tab_decode_widget.set_auth_enabled(has_auth)
        self.status_label.setText("Trình duyệt đã đóng")
        self.status_label.setStyleSheet("QLabel#status_label { color: #475569; background-color: #FFFFFF; border-color: #CBD5E1; }")
        self.log("Trình duyệt đã đóng.")

    def poll_for_session(self):
        if not self.driver:
            return
        elapsed = time.time() - getattr(self, "start_time", 0)
        if elapsed > POLL_TIMEOUT:
            self.status_label.setText("Hết thời gian chờ đăng nhập (QR). Hãy thử lại.")
            self.status_label.setStyleSheet("QLabel#status_label { color: #EF4444; background-color: #FFFFFF; border-color: #EF4444; }")
            self.log("Hết thời gian chờ lấy cookies/localStorage.")
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
            status = f"Đợi quét QR... Cookies: {len(present)}/{len(REQUIRED_COOKIE_KEYS)} | z_uuid: {'Có' if z_uuid else 'Không'}"
            self.status_label.setText(status)
            self.status_label.setStyleSheet("QLabel#status_label { color: #0284C7; background-color: #FFFFFF; border-color: #0284C7; }")

            if all(k in cookies for k in REQUIRED_COOKIE_KEYS) and z_uuid:
                self.zalo_service.session_cookies = cookies
                self.zalo_service.user_agent = self.driver.execute_script("return navigator.userAgent;")
                self.log("Thu thập cookies + localStorage thành công. Đang lấy secret_key...")
                got = self.zalo_service.obtain_secret_key(cookies, z_uuid, log_callback=self.log)
                if got:
                    self.status_label.setText(f"Đã đăng nhập | Secret key: {self.zalo_service.secret_key[:20]}...")
                    self.status_label.setStyleSheet("QLabel#status_label { color: #10B981; background-color: #FFFFFF; border-color: #10B981; }")
                    self.log(f"Secret key thu được: {self.zalo_service.secret_key}")
                    try:
                        self.zalo_service.client._state._cookies = cookies
                        self.zalo_service.client._state._config["secret_key"] = self.zalo_service.secret_key
                    except Exception as e:
                        self.log("Không thiết lập được trạng thái cho zlapi:", e)
                    
                    self.log("Bỏ qua inject request hook (theo yêu cầu tối ưu hóa).")
                    
                    # Kích hoạt các nút chức năng sau khi đăng nhập thành công
                    self.tab_decode_widget.set_auth_enabled(True)
                    return
                else:
                    self.log("Không lấy được secret_key. Hãy thử chờ thêm hoặc quét lại mã QR.")
                    self.status_label.setText("Không lấy được secret_key")
                    self.status_label.setStyleSheet("QLabel#status_label { color: #EF4444; background-color: #FFFFFF; border-color: #EF4444; }")
                    return
        except Exception as e:
            err_msg = str(e).lower()
            if "invalid session id" in err_msg or "not connected to devtools" in err_msg or "chrome not reachable" in err_msg:
                self.close_browser()
                return
            else:
                self.log("Lỗi trong quá trình kiểm tra đăng nhập:", e)

        QtCore.QTimer.singleShot(int(POLL_INTERVAL * 1000), self.poll_for_session)
