"""
Intake Analysis Routes - Demonstrates modular Flask architecture

This blueprint handles all intake-related routes that were previously in the monolithic app.py.
Benefits:
- Smaller, focused files (easier to edit without indentation errors)
- Clear separation of concerns
- Better maintainability and testing
- Reduced merge conflicts in team development
"""

from flask import Blueprint, render_template, jsonify, request, Response
from ..document_detector import get_detector
from ..config_manager import app_config
import logging
import json
import os
import os

# Create blueprint for intake routes
intake_bp = Blueprint('intake', __name__)

@intake_bp.route("/analyze_intake")
def analyze_intake_page():
    """Display the intake analysis page with cached results if available."""
    # Check if we have cached analysis results to avoid re-analyzing
    cached_analyses = None
    try:
        import tempfile
        import pickle
        cache_file = os.path.join(tempfile.gettempdir(), 'intake_analysis_cache.pkl')
        if os.path.exists(cache_file):
            with open(cache_file, 'rb') as f:
                cached_analyses = pickle.load(f)
            logging.info("Loaded cached analysis results")
    except Exception as e:
        logging.warning(f"Failed to load cached analysis results: {e}")
        cached_analyses = None
    
    return render_template("intake_analysis.html", 
                         analyses=cached_analyses,  # Use cached if available
                         intake_dir=app_config.INTAKE_DIR)

@intake_bp.route("/api/analyze_intake_progress")
def analyze_intake_progress():
    """
    Server-Sent Events endpoint for real-time intake analysis progress.
    
    This endpoint provides live updates during the document detection and analysis process.
    """
    def generate_progress():
        try:
            # Import here to avoid circular imports
            import os
            
            intake_dir = app_config.INTAKE_DIR
            if not os.path.exists(intake_dir):
                yield f"data: {json.dumps({'error': f'Intake directory does not exist: {intake_dir}'})}\n\n"
                return
                
            # Check for supported files (PDFs and images) 
            supported_files = []
            for f in os.listdir(intake_dir):
                file_ext = os.path.splitext(f)[1].lower()
                if file_ext in ['.pdf', '.png', '.jpg', '.jpeg']:
                    supported_files.append(os.path.join(intake_dir, f))
            
            total_files = len(supported_files)
            
            if total_files == 0:
                yield f"data: {json.dumps({'complete': True, 'analyses': [], 'total': 0, 'single_count': 0, 'batch_count': 0, 'success': True})}\n\n"
                return
            
            # Send initial progress
            logging.info(f"Starting SSE analysis for {total_files} files (PDFs and images)")
            yield f"data: {json.dumps({'progress': 0, 'total': total_files, 'current_file': None, 'message': f'Found {total_files} files to analyze...'})}\n\n"
            
            analyses = []
            single_count = 0
            batch_count = 0
            
            # Initialize detector
            detector = get_detector(use_llm_for_ambiguous=True)
            
            for i, file_path in enumerate(supported_files):
                filename = os.path.basename(file_path)
                
                # Send progress update for current file
                yield f"data: {json.dumps({'progress': i, 'total': total_files, 'current_file': filename, 'message': f'Analyzing {filename}...'})}\n\n"
                
                # Analyze the file (PDF or image)
                if file_path.lower().endswith('.pdf'):
                    analysis = detector.analyze_pdf(file_path)
                else:
                    analysis = detector.analyze_image_file(file_path)
                
                # Prepare analysis data
                analysis_data = {
                    'filename': filename,
                    'file_size_mb': analysis.file_size_mb,
                    'page_count': analysis.page_count,
                    'processing_strategy': analysis.processing_strategy,
                    'confidence': analysis.confidence,
                    'reasoning': analysis.reasoning,
                    'filename_hints': analysis.filename_hints,
                    'content_sample': analysis.content_sample,
                    'llm_analysis': analysis.llm_analysis,  # Include LLM analysis data
                    'detected_rotation': analysis.detected_rotation  # Include rotation info
                }
                
                analyses.append(analysis_data)
                
                if analysis.processing_strategy == "single_document":
                    single_count += 1
                else:
                    batch_count += 1
            
            # Cache the analysis results for future use
            import tempfile
            import pickle
            cache_file = os.path.join(tempfile.gettempdir(), 'intake_analysis_cache.pkl')
            try:
                with open(cache_file, 'wb') as f:
                    pickle.dump(analyses, f)
                logging.info(f"Cached analysis results to {cache_file}")
            except Exception as cache_err:
                logging.warning(f"Failed to cache analysis results: {cache_err}")
            
            # Send completion
            yield f"data: {json.dumps({'complete': True, 'analyses': analyses, 'total': total_files, 'single_count': single_count, 'batch_count': batch_count, 'success': True})}\n\n"
            
        except Exception as e:
            logging.error(f"Error in intake analysis SSE: {e}")
            yield f"data: {json.dumps({'error': str(e), 'complete': True, 'success': False})}\n\n"
    
    return Response(generate_progress(), mimetype='text/event-stream')

@intake_bp.route("/api/analyze_intake")
def analyze_intake_api():
    """
    API endpoint for intake analysis (fallback for browsers with SSE issues).
    
    Returns JSON response with analysis results for all files in intake directory.
    """
    try:
        from ..document_detector import get_detector
        
        detector = get_detector(use_llm_for_ambiguous=True)
        analyses = detector.analyze_intake_directory(app_config.INTAKE_DIR)
        
        # Convert analyses to JSON-serializable format
        analyses_data = []
        single_count = 0
        batch_count = 0
        
        for analysis in analyses:
            analysis_data = {
                'filename': os.path.basename(analysis.file_path),
                'file_size_mb': analysis.file_size_mb,
                'page_count': analysis.page_count,
                'processing_strategy': analysis.processing_strategy,
                'confidence': analysis.confidence,
                'reasoning': analysis.reasoning,
                'filename_hints': analysis.filename_hints,
                'content_sample': analysis.content_sample,
                'llm_analysis': analysis.llm_analysis,  # Include LLM analysis data
                'detected_rotation': analysis.detected_rotation  # Include rotation info
            }
            analyses_data.append(analysis_data)
            
            if analysis.processing_strategy == "single_document":
                single_count += 1
            else:
                batch_count += 1
        
        # Cache the analysis results for future use
        import tempfile
        import pickle
        cache_file = os.path.join(tempfile.gettempdir(), 'intake_analysis_cache.pkl')
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(analyses_data, f)
            logging.info(f"Cached analysis results to {cache_file}")
        except Exception as cache_err:
            logging.warning(f"Failed to cache analysis results: {cache_err}")
        
        return jsonify({
            'analyses': analyses_data,
            'total': len(analyses_data),
            'single_count': single_count,
            'batch_count': batch_count,
            'success': True
        })
        
    except Exception as e:
        logging.error(f"Error in analyze_intake_api: {e}")
        return jsonify({'error': str(e), 'success': False}), 500

@intake_bp.route("/rescan_ocr", methods=["POST"])
def rescan_ocr():
    """
    API endpoint to rescan OCR for a specific document with manual rotation.
    
    Expected JSON payload:
    {
        "filename": "document.pdf",
        "rotation": 90
    }
    """
    try:
        data = request.get_json()
        filename = data.get('filename')
        rotation = data.get('rotation', 0)
        
        if not filename:
            return jsonify({'error': 'Filename is required', 'success': False}), 400
            
        logging.info(f"Rescanning OCR for {filename} with {rotation}° rotation")
        
        # Get the full file path
        file_path = os.path.join(app_config.INTAKE_DIR, filename)
        if not os.path.exists(file_path):
            return jsonify({'error': f'File not found: {filename}', 'success': False}), 404
        
        # Determine file type and perform OCR with rotation
        if filename.lower().endswith('.pdf'):
            content_sample = _rescan_pdf_ocr(file_path, rotation)
        elif filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            content_sample = _rescan_image_ocr(file_path, rotation)
        else:
            return jsonify({'error': f'Unsupported file type: {filename}', 'success': False}), 400
            
        return jsonify({
            'success': True,
            'filename': filename,
            'rotation': rotation,
            'content_sample': content_sample[:500] if content_sample else None,
            'message': f'OCR rescanned successfully with {rotation}° rotation'
        })
        
    except Exception as e:
        logging.error(f"Error in rescan_ocr: {e}")
        return jsonify({'error': str(e), 'success': False}), 500

@intake_bp.route("/reanalyze_llm", methods=["POST"])
def reanalyze_llm():
    """
    API endpoint to re-analyze a document with LLM using updated OCR text.
    
    Expected JSON payload:
    {
        "filename": "document.pdf"
    }
    """
    try:
        data = request.get_json()
        filename = data.get('filename')
        
        if not filename:
            return jsonify({'error': 'Filename is required', 'success': False}), 400
            
        logging.info(f"Re-analyzing LLM for {filename}")
        
        # Get the full file path
        file_path = os.path.join(app_config.INTAKE_DIR, filename)
        if not os.path.exists(file_path):
            return jsonify({'error': f'File not found: {filename}', 'success': False}), 404
        
        # Get current analysis from cache or re-analyze
        from ..document_detector import get_detector
        detector = get_detector(use_llm_for_ambiguous=True)
        
        # Re-run analysis with LLM
        if filename.lower().endswith('.pdf'):
            analysis = detector.analyze_pdf(file_path)
        elif filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            analysis = detector.analyze_image_file(file_path)
        else:
            return jsonify({'error': f'Unsupported file type: {filename}', 'success': False}), 400
        
        if not analysis:
            return jsonify({'error': 'Failed to re-analyze document', 'success': False}), 500
            
        return jsonify({
            'success': True,
            'filename': filename,
            'processing_strategy': analysis.processing_strategy,
            'confidence': analysis.confidence,
            'reasoning': analysis.reasoning,
            'llm_analysis': analysis.llm_analysis,
            'message': 'LLM re-analysis completed successfully'
        })
        
    except Exception as e:
        logging.error(f"Error in reanalyze_llm: {e}")
        return jsonify({'error': str(e), 'success': False}), 500

def _rescan_pdf_ocr(file_path: str, rotation: int) -> str:
    """
    Re-run OCR on a PDF file with specified rotation.
    
    Args:
        file_path (str): Path to the PDF file
        rotation (int): Rotation angle (0, 90, 180, 270)
        
    Returns:
        str: Extracted text content
    """
    try:
        from pdf2image import convert_from_path
        from PIL import Image
        import pytesseract
        
        # Convert first few pages to images
        pages = convert_from_path(file_path, first_page=1, last_page=3)
        page_texts = []
        
        for page_idx, page_img in enumerate(pages):
            # Apply rotation if specified
            if rotation != 0:
                page_img = page_img.rotate(-rotation, expand=True)
                logging.info(f"Applied {rotation}° rotation to page {page_idx + 1}")
            
            # Run OCR
            page_text = pytesseract.image_to_string(page_img)
            if page_text and len(page_text.strip()) > 10:
                page_texts.append(f"=== PAGE {page_idx + 1} ===\n{page_text.strip()}")
                logging.info(f"Extracted {len(page_text)} characters from rotated page {page_idx + 1}")
        
        combined_text = "\n\n".join(page_texts)
        logging.info(f"Total OCR text extracted: {len(combined_text)} characters")
        
        return combined_text
        
    except Exception as e:
        logging.error(f"Error in PDF OCR rescan: {e}")
        return ""

def _rescan_image_ocr(file_path: str, rotation: int) -> str:
    """
    Re-run OCR on an image file with specified rotation.
    
    Args:
        file_path (str): Path to the image file
        rotation (int): Rotation angle (0, 90, 180, 270)
        
    Returns:
        str: Extracted text content
    """
    try:
        from PIL import Image
        import numpy as np
        
        with Image.open(file_path) as img:
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Apply rotation if specified
            if rotation != 0:
                img = img.rotate(-rotation, expand=True)
                logging.info(f"Applied {rotation}° rotation to image")
            
            # Use EasyOCR for better results
            from ..processing import EasyOCRSingleton
            reader = EasyOCRSingleton.get_reader()
            ocr_results = reader.readtext(np.array(img))
            
            if ocr_results:
                text = " ".join([text for (_, text, _) in ocr_results])
                logging.info(f"Extracted {len(text)} characters from rotated image")
                return text
            else:
                logging.warning("No text extracted from rotated image")
                return ""
                
    except Exception as e:
        logging.error(f"Error in image OCR rescan: {e}")
        return ""