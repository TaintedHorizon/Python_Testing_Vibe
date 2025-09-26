from .llm_utils import get_ai_document_type_analysis
"""
Document type detection and processing strategy selection.

This module provides conservative heuristics to determine whether a PDF should be
processed as a single document or as a batch scan. The detection is intentionally
conservative to avoid misclassification that would require reprocessing.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass
import fitz

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
                # Extract first page text sample for analysis
                content_sample = ""
                if page_count > 0:
                    first_page = doc[0]
                    try:
                        # Extract text from first page for LLM analysis - handle PyMuPDF API variations
                        if hasattr(first_page, 'get_text'):
                            content_sample = getattr(first_page, 'get_text')()
                        elif hasattr(first_page, 'getText'):
                            content_sample = getattr(first_page, 'getText')()
                        else:
                            self.logger.warning(f"No text extraction method available in PyMuPDF for {file_path}")
                        
                        # If no embedded text found, try light OCR for scanned PDFs
                        if not content_sample or len(content_sample.strip()) < 50:
                            self.logger.info(f"📄 No embedded text in {os.path.basename(file_path)}, attempting OCR extraction...")
                            try:
                                # Convert first page to image and run OCR
                                from pdf2image import convert_from_path
                                import pytesseract
                                from .config_manager import app_config
                                
                                if not app_config.DEBUG_SKIP_OCR:
                                    # Convert just the first page
                                    pages = convert_from_path(file_path, first_page=1, last_page=1, dpi=150)
                                    if pages:
                                        # Run OCR on the first page
                                        ocr_text = pytesseract.image_to_string(pages[0])
                                        if ocr_text and len(ocr_text.strip()) > content_sample.count(' '):
                                            content_sample = ocr_text
                                            self.logger.info(f"📄 OCR extracted {len(content_sample)} characters from {os.path.basename(file_path)}")
                                        else:
                                            self.logger.debug(f"📄 OCR didn't improve text extraction for {os.path.basename(file_path)}")
                                else:
                                    content_sample = f"[DEBUG MODE - Sample content for {os.path.basename(file_path)}]"
                                    self.logger.debug(f"📄 DEBUG mode: using sample content for {os.path.basename(file_path)}")
                            except Exception as ocr_error:
                                self.logger.warning(f"📄 OCR extraction failed for {os.path.basename(file_path)}: {ocr_error}")
                        
                        if content_sample:
                            self.logger.debug(f"📄 Final content sample: {len(content_sample)} characters from {os.path.basename(file_path)}")
                        else:
                            self.logger.debug(f"📄 No content available for LLM analysis from {os.path.basename(file_path)}")
                    except Exception as text_error:
                        self.logger.warning(f"Failed to extract text from {file_path}: {text_error}")
                        content_sample = ""
            
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
                skip_reason = "disabled" if not self.use_llm_for_ambiguous else "no content"
                self.logger.info(f"⏭️ Skipping LLM analysis for {os.path.basename(file_path)}: {skip_reason}")
                reasoning.append(f"🤖 LLM ANALYSIS: Skipped ({skip_reason})")
            result = DocumentAnalysis(
                file_path=file_path,
                file_size_mb=file_size_mb,
                page_count=page_count,
                processing_strategy=strategy if strategy is not None else "batch_scan",
                confidence=confidence,
                reasoning=reasoning,
                filename_hints=filename_hint,
                content_sample=content_sample[:200] if content_sample else None,
                llm_analysis=llm_analysis
            )
            # Log detection decision for training data collection
            try:
                from .database import log_interaction
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
                reasoning=[f"Analysis error: {e}", "Defaulting to batch scan for safety"]
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
        Analyze all PDFs in intake directory and return processing strategies.
        
        Returns list of DocumentAnalysis objects for preview/confirmation.
        """
        if not os.path.exists(intake_dir):
            self.logger.error(f"Intake directory does not exist: {intake_dir}")
            return []
        
        pdf_files = [
            os.path.join(intake_dir, f) 
            for f in os.listdir(intake_dir) 
            if f.lower().endswith('.pdf')
        ]
        
        self.logger.info(f"Found {len(pdf_files)} PDF files in {intake_dir}")
        
        analyses = []
        for pdf_file in pdf_files:
            analysis = self.analyze_pdf(pdf_file)
            analyses.append(analysis)
        
        # Summary logging
        single_count = sum(1 for a in analyses if a.processing_strategy == "single_document")
        batch_count = len(analyses) - single_count
        
        self.logger.info(f"Analysis complete: {single_count} single documents, {batch_count} batch scans")
        
        return analyses

def get_detector(use_llm_for_ambiguous: bool = True) -> DocumentTypeDetector:
    """
    Factory function to get document type detector instance.
    
    Args:
        use_llm_for_ambiguous: Whether to use LLM analysis for ambiguous cases
    """
    return DocumentTypeDetector(use_llm_for_ambiguous=use_llm_for_ambiguous)