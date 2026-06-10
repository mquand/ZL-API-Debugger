import json
import traceback
import threading
# pyrefly: ignore [missing-import]
from PyQt6 import QtWidgets, QtCore

from utils import extract_params_from_input

class DecodeUniversalTab(QtWidgets.QWidget):
    # Tín hiệu an toàn luồng (thread-safe signal) để thông báo cho luồng UI khi quá trình giải mã kết thúc (truyền giá trị bool thành công)
    decode_finished = QtCore.pyqtSignal(bool)

    def __init__(self, zalo_service, log_callback, tab_switch_callback, parent=None):
        super().__init__(parent)
        self.zalo_service = zalo_service
        self.log_callback = log_callback
        self.tab_switch_callback = tab_switch_callback
        self.last_decoded_result = None
        
        # Kết nối tín hiệu để cập nhật giao diện luồng UI một cách an toàn
        self.decode_finished.connect(self.on_decode_finished)
        
        self.init_ui()

    def log(self, *args):
        if self.log_callback:
            self.log_callback(*args)

    def switch_to_log_tab(self):
        if self.tab_switch_callback:
            self.tab_switch_callback()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)

        decode_group = QtWidgets.QGroupBox("Giải mã API Params Universal (Bất kỳ API nào)")
        decode_layout = QtWidgets.QVBoxLayout()

        decode_desc = QtWidgets.QLabel("Dán params (hoặc URL hoàn chỉnh) từ bất kỳ API mã hóa nào (sendreq, alias, convlabel, deliveredv2...) để giải mã.")
        decode_desc.setObjectName("subtext")
        decode_layout.addWidget(decode_desc)

        self.universal_params_input = QtWidgets.QTextEdit()
        self.universal_params_input.setPlaceholderText("Dán params (hoặc URL hoàn chỉnh) vào đây...\nVí dụ: https://tt-group-wpa.chat.zalo.me/.../deliveredv2?params=xxxx")
        self.universal_params_input.setFixedHeight(220)
        decode_layout.addWidget(self.universal_params_input)

        self.decode_universal_btn = QtWidgets.QPushButton("Bắt đầu giải mã")
        self.decode_universal_btn.setObjectName("primary_btn")
        self.decode_universal_btn.clicked.connect(self.on_decode_universal_params_with_effect)
        self.decode_universal_btn.setEnabled(False)
        decode_layout.addWidget(self.decode_universal_btn)

        self.save_decode_btn = QtWidgets.QPushButton("Lưu kết quả giải mã")
        self.save_decode_btn.setObjectName("action_btn")
        self.save_decode_btn.clicked.connect(self.on_save_decode)
        self.save_decode_btn.setEnabled(False)
        decode_layout.addWidget(self.save_decode_btn)

        decode_group.setLayout(decode_layout)
        layout.addWidget(decode_group)

        layout.addStretch()

    def set_auth_enabled(self, enabled):
        self.decode_universal_btn.setEnabled(enabled)

    def on_decode_universal_params_with_effect(self):
        params_text = self.universal_params_input.toPlainText().strip()
        if not params_text:
            self.log("Vui lòng nhập params hoặc URL trước.")
            return
        if not self.zalo_service.secret_key or not self.zalo_service.session_cookies:
            self.log("Chưa có phiên làm việc hợp lệ. Hãy quét mã QR trước.")
            return

        self.decode_universal_btn.setText("Đang giải mã...")
        self.decode_universal_btn.setEnabled(False)
        self.save_decode_btn.setEnabled(False)
        self.switch_to_log_tab()
        self.log("Đã nhận lệnh giải mã Universal, đang xử lý...")

        def worker():
            try:
                self._do_decode_universal_params()
            finally:
                # Kích hoạt cập nhật giao diện trên luồng chính thông qua tín hiệu signal một cách an toàn
                self.decode_finished.emit(self.last_decoded_result is not None)
        
        t = threading.Thread(target=worker)
        t.daemon = True
        t.start()

    def on_decode_finished(self, success):
        """Được thực thi trên luồng chính GUI một cách an toàn"""
        self.decode_universal_btn.setText("Bắt đầu giải mã")
        self.decode_universal_btn.setEnabled(True)
        self.save_decode_btn.setEnabled(success)

    def _do_decode_universal_params(self):
        try:
            params_text = self.universal_params_input.toPlainText()
            encoded_params = extract_params_from_input(params_text)
            
            if not encoded_params:
                self.log("Vui lòng nhập params hoặc URL hợp lệ.")
                return

            self.log(f"\n{'='*60}")
            self.log("GIẢI MÃ UNIVERSAL PARAMS")
            self.log(f"{'='*60}")
            self.log(f"Params (cắt ngắn): {encoded_params[:80]}...")
            
            decoded = self.zalo_service.decode_params(encoded_params, log_callback=self.log)
            if decoded:
                self.log(f"\n{'='*60}")
                self.log("KẾT QỦA GIẢI MÃ CUỐI CÙNG:")
                self.log(f"{'='*60}")
                self.log(json.dumps(decoded, ensure_ascii=False, indent=2))
                self.log(f"{'='*60}\n")
                
                self.last_decoded_result = decoded
            else:
                self.log(f"\n{'='*60}")
                self.log("GIẢI MÃ THẤT BẠI: Không thể giải mã chuỗi này với Secret Key hiện tại.")
                self.log(f"{'='*60}\n")
                self.last_decoded_result = None
                
        except Exception as e:
            self.log(f"Lỗi khi giải mã universal: {e}")
            self.log(traceback.format_exc())

    def on_save_decode(self):
        if not self.last_decoded_result:
            self.log("Không có kết quả giải mã để lưu.")
            return
        
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 
            "Lưu kết quả giải mã", 
            "", 
            "JSON Files (*.json);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', encoding='utf-8') as fp:
                json.dump(self.last_decoded_result, fp, ensure_ascii=False, indent=2)
            self.log(f"Đã lưu kết quả giải mã vào: {file_path}")
        except Exception as e:
            self.log(f"Lỗi khi lưu file: {e}")
