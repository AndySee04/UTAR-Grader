import torch
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from PIL import Image
from typing import List, Optional, Tuple
import numpy as np
from .cv_service import cv_service, TextRegion


class OCRService:
    """Service for OCR using TrOCR model."""
    
    def __init__(self, model_name: str = "microsoft/trocr-large-handwritten"):
        """
        Initialize TrOCR model.
        
        Args:
            model_name: HuggingFace model name. Options:
                - microsoft/trocr-large-handwritten (default, for handwriten text)
                - microsoft/trocr-base-printed (for printed text)
        """
        self.model_name = model_name
        self.processor = None
        self.model = None
        self.device = None
        self._initialized = False
    
    def preload(self) -> None:
        """Load processor and weights now (e.g. at API startup)."""
        self._lazy_init()
    
    def _lazy_init(self):
        """Lazy initialization of model to save memory until first use."""
        if self._initialized:
            return
        
        print(f"Loading TrOCR model: {self.model_name}")
        
        # Determine device
        if torch.cuda.is_available():
            self.device = torch.device("cuda")
            print(f"Using GPU: {torch.cuda.get_device_name(0)}")
        else:
            self.device = torch.device("cpu")
            print("Using CPU (GPU not available)")
        
        # Load processor and model
        self.processor = TrOCRProcessor.from_pretrained(self.model_name)
        self.model = VisionEncoderDecoderModel.from_pretrained(self.model_name)
        self.model.to(self.device)
        self.model.eval()
        
        self._initialized = True
        print("TrOCR model loaded successfully")
    
    def extract_text_from_line(self, image: Image.Image) -> str:
        """
        Extract text from a single line image.
        TrOCR works best with single lines of text.
        
        Args:
            image: PIL Image containing a single line of text
            
        Returns:
            Extracted text string
        """
        self._lazy_init()
        
        # Convert to RGB if needed
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        # Process image
        pixel_values = self.processor(
            images=image,
            return_tensors="pt"
        ).pixel_values.to(self.device)
        
        # Generate text
        with torch.no_grad():
            generated_ids = self.model.generate(pixel_values, max_length=256)
        
        # Decode
        text = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        
        return text.strip()
    
    def extract_text_from_image(
        self,
        image: Image.Image,
        detect_lines: bool = True
    ) -> Tuple[str, List[dict]]:
        """
        Extract text from an image, optionally detecting lines first.
        
        Args:
            image: PIL Image
            detect_lines: If True, detect and process individual lines
            
        Returns:
            Tuple of (full_text, list of line details)
        """
        self._lazy_init()
        
        # 1. Deskew — straighten tilted images.
        image = cv_service.deskew_image(image)

        # 2. Enhance the image
        enhanced_image = cv_service.enhance_for_ocr(image)

        if not detect_lines:
            # 3. Extract text from the enhanced image.
            text = self.extract_text_from_line(enhanced_image)
            return text, [{"text": text, "region": None}]

        # 4. Detect text lines on the enhanced image.
        model_name_lower = (self.model_name or "").lower()
        method = "craft" if "handwritten" in model_name_lower else "opencv"
        crop_source = enhanced_image
        lines = cv_service.detect_text_lines(enhanced_image, method=method)

        # Fallback: if enhancement made segmentation worse, retry line detection
        # on the deskewed original.
        if not lines:
            crop_source = image
            lines = cv_service.detect_text_lines(image, method=method)

        if not lines:
            # Final fallback: OCR whole enhanced image.
            text = self.extract_text_from_line(enhanced_image)
            return text, [{"text": text, "region": None}]

        results = []
        full_text_parts = []

        for line in lines:
            # Crop each detected line from the chosen source image.
            line_img = cv_service.crop_region(crop_source, line)

            # TrOCR line-by-line (no per-line enhancement; already enhanced once).
            text = self.extract_text_from_line(line_img)

            if text:
                results.append({
                    "text": text,
                    "region": {
                        "x": line.x,
                        "y": line.y,
                        "width": line.width,
                        "height": line.height
                    }
                })
                full_text_parts.append(text)

        full_text = "\n".join(full_text_parts)
        return full_text, results
    
    def extract_text_from_region(
        self,
        image: Image.Image,
        x: int,
        y: int,
        width: int,
        height: int
    ) -> str:
        """
        Extract text from a specific region of an image.
        
        Args:
            image: PIL Image
            x, y: Top-left corner
            width, height: Region dimensions
            
        Returns:
            Extracted text
        """
        # Crop region
        region = image.crop((x, y, x + width, y + height))
        
        # Extract text with line detection
        text, _ = self.extract_text_from_image(region, detect_lines=True)
        
        return text
    
    def batch_extract(
        self,
        images: List[Image.Image],
        batch_size: int = 4
    ) -> List[str]:
        """
        Extract text from multiple images in batches.
        
        Args:
            images: List of PIL Images
            batch_size: Number of images to process at once
            
        Returns:
            List of extracted texts
        """
        self._lazy_init()
        
        results = []
        
        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]
            
            # Preprocess + convert to RGB
            batch_rgb = [
                cv_service.enhance_for_ocr(img)
                for img in batch
            ]
            
            # Process batch
            pixel_values = self.processor(
                images=batch_rgb,
                return_tensors="pt"
            ).pixel_values.to(self.device)
            
            # Generate
            with torch.no_grad():
                generated_ids = self.model.generate(pixel_values, max_length=256)
            
            # Decode
            texts = self.processor.batch_decode(generated_ids, skip_special_tokens=True)
            results.extend([t.strip() for t in texts])
        
        return results
    
    def get_confidence(self, image: Image.Image) -> float:
        """
        Get confidence score for OCR result (placeholder).
        TrOCR doesn't directly provide confidence, so we estimate.
        
        Args:
            image: PIL Image
            
        Returns:
            Confidence score between 0 and 1
        """
        self._lazy_init()
        
        image = cv_service.enhance_for_ocr(image)
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        pixel_values = self.processor(
            images=image,
            return_tensors="pt"
        ).pixel_values.to(self.device)
        
        with torch.no_grad():
            outputs = self.model.generate(
                pixel_values,
                max_length=256,
                output_scores=True,
                return_dict_in_generate=True
            )
        
        # Calculate average confidence from scores
        if outputs.scores:
            scores = torch.stack(outputs.scores, dim=1)
            probs = torch.softmax(scores, dim=-1)
            max_probs = probs.max(dim=-1).values
            confidence = max_probs.mean().item()
            return confidence
        
        return 0.5  # Default if no scores


# Singleton instances - lazy loaded
# Default instance is optimized for handwriting (student answers).
ocr_service = OCRService()
# Separate instance using the printed-text TrOCR model, better for question papers
ocr_service_printed = OCRService("microsoft/trocr-base-printed")
