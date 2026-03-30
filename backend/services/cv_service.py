import cv2
import numpy as np
from PIL import Image
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass


@dataclass
class TextRegion:
    """Represents a detected text region."""
    x: int
    y: int
    width: int
    height: int
    confidence: float = 0.0
    region_type: str = "unknown"  # question, answer, etc.
    

class CVService:
    """Service for computer vision operations using OpenCV."""
    
    def __init__(self):
        pass
    
    def preprocess_image(self, image: Image.Image) -> np.ndarray:
        """
        Preprocess image for better OCR results.
        
        Steps:
        1. Convert to grayscale
        2. Apply adaptive thresholding
        3. Denoise
        
        Args:
            image: PIL Image
            
        Returns:
            Preprocessed numpy array
        """
        # Convert PIL to OpenCV format
        img_array = np.array(image)
        
        # Convert to grayscale if needed
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        # Apply adaptive thresholding
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11, 2
        )
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(binary, None, 10, 7, 21)
        
        return denoised
    
    def detect_text_regions(
        self,
        image: Image.Image,
        min_area: int = 1000,
        merge_threshold: int = 20
    ) -> List[TextRegion]:
        """
        Detect text regions in an image using contour detection.
        
        Args:
            image: PIL Image
            min_area: Minimum area for a region to be considered
            merge_threshold: Distance threshold for merging nearby regions
            
        Returns:
            List of TextRegion objects
        """
        # Convert to numpy array
        img_array = np.array(image)
        
        # Convert to grayscale
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        # Apply binary threshold
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Dilate to connect text components
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 5))
        dilated = cv2.dilate(binary, kernel, iterations=3)
        
        # Find contours
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        regions = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            
            if area >= min_area:
                regions.append(TextRegion(x=x, y=y, width=w, height=h))
        
        # Sort by y-coordinate (top to bottom), then by x (left to right)
        regions.sort(key=lambda r: (r.y, r.x))
        
        # Merge nearby regions
        merged_regions = self._merge_regions(regions, merge_threshold)
        
        return merged_regions
    
    def _merge_regions(
        self,
        regions: List[TextRegion],
        threshold: int
    ) -> List[TextRegion]:
        """Merge overlapping or nearby regions."""
        if not regions:
            return []
        
        merged = []
        used = set()
        
        for i, r1 in enumerate(regions):
            if i in used:
                continue
            
            current = TextRegion(x=r1.x, y=r1.y, width=r1.width, height=r1.height)
            used.add(i)
            
            for j, r2 in enumerate(regions):
                if j in used:
                    continue
                
                # Check if regions are close enough to merge
                if self._should_merge(current, r2, threshold):
                    current = self._merge_two_regions(current, r2)
                    used.add(j)
            
            merged.append(current)
        
        return merged
    
    def _should_merge(self, r1: TextRegion, r2: TextRegion, threshold: int) -> bool:
        """Check if two regions should be merged based on proximity."""
        # Check vertical overlap and horizontal proximity
        v_overlap = not (r1.y + r1.height < r2.y - threshold or r2.y + r2.height < r1.y - threshold)
        h_close = abs(r1.x - (r2.x + r2.width)) < threshold or abs(r2.x - (r1.x + r1.width)) < threshold
        
        return v_overlap and h_close
    
    def _merge_two_regions(self, r1: TextRegion, r2: TextRegion) -> TextRegion:
        """Merge two regions into one bounding box."""
        x = min(r1.x, r2.x)
        y = min(r1.y, r2.y)
        x2 = max(r1.x + r1.width, r2.x + r2.width)
        y2 = max(r1.y + r1.height, r2.y + r2.height)
        
        return TextRegion(x=x, y=y, width=x2 - x, height=y2 - y)
    
    def _detect_text_lines_opencv(
        self,
        image: Image.Image,
        min_width: int = 50,
        min_height: int = 10
    ) -> List[TextRegion]:
        """
        Detect individual text lines for TrOCR processing using OpenCV morphology.
        """
        img_array = np.array(image)

        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array

        # Binary threshold
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Horizontal dilation to connect characters in a line
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        dilated = cv2.dilate(binary, kernel, iterations=2)

        # Vertical dilation to separate lines
        kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 3))
        dilated = cv2.erode(dilated, kernel_v, iterations=1)

        # Find contours
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        lines: List[TextRegion] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)

            if w >= min_width and h >= min_height:
                padding = 5
                x = max(0, x - padding)
                y = max(0, y - padding)
                w = w + 2 * padding
                h = h + 2 * padding
                lines.append(TextRegion(x=x, y=y, width=w, height=h))

        lines.sort(key=lambda r: r.y)
        return lines

    def _detect_text_lines_craft(
        self,
        image: Image.Image,
        min_width: int = 50,
        min_height: int = 10
    ) -> List[TextRegion]:
        """
        Detect text lines using CRAFT via EasyOCR.
        Returns line bounding boxes as TextRegion objects.
        """
        try:
            import easyocr  # type: ignore[import-not-found]
        except Exception:
            # If easyocr isn't installed, return no lines so caller can fall back to whole-crop OCR.
            return []

        if getattr(self, "_easyocr_reader", None) is None:
            # Load only the detector; recognition is not needed for line boxes.
            self._easyocr_reader = easyocr.Reader(
                ["en"],
                gpu=False,
                detector=True,
                recognizer=False,
            )

        reader = self._easyocr_reader
        img_rgb = np.array(image.convert("RGB"))
        height, width = img_rgb.shape[:2]

        try:
            horizontal_list, free_list = reader.detect(img_rgb)
        except Exception:
            return []

        # Convert polygons to axis-aligned boxes first.
        candidates: List[TextRegion] = []
        # Prefer EasyOCR's horizontal boxes when available.
        # EasyOCR may return nested lists depending on internal detection mode.
        rects: List[list] = []
        for item in horizontal_list or []:
            if not item:
                continue
            # Case A: a single rect [x_min, x_max, y_min, y_max]
            if isinstance(item, (list, tuple)) and len(item) == 4 and all(
                isinstance(v, (int, float, np.floating, np.integer)) for v in item
            ):
                rects.append(list(item))
                continue
            # Case B: list of rects [[...],[...],...]
            if isinstance(item, (list, tuple)) and len(item) > 0 and isinstance(item[0], (list, tuple)) and len(item[0]) == 4:
                for r in item:
                    if isinstance(r, (list, tuple)) and len(r) == 4:
                        rects.append(list(r))

        for rect in rects:
            try:
                x_min, x_max, y_min, y_max = rect
                x1 = int(np.floor(float(x_min)))
                x2 = int(np.ceil(float(x_max)))
                y1 = int(np.floor(float(y_min)))
                y2 = int(np.ceil(float(y_max)))
                w = x2 - x1
                h = y2 - y1
                if w < min_width or h < min_height:
                    continue
                candidates.append(TextRegion(x=x1, y=y1, width=w, height=h))
            except Exception:
                continue

        for poly in free_list:
            # poly is [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            if not poly:
                continue
            pts = np.array(poly, dtype=np.float32)
            if pts.shape[0] < 4:
                continue
            x_min = int(np.floor(pts[:, 0].min()))
            x_max = int(np.ceil(pts[:, 0].max()))
            y_min = int(np.floor(pts[:, 1].min()))
            y_max = int(np.ceil(pts[:, 1].max()))

            w = x_max - x_min
            h = y_max - y_min
            if w < min_width or h < min_height:
                continue

            candidates.append(TextRegion(x=x_min, y=y_min, width=w, height=h))

        if not candidates:
            return []

        # Cluster candidates by y-center to form line boxes.
        candidates.sort(key=lambda r: (r.y + r.height / 2.0))
        clusters: List[TextRegion] = []

        current = None
        current_y_center = None
        current_avg_h = None

        def clamp_box(x1: int, y1: int, x2: int, y2: int) -> Tuple[int, int, int, int]:
            cx1 = max(0, x1)
            cy1 = max(0, y1)
            cx2 = min(width, x2)
            cy2 = min(height, y2)
            return cx1, cy1, cx2, cy2

        for c in candidates:
            c_y_center = c.y + c.height / 2.0
            if current is None:
                current = TextRegion(x=c.x, y=c.y, width=c.width, height=c.height)
                current_y_center = c_y_center
                current_avg_h = float(c.height)
                continue

            avg_h = current_avg_h or float(current.height)
            # Allow moderate vertical spread inside one line.
            threshold = max(10.0, 0.5 * avg_h)
            if abs(c_y_center - current_y_center) <= threshold:
                x1 = min(current.x, c.x)
                y1 = min(current.y, c.y)
                x2 = max(current.x + current.width, c.x + c.width)
                y2 = max(current.y + current.height, c.y + c.height)
                cx1, cy1, cx2, cy2 = clamp_box(x1, y1, x2, y2)
                current = TextRegion(x=cx1, y=cy1, width=max(1, cx2 - cx1), height=max(1, cy2 - cy1))

                # Update cluster center/height estimate.
                current_avg_h = (avg_h + float(c.height)) / 2.0
                current_y_center = current.y + current.height / 2.0
            else:
                clusters.append(current)
                current = TextRegion(x=c.x, y=c.y, width=c.width, height=c.height)
                current_y_center = c_y_center
                current_avg_h = float(c.height)

        if current is not None:
            clusters.append(current)

        # Add padding and re-check minimums.
        padded: List[TextRegion] = []
        padding = 5
        for line in clusters:
            x1, y1, x2, y2 = (
                line.x,
                line.y,
                line.x + line.width,
                line.y + line.height,
            )
            x1, y1, x2, y2 = clamp_box(x1 - padding, y1 - padding, x2 + padding, y2 + padding)
            w = x2 - x1
            h = y2 - y1
            if w >= min_width and h >= min_height:
                padded.append(TextRegion(x=x1, y=y1, width=w, height=h))

        padded.sort(key=lambda r: r.y)
        return padded

    def detect_text_lines(
        self,
        image: Image.Image,
        min_width: int = 50,
        min_height: int = 10,
        method: str = "opencv"
    ) -> List[TextRegion]:
        """
        Detect individual text lines for TrOCR processing.
        method:
          - "craft": CRAFT via EasyOCR
          - "opencv": OpenCV morphology
        """
        if method == "craft":
            return self._detect_text_lines_craft(image, min_width=min_width, min_height=min_height)
        return self._detect_text_lines_opencv(image, min_width=min_width, min_height=min_height)
    
    def deskew_image(self, image: Image.Image) -> Image.Image:
        """
        Deskew a rotated image.
        
        Args:
            image: PIL Image
            
        Returns:
            Deskewed PIL Image
        """
        img_array = np.array(image)
        
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        # Detect edges
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # Detect lines using Hough transform
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
        
        if lines is None:
            return image
        
        # Calculate average angle
        angles = []
        for line in lines:
            rho, theta = line[0]
            angle = (theta * 180 / np.pi) - 90
            if -45 < angle < 45:
                angles.append(angle)
        
        if not angles:
            return image
        
        median_angle = np.median(angles)
        
        # Rotate image
        (h, w) = img_array.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        rotated = cv2.warpAffine(
            img_array, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )
        
        return Image.fromarray(rotated)
    
    def crop_region(
        self,
        image: Image.Image,
        region: TextRegion
    ) -> Image.Image:
        """Crop a region from an image."""
        img_array = np.array(image)
        cropped = img_array[
            region.y:region.y + region.height,
            region.x:region.x + region.width
        ]
        return Image.fromarray(cropped)


# Singleton instance
cv_service = CVService()
