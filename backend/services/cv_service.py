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
    
    def detect_text_lines(
        self,
        image: Image.Image,
        min_width: int = 50,
        min_height: int = 10
    ) -> List[TextRegion]:
        """
        Detect individual text lines for TrOCR processing.
        TrOCR works best with single lines of text.
        
        Args:
            image: PIL Image
            min_width: Minimum width for a line
            min_height: Minimum height for a line
            
        Returns:
            List of TextRegion objects representing text lines
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
        
        lines = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            if w >= min_width and h >= min_height:
                # Add padding
                padding = 5
                x = max(0, x - padding)
                y = max(0, y - padding)
                w = w + 2 * padding
                h = h + 2 * padding
                
                lines.append(TextRegion(x=x, y=y, width=w, height=h))
        
        # Sort by y-coordinate (top to bottom)
        lines.sort(key=lambda r: r.y)
        
        return lines
    
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
