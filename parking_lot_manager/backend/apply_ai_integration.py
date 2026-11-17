"""Idempotently patches the existing Flask app.py to expose the local AI worker API.
Run from the backend folder with any Python 3.10+; uses stdlib only.
Creates app.py.bak before changing anything.
"""
from pathlib import Path
import shutil
import sys

BASE = Path(__file__).resolve().parent
APP = BASE / "app.py"
WORKER = BASE / "plate_ai_worker.py"

if not APP.is_file():
    print(f"ERROR: Không thấy {APP}. Hãy đặt file này trong thư mục backend.")
    raise SystemExit(2)
if not WORKER.is_file():
    print(f"ERROR: Không thấy {WORKER}. Hãy giải nén plate_ai_worker.py cùng thư mục.")
    raise SystemExit(2)

text = APP.read_text(encoding="utf-8")
original = text

# Imports are stdlib and safe to add to the existing import group.
if "import json" not in text:
    text = text.replace("import os, re, secrets, warnings", "import os, re, secrets, warnings, json, subprocess", 1)
    if text == original:
        # Handle a changed import line without discarding local edits.
        text = "import json\nimport subprocess\n" + text
elif "import subprocess" not in text:
    text = text.replace("import json", "import json\nimport subprocess", 1)

# Enable only local Flutter development origins; don't use wildcard CORS.
if "Access-Control-Allow-Origin" not in text:
    func_start = text.find("@app.after_request\ndef add_security_headers(response):")
    if func_start < 0:
        print("ERROR: Không tìm thấy hàm add_security_headers(response). Không sửa app.py.")
        raise SystemExit(2)
    class_start = text.find("\nclass VehicleSession", func_start)
    if class_start < 0:
        print("ERROR: Không tìm thấy điểm kết thúc hàm add_security_headers. Không sửa app.py.")
        raise SystemExit(2)
    section = text[func_start:class_start]
    if "    return response" not in section:
        print("ERROR: Không tìm thấy return response trong add_security_headers. Không sửa app.py.")
        raise SystemExit(2)
    cors_block = '''    origin = request.headers.get("Origin", "")
    if re.fullmatch(r"http://(localhost|127\\.0\\.0\\.1):\\d+", origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Device-Token"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Max-Age"] = "600"
'''
    section = section.replace("    return response", cors_block + "    return response", 1)
    text = text[:func_start] + section + text[class_start:]

# Add AI endpoint before entry route, only once.
if 'def api_recognize_plate()' not in text:
    marker = '@app.post("/api/vehicles/entry")'
    pos = text.find(marker)
    if pos < 0:
        print('ERROR: Không tìm thấy @app.post("/api/vehicles/entry"). Không sửa app.py.')
        raise SystemExit(2)
    route_path = BASE / "plate_ai_route_snippet.py.txt"
    if route_path.is_file():
        route = route_path.read_text(encoding="utf-8")
    else:
        # The update ZIP distributes this snippet next to this patcher.
        print("ERROR: Thiếu plate_ai_route_snippet.py.txt cùng thư mục. Không sửa app.py.")
        raise SystemExit(2)
    text = text[:pos] + route.rstrip() + "\n\n" + text[pos:]

if text == original:
    print("Không cần thay đổi: tích hợp AI có vẻ đã được áp dụng trước đó.")
    raise SystemExit(0)

backup = APP.with_suffix(".py.bak")
if not backup.exists():
    shutil.copy2(APP, backup)
APP.write_text(text, encoding="utf-8", newline="\n")
print(f"Đã cập nhật: {APP}")
print(f"Bản sao lưu: {backup}")
print("Đã thêm endpoint POST /api/plates/recognize và cấu hình CORS localhost (nếu chưa có).")
print("Khởi động lại Flask rồi kiểm tra GET /api/health.")
