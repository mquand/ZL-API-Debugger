import urllib.parse


def extract_params_from_input(raw_input):
    """
    Phân tích chuỗi đầu vào (có thể là URL đầy đủ, chuỗi truy vấn query string, hoặc chuỗi params thô)
    để trích xuất giá trị params đã được mã hóa.
    """
    raw_input = raw_input.strip()
    if not raw_input:
        return None
    
    encoded_params = raw_input
    try:
        # Kiểm tra nếu đầu vào là một URL hoàn chỉnh hoặc có chứa tham số query params
        if "params=" in raw_input and (raw_input.startswith("http") or "?" in raw_input or raw_input.startswith("params=")):
            if not raw_input.startswith("http"):
                # Xử lý trường hợp chỉ là chuỗi query string (?a=1&params=xyz)
                if not raw_input.startswith("?"):
                    raw_input = "?" + raw_input
                parsed_url = urllib.parse.urlparse("http://dummy.com/" + raw_input)
            else:
                parsed_url = urllib.parse.urlparse(raw_input)
            
            query_params = urllib.parse.parse_qs(parsed_url.query)
            if 'params' in query_params:
                encoded_params = query_params['params'][0]
                encoded_params = urllib.parse.unquote(encoded_params)
                return encoded_params

        return encoded_params
    except Exception:
        return raw_input
