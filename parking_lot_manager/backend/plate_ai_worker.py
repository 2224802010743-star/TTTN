"""YOLO plate detection + PaddleOCR worker. Emits one machine-readable JSON marker line."""
from __future__ import annotations
import json
import re
import sys
import traceback
import tempfile
from pathlib import Path

MARKER = "PARKING_AI_JSON="
BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models" / "plate_detector.pt"


def emit(payload: dict) -> None:
    print(MARKER + json.dumps(payload, ensure_ascii=False, separators=(",", ":")), flush=True)


def run(image_arg: str) -> int:
    image_path = Path(image_arg).expanduser().resolve()
    if not image_path.is_file():
        emit({"ok": False, "error": "image_missing", "message": "Không tìm thấy ảnh cần nhận diện."})
        return 2
    if not MODEL_PATH.is_file():
        emit({"ok": False, "error": "model_missing", "message": f"Thiếu mô hình YOLO tại {MODEL_PATH}"})
        return 2

    try:
        import cv2
        from ultralytics import YOLO
        from paddleocr import PaddleOCR

        image = cv2.imread(str(image_path))
        if image is None:
            emit({"ok": False, "error": "invalid_image", "message": "Không đọc được ảnh."})
            return 2

        detector = YOLO(str(MODEL_PATH))
        detections = detector.predict(
            source=str(image_path), conf=0.25, device="cpu", verbose=False
        )
        boxes = detections[0].boxes
        if boxes is None or len(boxes) == 0:
            emit({"ok": False, "error": "plate_not_found", "message": "AI chưa phát hiện được biển số. Hãy chọn ảnh rõ hơn hoặc nhập biển số thủ công."})
            return 1

        confidences = boxes.conf.cpu().tolist()
        best_idx = max(range(len(confidences)), key=lambda index: confidences[index])
        x1, y1, x2, y2 = boxes.xyxy[best_idx].cpu().tolist()
        height, width = image.shape[:2]
        pad_x = int(max(2, (x2 - x1) * 0.06))
        pad_y = int(max(2, (y2 - y1) * 0.12))
        x1 = max(0, int(x1) - pad_x)
        y1 = max(0, int(y1) - pad_y)
        x2 = min(width, int(x2) + pad_x)
        y2 = min(height, int(y2) + pad_y)
        crop = image[y1:y2, x1:x2]
        if crop.size == 0:
            emit({"ok": False, "error": "empty_crop", "message": "Không cắt được vùng biển số."})
            return 1

        # The tested environment uses PaddlePaddle 3.3.1. Disabling oneDNN avoids
        # the PIR/oneDNN CPU error encountered in this environment.
        ocr = PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            engine="paddle",
            enable_mkldnn=False,
        )
        with tempfile.TemporaryDirectory(prefix="parking_plate_") as tmp_dir:
            crop_path = Path(tmp_dir) / "plate_crop.jpg"
            if not cv2.imwrite(str(crop_path), crop):
                emit({"ok": False, "error": "crop_write_failed", "message": "Không tạo được ảnh cắt biển số."})
                return 1
            results = ocr.predict(str(crop_path))

        texts: list[str] = []
        scores: list[float] = []
        for result in results or []:
            try:
                record_texts = result["rec_texts"]
                record_scores = result["rec_scores"]
            except (KeyError, TypeError, IndexError):
                continue
            for text, score in zip(record_texts or [], record_scores or []):
                text = str(text).strip()
                if text:
                    texts.append(text)
                    scores.append(float(score))

        raw_text = "".join(texts).upper()
        plate = re.sub(r"[^A-Z0-9]", "", raw_text)
        ocr_confidence = sum(scores) / len(scores) if scores else 0.0
        yolo_confidence = float(confidences[best_idx])
        if not plate:
            emit({
                "ok": False,
                "error": "ocr_empty",
                "message": "Đã phát hiện vùng biển số nhưng OCR chưa đọc được ký tự. Hãy nhập biển số thủ công.",
                "yolo_confidence": round(yolo_confidence, 4),
                "ocr_confidence": round(ocr_confidence, 4),
            })
            return 1

        needs_review = not (4 <= len(plate) <= 12 and yolo_confidence >= 0.45 and ocr_confidence >= 0.60)
        emit({
            "ok": True,
            "plate": plate,
            "raw_text": raw_text,
            "yolo_confidence": round(yolo_confidence, 4),
            "ocr_confidence": round(ocr_confidence, 4),
            "needs_review": needs_review,
            "message": "AI đã dự đoán biển số. Nhân viên cần kiểm tra trước khi xác nhận.",
        })
        return 0
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        emit({
            "ok": False,
            "error": "ai_inference_failed",
            "message": f"Lỗi khi chạy AI: {type(exc).__name__}: {str(exc)[:350]}",
        })
        return 3


if __name__ == "__main__":
    if len(sys.argv) != 2:
        emit({"ok": False, "error": "usage", "message": "Cần truyền đúng một đường dẫn ảnh."})
        raise SystemExit(2)
    raise SystemExit(run(sys.argv[1]))
