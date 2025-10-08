"""
Export Service Layer

This service handles all export and finalization operations including:
- Export process orchestration
- File generation and management
- Progress tracking for exports
- Different export formats and options

Extracted from route handlers to improve separation of concerns.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
import threading
import os
import json
from datetime import datetime
from pathlib import Path

# Import modules (adjust imports as needed)
from ..database import get_db_connection, get_documents_for_batch, get_batch_by_id
from ..processing import safe_move, database_connection, _create_single_document_markdown_content
from ..config_manager import app_config

logger = logging.getLogger(__name__)

class ExportService:
    """Service class for export and finalization operations."""
    
    def __init__(self):
        self.export_status = {}
        self.export_lock = threading.Lock()
    
    def export_batch(self, batch_id: int, export_format: str = 'pdf', 
                    include_originals: bool = False, grouping_method: str = 'ai_suggested') -> Dict[str, Any]:
        """
        Export a batch in the specified format.
        
        Args:
            batch_id: ID of the batch to export
            export_format: Format for export ('pdf', 'images', 'both')
            include_originals: Whether to include original files
            grouping_method: Method for document grouping
            
        Returns:
            Dictionary with export results
        """
        try:
            # Validate batch is ready for export
            if not self._validate_batch_for_export(batch_id):
                return {
                    'success': False,
                    'error': f'Batch {batch_id} is not ready for export'
                }
            
            # Start export process
            export_id = f"{batch_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            def export_async():
                try:
                    with self.export_lock:
                        self.export_status[batch_id] = {
                            'export_id': export_id,
                            'status': 'starting',
                            'progress': 0,
                            'message': 'Preparing export...',
                            'export_format': export_format,
                            'include_originals': include_originals,
                            'started_at': datetime.now().isoformat(),
                            'files_created': [],
                            'total_size': 0
                        }
                    
                    # Get documents for export
                    # with database_connection() as conn:
                    #     documents = get_documents_by_batch(batch_id)
                    
                    documents = []  # Placeholder
                    total_docs = len(documents)
                    
                    with self.export_lock:
                        self.export_status[batch_id]['total_documents'] = total_docs
                        self.export_status[batch_id]['message'] = f'Exporting {total_docs} documents...'
                    
                    # Export based on format
                    if export_format == 'pdf':
                        result = self._export_as_pdf(batch_id, documents, grouping_method)
                    elif export_format == 'images':
                        result = self._export_as_images(batch_id, documents)
                    elif export_format == 'both':
                        result = self._export_both_formats(batch_id, documents, grouping_method)
                    else:
                        raise ValueError(f"Unsupported export format: {export_format}")
                    
                    if include_originals:
                        self._include_original_files(batch_id, result)
                    
                    # Calculate total size
                    total_size = sum(os.path.getsize(f) for f in result.get('files_created', []) if os.path.exists(f))
                    
                    with self.export_lock:
                        self.export_status[batch_id].update({
                            'status': 'completed',
                            'progress': 100,
                            'message': 'Export completed successfully',
                            'completed_at': datetime.now().isoformat(),
                            'files_created': result.get('files_created', []),
                            'total_size': total_size,
                            'download_links': self._generate_download_links(result.get('files_created', []))
                        })
                    
                except Exception as e:
                    logger.error(f"Error in export process: {e}")
                    with self.export_lock:
                        self.export_status[batch_id] = {
                            'status': 'error',
                            'progress': 0,
                            'message': f"Export failed: {str(e)}",
                            'error_at': datetime.now().isoformat()
                        }
            
            thread = threading.Thread(target=export_async)
            thread.start()
            
            return {
                'success': True,
                'export_id': export_id,
                'message': f'Export started for batch {batch_id}',
                'batch_id': batch_id
            }
            
        except Exception as e:
            logger.error(f"Error starting export for batch {batch_id}: {e}")
            return {
                'success': False,
                'error': f'Failed to start export: {str(e)}'
            }
    
    def _export_as_pdf(self, batch_id: int, documents: List[Dict], grouping_method: str) -> Dict[str, Any]:
        """Export documents as PDF files."""
        files_created = []
        
        try:
            # Group documents based on method
            if grouping_method == 'single':
                # Create individual PDFs
                for i, doc in enumerate(documents):
                    with self.export_lock:
                        self.export_status[batch_id]['progress'] = int(i / len(documents) * 100)
                        self.export_status[batch_id]['message'] = f'Creating PDF {i+1}/{len(documents)}'
                    
                    # pdf_path = create_single_document_pdf(doc)
                    pdf_path = f"/tmp/export/batch_{batch_id}_doc_{i+1}.pdf"  # Placeholder
                    files_created.append(pdf_path)
                    
            elif grouping_method == 'ai_suggested':
                # Group by AI suggestions and create multi-page PDFs
                # groups = group_documents_by_ai(documents)
                groups = [documents]  # Placeholder - single group
                
                for i, group in enumerate(groups):
                    with self.export_lock:
                        self.export_status[batch_id]['progress'] = int(i / len(groups) * 100)
                        self.export_status[batch_id]['message'] = f'Creating group PDF {i+1}/{len(groups)}'
                    
                    # pdf_path = create_grouped_pdf(group, f"Group_{i+1}")
                    pdf_path = f"/tmp/export/batch_{batch_id}_group_{i+1}.pdf"  # Placeholder
                    files_created.append(pdf_path)
                    
            elif grouping_method == 'combined':
                # Create single PDF with all documents
                with self.export_lock:
                    self.export_status[batch_id]['message'] = 'Creating combined PDF'
                
                # pdf_path = create_combined_pdf(documents, f"Batch_{batch_id}")
                pdf_path = f"/tmp/export/batch_{batch_id}_combined.pdf"  # Placeholder
                files_created.append(pdf_path)
            
            return {
                'success': True,
                'files_created': files_created,
                'format': 'pdf'
            }
            
        except Exception as e:
            logger.error(f"Error creating PDF export: {e}")
            return {
                'success': False,
                'error': f'PDF export failed: {str(e)}'
            }
    
    def _export_as_images(self, batch_id: int, documents: List[Dict]) -> Dict[str, Any]:
        """Export documents as image files."""
        files_created = []
        
        try:
            for i, doc in enumerate(documents):
                with self.export_lock:
                    self.export_status[batch_id]['progress'] = int(i / len(documents) * 100)
                    self.export_status[batch_id]['message'] = f'Exporting image {i+1}/{len(documents)}'
                
                # Copy or convert document to image
                # image_path = export_document_as_image(doc)
                image_path = f"/tmp/export/batch_{batch_id}_doc_{i+1}.png"  # Placeholder
                files_created.append(image_path)
            
            return {
                'success': True,
                'files_created': files_created,
                'format': 'images'
            }
            
        except Exception as e:
            logger.error(f"Error creating image export: {e}")
            return {
                'success': False,
                'error': f'Image export failed: {str(e)}'
            }
    
    def _export_both_formats(self, batch_id: int, documents: List[Dict], grouping_method: str) -> Dict[str, Any]:
        """Export documents in both PDF and image formats."""
        try:
            pdf_result = self._export_as_pdf(batch_id, documents, grouping_method)
            image_result = self._export_as_images(batch_id, documents)
            
            all_files = []
            if pdf_result.get('success'):
                all_files.extend(pdf_result.get('files_created', []))
            if image_result.get('success'):
                all_files.extend(image_result.get('files_created', []))
            
            return {
                'success': True,
                'files_created': all_files,
                'format': 'both',
                'pdf_files': pdf_result.get('files_created', []),
                'image_files': image_result.get('files_created', [])
            }
            
        except Exception as e:
            logger.error(f"Error creating dual format export: {e}")
            return {
                'success': False,
                'error': f'Dual format export failed: {str(e)}'
            }

    # --- Grouped Workflow Placeholder (lightweight) ---
    def export_grouped_documents(self, batch_id: int) -> Dict[str, Any]:
        """Placeholder grouped export that enumerates grouped documents and logs intent.

        This allows UI actions to call a stable endpoint even while full
        implementation (PDF assembly, metadata packaging) evolves.
        """
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            try:
                rows = cur.execute("SELECT d.id, d.document_name FROM documents d WHERE d.batch_id = ? ORDER BY d.id", (batch_id,)).fetchall()
            except Exception as e:
                return {'success': False, 'error': f'Grouped export unavailable (schema missing): {e}'}
            doc_summaries = [f"{r[0]}:{r[1]}" for r in rows]
            logger.info(f"[export] grouped export placeholder for batch {batch_id} docs={len(rows)}")
            return {'success': True, 'documents': doc_summaries, 'message': 'Grouped export placeholder'}
        except Exception as e:
            logger.error(f"Grouped export placeholder failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _include_original_files(self, batch_id: int, export_result: Dict[str, Any]) -> None:
        """Include original files in the export."""
        try:
            # Copy original files to export directory
            # original_files = get_original_files_for_batch(batch_id)
            original_files = []  # Placeholder
            
            for original_file in original_files:
                # Copy to export directory
                # destination = copy_original_file(original_file, export_dir)
                # export_result['files_created'].append(destination)
                pass
                
        except Exception as e:
            logger.error(f"Error including original files: {e}")
    
    def _generate_download_links(self, file_paths: List[str]) -> List[Dict[str, str]]:
        """Generate download links for exported files."""
        links = []
        
        for file_path in file_paths:
            if os.path.exists(file_path):
                filename = os.path.basename(file_path)
                size = os.path.getsize(file_path)
                
                links.append({
                    'filename': filename,
                    'size': size,
                    'download_url': f'/export/download/{filename}',
                    'created': datetime.fromtimestamp(os.path.getctime(file_path)).isoformat()
                })
        
        return links
    
    def finalize_batch(self, batch_id: int, finalization_type: str = 'grouped') -> Dict[str, Any]:
        """
        Finalize a batch for completion.
        
        Args:
            batch_id: ID of the batch to finalize
            finalization_type: Type of finalization ('grouped', 'single', 'combined')
            
        Returns:
            Dictionary with finalization results
        """
        try:
            def finalize_async():
                try:
                    with self.export_lock:
                        self.export_status[batch_id] = {
                            'status': 'finalizing',
                            'progress': 0,
                            'message': f'Starting {finalization_type} finalization...',
                            'finalization_type': finalization_type,
                            'started_at': datetime.now().isoformat()
                        }
                    
                    # Perform finalization based on type
                    if finalization_type == 'single':
                        result = self._finalize_as_single_documents(batch_id)
                    elif finalization_type == 'combined':
                        result = self._finalize_as_combined_document(batch_id)
                    else:  # grouped
                        result = self._finalize_as_grouped_documents(batch_id)
                    
                    # Update batch status in database
                    # with database_connection() as conn:
                    #     cursor = conn.cursor()
                    #     cursor.execute("UPDATE batches SET status = 'finalized' WHERE id = ?", (batch_id,))
                    
                    with self.export_lock:
                        self.export_status[batch_id].update({
                            'status': 'completed',
                            'progress': 100,
                            'message': 'Finalization completed successfully',
                            'completed_at': datetime.now().isoformat(),
                            'files_created': result.get('files_created', [])
                        })
                    
                except Exception as e:
                    logger.error(f"Error in finalization process: {e}")
                    with self.export_lock:
                        self.export_status[batch_id] = {
                            'status': 'error',
                            'progress': 0,
                            'message': f"Finalization failed: {str(e)}",
                            'error_at': datetime.now().isoformat()
                        }
            
            thread = threading.Thread(target=finalize_async)
            thread.start()
            
            return {
                'success': True,
                'message': f'Finalization started for batch {batch_id}',
                'finalization_type': finalization_type
            }
            
        except Exception as e:
            logger.error(f"Error starting finalization: {e}")
            return {
                'success': False,
                'error': f'Failed to start finalization: {str(e)}'
            }
    
    def _finalize_as_single_documents(self, batch_id: int) -> Dict[str, Any]:
        """Finalize each document as a separate file."""
        # Implementation for single document finalization
        return {'success': True, 'files_created': []}
    
    def _finalize_as_grouped_documents(self, batch_id: int) -> Dict[str, Any]:
        """Finalize documents grouped by AI suggestions (group = each logical document).

        For each document in `documents` table:
          - Fetch ordered pages
          - Assemble standard PDF and searchable PDF (if page images + OCR available)
          - Build enriched markdown (using unified single doc generator) combining all page OCR
        Returns list of created file paths.
        """
        files = []
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            docs = cur.execute("SELECT id, final_filename_base, document_name FROM documents WHERE batch_id = ? ORDER BY id", (batch_id,)).fetchall()
            cabinet = app_config.FILING_CABINET_DIR
            os.makedirs(cabinet, exist_ok=True)
            total = len(docs) or 1
            for idx, d in enumerate(docs):
                doc_id = d[0]
                final_base = d[1] or d[2] or f"document_{doc_id}"
                # Get pages for document
                pages = cur.execute(
                    """
                    SELECT p.id, p.processed_image_path, p.ocr_text, p.ai_suggested_category, p.ai_suggested_filename,
                           p.human_verified_category, p.rotation
                    FROM pages p
                    JOIN document_pages dp ON p.id = dp.page_id
                    WHERE dp.document_id = ?
                    ORDER BY dp.sequence ASC
                    """,
                    (doc_id,)
                ).fetchall()
                if not pages:
                    continue
                # Build PDFs
                from PIL import Image
                import fitz
                category = pages[0][5] or pages[0][3] or 'Uncategorized'
                cat_dir = os.path.join(cabinet, category.replace(' ', '_'))
                os.makedirs(cat_dir, exist_ok=True)
                standard_pdf = os.path.join(cat_dir, f"{final_base}.pdf")
                searchable_pdf = os.path.join(cat_dir, f"{final_base}_ocr.pdf")
                images = []
                for pg in pages:
                    img_path = pg[1]
                    if img_path and os.path.exists(img_path):
                        im = Image.open(img_path)
                        if im.mode != 'RGB':
                            im = im.convert('RGB')
                        images.append(im)
                if images:
                    images[0].save(standard_pdf, save_all=True, append_images=images[1:])
                    for im in images:
                        im.close()
                    files.append(standard_pdf)
                # Searchable PDF
                with fitz.open() as out_doc:
                    for pg in pages:
                        img_path = pg[1]
                        ocr_text = pg[2] or ''
                        if not img_path or not os.path.exists(img_path):
                            continue
                        with fitz.open(img_path) as img_doc:
                            rect = img_doc[0].rect
                            # Use helper from processing if available to abstract version differences
                            try:
                                from ..processing import _doc_new_page as _compat_new_page  # type: ignore
                                new_page = _compat_new_page(out_doc, width=rect.width, height=rect.height)
                            except Exception:
                                # Fallback: attempt generic new_page via getattr (satisfy differing versions)
                                try:
                                    new_page = getattr(out_doc, 'new_page')(width=rect.width, height=rect.height)  # type: ignore
                                except Exception:
                                    # Last resort: use page insertion via a rect clone (may no-op if unsupported)
                                    new_page = out_doc.insert_page(len(out_doc), width=rect.width, height=rect.height)  # type: ignore
                            new_page.insert_image(rect, filename=img_path)
                            if ocr_text:
                                new_page.insert_text((0,0), ocr_text, render_mode=3)
                    if out_doc.page_count:
                        out_doc.save(searchable_pdf, garbage=4, deflate=True)
                        files.append(searchable_pdf)
                # Markdown
                full_ocr = '\n\n---\n\n'.join([(pg[2] or '') for pg in pages])
                ai_cat = pages[0][3]
                ai_file = pages[0][4]
                verified_cat = pages[0][5]
                rotation = pages[0][6]
                md = _create_single_document_markdown_content(
                    original_filename=final_base,
                    category=category,
                    ocr_text=full_ocr,
                    ai_suggested_category=ai_cat,
                    ai_suggested_filename=ai_file,
                    final_category=verified_cat or category,
                    final_filename=final_base,
                    rotation=rotation,
                )
                md_path = os.path.join(cat_dir, f"{final_base}.md")
                with open(md_path, 'w', encoding='utf-8') as f:
                    f.write(md)
                files.append(md_path)
                # Progress update
                with self.export_lock:
                    if batch_id in self.export_status:
                        self.export_status[batch_id]['progress'] = int(((idx+1)/total)*100)
                        self.export_status[batch_id]['message'] = f"Grouped export {idx+1}/{total}"
            conn.close()
            return {'success': True, 'files_created': files}
        except Exception as e:
            logger.error(f"Grouped export failed: {e}")
            return {'success': False, 'error': str(e), 'files_created': files}
    
    def _finalize_as_combined_document(self, batch_id: int) -> Dict[str, Any]:
        """Finalize all documents as a single combined file."""
        # Implementation for combined finalization
        return {'success': True, 'files_created': []}
    
    def _validate_batch_for_export(self, batch_id: int) -> bool:
        """Validate that a batch is ready for export."""
        try:
            # Check batch status
            # with database_connection() as conn:
            #     cursor = conn.cursor()
            #     cursor.execute("SELECT status FROM batches WHERE id = ?", (batch_id,))
            #     result = cursor.fetchone()
            #     
            #     if not result:
            #         return False
            #     
            #     status = result[0]
            #     return status in ['ordered', 'ready_for_export', 'processed']
            
            return True  # Placeholder
            
        except Exception as e:
            logger.error(f"Error validating batch for export: {e}")
            return False
    
    def get_export_status(self, batch_id: int) -> Dict[str, Any]:
        """Get current export status for a batch."""
        with self.export_lock:
            return self.export_status.get(batch_id, {
                'status': 'not_started',
                'progress': 0,
                'message': 'No export started'
            })
    
    def get_all_export_status(self) -> Dict[str, Any]:
        """Get export status for all batches."""
        with self.export_lock:
            return dict(self.export_status)
    
    def reset_export_status(self, batch_id: Optional[int] = None) -> Dict[str, Any]:
        """Reset export status for a specific batch or all batches."""
        try:
            with self.export_lock:
                if batch_id:
                    if batch_id in self.export_status:
                        del self.export_status[batch_id]
                    message = f'Export status reset for batch {batch_id}'
                else:
                    self.export_status.clear()
                    message = 'Export status reset for all batches'
            
            return {
                'success': True,
                'message': message
            }
            
        except Exception as e:
            logger.error(f"Error resetting export status: {e}")
            return {
                'success': False,
                'error': f'Failed to reset export status: {str(e)}'
            }
    
    def get_available_exports(self, export_dir: Optional[str] = None) -> Dict[str, Any]:
        """Get list of available export files."""
        try:
            if not export_dir:
                # export_dir = app_config.get('EXPORT_DIR', '/tmp/exports')
                export_dir = '/tmp/exports'  # Placeholder
            
            if not os.path.exists(export_dir):
                return {'success': True, 'exports': []}
            
            exports = []
            for filename in os.listdir(export_dir):
                file_path = os.path.join(export_dir, filename)
                if os.path.isfile(file_path):
                    stat = os.stat(file_path)
                    exports.append({
                        'filename': filename,
                        'size': stat.st_size,
                        'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        'download_url': f'/export/download/{filename}'
                    })
            
            # Sort by creation date (newest first)
            exports.sort(key=lambda x: x['created'], reverse=True)
            
            return {
                'success': True,
                'exports': exports,
                'total_files': len(exports),
                'total_size': sum(export['size'] for export in exports)
            }
            
        except Exception as e:
            logger.error(f"Error getting available exports: {e}")
            return {
                'success': False,
                'error': f'Failed to get exports: {str(e)}'
            }
    
    def cleanup_old_exports(self, days_old: int = 30) -> Dict[str, Any]:
        """Clean up export files older than specified days."""
        try:
            # export_dir = app_config.get('EXPORT_DIR', '/tmp/exports')
            export_dir = '/tmp/exports'  # Placeholder
            
            if not os.path.exists(export_dir):
                return {'success': True, 'deleted_files': 0, 'freed_space': 0}
            
            cutoff_time = datetime.now().timestamp() - (days_old * 24 * 60 * 60)
            deleted_files = 0
            freed_space = 0
            
            for filename in os.listdir(export_dir):
                file_path = os.path.join(export_dir, filename)
                if os.path.isfile(file_path):
                    if os.path.getctime(file_path) < cutoff_time:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        deleted_files += 1
                        freed_space += file_size
            
            return {
                'success': True,
                'deleted_files': deleted_files,
                'freed_space': freed_space,
                'days_old': days_old
            }
            
        except Exception as e:
            logger.error(f"Error cleaning up exports: {e}")
            return {
                'success': False,
                'error': f'Failed to cleanup exports: {str(e)}'
            }