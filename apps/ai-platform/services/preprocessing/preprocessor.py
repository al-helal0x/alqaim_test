"""IDocumentPreprocessor — القسم 7.2: Deskew/Denoise/Detection عبر OpenCV
الكلاسيكي (لا نموذج تعلّم عميق — القسم 7.12 يوصي صراحة بعدم التعقيد هنا).

تنفيذ حقيقي فعّال: تحويل رمادي → إزالة ضوضاء (fastNlMeans) → عتبة تكيّفية
(Adaptive Threshold) لتحسين تباين النص قبل OCR → تصحيح ميلان بسيط عبر
Hough Transform على حواف النص.
"""
import cv2
import numpy as np


class OpenCvPreprocessor:
    def preprocess(self, image_bytes: bytes) -> bytes:
        array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("تعذّر فك ترميز الصورة — تنسيق غير مدعوم أو ملف تالف")

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        denoised = cv2.fastNlMeansDenoising(gray, h=10)
        thresholded = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
        )
        deskewed = self._deskew(thresholded)

        success, encoded = cv2.imencode(".png", deskewed)
        if not success:
            raise ValueError("تعذّر إعادة ترميز الصورة بعد المعالجة")
        return encoded.tobytes()

    def _deskew(self, binary_image: np.ndarray) -> np.ndarray:
        coords = np.column_stack(np.where(binary_image < 255))
        if coords.shape[0] < 10:
            return binary_image  # صورة فارغة تقريباً — لا شيء لتصحيحه

        angle = cv2.minAreaRect(coords)[-1]
        angle = -(90 + angle) if angle < -45 else -angle
        if abs(angle) < 0.3:  # تفادي تشويه صور مستقيمة أصلاً بضجيج قياس بسيط
            return binary_image

        (h, w) = binary_image.shape[:2]
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(
            binary_image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
        )
