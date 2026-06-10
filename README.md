<p align="center">
  <img src="resource/logo.png" alt="Zalo API Tools Logo" width="128" height="128">
</p>

# Zalo API Tools - Công cụ Giải mã API Zalo

Một ứng dụng Desktop hiện đại phát triển bằng **Python** và **PyQt6**, cung cấp công cụ giải mã (decode) các tham số mã hóa từ bất kỳ API nào của Zalo.

Giao diện ứng dụng được thiết kế theo phong cách tinh tế, chuyên nghiệp kiểu SaaS (Modern Light Slate SaaS Theme).

---

## Các tính năng chính

1. **Đăng nhập QR tự động**: Tự động mở trình duyệt Chrome (`undetected-chromedriver`), bắt các sự kiện đăng nhập (`session cookies` và Local Storage `z_uuid`), từ đó tự động trích xuất `secret_key` từ Zalo API.
2. **Hỗ trợ Debug thủ công với DevTools**:
   * Tự động mở cửa sổ Chrome DevTools khi chạy trình duyệt.
   * Tự động chuyển thẳng sang tab **Network** và tích sẵn ô **Preserve log** để dễ dàng theo dõi các gói tin.
3. **Giải mã Universal Params**:
   * Giải mã `params` mã hóa từ bất kỳ API nào của Zalo (ví dụ: `sendreq`, `alias`, `convlabel`, `deliveredv2`...).
   * Hỗ trợ lưu kết quả đã giải mã thành file `.json`.

---

## Cấu trúc thư mục dự án

Dự án được cấu trúc modular hóa rõ ràng:

```
d:\Test-zalo\request\
├── main.py                     # File chạy chính của ứng dụng
├── requirements.txt            # Danh sách thư viện phụ thuộc
├── utils/                      # Chức năng tiện ích bổ trợ
│   ├── crypto.py               # Thuật toán AES-ECB giải mã fallback
│   ├── browser.py              # Cấu hình Selenium và vá các tiến trình lỗi
│   └── url_helpers.py          # Trích xuất và làm sạch đường dẫn
├── services/                   # Nghiệp vụ logic chính
│   └── zalo_service.py         # Quản lý ZaloAPI client, mã hóa & giải mã dữ liệu
└── ui/                         # Thành phần giao diện người dùng
    ├── styles.py               # Giao diện sáng phong cách SaaS (QSS)
    ├── main_gui.py             # Lớp Shell chính kết nối các component
    ├── decode_universal_tab.py # Giao diện Tab Giải mã Params
    └── log_tab.py              # Giao diện màn hình hiển thị log kết quả
```

---

## Yêu cầu hệ thống

* **Python 3.8+**
* Google Chrome đã được cài đặt trên hệ thống (để chạy Chrome Driver)

---

## Hướng dẫn cài đặt & Khởi chạy

1. **Cài đặt các thư viện phụ thuộc**:
   Mở terminal trong thư mục dự án và chạy lệnh:
   ```bash
   pip install -r requirements.txt
   ```
2. **Khởi chạy ứng dụng**:
   Chạy lệnh:
   ```bash
   python main.py
   ```

---

## Hướng dẫn sử dụng

1. **Bước 1**: Nhấn nút **Mở trình duyệt (Quét mã QR)**. Một trình duyệt Chrome tự động sẽ xuất hiện kèm theo cửa sổ DevTools đã mở sẵn ở tab **Network** và đã tích **Preserve log**.
2. **Bước 2**: Nhấp chọn nút bộ lọc **Fetch/XHR** trên tab Network của cửa sổ DevTools để lọc gói tin. Sau đó tiến hành quét mã QR đăng nhập tài khoản Zalo của bạn.
3. **Bước 3**: Sau khi đăng nhập thành công, thanh trạng thái sẽ chuyển sang màu xanh lá báo `Đã đăng nhập | Secret key...`. Trình duyệt có thể tự đóng hoặc bạn có thể nhấn **Đóng trình duyệt**. Lúc này, nút tính năng giải mã sẽ được kích hoạt.
4. **Bước 4 (Giải mã API)**: Sao chép URL API hoặc chuỗi `params=` thu được trong tab Network của DevTools, dán vào Tab **Giải mã Params** -> nhấn **Bắt đầu giải mã**. Bạn có thể bấm **Lưu kết quả giải mã** để xuất dữ liệu ra file JSON.
