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
import fitz  # PyMuPDF
from dataclasses import dataclass

@dataclass
class DocumentAnalysis:
    """Results of document analysis for processing strategy determination."""
    file_path: str
    file_size_mb: float
    page_count: int
    processing_strategy: str  # 'single_document' or 'batch_scan'
    confidence: float  # 0.0 to 1.0
    reasoning: List[str]  # Human-readable reasons for the decision
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
        self._get_ai_analysis = None
        
        # Lazy import to avoid circular imports
        if use_llm_for_ambiguous:
            self._import_llm_function()
    
    def _import_llm_function(self):
        """Lazy import of LLM function to avoid circular imports."""
        try:
            # Try relative import first
            from . import processing
            self._get_ai_analysis = processing.get_ai_document_type_analysis
            self.logger.info("LLM analysis function loaded successfully")
        except ImportError:
            try:
                # Try direct import as fallback
                import processing
                self._get_ai_analysis = processing.get_ai_document_type_analysis
                self.logger.info("LLM analysis function loaded successfully (fallback)")
            except Exception as e:
                self.logger.warning(f"Could not import LLM analysis function: {e} - LLM detection disabled")
                self.use_llm_for_ambiguous = False
                self._get_ai_analysis = None
    
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
                    # Use PyMuPDF text extraction - try multiple methods for compatibility
                    try:
                        # Modern PyMuPDF API
                        if hasattr(first_page, 'get_text'):
                            content_sample = first_page.get_text()[:500]
                        # Legacy PyMuPDF API
                        elif hasattr(first_page, 'getText'):
                            content_sample = first_page.getText()[:500]
                        # Alternative method using textpage
                        elif hasattr(first_page, 'get_textpage'):
                            textpage = first_page.get_textpage()
                            content_sample = textpage.extractText()[:500] if textpage else ""
                        else:
                            self.logger.warning("No text extraction method available in PyMuPDF")
                            content_sample = ""
                    except Exception as text_error:
                        self.logger.warning(f"Text extraction failed: {text_error}")
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
            
            # Decision logic with LLM enhancement for ambiguous cases
            total_score = single_doc_score + batch_doc_score
            if total_score > 0:
                confidence = max(single_doc_score, batch_doc_score) / total_score
            
            llm_analysis = None
            
            # Check if this is an ambiguous case that could benefit from LLM analysis
            score_difference = abs(single_doc_score - batch_doc_score)
            is_ambiguous = (
                score_difference <= 2 or  # Close scores
                confidence < 0.7 or       # Low confidence
                (5 <= page_count <= 20)   # Ambiguous page count range
            )
            
            # Use LLM for ambiguous cases if available
            if (is_ambiguous and self.use_llm_for_ambiguous and 
                self._get_ai_analysis and content_sample.strip()):
                
                self.logger.info(f"Ambiguous case detected for {os.path.basename(file_path)}, consulting LLM...")
                reasoning.append("Ambiguous heuristics - consulting LLM for deeper analysis")
                
                llm_analysis = self._get_ai_analysis(
                    file_path, content_sample, os.path.basename(file_path), 
                    page_count, file_size_mb
                )
                
                if llm_analysis:
                    llm_strategy = llm_analysis.get('classification')
                    llm_confidence = llm_analysis.get('confidence', 50) / 100.0  # Convert to 0-1
                    llm_reasoning = llm_analysis.get('reasoning', 'LLM analysis')
                    
                    # Combine heuristic and LLM analysis
                    if llm_confidence >= 0.6:  # Trust LLM if reasonably confident
                        strategy = llm_strategy
                        confidence = (confidence + llm_confidence) / 2  # Average confidences
                        reasoning.append(f"LLM analysis (confidence: {llm_confidence:.2f}): {llm_reasoning[:100]}...")
                        reasoning.append(f"Final decision: {strategy} based on LLM analysis")
                    else:
                        # LLM not confident, stick with heuristics but note the analysis
                        reasoning.append(f"LLM uncertain (confidence: {llm_confidence:.2f}): {llm_reasoning[:100]}...")
                        reasoning.append("Sticking with heuristic analysis due to low LLM confidence")
            
            # Apply final decision logic if not already set by LLM
            if 'strategy' not in locals() or not strategy:
                # Conservative threshold: require 70% confidence AND score advantage for single doc
                if single_doc_score >= batch_doc_score + 2 and confidence >= 0.7:
                    strategy = "single_document"
                    reasoning.append(f"HIGH CONFIDENCE single document (score: {single_doc_score} vs {batch_doc_score})")
                else:
                    strategy = "batch_scan" 
                    reasoning.append(f"Defaulting to batch scan (score: {single_doc_score} vs {batch_doc_score})")
            
            result = DocumentAnalysis(
                file_path=file_path,
                file_size_mb=file_size_mb,
                page_count=page_count,
                processing_strategy=strategy,
                confidence=confidence,
                reasoning=reasoning,
                filename_hints=filename_hint,
                content_sample=content_sample[:200] if content_sample else None,
                llm_analysis=llm_analysis
            )
            
            # Log detection decision for training data collection
            try:
                # Import here to avoid circular imports
                from . import database
                
                detection_data = {
                    "filename": os.path.basename(file_path),
                    "file_size_mb": file_size_mb,
                    "page_count": page_count,
                    "heuristic_scores": {"single": single_doc_score, "batch": batch_doc_score},
                    "filename_hints": filename_hint,
                    "final_strategy": strategy,
                    "final_confidence": confidence,
                    "llm_used": llm_analysis is not None,
                    "llm_analysis": llm_analysis,
                    "reasoning": reasoning
                }
                
                database.log_interaction(
                    batch_id=None,
                    document_id=None,
                    user_id="system",  # Use system directly since get_current_user_id is in processing.py
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