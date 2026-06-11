from PyQt6 import QtWidgets, QtCore

class LogTab(QtWidgets.QWidget):
    log_signal = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.log_signal.connect(self._log_on_gui)

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Thanh chứa nút xóa log
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        
        self.clear_log_btn = QtWidgets.QPushButton("Xóa log")
        self.clear_log_btn.setObjectName("danger_btn")
        self.clear_log_btn.clicked.connect(self.clear_log)
        btn_layout.addWidget(self.clear_log_btn)
        
        layout.addLayout(btn_layout)
        
        self.output_box = QtWidgets.QTextEdit()
        self.output_box.setReadOnly(True)
        self.output_box.setAcceptRichText(False)
        layout.addWidget(self.output_box)
    
    def clear_log(self):
        """Xóa toàn bộ nội dung trong khung hiển thị log"""
        self.output_box.clear()
        self.log("Đã xóa nhật ký log")

    def log(self, *args):
        """Ghi nhận tin nhắn mới và hiển thị lên khung log"""
        txt = " ".join(str(a) for a in args)
        self.log_signal.emit(txt)

    def _log_on_gui(self, txt):
        self.output_box.append(txt)
        self.output_box.ensureCursorVisible()
