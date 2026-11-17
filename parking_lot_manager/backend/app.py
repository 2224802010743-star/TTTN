import os, re, secrets, warnings, json, subprocess
from datetime import datetime, date
from pathlib import Path
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, send_from_directory, abort, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = (BASE_DIR / os.getenv("UPLOAD_FOLDER", "uploads")).resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_MB = int(os.getenv("MAX_CONTENT_LENGTH_MB", "8"))
ALLOWED_EXT = {"jpg", "jpeg", "png", "webp"}
Image.MAX_IMAGE_PIXELS = 20_000_000  # reject suspiciously large/decompression-bomb images
warnings.simplefilter("error", Image.DecompressionBombWarning)

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "unsafe-development-secret-change-me"),
    SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///parking_dev.db"),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAX_CONTENT_LENGTH=MAX_MB * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",  # Set True behind HTTPS.
)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "admin_login"

@app.context_processor
def inject_csrf_token():
    def csrf_token():
        token = session.get("_csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["_csrf_token"] = token
        return token
    return {"csrf_token": csrf_token}

@app.before_request
def protect_admin_posts_with_csrf():
    if request.method == "POST" and request.path.startswith("/admin/"):
        expected = session.get("_csrf_token", "")
        supplied = request.form.get("csrf_token", "")
        if not expected or not supplied or not secrets.compare_digest(expected, supplied):
            abort(400, description="CSRF token không hợp lệ. Hãy tải lại trang và thử lại.")

@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Cache-Control", "no-store")
    origin = request.headers.get("Origin", "")
    if re.fullmatch(r"http://(localhost|127\.0\.0\.1):\d+", origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, X-Device-Token"
        )
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

class VehicleSession(db.Model):
    __tablename__ = "vehicle_sessions"
    id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True)
    plate = db.Column(db.String(20), nullable=False, index=True)
    status = db.Column(db.Enum("IN", "EXITED"), nullable=False, default="IN", index=True)
    active_plate = db.Column(db.String(20), db.Computed("CASE WHEN status = 'IN' THEN plate ELSE NULL END", persisted=True), unique=True)
    entry_time = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    exit_time = db.Column(db.DateTime, nullable=True)
    entry_image = db.Column(db.String(255), nullable=False)
    exit_image = db.Column(db.String(255), nullable=True)
    entry_source = db.Column(db.String(32), nullable=False, default="flutter")
    exit_source = db.Column(db.String(32), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

class AdminUser(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(user_id):
    if user_id == os.getenv("ADMIN_USERNAME", "admin"):
        return AdminUser(user_id)
    return None

def normalize_plate(value):
    value = (value or "").upper().strip()
    return re.sub(r"[^A-Z0-9]", "", value)

def api_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = os.getenv("API_DEVICE_TOKEN", "")
        provided = request.headers.get("X-Device-Token", "")
        if not expected or len(expected) < 24 or not secrets.compare_digest(provided, expected):
            return jsonify(error="unauthorized", message="Thiếu hoặc sai X-Device-Token"), 401
        return fn(*args, **kwargs)
    return wrapper

def save_image(file):
    if not file or not file.filename:
        return None, "Thiếu ảnh"
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXT:
        return None, "Chỉ chấp nhận jpg, jpeg, png, webp"
    # Ignore user-provided filename; random server-generated name prevents traversal/collisions.
    name = f"{secrets.token_hex(16)}.{ext}"
    target = UPLOAD_DIR / name
    file.save(target)
    expected_formats = {"jpg": {"JPEG"}, "jpeg": {"JPEG"}, "png": {"PNG"}, "webp": {"WEBP"}}[ext]
    try:
        with Image.open(target) as image:
            if image.format not in expected_formats:
                target.unlink(missing_ok=True)
                return None, "Nội dung tệp không khớp định dạng ảnh đã chọn"
            image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        target.unlink(missing_ok=True)
        return None, "Tệp ảnh bị lỗi hoặc không hợp lệ"
    return name, None

def delete_image(relative_name):
    if not relative_name:
        return True
    # Only delete a basename under UPLOAD_DIR.
    name = Path(relative_name).name
    target = (UPLOAD_DIR / name).resolve()
    if target.parent != UPLOAD_DIR:
        return False
    if not target.exists():
        return True
    if not target.is_file():
        return False
    try:
        target.unlink()
        return True
    except OSError:
        app.logger.exception("Could not delete image %s", name)
        return False

def session_json(s):
    return {
        "id": s.id, "plate": s.plate, "status": s.status,
        "entry_time": s.entry_time.isoformat(timespec="seconds"),
        "exit_time": s.exit_time.isoformat(timespec="seconds") if s.exit_time else None,
        "entry_image_url": url_for("api_image", filename=s.entry_image, _external=True),
        "exit_image_url": url_for("api_image", filename=s.exit_image, _external=True) if s.exit_image else None,
    }

@app.get("/api/health")
def api_health():
    return jsonify(status="ok", service="parking-api")

@app.post("/api/plates/recognize")
@api_required
def api_recognize_plate():
    """Run YOLO + PaddleOCR in the isolated .venv-ai environment."""
    image_name, err = save_image(request.files.get("image"))
    if err:
        return jsonify(error="invalid_image", message=err), 400

    image_path = UPLOAD_DIR / image_name
    ai_python = Path(os.getenv(
        "AI_PYTHON_EXE", str(BASE_DIR / ".venv-ai" / "Scripts" / "python.exe")
    ))
    ai_script = BASE_DIR / "plate_ai_worker.py"
    model_path = BASE_DIR / "models" / "plate_detector.pt"

    try:
        if not ai_python.is_file():
            return jsonify(
                error="ai_environment_missing",
                message=f"Không tìm thấy Python AI: {ai_python}. Hãy tạo .venv-ai và cài thư viện AI.",
            ), 503
        if not ai_script.is_file() or not model_path.is_file():
            return jsonify(
                error="ai_model_missing",
                message="Thiếu plate_ai_worker.py hoặc models/plate_detector.pt trong thư mục backend.",
            ), 503

        try:
            completed = subprocess.run(
                [str(ai_python), str(ai_script), str(image_path)],
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=int(os.getenv("AI_TIMEOUT_SECONDS", "240")),
                env={**os.environ, "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK": "True"},
                check=False,
            )
        except subprocess.TimeoutExpired:
            return jsonify(
                error="ai_timeout",
                message="AI xử lý ảnh quá thời gian cho phép. Hãy thử ảnh nhỏ hơn hoặc kiểm tra cấu hình AI.",
            ), 504

        marker = "PARKING_AI_JSON="
        json_lines = [line[len(marker):] for line in completed.stdout.splitlines() if line.startswith(marker)]
        if not json_lines:
            app.logger.error(
                "AI worker did not return a result. rc=%s stdout=%s stderr=%s",
                completed.returncode, completed.stdout[-1500:], completed.stderr[-2500:],
            )
            return jsonify(
                error="ai_worker_failed",
                message="Tiến trình AI không trả được kết quả. Kiểm tra cửa sổ/log Flask để biết chi tiết.",
            ), 500

        try:
            result = json.loads(json_lines[-1])
        except json.JSONDecodeError:
            app.logger.exception("AI worker returned invalid JSON")
            return jsonify(error="ai_invalid_result", message="Kết quả AI không hợp lệ."), 500

        if not result.get("ok"):
            status_code = 422 if result.get("error") in {
                "plate_not_found", "ocr_empty", "empty_crop", "invalid_image"
            } else 503 if result.get("error") == "model_missing" else 500
            response = {
                "error": result.get("error", "plate_not_recognized"),
                "message": result.get("message", "AI chưa nhận diện được biển số."),
            }
            for key in ("yolo_confidence", "ocr_confidence"):
                if key in result:
                    response[key] = result[key]
            return jsonify(response), status_code

        plate = normalize_plate(result.get("plate"))
        if not 4 <= len(plate) <= 12:
            return jsonify(
                error="invalid_prediction",
                message="AI trả về chuỗi có độ dài không hợp lệ. Hãy nhập biển số thủ công.",
                plate=plate,
            ), 422

        return jsonify(
            message="AI đã dự đoán biển số. Vui lòng kiểm tra và xác nhận trước khi lưu.",
            plate=plate,
            raw_text=result.get("raw_text", ""),
            yolo_confidence=result.get("yolo_confidence"),
            ocr_confidence=result.get("ocr_confidence"),
            needs_manual_confirmation=True,
        ), 200
    except Exception:
        app.logger.exception("Plate-recognition endpoint failed")
        return jsonify(error="ai_server_error", message="Không thể xử lý ảnh bằng AI."), 500
    finally:
        # Recognition is temporary: delete the extra upload copy. The original entry/exit
        # image is saved separately only after the operator confirms the vehicle action.
        delete_image(image_name)

@app.post("/api/vehicles/entry")
@api_required
def api_entry():
    plate = normalize_plate(request.form.get("plate"))
    if not 4 <= len(plate) <= 12:
        return jsonify(error="invalid_plate", message="Biển số phải có 4–12 ký tự sau chuẩn hóa"), 400
    image_name, err = save_image(request.files.get("image"))
    if err:
        return jsonify(error="invalid_image", message=err), 400
    existing = VehicleSession.query.filter_by(plate=plate, status="IN").first()
    if existing:
        delete_image(image_name)
        return jsonify(error="already_inside", message="Biển số đang có lượt gửi chưa kết thúc", session=session_json(existing)), 409
    record = VehicleSession(plate=plate, status="IN", entry_time=datetime.now(),
                            entry_image=image_name, entry_source="flutter")
    try:
        db.session.add(record)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        delete_image(image_name)
        # Unique generated active_plate column is the final guard against concurrent duplicate entries.
        existing = VehicleSession.query.filter_by(plate=plate, status="IN").first()
        if existing:
            return jsonify(error="already_inside", message="Biển số đang có lượt gửi chưa kết thúc", session=session_json(existing)), 409
        app.logger.exception("Entry integrity failure")
        return jsonify(error="database_conflict", message="Xung đột dữ liệu khi ghi nhận xe vào"), 409
    except Exception:
        db.session.rollback()
        delete_image(image_name)
        app.logger.exception("Entry insert failed")
        return jsonify(error="server_error", message="Không lưu được lượt vào"), 500
    return jsonify(message="Đã ghi nhận xe vào", session=session_json(record)), 201

@app.post("/api/vehicles/exit")
@api_required
def api_exit():
    plate = normalize_plate(request.form.get("plate"))
    if not 4 <= len(plate) <= 12:
        return jsonify(error="invalid_plate", message="Biển số không hợp lệ"), 400
    record = VehicleSession.query.filter_by(plate=plate, status="IN").order_by(VehicleSession.entry_time.desc()).first()
    if not record:
        return jsonify(error="not_inside", message="Không tìm thấy lượt xe đang gửi"), 404
    image_name = None
    if request.files.get("image"):
        image_name, err = save_image(request.files.get("image"))
        if err:
            return jsonify(error="invalid_image", message=err), 400
    record.status = "EXITED"
    record.exit_time = datetime.now()
    record.exit_image = image_name
    record.exit_source = "flutter"
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        delete_image(image_name)
        app.logger.exception("Exit update failed")
        return jsonify(error="server_error", message="Không lưu được lượt ra"), 500
    return jsonify(message="Đã ghi nhận xe ra", session=session_json(record)), 200

@app.get("/api/vehicles/current")
@api_required
def api_current():
    plate = normalize_plate(request.args.get("plate"))
    q = VehicleSession.query.filter_by(status="IN")
    if plate:
        q = q.filter(VehicleSession.plate.like(f"%{plate}%"))
    records = q.order_by(VehicleSession.entry_time.desc()).limit(500).all()
    return jsonify(items=[session_json(s) for s in records], count=len(records))

@app.get("/api/vehicles/history")
@api_required
def api_history():
    plate = normalize_plate(request.args.get("plate"))
    page = max(1, request.args.get("page", 1, type=int))
    q = VehicleSession.query
    if plate:
        q = q.filter(VehicleSession.plate.like(f"%{plate}%"))
    pagination = q.order_by(VehicleSession.entry_time.desc()).paginate(page=page, per_page=30, error_out=False)
    return jsonify(items=[session_json(s) for s in pagination.items], page=page, pages=pagination.pages, total=pagination.total)

@app.get("/api/vehicles/current/<int:session_id>")
@api_required
def api_current_detail(session_id):
    record = VehicleSession.query.filter_by(id=session_id, status="IN").first_or_404()
    return jsonify(session=session_json(record))

@app.get("/api/images/<path:filename>")
@api_required
def api_image(filename):
    # Flutter can retrieve private images only when it supplies the device token.
    return send_from_directory(UPLOAD_DIR, secure_filename(filename), max_age=0)

@app.get("/uploads/<path:filename>")
@login_required
def uploaded_image(filename):
    # Admin session required for private vehicle images.
    return send_from_directory(UPLOAD_DIR, secure_filename(filename), max_age=0)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        expected_user = os.getenv("ADMIN_USERNAME", "admin")
        expected_pass = os.getenv("ADMIN_PASSWORD", "")
        # Compare without early-exit timing behavior; change the secret using the local .env file.
        if username == expected_user and expected_pass and secrets.compare_digest(password.encode("utf-8"), expected_pass.encode("utf-8")):
            login_user(AdminUser(username))
            return redirect(url_for("admin_dashboard"))
        flash("Tên đăng nhập hoặc mật khẩu không đúng.", "error")
    return render_template("login.html")

@app.post("/admin/logout")
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for("admin_login"))

@app.get("/admin")
@login_required
def admin_dashboard():
    today = date.today()
    start = datetime.combine(today, datetime.min.time())
    end = datetime.combine(today, datetime.max.time())
    entered_today = VehicleSession.query.filter(VehicleSession.entry_time >= start, VehicleSession.entry_time <= end).count()
    exited_today = VehicleSession.query.filter(VehicleSession.exit_time >= start, VehicleSession.exit_time <= end).count()
    current_count = VehicleSession.query.filter_by(status="IN").count()
    q = VehicleSession.query
    plate = normalize_plate(request.args.get("plate"))
    status = request.args.get("status", "all")
    if plate:
        q = q.filter(VehicleSession.plate.like(f"%{plate}%"))
    if status == "IN":
        q = q.filter_by(status="IN")
    elif status == "EXITED":
        q = q.filter_by(status="EXITED")
    records = q.order_by(VehicleSession.entry_time.desc()).limit(300).all()
    return render_template("dashboard.html", records=records, entered_today=entered_today,
                           exited_today=exited_today, current_count=current_count,
                           plate=request.args.get("plate", ""), status=status)

@app.post("/admin/delete/<plate>")
@login_required
def admin_delete_plate(plate):
    # Intentional permanent deletion of every session and associated image for this plate.
    normalized = normalize_plate(plate)
    records = VehicleSession.query.filter_by(plate=normalized).all()
    if not records:
        flash(f"Không tìm thấy dữ liệu cho biển số {normalized}.", "error")
        return redirect(url_for("admin_dashboard"))
    images = []
    for record in records:
        images.extend([record.entry_image, record.exit_image])
        db.session.delete(record)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception("Delete by plate failed")
        flash("Không thể xóa dữ liệu. Hãy kiểm tra log máy chủ.", "error")
        return redirect(url_for("admin_dashboard"))
    failed_images = [name for name in images if name and not delete_image(name)]
    if failed_images:
        flash(f"Đã xóa {len(records)} lượt của {normalized}, nhưng còn {len(failed_images)} ảnh không xóa được. Hãy kiểm tra thư mục uploads.", "error")
    else:
        flash(f"Đã xóa {len(records)} lượt và ảnh liên quan của biển số {normalized}.", "success")
    return redirect(url_for("admin_dashboard"))

def validate_runtime_config():
    """Fail closed on the obvious sample/default secrets before serving requests."""
    secret = os.getenv("SECRET_KEY", "")
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    device_token = os.getenv("API_DEVICE_TOKEN", "")
    database_url = os.getenv("DATABASE_URL", "")
    problems = []
    if len(secret) < 32 or "REPLACE" in secret or "CHANGE" in secret:
        problems.append("SECRET_KEY phải là chuỗi ngẫu nhiên tối thiểu 32 ký tự")
    if len(admin_password) < 12 or "CHANGE_THIS" in admin_password:
        problems.append("ADMIN_PASSWORD phải có tối thiểu 12 ký tự và không dùng giá trị mẫu")
    if len(device_token) < 24 or "REPLACE" in device_token:
        problems.append("API_DEVICE_TOKEN phải là token ngẫu nhiên tối thiểu 24 ký tự")
    if not database_url.startswith("mysql+pymysql://"):
        problems.append("DATABASE_URL phải trỏ đến MySQL qua mysql+pymysql://")
    if problems:
        raise RuntimeError("Cấu hình chưa an toàn trong backend/.env:\n- " + "\n- ".join(problems))

@app.errorhandler(413)
def too_large(_):
    if request.path.startswith("/api/"):
        return jsonify(error="file_too_large", message=f"Ảnh vượt quá {MAX_MB} MB"), 413
    return "Tệp quá lớn", 413

@app.errorhandler(500)
def server_error(_):
    db.session.rollback()
    return "Lỗi máy chủ. Kiểm tra terminal để xem log.", 500

if __name__ == "__main__":
    # Fail before serving if sample secrets or SQLite fallback are still active.
    validate_runtime_config()
    # For LAN testing only. Use Waitress + HTTPS reverse proxy for production.
    if os.getenv("AUTO_CREATE_TABLES", "false").lower() == "true":
        with app.app_context():
            db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=False)
