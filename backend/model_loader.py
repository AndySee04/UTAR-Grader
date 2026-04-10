"""
Eager loading of heavy ML models (TrOCR, etc.) at application startup.

Lazy loading remains available inside services for tests or imports that
should not touch the GPU.
"""

from services.ocr_service import ocr_service, ocr_service_printed


def load_models() -> None:
    """Load all configured OCR / vision models into memory."""
    ocr_service.preload()
    ocr_service_printed.preload()
