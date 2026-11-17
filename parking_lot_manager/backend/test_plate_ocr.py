r"""Test YOLO license-plate detection + PaddleOCR on one vehicle image.
Run from the backend folder:
  .\.venv-ai\Scripts\python.exe test_plate_ocr.py "C:\\temp\\car.jpg"
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

import cv2
from ultralytics import YOLO
from paddleocr import PaddleOCR

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models" / "plate_detector.pt"
OUT_DIR = BASE_DIR / "runs" / "plate_ocr_test"


def main() -> int:
    if len(sys.argv) < 2:
        print('Cách dùng: python test_plate_ocr.py "C:\\duong-dan\\anh-xe.jpg"')
        return 2
    image_path = Path(sys.argv[1]).expanduser().resolve()
    if not image_path.is_file():
        print(f"LỖI: Không tìm thấy ảnh: {image_path}")
        return 2
    if not MODEL_PATH.is_file():
        print(f"LỖI: Không tìm thấy mô hình YOLO: {MODEL_PATH}")
        print("Đảm bảo tệp models\\plate_detector.pt đã tải ở bước trước.")
        return 2

    image = cv2.imread(str(image_path))
    if image is None:
        print(f"LỖI: Không đọc được ảnh: {image_path}")
        return 2

    print("[1/3] Phát hiện vùng biển số bằng YOLO...")
    detector = YOLO(str(MODEL_PATH))
    results = detector.predict(source=str(image_path), conf=0.25, device="cpu", verbose=False)
    boxes = results[0].boxes
    if boxes is None or len(boxes) == 0:
        print("Không phát hiện được biển số. Thử ảnh rõ hơn, biển số lớn hơn hoặc đủ sáng.")
        return 1

    # Pick the detection with greatest confidence for a single vehicle-photo test.
    confidences = boxes.conf.cpu().tolist()
    best_idx = max(range(len(confidences)), key=lambda i: confidences[i])
    x1, y1, x2, y2 = boxes.xyxy[best_idx].cpu().tolist()
    h, w = image.shape[:2]
    # Expand the crop slightly so edge characters are not cut off.
    pad_x = int(max(2, (x2 - x1) * 0.06))
    pad_y = int(max(2, (y2 - y1) * 0.12))
    x1 = max(0, int(x1) - pad_x)
    y1 = max(0, int(y1) - pad_y)
    x2 = min(w, int(x2) + pad_x)
    y2 = min(h, int(y2) + pad_y)
    crop = image[y1:y2, x1:x2]
    if crop.size == 0:
        print("LỖI: Vùng cắt biển số rỗng.")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    crop_path = OUT_DIR / "plate_crop.jpg"
    if not cv2.imwrite(str(crop_path), crop):
        print("LỖI: Không lưu được ảnh cắt biển số.")
        return 1
    print(f"Đã cắt biển số: {crop_path}")
    print(f"Độ tin cậy YOLO: {confidences[best_idx]:.3f}")

    print("[2/3] Khởi tạo PaddleOCR (lần đầu có thể tải model OCR)...")
    ocr = PaddleOCR(
        lang="en",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        engine="paddle",
        enable_mkldnn=False,  # Work around PaddlePaddle 3.3.1 oneDNN/PIR CPU bug.
    )
    print("[3/3] Đọc ký tự trên biển số...")
    ocr_results = ocr.predict(str(crop_path))

    detected_texts: list[str] = []
    detected_scores: list[float] = []
    for result in ocr_results or []:
        try:
            texts = result["rec_texts"]
            scores = result["rec_scores"]
        except (KeyError, TypeError, IndexError):
            # Print result for diagnostics if the local PaddleOCR version has a changed schema.
            print("Không đọc được trường rec_texts/rec_scores. Kết quả OCR thô:")
            print(result)
            continue
        for text, score in zip(texts or [], scores or []):
            clean = str(text).strip()
            if clean:
                detected_texts.append(clean)
                detected_scores.append(float(score))

    print("\n--- KẾT QUẢ OCR ---")
    if not detected_texts:
        print("OCR chưa đọc được ký tự. Hãy mở ảnh crop để kiểm tra vùng cắt có đủ biển số không:")
        print(crop_path)
        return 1

    for text, score in zip(detected_texts, detected_scores):
        print(f"{score:.3f}  {text}")

    combined = "".join(detected_texts).upper()
    normalized = re.sub(r"[^A-Z0-9]", "", combined)
    avg_score = sum(detected_scores) / len(detected_scores)
    print(f"Biển số sau chuẩn hóa: {normalized or '(trống)'}")
    print(f"Điểm OCR trung bình: {avg_score:.3f}")
    print("Lưu ý: đây là kết quả dự đoán để kiểm thử; cần người vận hành xác nhận trước khi ghi nhận xe.")
    print(f"Mở ảnh cắt kiểm tra: {crop_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
