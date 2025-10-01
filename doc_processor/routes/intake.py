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
    """Display the intake analysis page."""
    return render_template("intake_analysis.html")

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
                    'content_sample': analysis.content_sample
                }
                
                analyses.append(analysis_data)
                
                if analysis.processing_strategy == "single_document":
                    single_count += 1
                else:
                    batch_count += 1
            
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
                'content_sample': analysis.content_sample
            }
            analyses_data.append(analysis_data)
            
            if analysis.processing_strategy == "single_document":
                single_count += 1
            else:
                batch_count += 1
        
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