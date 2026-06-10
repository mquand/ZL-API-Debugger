# File định dạng giao diện QSS phong cách SaaS sáng (Light Slate)

SAAS_STYLING = """
/* Định dạng chung cho các Widget */
QWidget {
    background-color: #F8FAFC;
    color: #0F172A;
    font-family: "Segoe UI", "Segoe UI Semibold", "Inter", sans-serif;
    font-size: 13px;
}

/* Định dạng thanh cuộn (Scrollbar) */
QScrollBar:vertical {
    border: none;
    background: #F8FAFC;
    width: 8px;
    margin: 0px 0 0px 0;
}
QScrollBar::handle:vertical {
    background: #CBD5E1;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #94A3B8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Định dạng Nhãn chữ (Label) */
QLabel {
    color: #0F172A;
}
QLabel#subtext {
    color: #475569;
    font-size: 12px;
}

/* Định dạng Thanh trạng thái (Status Bar) */
QLabel#status_label {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    padding: 10px;
    border-radius: 8px;
    font-weight: bold;
    color: #0284C7;
}

/* Định dạng Hộp nhóm (GroupBox - các khung giao diện) */
QGroupBox {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    margin-top: 16px;
    font-weight: bold;
    font-size: 14px;
    padding: 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 2px 8px;
    color: #4F46E5;
}

/* Định dạng Nút bấm (Button) */
QPushButton {
    background-color: #4F46E5;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #4338CA;
}
QPushButton:pressed {
    background-color: #3730A3;
}
QPushButton:disabled {
    background-color: #E2E8F0;
    color: #94A3B8;
    border: 1px solid #CBD5E1;
}

/* Nút bấm nổi bật / chính (Primary buttons) */
QPushButton#primary_btn {
    background-color: #4F46E5;
}
QPushButton#primary_btn:hover {
    background-color: #4338CA;
}
QPushButton#primary_btn:pressed {
    background-color: #3730A3;
}

/* Nút bấm hành động phụ (Action buttons) */
QPushButton#action_btn {
    background-color: #0EA5E9;
}
QPushButton#action_btn:hover {
    background-color: #0284C7;
}

/* Nút bấm nguy hiểm / xóa (Danger/Delete buttons) */
QPushButton#danger_btn {
    background-color: #EF4444;
}
QPushButton#danger_btn:hover {
    background-color: #DC2626;
}

/* Ô nhập liệu văn bản (LineEdit và TextEdit) */
QLineEdit, QTextEdit {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 8px;
    color: #0F172A;
    font-family: "Consolas", monospace;
    font-size: 13px;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #4F46E5;
}

/* Định dạng Tab Widget */
QTabWidget::pane {
    border: 1px solid #E2E8F0;
    background-color: #FFFFFF;
    border-radius: 8px;
    top: -1px;
}
QTabBar::tab {
    background-color: #F1F5F9;
    color: #64748B;
    padding: 10px 20px;
    border: 1px solid #E2E8F0;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 4px;
}
QTabBar::tab:hover {
    background-color: #E2E8F0;
    color: #0F172A;
}
QTabBar::tab:selected {
    background-color: #FFFFFF;
    color: #0F172A;
    border-bottom: 2px solid #4F46E5;
}
"""
