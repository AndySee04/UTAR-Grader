import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Tuple, Optional
from PIL import Image
import io
import os


class PDFService:
    """Service for PDF processing operations."""
    
    def __init__(self, dpi: int = 200):
        self.dpi = dpi
        self.zoom = dpi / 72  # 72 is default PDF DPI
    
    def get_page_count(self, pdf_path: str) -> int:
        """Get number of pages in a PDF."""
        doc = fitz.open(pdf_path)
        count = len(doc)
        doc.close()
        return count
    
    def pdf_to_images(self, pdf_path: str, output_dir: Optional[str] = None) -> List[str]:
        """
        Convert all PDF pages to images.
        
        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to save images. If None, saves alongside PDF.
            
        Returns:
            List of image file paths
        """
        pdf_path = Path(pdf_path)
        if output_dir is None:
            output_dir = pdf_path.parent / f"{pdf_path.stem}_pages"
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        doc = fitz.open(str(pdf_path))
        image_paths = []
        
        mat = fitz.Matrix(self.zoom, self.zoom)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=mat)
            
            image_path = output_dir / f"page_{page_num + 1}.png"
            pix.save(str(image_path))
            image_paths.append(str(image_path))
        
        doc.close()
        return image_paths
    
    def get_page_as_image(self, pdf_path: str, page_number: int) -> Image.Image:
        """
        Get a specific page as a PIL Image.
        
        Args:
            pdf_path: Path to the PDF file
            page_number: 1-based page number
            
        Returns:
            PIL Image object
        """
        doc = fitz.open(pdf_path)
        
        if page_number < 1 or page_number > len(doc):
            doc.close()
            raise ValueError(f"Page number {page_number} out of range (1-{len(doc)})")
        
        page = doc[page_number - 1]
        mat = fitz.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=mat)
        
        # Convert to PIL Image
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        
        doc.close()
        return img
    
    def get_page_dimensions(self, pdf_path: str, page_number: int) -> Tuple[int, int]:
        """Get dimensions of a page after conversion to image."""
        doc = fitz.open(pdf_path)
        
        if page_number < 1 or page_number > len(doc):
            doc.close()
            raise ValueError(f"Page number {page_number} out of range")
        
        page = doc[page_number - 1]
        rect = page.rect
        
        width = int(rect.width * self.zoom)
        height = int(rect.height * self.zoom)
        
        doc.close()
        return width, height
    
    def crop_region(
        self,
        pdf_path: str,
        page_number: int,
        x: int,
        y: int,
        width: int,
        height: int
    ) -> Image.Image:
        """
        Crop a region from a PDF page.
        
        Args:
            pdf_path: Path to the PDF file
            page_number: 1-based page number
            x, y: Top-left corner coordinates
            width, height: Dimensions of the crop region
            
        Returns:
            Cropped PIL Image
        """
        img = self.get_page_as_image(pdf_path, page_number)
        
        # Ensure coordinates are within bounds
        img_width, img_height = img.size
        x = max(0, min(x, img_width))
        y = max(0, min(y, img_height))
        x2 = max(0, min(x + width, img_width))
        y2 = max(0, min(y + height, img_height))
        
        cropped = img.crop((x, y, x2, y2))
        return cropped
    
    def save_page_image(self, pdf_path: str, page_number: int, output_path: str) -> str:
        """Save a specific page as an image file."""
        img = self.get_page_as_image(pdf_path, page_number)
        img.save(output_path)
        return output_path


# Singleton instance
pdf_service = PDFService()
