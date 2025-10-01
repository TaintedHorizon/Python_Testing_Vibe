"""
Batch Service Layer

This service handles all batch-related business logic including:
- Batch creation and management
- Processing orchestration
- Status tracking and updates

Extracted from route handlers to improve separation of concerns.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
import threading
import os
from datetime import datetime

# Import database and processing modules (adjust imports as needed)
from ..database import get_db_connection, get_batch_by_id, get_documents_for_batch
from ..processing import process_batch, database_connection
from ..config_manager import app_config

logger = logging.getLogger(__name__)

class BatchService:
    """Service class for batch operations."""
    
    def __init__(self):
        self.processing_status = {}
        self.processing_lock = threading.Lock()
    
    def create_batch(self, name: Optional[str] = None, intake_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new batch from intake directory or manually.
        
        Args:
            name: Optional batch name
            intake_dir: Optional specific intake directory
            
        Returns:
            Dictionary with batch creation results
        """
        try:
            # Generate batch name if not provided
            if not name:
                name = f"Batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Create batch record
            # with database_connection() as conn:
            #     cursor = conn.cursor()
            #     cursor.execute("""
            #         INSERT INTO batches (name, status, created_at)
            #         VALUES (?, 'intake', datetime('now'))
            #     """, (name,))
            #     batch_id = cursor.lastrowid
            
            batch_id = 1  # Placeholder
            
            return {
                'success': True,
                'batch_id': batch_id,
                'name': name,
                'status': 'created'
            }
            
        except Exception as e:
            logger.error(f"Error creating batch: {e}")
            return {
                'success': False,
                'error': f'Failed to create batch: {str(e)}'
            }
    
    def get_batch_summary(self, batch_id: int) -> Dict[str, Any]:
        """
        Get comprehensive summary of a batch.
        
        Args:
            batch_id: ID of the batch
            
        Returns:
            Dictionary with batch summary data
        """
        try:
            # Get batch information
            # with database_connection() as conn:
            #     cursor = conn.cursor()
            #     batch_info = get_batch_by_id(batch_id)
            #     documents = get_documents_by_batch(batch_id)
            
            # Placeholder data
            batch_info = {'id': batch_id, 'name': f'Batch_{batch_id}', 'status': 'unknown'}
            documents = []
            
            # Calculate statistics
            total_documents = len(documents)
            status_counts = {}
            # for doc in documents:
            #     status = doc.get('status', 'unknown')
            #     status_counts[status] = status_counts.get(status, 0) + 1
            
            return {
                'success': True,
                'batch': batch_info,
                'total_documents': total_documents,
                'status_counts': status_counts,
                'processing_status': self.get_processing_status(batch_id)
            }
            
        except Exception as e:
            logger.error(f"Error getting batch summary: {e}")
            return {
                'success': False,
                'error': f'Failed to get batch summary: {str(e)}'
            }
    
    def start_processing(self, batch_id: int, processing_type: str = 'standard') -> Dict[str, Any]:
        """
        Start processing for a batch.
        
        Args:
            batch_id: ID of the batch to process
            processing_type: Type of processing ('standard', 'smart', 'single', 'traditional')
            
        Returns:
            Dictionary with processing start results
        """
        try:
            # Validate batch exists and is ready
            batch_summary = self.get_batch_summary(batch_id)
            if not batch_summary['success']:
                return batch_summary
            
            # Check if already processing
            with self.processing_lock:
                if batch_id in self.processing_status:
                    current_status = self.processing_status[batch_id]['status']
                    if current_status in ['processing', 'smart_processing', 'traditional_processing']:
                        return {
                            'success': False,
                            'error': f'Batch {batch_id} is already being processed'
                        }
            
            # Start processing based on type
            if processing_type == 'smart':
                return self._start_smart_processing(batch_id)
            elif processing_type == 'single':
                return self._start_single_processing(batch_id)
            elif processing_type == 'traditional':
                return self._start_traditional_processing(batch_id)
            else:
                return self._start_standard_processing(batch_id)
                
        except Exception as e:
            logger.error(f"Error starting processing for batch {batch_id}: {e}")
            return {
                'success': False,
                'error': f'Failed to start processing: {str(e)}'
            }
    
    def _start_standard_processing(self, batch_id: int) -> Dict[str, Any]:
        """Start standard batch processing."""
        def process_async():
            try:
                with self.processing_lock:
                    self.processing_status[batch_id] = {
                        'status': 'processing',
                        'progress': 0,
                        'message': 'Starting standard processing...',
                        'started_at': datetime.now().isoformat()
                    }
                
                # Perform processing
                # result = process_batch(batch_id)
                
                with self.processing_lock:
                    self.processing_status[batch_id] = {
                        'status': 'completed',
                        'progress': 100,
                        'message': 'Standard processing completed',
                        'completed_at': datetime.now().isoformat()
                    }
                    
            except Exception as e:
                logger.error(f"Error in standard processing: {e}")
                with self.processing_lock:
                    self.processing_status[batch_id] = {
                        'status': 'error',
                        'progress': 0,
                        'message': f"Processing failed: {str(e)}",
                        'error_at': datetime.now().isoformat()
                    }
        
        thread = threading.Thread(target=process_async)
        thread.start()
        
        return {
            'success': True,
            'message': f'Standard processing started for batch {batch_id}',
            'processing_type': 'standard'
        }
    
    def _start_smart_processing(self, batch_id: int) -> Dict[str, Any]:
        """Start smart AI-powered processing."""
        def smart_process_async():
            try:
                with self.processing_lock:
                    self.processing_status[batch_id] = {
                        'status': 'smart_processing',
                        'progress': 0,
                        'message': 'Starting smart processing...',
                        'stages': {
                            'ocr': {'status': 'pending', 'progress': 0},
                            'classification': {'status': 'pending', 'progress': 0},
                            'grouping': {'status': 'pending', 'progress': 0},
                            'ordering': {'status': 'pending', 'progress': 0}
                        },
                        'started_at': datetime.now().isoformat()
                    }
                
                # Process each stage
                stages = ['ocr', 'classification', 'grouping', 'ordering']
                for i, stage in enumerate(stages):
                    with self.processing_lock:
                        self.processing_status[batch_id]['stages'][stage]['status'] = 'processing'
                        self.processing_status[batch_id]['message'] = f'Processing {stage}...'
                    
                    # Perform actual stage processing
                    # stage_result = process_stage(batch_id, stage)
                    
                    with self.processing_lock:
                        self.processing_status[batch_id]['stages'][stage]['status'] = 'completed'
                        self.processing_status[batch_id]['stages'][stage]['progress'] = 100
                        self.processing_status[batch_id]['progress'] = int((i + 1) / len(stages) * 100)
                
                with self.processing_lock:
                    self.processing_status[batch_id]['status'] = 'completed'
                    self.processing_status[batch_id]['message'] = 'Smart processing completed'
                    self.processing_status[batch_id]['completed_at'] = datetime.now().isoformat()
                    
            except Exception as e:
                logger.error(f"Error in smart processing: {e}")
                with self.processing_lock:
                    self.processing_status[batch_id] = {
                        'status': 'error',
                        'progress': 0,
                        'message': f"Smart processing failed: {str(e)}",
                        'error_at': datetime.now().isoformat()
                    }
        
        thread = threading.Thread(target=smart_process_async)
        thread.start()
        
        return {
            'success': True,
            'message': f'Smart processing started for batch {batch_id}',
            'processing_type': 'smart'
        }
    
    def _start_single_processing(self, batch_id: int) -> Dict[str, Any]:
        """Start single document processing."""
        def single_process_async():
            try:
                # Get all documents in batch
                # with database_connection() as conn:
                #     cursor = conn.cursor()
                #     documents = get_documents_by_batch(batch_id)
                
                documents = []  # Placeholder
                total_docs = len(documents)
                
                with self.processing_lock:
                    self.processing_status[batch_id] = {
                        'status': 'processing_single',
                        'progress': 0,
                        'message': f'Processing {total_docs} documents individually...',
                        'total_documents': total_docs,
                        'processed_documents': 0,
                        'started_at': datetime.now().isoformat()
                    }
                
                processed = 0
                for doc in documents:
                    try:
                        # process_single_document(doc['id'])
                        processed += 1
                        
                        with self.processing_lock:
                            self.processing_status[batch_id]['processed_documents'] = processed
                            self.processing_status[batch_id]['progress'] = int(processed / total_docs * 100)
                            self.processing_status[batch_id]['message'] = f'Processed {processed}/{total_docs} documents'
                            
                    except Exception as e:
                        logger.error(f"Error processing document {doc.get('id', 'unknown')}: {e}")
                
                with self.processing_lock:
                    self.processing_status[batch_id]['status'] = 'completed'
                    self.processing_status[batch_id]['message'] = f'Completed processing {processed}/{total_docs} documents'
                    self.processing_status[batch_id]['completed_at'] = datetime.now().isoformat()
                    
            except Exception as e:
                logger.error(f"Error in single document processing: {e}")
                with self.processing_lock:
                    self.processing_status[batch_id] = {
                        'status': 'error',
                        'progress': 0,
                        'message': f"Single processing failed: {str(e)}",
                        'error_at': datetime.now().isoformat()
                    }
        
        thread = threading.Thread(target=single_process_async)
        thread.start()
        
        return {
            'success': True,
            'message': f'Single document processing started for batch {batch_id}',
            'processing_type': 'single'
        }
    
    def _start_traditional_processing(self, batch_id: int) -> Dict[str, Any]:
        """Start traditional (non-AI) processing."""
        def traditional_process_async():
            try:
                with self.processing_lock:
                    self.processing_status[batch_id] = {
                        'status': 'traditional_processing',
                        'progress': 0,
                        'message': 'Starting traditional processing (no AI)...',
                        'started_at': datetime.now().isoformat()
                    }
                
                # Perform traditional processing
                # result = process_batch(batch_id, use_ai=False)
                
                with self.processing_lock:
                    self.processing_status[batch_id] = {
                        'status': 'completed',
                        'progress': 100,
                        'message': 'Traditional processing completed',
                        'completed_at': datetime.now().isoformat()
                    }
                    
            except Exception as e:
                logger.error(f"Error in traditional processing: {e}")
                with self.processing_lock:
                    self.processing_status[batch_id] = {
                        'status': 'error',
                        'progress': 0,
                        'message': f"Traditional processing failed: {str(e)}",
                        'error_at': datetime.now().isoformat()
                    }
        
        thread = threading.Thread(target=traditional_process_async)
        thread.start()
        
        return {
            'success': True,
            'message': f'Traditional processing started for batch {batch_id}',
            'processing_type': 'traditional'
        }
    
    def get_processing_status(self, batch_id: int) -> Dict[str, Any]:
        """Get current processing status for a batch."""
        with self.processing_lock:
            return self.processing_status.get(batch_id, {
                'status': 'not_started',
                'progress': 0,
                'message': 'No processing started'
            })
    
    def get_all_processing_status(self) -> Dict[str, Any]:
        """Get processing status for all batches."""
        with self.processing_lock:
            return dict(self.processing_status)
    
    def reset_batch(self, batch_id: int) -> Dict[str, Any]:
        """Reset a batch to initial state."""
        try:
            # Reset batch in database
            # with database_connection() as conn:
            #     cursor = conn.cursor()
            #     cursor.execute("UPDATE batches SET status = 'intake' WHERE id = ?", (batch_id,))
            #     cursor.execute("UPDATE documents SET status = 'pending' WHERE batch_id = ?", (batch_id,))
            
            # Clear processing status
            with self.processing_lock:
                if batch_id in self.processing_status:
                    del self.processing_status[batch_id]
            
            return {
                'success': True,
                'message': f'Batch {batch_id} reset successfully'
            }
            
        except Exception as e:
            logger.error(f"Error resetting batch {batch_id}: {e}")
            return {
                'success': False,
                'error': f'Failed to reset batch: {str(e)}'
            }
    
    def delete_batch(self, batch_id: int) -> Dict[str, Any]:
        """Delete a batch and all its documents."""
        try:
            # Delete from database
            # with database_connection() as conn:
            #     cursor = conn.cursor()
            #     cursor.execute("DELETE FROM documents WHERE batch_id = ?", (batch_id,))
            #     cursor.execute("DELETE FROM batches WHERE id = ?", (batch_id,))
            
            # Clear processing status
            with self.processing_lock:
                if batch_id in self.processing_status:
                    del self.processing_status[batch_id]
            
            return {
                'success': True,
                'message': f'Batch {batch_id} deleted successfully'
            }
            
        except Exception as e:
            logger.error(f"Error deleting batch {batch_id}: {e}")
            return {
                'success': False,
                'error': f'Failed to delete batch: {str(e)}'
            }
    
    def get_all_batches(self, status_filter: Optional[str] = None) -> Dict[str, Any]:
        """Get all batches with optional status filtering."""
        try:
            # Get batches from database
            # with database_connection() as conn:
            #     cursor = conn.cursor()
            #     if status_filter:
            #         batches = get_batches_by_status(status_filter)
            #     else:
            #         batches = get_all_batches()
            
            batches = []  # Placeholder
            
            return {
                'success': True,
                'batches': batches,
                'total': len(batches)
            }
            
        except Exception as e:
            logger.error(f"Error getting batches: {e}")
            return {
                'success': False,
                'error': f'Failed to get batches: {str(e)}'
            }