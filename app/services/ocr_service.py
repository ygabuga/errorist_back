import cv2
import numpy as np
import re
from PIL import Image
import io
import pytesseract
from pyzbar.pyzbar import decode
from typing import Tuple, List, Dict, Optional


class OCRService:

    @staticmethod
    def extract_codes_from_text(text: str) -> list:
        """Извлечение кодов ошибок из текста"""
        pattern = r'\b[A-Za-z0-9]{4,10}\b'
        codes = re.findall(pattern, text)

        unique_codes = []
        for code in codes:
            code = code.upper()
            if code not in unique_codes and len(code) >= 4:
                unique_codes.append(code)

        print(f"Извлечены коды: {unique_codes}")
        return unique_codes

    @staticmethod
    def parse_qr_data(qr_text: str) -> Dict:
        """Парсинг QR-кода с диагностической информацией"""
        result = {
            "device_id": None,
            "sn": None,
            "timestamp": None,
            "model": None,
            "versions": {},
            "errors": []
        }

        id_match = re.search(r'ID:(\S+)', qr_text)
        if id_match:
            result["device_id"] = id_match.group(1)

        sn_match = re.search(r'SN:(\S+)', qr_text)
        if sn_match:
            result["sn"] = sn_match.group(1)

        time_match = re.search(r'Time:(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})', qr_text)
        if time_match:
            result["timestamp"] = time_match.group(1)

        model_match = re.search(r'Model:(\S+)', qr_text)
        if model_match:
            result["model"] = model_match.group(1)

        version_pattern = r'(\w+):V\s*([\d.,-]+)'
        for match in re.finditer(version_pattern, qr_text):
            result["versions"][match.group(1)] = match.group(2)

        error_section = re.search(r'Error_:([\d\s,A-Z]+)', qr_text)
        if error_section:
            errors_str = error_section.group(1)
            error_pattern = r'(\d{6})\s+(\d{6})\s+([A-Z0-9]+)'
            matches = re.findall(error_pattern, errors_str)

            if not matches:
                error_pattern2 = r'(\d{6})(\d{6})([A-Z0-9]+)'
                matches = re.findall(error_pattern2, errors_str)

            for match in matches:
                date = match[0]
                time = match[1]
                code = match[2]
                result["errors"].append({
                    "datetime": f"{date[:2]}.{date[2:4]}.{date[4:6]} {time[:2]}:{time[2:4]}:{time[4:6]}",
                    "code": code
                })

        if not result["errors"]:
            all_codes = OCRService.extract_codes_from_text(qr_text)
            for code in all_codes:
                result["errors"].append({
                    "datetime": None,
                    "code": code
                })

        print(f"Найдено ошибок в QR: {len(result['errors'])}")
        return result

    # ============== PYZBAR - ЭКСТРЕМАЛЬНОЕ УМЕНЬШЕНИЕ ==============
    @staticmethod
    def read_qr_code_pyzbar(image_bytes: bytes) -> Optional[str]:
        """Поиск QR через pyzbar с экстремальным уменьшением для больших QR"""
        try:
            from PIL import ImageEnhance

            img = Image.open(io.BytesIO(image_bytes))
            original_size = img.size
            print(f"[PYZ] Оригинальный размер: {original_size}")

            # ЭКСТРЕМАЛЬНЫЕ масштабы уменьшения (для огромных QR во весь экран)
            # Начинаем с 0.05 (5% от оригинала) и постепенно увеличиваем
            scales = [0.05, 0.06, 0.07, 0.08, 0.09, 0.1, 0.12, 0.15, 0.18, 0.2, 0.22, 0.25, 0.3, 0.35, 0.4, 0.5]

            for scale in scales:
                new_w = int(original_size[0] * scale)
                new_h = int(original_size[1] * scale)
                if new_w < 50 or new_h < 50:
                    continue
                resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                decoded = decode(resized)
                if decoded:
                    print(f"[PYZ] ✅ QR найден! Уменьшение до: {new_w}x{new_h} (масштаб {scale})")
                    return decoded[0].data.decode('utf-8')

            # Если уменьшение не помогло, пробуем с повышением контраста
            enhancer = ImageEnhance.Contrast(img)
            for scale in scales:
                new_w = int(original_size[0] * scale)
                new_h = int(original_size[1] * scale)
                if new_w < 50 or new_h < 50:
                    continue
                resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                for factor in [1.5, 2.0, 2.5, 3.0]:
                    enhanced = enhancer.enhance(factor)
                    resized_enhanced = enhanced.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    decoded = decode(resized_enhanced)
                    if decoded:
                        print(f"[PYZ] ✅ QR найден! Контраст x{factor}, масштаб {scale}")
                        return decoded[0].data.decode('utf-8')

            print("[PYZ] ❌ QR не найден")
            return None

        except Exception as e:
            print(f"[PYZ] Ошибка: {e}")
            return None

    # ============== OPENCV - ЭКСТРЕМАЛЬНОЕ УМЕНЬШЕНИЕ ==============
    @staticmethod
    def read_qr_code_opencv(image_bytes: bytes) -> Optional[str]:
        """Поиск QR через OpenCV с экстремальным уменьшением"""
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                return None

            h, w = img.shape[:2]
            print(f"[CV] Оригинальный размер: {w}x{h}")

            detector = cv2.QRCodeDetector()

            # ЭКСТРЕМАЛЬНЫЕ масштабы уменьшения
            scales = [0.05, 0.06, 0.07, 0.08, 0.09, 0.1, 0.12, 0.15, 0.18, 0.2, 0.22, 0.25, 0.3, 0.35, 0.4]

            for scale in scales:
                new_w = max(80, int(w * scale))
                new_h = max(80, int(h * scale))
                resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

                # Мягкое размытие для улучшения
                blurred = cv2.GaussianBlur(resized, (3, 3), 0)

                data, _, _ = detector.detectAndDecode(blurred)
                if data:
                    print(f"[CV] ✅ QR найден! Уменьшение до: {new_w}x{new_h} (масштаб {scale})")
                    return data

                # Пробуем на оттенках серого
                gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)
                data, _, _ = detector.detectAndDecode(gray)
                if data:
                    print(f"[CV] ✅ QR найден (gray)! Масштаб {scale}")
                    return data

            # Пробуем с повышением контраста
            for scale in scales:
                new_w = max(80, int(w * scale))
                new_h = max(80, int(h * scale))
                resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

                # CLAHE для повышения контраста
                gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
                clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
                enhanced = clahe.apply(gray)

                data, _, _ = detector.detectAndDecode(enhanced)
                if data:
                    print(f"[CV] ✅ QR найден (CLAHE)! Масштаб {scale}")
                    return data

            print("[CV] ❌ QR не найден")
            return None

        except Exception as e:
            print(f"[CV] Ошибка: {e}")
            return None

    @staticmethod
    def recognize_text(image_bytes: bytes) -> str:
        """OCR распознавание текста"""
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                return ""

            h, w = img.shape[:2]
            if w < 1000:
                scale = 2.0
                new_w = int(w * scale)
                new_h = int(h * scale)
                img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            _, thresh = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            denoised = cv2.medianBlur(thresh, 3)

            config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:-/() '
            text = pytesseract.image_to_string(denoised, config=config, lang='rus+eng')

            return text.upper()

        except Exception as e:
            print(f"OCR error: {e}")
            return ""

    @staticmethod
    async def process_image(image_bytes: bytes) -> Tuple[Dict, List[str]]:
        """
        Основной метод:
        1. pyzbar с экстремальным уменьшением (от 5%)
        2. OpenCV с экстремальным уменьшением
        3. OCR
        """
        qr_data = None

        print("\n=== НАЧАЛО РАСПОЗНАВАНИЯ ===")

        # 1. pyzbar (с уменьшением до 5% от оригинала)
        print("🔍 [1/2] pyzbar (уменьшаем до 5% для поиска большого QR)...")
        qr_data = OCRService.read_qr_code_pyzbar(image_bytes)

        # 2. OpenCV
        if not qr_data:
            print("🔍 [2/2] OpenCV (уменьшаем до 5% для поиска большого QR)...")
            qr_data = OCRService.read_qr_code_opencv(image_bytes)

        if qr_data:
            print(f"\n✅ QR УСПЕШНО РАСПОЗНАН!")
            parsed = OCRService.parse_qr_data(qr_data)
            codes = list(set([err["code"] for err in parsed.get("errors", [])]))
            print(f"📋 Коды из QR: {codes}")
            return parsed, codes

        # 3. OCR (если QR не найден)
        print("\n❌ QR не найден, выполняю OCR...")
        text = OCRService.recognize_text(image_bytes)
        codes = OCRService.extract_codes_from_text(text)

        return {}, codes