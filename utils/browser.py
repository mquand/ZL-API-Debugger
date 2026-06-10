import undetected_chromedriver as uc
# pyrefly: ignore [missing-import]
from webdriver_manager.chrome import ChromeDriverManager

# Vá hàm hủy của undetected_chromedriver để ẩn lỗi WinError 6 (Invalid handle) khi thoát ứng dụng
try:
    _orig_del = uc.Chrome.__del__
    def _safe_del(self):
        try:
            _orig_del(self)
        except Exception:
            pass
    uc.Chrome.__del__ = _safe_del
except Exception:
    pass

# Vá hàm hủy của subprocess.Popen để tránh lỗi OSError: [WinError 6] The handle is invalid trong quá trình dọn dẹp bộ nhớ (garbage collection)
import subprocess
try:
    _orig_popen_del = subprocess.Popen.__del__
    def _safe_popen_del(self):
        try:
            _orig_popen_del(self)
        except Exception:
            pass
    subprocess.Popen.__del__ = _safe_popen_del
except Exception:
    pass

REQUIRED_COOKIE_KEYS = ["__zi", "zpsid", "zpw_sek", "_zlang", "app.event.zalo.me"]
POLL_INTERVAL = 1.0
POLL_TIMEOUT = 180  # số giây chờ quét cookies + localStorage

def browser_builder():
    """
    Khởi tạo và trả về phiên bản trình duyệt Chrome tự động (undetected-chromedriver)
    với cấu hình tự động mở DevTools và ẩn các cảnh báo/lỗi hệ thống từ chromedriver.
    """
    options = uc.ChromeOptions()
    
    # Tự động mở cửa sổ Chrome DevTools khi trình duyệt khởi động
    options.add_argument("--auto-open-devtools-for-tabs")
    
    # Cấu hình mặc định mở tab Network và tích chọn Preserve Log trong DevTools
    options.add_experimental_option("prefs", {
        "devtools": {
            "preferences": {
                "panel-selectedTab": "\"network\"",
                "panel-selected-tab": "\"network\"",
                "network-log.preserve-log": "\"true\""
            }
        }
    })
    
    # Ẩn các log hệ thống không cần thiết từ chromedriver ra màn hình terminal
    options.add_argument("--log-level=3")
    
    return uc.Chrome(driver_executable_path=ChromeDriverManager().install(), options=options)
