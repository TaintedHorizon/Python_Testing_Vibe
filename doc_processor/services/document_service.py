"""
Document Service Layer

This module contains business logic for document operations that was previously
embedded in route handlers. By extracting this logic:
- Routes become simpler and focused on HTTP concerns
- Business logic is reusable across different interfaces
- Testing becomes easier with isolated business logic
- Code is more maintainable and follows separation of concerns
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple, Union
# Note: These imports may need adjustment based on actual module structure
from ..database import get_db_connection
from ..processing import process_batch, process_image_file, database_connection
from ..document_detector import get_detector
from ..config_manager import app_config
from ..utils.helpers import get_supported_files, validate_file_type

logger = logging.getLogger(__name__)

class DocumentService:
    """Service class for document-related business operations."""
    
    def __init__(self):
        self.detector = get_detector()
    
    def analyze_intake_directory(self, intake_dir: str) -> Dict[str, Any]:
        """
        Analyze intake directory for new documents.
        
        Args:
            intake_dir: Path to intake directory
            
        Returns:
            Dictionary with analysis results
        """
        try:
            if not os.path.exists(intake_dir):
                return {
                    'success': False,
                    'error': f'Intake directory does not exist: {intake_dir}'
                }
            
            # Get all supported files
            files = get_supported_files(intake_dir)
            
            if not files:
                return {
                    'success': True,
                    'message': 'No supported files found in intake directory',
                    'file_count': 0,
                    'files': []
                }
            
            # Analyze each file
            file_analyses = []
            for file_path in files:
                analysis = self._analyze_single_file(file_path)
                file_analyses.append(analysis)
            
            return {
                'success': True,
                'file_count': len(files),
                'files': file_analyses,
                'supported_types': ['.pdf', '.png', '.jpg', '.jpeg']
            }
            
        except Exception as e:
            logger.error(f"Error analyzing intake directory: {e}")
            return {
                'success': False,
                'error': f'Analysis failed: {str(e)}'
            }
    
    def _analyze_single_file(self, file_path: str) -> Dict[str, Any]:
        """Analyze a single file for type and basic properties."""
        try:
            stat = os.stat(file_path)
            file_ext = os.path.splitext(file_path)[1].lower()
            
            analysis = {
                'filename': os.path.basename(file_path),
                'path': file_path,
                'size_bytes': stat.st_size,
                'extension': file_ext,
                'is_image': file_ext in ['.png', '.jpg', '.jpeg'],
                'is_pdf': file_ext == '.pdf',
                'supported': validate_file_type(file_path)
            }
            
            # Add image-specific analysis if needed
            if analysis['is_image']:
                analysis['requires_conversion'] = True
                analysis['target_format'] = 'PDF'
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {e}")
            return {
                'filename': os.path.basename(file_path),
                'path': file_path,
                'error': str(e),
                'supported': False
            }
    
    def create_batch_from_intake(self, intake_dir: str, batch_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new batch from files in intake directory.
        
        Args:
            intake_dir: Path to intake directory
            batch_name: Optional name for the batch
            
        Returns:
            Dictionary with batch creation results
        """
        try:
            # Analyze intake first
            analysis = self.analyze_intake_directory(intake_dir)
            if not analysis['success']:
                return analysis
            
            if analysis['file_count'] == 0:
                return {
                    'success': False,
                    'error': 'No files to process in intake directory'
                }
            
            # Create batch and process files
            batch_id = self._create_new_batch(batch_name)
            
            # Process each file into the batch
            processed_count = 0
            errors = []
            success_files = []
            
            for file_info in analysis['files']:
                if not file_info.get('supported', False):
                    errors.append(f"Unsupported file: {file_info['filename']}")
                    continue
                
                try:
                    if file_info['is_image']:
                        # Convert image to PDF first
                        result_path = process_image_file(file_info['path'], batch_id)
                        if result_path:
                            success_files.append({
                                'filename': file_info['filename'],
                                'path': file_info['path'],
                                'processed_path': result_path,
                                'strategy': 'image_conversion',
                                'confidence': 1.0
                            })
                        else:
                            errors.append(f"Failed to process image {file_info['filename']}")
                    else:
                        # Process PDF directly
                        result = self.detector.analyze_pdf(file_info['path'])
                        
                        # Process result from DocumentAnalysis
                        if result:  # DocumentAnalysis object exists
                            success_files.append({
                                'filename': file_info['filename'],
                                'path': file_info['path'],
                                'strategy': result.processing_strategy,
                                'confidence': result.confidence
                            })
                        else:
                            errors.append(f"Failed to analyze {file_info['filename']}")
                        
                except Exception as e:
                    errors.append(f"Error processing {file_info['filename']}: {str(e)}")
            
            return {
                'success': True,
                'batch_id': batch_id,
                'total_files': analysis['file_count'],
                'processed_count': processed_count,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error creating batch from intake: {e}")
            return {
                'success': False,
                'error': f'Batch creation failed: {str(e)}'
            }
    
    def _create_new_batch(self, batch_name: Optional[str] = None) -> int:
        """Create a new batch record in database."""
        with database_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO batches (status)
                VALUES ('intake')
            """)
            
            return cursor.lastrowid or 0
    
    def get_batch_summary(self, batch_id: int) -> Dict[str, Any]:
        """
        Get summary information for a batch.
        
        Args:
            batch_id: ID of the batch
            
        Returns:
            Dictionary with batch summary
        """
        try:
            with database_connection() as conn:
                cursor = conn.cursor()
                
                # Get batch info
                cursor.execute("""
                    SELECT id, status, start_time
                    FROM batches WHERE id = ?
                """, (batch_id,))
                
                batch_row = cursor.fetchone()
                if not batch_row:
                    return {
                        'success': False,
                        'error': f'Batch {batch_id} not found'
                    }
                
                # Get document counts by status
                cursor.execute("""
                    SELECT status, COUNT(*) as count
                    FROM documents 
                    WHERE batch_id = ?
                    GROUP BY status
                """, (batch_id,))
                
                status_counts = dict(cursor.fetchall())
                
                # Get total page count
                cursor.execute("""
                    SELECT COUNT(*) FROM documents WHERE batch_id = ?
                """, (batch_id,))
                
                total_pages = cursor.fetchone()[0]
                
                return {
                    'success': True,
                    'batch': {
                        'id': batch_row[0],
                        'name': f'Batch {batch_row[0]}',  # Generate name since column doesn't exist
                        'status': batch_row[1],
                        'created_at': batch_row[2],  # start_time mapped to created_at
                        'total_pages': total_pages,
                        'status_counts': status_counts
                    }
                }
                
        except Exception as e:
            logger.error(f"Error getting batch summary: {e}")
            return {
                'success': False,
                'error': f'Failed to get batch summary: {str(e)}'
            }
    
    def start_batch_processing(self, batch_id: int) -> Dict[str, Any]:
        """
        Start automated processing for a batch.
        
        Args:
            batch_id: ID of the batch to process
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Validate batch exists and is in correct status
            batch_summary = self.get_batch_summary(batch_id)
            if not batch_summary['success']:
                return batch_summary
            
            batch_status = batch_summary['batch']['status']
            if batch_status not in ['intake', 'ready']:
                return {
                    'success': False,
                    'error': f'Batch is not ready for processing (status: {batch_status})'
                }
            
            # Start processing
            result = process_batch()
            
            return {
                'success': True,
                'message': 'Batch processing started',
                'batch_id': batch_id,
                'processing_result': result
            }
            
        except Exception as e:
            logger.error(f"Error starting batch processing: {e}")
            return {
                'success': False,
                'error': f'Failed to start processing: {str(e)}'
            }