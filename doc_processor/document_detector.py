try:
    # Try relative imports first (when used as module)
    from .llm_utils import get_ai_document_type_analysis
except ImportError:
    # Fallback to absolute imports (when run directly)
    from llm_utils import get_ai_document_type_analysis
"""
Document type detection and processing strategy selection.

This module provides conservative heuristics to determine whether a PDF should be
processed as a single document or as a batch scan. The detection is intentionally
conservative to avoid misclassification that would require reprocessing.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional
import logging
from dataclasses import dataclass
import fitz
from PIL import Image
import threading
import time

@dataclass
class DocumentAnalysis:
    """Results of document analysis for processing strategy determination."""
    file_path: str
    file_size_mb: float
    page_count: int
    processing_strategy: str
    confidence: float
    reasoning: list
    filename_hints: Optional[str] = None
    content_sample: Optional[str] = None
    llm_analysis: Optional[Dict] = None  # LLM analysis results when used
    detected_rotation: int = 0  # Rotation angle detected during analysis (0, 90, 180, 270)
    pdf_path: Optional[str] = None  # Path to PDF version (for converted images)

class DocumentTypeDetector:
    """
    Conservative document type detection with bias toward batch processing.

    The detector uses multiple heuristics and requires HIGH confidence to
    classify as single document. When in doubt, defaults to batch processing
    to avoid data loss or incorrect processing.
    """

    # Conservative thresholds - err on side of batch processing
    SINGLE_DOC_MAX_PAGES = 15  # Very conservative - most single docs under 15 pages
    BATCH_MIN_PAGES = 25       # Clear batch indicator
    LARGE_FILE_MB = 50         # Files over 50MB likely batch scans

    # Filename patterns that suggest single documents (high confidence)
    SINGLE_DOC_PATTERNS = [
        r'invoice.*\d{4}',        # invoice_2024_001.pdf
        r'contract.*\d+',         # contract_2024.pdf
        r'report.*\d{4}',         # report_annual_2024.pdf
        r'statement.*\d{4}',      # statement_march_2024.pdf
        r'receipt.*\d+',          # receipt_12345.pdf
        r'letter.*\d{4}',         # letter_2024_03.pdf
        r'memo.*\d{4}',           # memo_2024_march.pdf
        r'policy.*\d+',           # policy_handbook_v2.pdf
    ]

    # Filename patterns that suggest batch scans (high confidence)
    BATCH_DOC_PATTERNS = [
        r'scan.*\d{8}',           # scan_20240325.pdf
        r'batch.*\d+',            # batch_001.pdf
        r'scanned.*\d{4}',        # scanned_documents_2024.pdf
        r'multi.*doc',            # multi_document_scan.pdf
        r'combined.*\d{4}',       # combined_march_2024.pdf
        r'archive.*\d{4}',        # archive_2024_q1.pdf
    ]

    def __init__(self, use_llm_for_ambiguous=True):
        self.logger = logging.getLogger(__name__)
        self.use_llm_for_ambiguous = use_llm_for_ambiguous
        self._start_normalized_cleanup_once()

    _cleanup_started = False

    def _start_normalized_cleanup_once(self):
        if DocumentTypeDetector._cleanup_started:
            return
        DocumentTypeDetector._cleanup_started = True
        def _cleanup_loop():
            while True:
                try:
                    try:
                        from .config_manager import app_config
                    except ImportError:
                        from config_manager import app_config
                    root = app_config.NORMALIZED_DIR
                    max_age_days = app_config.NORMALIZED_CACHE_MAX_AGE_DAYS
                    if not root or not os.path.isdir(root):
                        time.sleep(3600)
                        continue
                    cutoff = time.time() - (max_age_days * 86400)
                    removed = 0
                    for fname in os.listdir(root):
                        if not fname.lower().endswith('.pdf'):
                            continue
                        fpath = os.path.join(root, fname)
                        try:
                            st = os.stat(fpath)
                            if st.st_mtime < cutoff:
                                os.remove(fpath)
                                removed += 1
                        except OSError:
                            continue
                    if removed:
                        self.logger.info(f"Normalized cache cleanup removed {removed} stale PDFs (>{max_age_days}d)")
                except Exception as e:
                    try:
                        self.logger.warning(f"Normalized cache cleanup error: {e}")
                    except Exception:
                        pass
                time.sleep(43200)  # 12 hours
        threading.Thread(target=_cleanup_loop, daemon=True, name='NormalizedCacheCleanup').start()

    def _convert_image_to_pdf(self, image_path: str) -> str:
        """Convert image file to a cached normalized PDF.

        Uses a content hash of the image to produce a stable filename in the
        configured NORMALIZED_DIR so repeated analyses across runs reuse the
        prior conversion (saving time and I/O). Rotation is NOT applied here;
        later OCR/searchable steps handle orientation.

        Returns path to normalized PDF or original path on failure.
        """
        try:
            try:
                from .config_manager import app_config
            except ImportError:
                from config_manager import app_config
            norm_root = app_config.NORMALIZED_DIR
            os.makedirs(norm_root, exist_ok=True)
            # Hash image contents for stable identity
            import hashlib
            h = hashlib.sha256()
            with open(image_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    h.update(chunk)
            digest = h.hexdigest()  # 64 hex chars
            pdf_name = f"img_{digest[:16]}.pdf"  # shorten name while preserving uniqueness
            pdf_path = os.path.join(norm_root, pdf_name)
            if os.path.exists(pdf_path):
                self.logger.debug(f"Reusing cached normalized PDF for {image_path} -> {pdf_path}")
                return pdf_path
            # Perform conversion
            with Image.open(image_path) as img:
                if img.mode in ('RGBA', 'LA', 'P'):
                    base = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    base.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = base
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                img.save(pdf_path, 'PDF', resolution=150.0, quality=95)
            self.logger.info(f"Normalized image cached: {image_path} -> {pdf_path}")
            return pdf_path
        except Exception as e:
            self.logger.error(f"Failed to normalize image {image_path}: {e}")
            return image_path

    def _import_llm_function(self):
        """Lazy import of LLM function to avoid circular imports."""
        # _import_llm_function removed: always use llm_utils.get_ai_document_type_analysis

    def analyze_pdf(self, file_path: str) -> DocumentAnalysis:
        """
        Analyze a PDF file and determine processing strategy.

        Returns DocumentAnalysis with conservative bias toward batch_scan.
        Only returns single_document with high confidence.
        """
        self.logger.info(f"Analyzing PDF: {file_path}")

        reasoning = []
        confidence = 0.0
        strategy = "batch_scan"  # Default to safe option

        try:
            # Basic file analysis
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            filename = Path(file_path).stem.lower()

            # Open PDF to get page count and sample content
            with fitz.open(file_path) as doc:
                page_count = len(doc)
                # Extract multi-point text samples for enhanced analysis
                content_sample = ""
                if page_count > 0:
                    # Determine which pages to sample based on page count
                    pages_to_sample = []
                    if page_count == 1:
                        pages_to_sample = [0]  # Just first page
                    elif page_count == 2:
                        pages_to_sample = [0, 1]  # First and last
                    else:  # 3 or more pages
                        middle_page = page_count // 2
                        pages_to_sample = [0, middle_page, page_count - 1]  # First, middle, last

                    self.logger.info(f"📄 Multi-point sampling for {os.path.basename(file_path)}: {page_count} pages, sampling pages {[p+1 for p in pages_to_sample]}")

                    # Extract text from selected pages
                    page_samples = []
                    for page_idx in pages_to_sample:
                        try:
                            page = doc[page_idx]
                            page_text = ""

                            # Extract text from page - handle PyMuPDF API variations
                            if hasattr(page, 'get_text'):
                                page_text = getattr(page, 'get_text')()
                            elif hasattr(page, 'getText'):
                                page_text = getattr(page, 'getText')()
                            else:
                                self.logger.warning(f"No text extraction method available in PyMuPDF for {file_path}")

                            # If no embedded text found, try OCR for this page
                            if not page_text or len(page_text.strip()) < 50:
                                self.logger.debug(f"📄 No embedded text on page {page_idx+1}, attempting OCR...")
                                try:
                                    from pdf2image import convert_from_path
                                    import pytesseract
                                    try:
                                        from .config_manager import app_config
                                    except ImportError:
                                        from config_manager import app_config

                                    if not app_config.DEBUG_SKIP_OCR:
                                        # Convert specific page to image and run OCR
                                        pages = convert_from_path(file_path, first_page=page_idx+1, last_page=page_idx+1, dpi=150)
                                        if pages:
                                            page_img = pages[0]

                                            # Apply auto-rotation detection for better OCR
                                            try:
                                                osd = pytesseract.image_to_osd(page_img, output_type=pytesseract.Output.DICT)
                                                rotation = osd.get("rotate", 0)
                                                if rotation and rotation > 0:
                                                    self.logger.info(f"📄 🔄 Auto-rotating page {page_idx+1} by {rotation}° for better OCR")
                                                    page_img = page_img.rotate(-rotation, expand=True)
                                            except pytesseract.TesseractError as osd_error:
                                                self.logger.debug(f"📄 Could not determine page {page_idx+1} orientation: {osd_error}")

                                            page_text = pytesseract.image_to_string(page_img)
                                            if page_text and len(page_text.strip()) > 10:
                                                self.logger.info(f"📄 ✅ OCR extracted {len(page_text)} characters from page {page_idx+1}")
                                            else:
                                                self.logger.debug(f"📄 Page {page_idx+1} OCR returned minimal text")
                                    else:
                                        page_text = f"[DEBUG MODE - Sample content for page {page_idx+1}]"
                                except Exception as ocr_error:
                                    self.logger.warning(f"📄 OCR failed for page {page_idx+1}: {ocr_error}")

                            if page_text and len(page_text.strip()) > 10:
                                # Truncate each page sample to reasonable length
                                page_sample = page_text.strip()[:1000]
                                page_samples.append(f"=== PAGE {page_idx+1} SAMPLE ===\n{page_sample}")

                        except Exception as page_error:
                            self.logger.warning(f"Failed to extract from page {page_idx+1}: {page_error}")

                    # Combine all page samples into content for LLM analysis
                    if page_samples:
                        content_sample = "\n\n".join(page_samples)
                        self.logger.info(f"📄 ✅ Multi-point content ready: {len(content_sample)} characters from {len(page_samples)} pages of {os.path.basename(file_path)}")
                    else:
                        content_reason = "no usable text found on any sampled pages"
                        self.logger.warning(f"📄 ❌ No usable content for LLM analysis from {os.path.basename(file_path)} - {content_reason}")

            reasoning.append(f"File size: {file_size_mb:.1f}MB, Pages: {page_count}")

            # Apply detection heuristics
            single_doc_score = 0
            batch_doc_score = 0

            # 1. Page count analysis (strongest indicator)
            if page_count <= 3:
                single_doc_score += 3
                reasoning.append("Very low page count suggests single document")
            elif page_count <= self.SINGLE_DOC_MAX_PAGES:
                # Only add points if we have filename hints, otherwise be conservative
                if self._analyze_filename(filename) == "single":
                    single_doc_score += 2
                    reasoning.append("Moderate page count + filename hints suggest single document")
                else:
                    batch_doc_score += 1
                    reasoning.append("Moderate page count without clear filename hints, defaulting to batch")
            elif page_count >= self.BATCH_MIN_PAGES:
                batch_doc_score += 4
                reasoning.append("High page count strongly suggests batch scan")
            else:
                batch_doc_score += 2  # Increased from 1 to be more conservative
                reasoning.append("Page count in ambiguous range, defaulting to batch for safety")

            # 2. File size analysis
            if file_size_mb > self.LARGE_FILE_MB:
                batch_doc_score += 3
                reasoning.append("Large file size suggests batch scan")
            elif file_size_mb < 5:
                single_doc_score += 1
                reasoning.append("Small file size suggests single document")

            # 3. Filename pattern analysis
            filename_hint = self._analyze_filename(filename)
            if filename_hint == "single":
                single_doc_score += 2
                reasoning.append("Filename pattern suggests single document")
            elif filename_hint == "batch":
                batch_doc_score += 3
                reasoning.append("Filename pattern suggests batch scan")

            # 4. Content analysis (light analysis to avoid processing time)
            content_hint = self._analyze_content_sample(content_sample)
            if content_hint == "single":
                single_doc_score += 1
                reasoning.append("Content structure suggests single document")
            elif content_hint == "batch":
                batch_doc_score += 2
                reasoning.append("Content structure suggests batch scan")

            # Decision logic with LLM enhancement
            total_score = single_doc_score + batch_doc_score
            if total_score > 0:
                confidence = max(single_doc_score, batch_doc_score) / total_score
            # Heuristic strategy first
            strategy = None
            if single_doc_score >= batch_doc_score + 2 and confidence >= 0.7:
                strategy = "single_document"
                reasoning.append(f"HIGH CONFIDENCE single document (score: {single_doc_score} vs {batch_doc_score})")
            else:
                strategy = "batch_scan"
                reasoning.append(f"Defaulting to batch scan (score: {single_doc_score} vs {batch_doc_score})")

            # LLM analysis (if enabled and content available)
            llm_analysis = None
            self.logger.info(f"LLM check for {os.path.basename(file_path)}: use_llm={self.use_llm_for_ambiguous}, content_len={len(content_sample.strip()) if content_sample else 0}")

            if self.use_llm_for_ambiguous and content_sample.strip():
                self.logger.info(f"🤖 Starting LLM analysis for {os.path.basename(file_path)} (content: {len(content_sample)} chars)")
                try:
                    llm_analysis = get_ai_document_type_analysis(
                        file_path, content_sample, os.path.basename(file_path), page_count, file_size_mb
                    )
                    if llm_analysis:
                        llm_strategy = llm_analysis.get('classification')
                        llm_confidence = llm_analysis.get('confidence', 50)
                        llm_reasoning = llm_analysis.get('reasoning', '')
                        self.logger.info(f"✅ LLM analysis successful for {os.path.basename(file_path)}: {llm_strategy} ({llm_confidence}%)")
                        reasoning.append(f"🤖 LLM ANALYSIS: {llm_strategy} (confidence: {llm_confidence}%) - {llm_reasoning}")
                        # If LLM is confident, override heuristic
                        if llm_confidence >= 70:
                            strategy = llm_strategy
                            confidence = llm_confidence / 100.0
                            self.logger.info(f"🎯 LLM override: {os.path.basename(file_path)} -> {llm_strategy} (confidence: {llm_confidence}%)")
                    else:
                        self.logger.warning(f"❌ LLM analysis returned None for {os.path.basename(file_path)}")
                        reasoning.append("🤖 LLM ANALYSIS: No result returned")
                except Exception as llm_e:
                    self.logger.error(f"💥 LLM analysis failed for {os.path.basename(file_path)}: {llm_e}")
                    reasoning.append(f"🤖 LLM ANALYSIS: Failed - {str(llm_e)}")
            else:
                if not self.use_llm_for_ambiguous:
                    skip_reason = "LLM analysis disabled"
                else:
                    skip_reason = "no usable content (embedded text + OCR both failed/insufficient)"
                self.logger.warning(f"⏭️ Skipping LLM analysis for {os.path.basename(file_path)}: {skip_reason}")
                reasoning.append(f"🤖 LLM ANALYSIS: Skipped - {skip_reason}")
            result = DocumentAnalysis(
                file_path=file_path,
                file_size_mb=file_size_mb,
                page_count=page_count,
                processing_strategy=strategy if strategy is not None else "batch_scan",
                confidence=confidence,
                reasoning=reasoning,
                filename_hints=filename_hint,
                content_sample=content_sample[:200] if content_sample else None,
                llm_analysis=llm_analysis,
                detected_rotation=0,  # PDFs don't need rotation detection in analysis phase
                pdf_path=file_path  # PDFs already in correct format
            )
            # Log detection decision for training data collection
            try:
                try:
                    from .database import log_interaction
                except ImportError:
                    from database import log_interaction
                detection_data = {
                    "filename": os.path.basename(file_path),
                    "file_size_mb": file_size_mb,
                    "page_count": page_count,
                    "heuristic_scores": {"single": single_doc_score, "batch": batch_doc_score},
                    "filename_hints": filename_hint,
                    "final_strategy": strategy,
                    "final_confidence": confidence,
                    "llm_used": bool(llm_analysis),
                    "llm_analysis": llm_analysis,
                    "reasoning": reasoning
                }
                log_interaction(
                    batch_id=None,
                    document_id=None,
                    user_id="system",
                    event_type="document_detection_decision",
                    step="intake_analysis",
                    content=str(detection_data),
                    notes=f"Detection: {strategy} (confidence: {confidence:.2f}, LLM: {'Yes' if llm_analysis else 'No'})"
                )
            except Exception as log_error:
                self.logger.warning(f"Failed to log detection decision: {log_error}")
            return result

        except Exception as e:
            self.logger.error(f"Error analyzing {file_path}: {e}")
            return DocumentAnalysis(
                file_path=file_path,
                file_size_mb=0,
                page_count=0,
                processing_strategy="batch_scan",  # Safe fallback
                confidence=0.0,
                reasoning=[f"Analysis error: {e}", "Defaulting to batch scan for safety"],
                detected_rotation=0,
                pdf_path=file_path  # Use original path even in error case
            )

    def _analyze_filename(self, filename: str) -> Optional[str]:
        """Analyze filename patterns for document type hints."""
        filename_lower = filename.lower()

        # Check for single document patterns
        for pattern in self.SINGLE_DOC_PATTERNS:
            if re.search(pattern, filename_lower):
                return "single"

        # Check for batch document patterns
        for pattern in self.BATCH_DOC_PATTERNS:
            if re.search(pattern, filename_lower):
                return "batch"

        # Additional heuristics
        if any(word in filename_lower for word in ['invoice', 'receipt', 'contract', 'letter']):
            return "single"

        if any(word in filename_lower for word in ['scan', 'batch', 'combined', 'multi']):
            return "batch"

        return None

    def _analyze_content_sample(self, content: str) -> Optional[str]:
        """Light analysis of document content structure."""
        if not content or len(content) < 100:
            return None

        content_lower = content.lower()

        # Single document indicators
        single_indicators = [
            'invoice number', 'contract number', 'receipt #',
            'dear sir/madam', 'sincerely', 'best regards',
            'invoice date', 'due date', 'total amount',
            'agreement', 'terms and conditions'
        ]

        # Batch scan indicators
        batch_indicators = [
            'page 1 of', 'continued on next page', 'see attachment',
            'document 1', 'document 2', 'scan date',
            'multiple documents', 'various documents'
        ]

        single_count = sum(1 for indicator in single_indicators if indicator in content_lower)
        batch_count = sum(1 for indicator in batch_indicators if indicator in content_lower)

        if single_count > batch_count and single_count >= 2:
            return "single"
        elif batch_count > single_count and batch_count >= 2:
            return "batch"

        return None

    def analyze_intake_directory(self, intake_dir: str) -> List[DocumentAnalysis]:
        """
        Analyze all supported files (PDFs and images) in intake directory and return processing strategies.

        Returns list of DocumentAnalysis objects for preview/confirmation.
        """
        if not os.path.exists(intake_dir):
            self.logger.error(f"Intake directory does not exist: {intake_dir}")
            return []

        # Supported file extensions
        supported_extensions = ['.pdf', '.png', '.jpg', '.jpeg']

        supported_files = []
        for f in os.listdir(intake_dir):
            file_ext = os.path.splitext(f)[1].lower()
            if file_ext in supported_extensions:
                supported_files.append(os.path.join(intake_dir, f))

        self.logger.info(f"Found {len(supported_files)} supported files in {intake_dir}")

        analyses = []
        for file_path in supported_files:
            if file_path.lower().endswith('.pdf'):
                analysis = self.analyze_pdf(file_path)
            else:
                # For image files, analyze as converted PDF
                analysis = self.analyze_image_file(file_path)
            analyses.append(analysis)

        # Summary logging
        single_count = sum(1 for a in analyses if a.processing_strategy == "single_document")
        batch_count = len(analyses) - single_count

        self.logger.info(f"Analysis complete: {single_count} single documents, {batch_count} batch scans")

        return analyses

    def analyze_image_file(self, file_path: str) -> DocumentAnalysis:
        """
        Analyze an image file (PNG, JPG, JPEG) for processing strategy.

        Images are typically single documents, but we'll apply similar logic
        based on file size and filename patterns.
        """
        self.logger.info(f"Analyzing image file: {file_path}")

        reasoning = []
        confidence = 0.8  # Images are usually single documents
        strategy = "single_document"  # Default for images

        try:
            # Basic file analysis
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            filename = Path(file_path).stem.lower()

            # For images, we can't easily get "page count", so we'll use 1
            page_count = 1

            reasoning.append(f"Image file: {file_size_mb:.1f}MB, treating as single page")

            # Apply similar filename analysis as PDFs
            filename_hint = self._analyze_filename(filename)
            if filename_hint == "batch":
                strategy = "batch_scan"
                confidence = 0.6
                reasoning.append("Filename pattern suggests batch scan despite being image")
            elif filename_hint == "single":
                confidence = 0.9
                reasoning.append("Filename pattern confirms single document")
            else:
                reasoning.append("No clear filename hints, defaulting to single document for image")

            # Large images might be scanned documents
            if file_size_mb > 10:  # Large image files
                if filename_hint != "single":
                    strategy = "batch_scan"
                    confidence = 0.7
                    reasoning.append("Large image file suggests possible batch scan")

            # Try to extract text for LLM analysis if enabled
            content_sample = ""
            detected_rotation = 0
            if self.use_llm_for_ambiguous:
                try:
                    try:
                        from .config_manager import app_config
                    except ImportError:
                        from config_manager import app_config

                    if not app_config.DEBUG_SKIP_OCR:
                        self.logger.info(f"Extracting text from image for LLM analysis: {os.path.basename(file_path)}")

                        # Use sophisticated 4-orientation rotation detection
                        detected_rotation, rotation_confidence, content_sample = self._detect_best_rotation_for_image(file_path)

                        if detected_rotation != 0:
                            self.logger.info(f"  🔄 Auto-detected optimal rotation: {detected_rotation}° (confidence: {rotation_confidence:.3f})")
                            reasoning.append(f"Detected {detected_rotation}° rotation needed (confidence: {rotation_confidence:.1f})")
                        else:
                            self.logger.info(f"  ✅ Image orientation is optimal (confidence: {rotation_confidence:.3f})")
                            reasoning.append(f"No rotation needed (confidence: {rotation_confidence:.1f})")

                        if content_sample and len(content_sample.strip()) > 50:
                            self.logger.info(f"Extracted {len(content_sample)} characters from image")
                            reasoning.append("Successfully extracted text from image for analysis")
                        else:
                            self.logger.debug("Minimal text extracted from image")
                            reasoning.append("Limited text extracted from image")
                    else:
                        content_sample = "[DEBUG MODE - Sample content for image file]"
                        reasoning.append("DEBUG mode - skipped OCR")

                except Exception as ocr_error:
                    self.logger.warning(f"Failed to extract text from image {file_path}: {ocr_error}")
                    reasoning.append(f"Text extraction failed: {str(ocr_error)}")

            # LLM analysis for images (if content available)
            llm_analysis = None
            if self.use_llm_for_ambiguous and content_sample.strip():
                self.logger.info(f"🤖 Starting LLM analysis for image {os.path.basename(file_path)}")
                try:
                    llm_analysis = get_ai_document_type_analysis(
                        file_path, content_sample, os.path.basename(file_path), page_count, file_size_mb
                    )
                    if llm_analysis:
                        llm_strategy = llm_analysis.get('classification')
                        llm_confidence = llm_analysis.get('confidence', 50)
                        llm_reasoning = llm_analysis.get('reasoning', '')
                        self.logger.info(f"✅ LLM analysis for image: {llm_strategy} ({llm_confidence}%)")
                        reasoning.append(f"🤖 LLM ANALYSIS: {llm_strategy} (confidence: {llm_confidence}%) - {llm_reasoning}")

                        # Apply LLM result if confident
                        if llm_confidence >= 70:
                            strategy = llm_strategy
                            confidence = llm_confidence / 100.0
                            self.logger.info(f"🎯 LLM override for image: {os.path.basename(file_path)} -> {llm_strategy}")

                except Exception as llm_e:
                    self.logger.error(f"💥 LLM analysis failed for image {file_path}: {llm_e}")
                    reasoning.append(f"🤖 LLM ANALYSIS: Failed - {str(llm_e)}")

            result = DocumentAnalysis(
                file_path=file_path,
                file_size_mb=file_size_mb,
                page_count=page_count,
                processing_strategy=strategy,
                confidence=confidence,
                reasoning=reasoning,
                filename_hints=filename_hint,
                content_sample=content_sample[:200] if content_sample else None,
                llm_analysis=llm_analysis,
                detected_rotation=detected_rotation,
                pdf_path=self._convert_image_to_pdf(file_path)
            )

            return result

        except Exception as e:
            self.logger.error(f"Error analyzing image {file_path}: {e}")
            return DocumentAnalysis(
                file_path=file_path,
                file_size_mb=0,
                page_count=1,
                processing_strategy="single_document",  # Safe default for images
                confidence=0.5,
                reasoning=[f"Analysis error: {e}", "Defaulting to single document for image file"],
                detected_rotation=0,
                pdf_path=file_path  # Use original path if conversion fails
            )

    def _detect_best_rotation_for_image(self, image_path: str) -> tuple[int, float, str]:
        """
        Automatically detect the best rotation for an image by testing OCR confidence at different rotations.

        Args:
            image_path (str): Path to the image file

        Returns:
            tuple: (best_rotation_angle, confidence_score, ocr_text)
        """
        if not os.path.exists(image_path):
            self.logger.warning(f"Image not found for rotation detection: {image_path}")
            return 0, 0.0, ""

        try:
            from PIL import Image
            import numpy as np

            # Test rotations: 0, 90, 180, 270 degrees
            rotations_to_test = [0, 90, 180, 270]
            best_rotation = 0
            best_confidence = 0.0
            best_text = ""
            results = {}

            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                try:
                    from .processing import EasyOCRSingleton
                except ImportError:
                    from processing import EasyOCRSingleton
                reader = EasyOCRSingleton.get_reader()

                for rotation in rotations_to_test:
                    try:
                        # Rotate image for testing
                        if rotation == 0:
                            test_img = img
                        else:
                            test_img = img.rotate(-rotation, expand=True)

                        # Run OCR and get results with confidence scores
                        ocr_results = reader.readtext(np.array(test_img))

                        if ocr_results:
                            # Calculate average confidence and extract text
                            confidences = [float(conf) for (_, _, conf) in ocr_results if isinstance(conf, (int, float))]
                            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
                            text = " ".join([str(text) for (_, text, _) in ocr_results])

                            # Additional heuristics for better detection
                            text_length = len(text.strip())
                            word_count = len(text.split())

                            # Boost score for longer, more readable text
                            adjusted_confidence = avg_confidence
                            if text_length > 50:  # Reasonable amount of text
                                adjusted_confidence *= 1.1

                            if word_count > 10:  # Good word count
                                adjusted_confidence *= 1.05

                            results[rotation] = {
                                'confidence': adjusted_confidence,
                                'text': text,
                                'raw_confidence': avg_confidence,
                                'text_length': text_length
                            }

                            self.logger.debug(f"Rotation {rotation}°: confidence={avg_confidence:.3f}, adjusted={adjusted_confidence:.3f}, text_len={text_length}")

                            if adjusted_confidence > best_confidence:
                                best_confidence = adjusted_confidence
                                best_rotation = rotation
                                best_text = text
                        else:
                            results[rotation] = {'confidence': 0.0, 'text': '', 'raw_confidence': 0.0, 'text_length': 0}

                    except Exception as rotation_error:
                        self.logger.warning(f"Failed to test rotation {rotation}°: {rotation_error}")
                        results[rotation] = {'confidence': 0.0, 'text': '', 'raw_confidence': 0.0, 'text_length': 0}

                self.logger.debug(f"Rotation detection results: {results}")
                return best_rotation, best_confidence, best_text

        except Exception as e:
            self.logger.error(f"Error in rotation detection for {image_path}: {e}")
            return 0, 0.0, ""

def get_detector(use_llm_for_ambiguous: bool = True) -> DocumentTypeDetector:
    """
    Factory function to get document type detector instance.

    Args:
        use_llm_for_ambiguous: Whether to use LLM analysis for ambiguous cases
    """
    return DocumentTypeDetector(use_llm_for_ambiguous=use_llm_for_ambiguous)