import time
import json
import re
import traceback
import requests
from zlapi.simple import ZaloAPI

from utils.crypto import decrypt_aes_ecb, is_crypto_enabled

class ZaloService:
    def __init__(self):
        self.client = ZaloAPI(phone=None, password=None, imei="gui-imei-xyz", auto_login=False)
        self.session_cookies = None
        self.secret_key = None
        self.user_agent = "Mozilla/5.0"

    def obtain_secret_key(self, cookies, z_uuid, log_callback=None):
        """
        Gọi API getLoginInfo để lấy mã khóa bí mật (zpw_enk).
        """
        def log(*args):
            if log_callback:
                log_callback(*args)

        try:
            imei = z_uuid
            ts = int(time.time())
            url = f"https://wpa.chat.zalo.me/api/login/getLoginInfo?imei={imei}&type=30&client_version=645&computer_name=Web&ts={ts}"
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "Referer": "https://chat.zalo.me/",
                "Origin": "https://chat.zalo.me"
            }

            r = requests.get(url, headers=headers, cookies=cookies, timeout=12)
            try:
                j = r.json()
            except Exception:
                log("getLoginInfo: không parse JSON:", r.text[:300])
                return False

            if j.get("error_code") == 0 and j.get("data"):
                zpw_enk = j["data"].get("zpw_enk")
                if zpw_enk:
                    self.secret_key = zpw_enk
                    log("getLoginInfo trả zpw_enk (secret_key).")
                    return True

            elif j.get("error_code") == 602:
                log("getLoginInfo báo lỗi 602 -> thử lại với zpw_type=30")
                time.sleep(2)
                retry_url = url.replace("type=30", "zpw_type=30")
                r2 = requests.get(retry_url, headers=headers, cookies=cookies, timeout=12)
                try:
                    j2 = r2.json()
                except Exception:
                    log("Retry không parse JSON:", r2.text[:300])
                    return False
                zpw_enk = j2.get("data", {}).get("zpw_enk")
                if zpw_enk:
                    self.secret_key = zpw_enk
                    log("Retry thành công -> secret_key:", zpw_enk)
                    return True
                log("Retry vẫn lỗi:", j2)
                return False
            else:
                log("getLoginInfo trả lỗi:", j)
                return False

        except Exception as e:
            log("Lỗi gọi getLoginInfo:", e, traceback.format_exc())
            return False

    def decode_params(self, params_value, log_callback=None):
        """
        Hàm giải mã chính phục vụ giải mã Params Universal.
        """
        def log(*args):
            if log_callback:
                log_callback(*args)

        try:
            if not self.session_cookies or not self.secret_key:
                log("Chưa có session/secret_key. Quét QR trước.")
                return None

            # Cập nhật trạng thái cho client zlapi
            self.client._state._cookies = self.session_cookies
            self.client._state._config["secret_key"] = self.secret_key

            # 1. Thử giải mã trực tiếp qua zlapi
            try:
                decoded = self.client._decode(params_value)
                log("Decode bằng zlapi (Chế độ 1: Raw params) thành công.")
                return decoded
            except Exception:
                # 2. Thử gọi API ginfo
                url = "https://tt-group-wpa.chat.zalo.me/api/group/link/ginfo"
                params = {"zpw_ver": 669, "zpw_type": 30, "params": params_value}
                headers = {
                    "User-Agent": self.user_agent,
                    "Accept": "application/json, text/plain, */*",
                    "Referer": "https://chat.zalo.me/",
                    "Origin": "https://chat.zalo.me"
                }

                log("Gọi ginfo (Chế độ 2) với params (cắt ngắn):", params_value[:60] + "..." if len(params_value) > 60 else params_value)
                r = requests.get(url, params=params, cookies=self.session_cookies, headers=headers, timeout=15)
                try:
                    j = r.json()
                except Exception:
                    log("ginfo: không parse JSON, raw:", r.text[:800])
                    return None

                enc = j.get("data") or j.get("payload") or j.get("enc") or j.get("response")

                if j.get("error_code") != 0:
                    log("ginfo trả lỗi:", json.dumps(j, ensure_ascii=False))
                    if enc:
                        params_value = enc
                    else:
                        return None
                
                if enc:
                    # 3. Thử giải mã trường enc từ API Response nhận được
                    try:
                        decoded = self.client._decode(enc)
                        log("Decode bằng zlapi (Chế độ 3: API Response) thành công.")
                        return decoded
                    except Exception as e:
                        log(f"Không decode được API Response bằng zlapi ({e}). Thử dự phòng AES-ECB...")

                # 4. Dự phòng giải mã qua AES-ECB tự viết
                if is_crypto_enabled():
                    try:
                        decoded = decrypt_aes_ecb(params_value, self.secret_key)
                        log("Decode bằng AES-ECB dự phòng thành công.")
                        return decoded
                    except Exception as e:
                        log("Giải mã dự phòng AES-ECB thất bại:", e)
                        return None
                else:
                    log("Phương thức dự phòng AES-ECB không hoạt động (thiếu pycryptodome).")
                    return None

        except Exception as e:
            log("Lỗi hệ thống khi giải mã:", e, traceback.format_exc())
            return None
