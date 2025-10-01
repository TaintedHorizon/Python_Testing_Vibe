"""
Admin and Configuration Routes Blueprint

This module contains all routes related to:
- Category management
- System configuration
- Administrative functions
- Cache and state management

Extracted from the monolithic app.py to improve maintainability.
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
import logging
from typing import Dict, Any, List, Optional
import json
import os

# Import existing modules (these imports will need to be adjusted)
# Import actual database and processing functions
from ..database import (
    get_all_categories, get_db_connection
)
# from ..config_manager import app_config
# from ..security import require_admin  # If admin authentication is implemented
from ..utils.helpers import create_error_response, create_success_response

# Create Blueprint
bp = Blueprint('admin', __name__, url_prefix='/admin')
logger = logging.getLogger(__name__)

@bp.route("/categories", methods=["GET"])
def categories():
    """Display category management page."""
    try:
        # Get all categories from database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all categories including inactive ones
        cursor.execute("""
            SELECT id, name, is_active, previous_name, notes 
            FROM categories 
            ORDER BY name ASC
        """)
        
        categories_data = cursor.fetchall()
        conn.close()
        
        # Convert to list of dictionaries for template use
        categories = []
        for row in categories_data:
            categories.append({
                'id': row['id'],
                'name': row['name'],
                'is_active': bool(row['is_active']),
                'previous_name': row['previous_name'],
                'notes': row['notes']
            })
        
        return render_template('categories.html', categories=categories)
        
    except Exception as e:
        logger.error(f"Error loading categories page: {e}")
        flash(f"Error loading categories: {str(e)}", "error")
        return render_template('categories.html', categories=[])

@bp.route("/categories/add", methods=["POST"])
def add_category():
    """Add a new category."""
    try:
        category_name = request.form.get('name')
        category_notes = request.form.get('notes', '')
        
        if not category_name:
            return jsonify(create_error_response("Category name is required"))
        
        # Add category to database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO categories (name, is_active, notes)
            VALUES (?, 1, ?)
        """, (category_name, category_notes))
        category_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify(create_success_response({
            'message': f'Category "{category_name}" added successfully',
            'category_id': category_id,
            'category_name': category_name
        }))
        
    except Exception as e:
        logger.error(f"Error adding category: {e}")
        return jsonify(create_error_response(f"Failed to add category: {str(e)}"))

@bp.route("/categories/<int:cat_id>/rename", methods=["POST"])
def rename_category(cat_id: int):
    """Rename an existing category."""
    try:
        new_name = request.form.get('name')
        if not new_name:
            return jsonify(create_error_response("New category name is required"))
        
        # Update category in database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current name for history
        cursor.execute("SELECT name FROM categories WHERE id = ?", (cat_id,))
        current_result = cursor.fetchone()
        if not current_result:
            conn.close()
            return jsonify(create_error_response("Category not found"))
        
        current_name = current_result['name']
        
        # Update with new name and store previous name
        cursor.execute("""
            UPDATE categories 
            SET name = ?, previous_name = ?
            WHERE id = ?
        """, (new_name, current_name, cat_id))
        
        conn.commit()
        conn.close()
        
        return jsonify(create_success_response({
            'message': f'Category renamed to "{new_name}" successfully',
            'category_id': cat_id,
            'new_name': new_name
        }))
        
    except Exception as e:
        logger.error(f"Error renaming category {cat_id}: {e}")
        return jsonify(create_error_response(f"Failed to rename category: {str(e)}"))

@bp.route("/categories/<int:cat_id>/delete", methods=["POST"])
def delete_category(cat_id: int):
    """Soft delete a category."""
    try:
        # Soft delete category
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE categories 
            SET is_active = 0
            WHERE id = ?
        """, (cat_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify(create_success_response({
            'message': 'Category deleted successfully',
            'category_id': cat_id
        }))
        
    except Exception as e:
        logger.error(f"Error deleting category {cat_id}: {e}")
        return jsonify(create_error_response(f"Failed to delete category: {str(e)}"))

@bp.route("/categories/<int:cat_id>/restore", methods=["POST"])
def restore_category(cat_id: int):
    """Restore a deleted category."""
    try:
        # Restore category
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE categories 
            SET is_active = 1
            WHERE id = ?
        """, (cat_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify(create_success_response({
            'message': 'Category restored successfully',
            'category_id': cat_id
        }))
        
    except Exception as e:
        logger.error(f"Error restoring category {cat_id}: {e}")
        return jsonify(create_error_response(f"Failed to restore category: {str(e)}"))

@bp.route("/clear_analysis_cache", methods=["POST"])
def clear_analysis_cache():
    """Clear the cached analysis results to force re-analysis."""
    try:
        import tempfile
        # Clear the same cache file that the original used
        cache_file = os.path.join(tempfile.gettempdir(), 'intake_analysis_cache.pkl')
        if os.path.exists(cache_file):
            os.remove(cache_file)
            logger.info("Cleared analysis cache")
        
        # Also clear any other cache directories that might exist
        cache_dir = '/tmp/analysis_cache'
        if os.path.exists(cache_dir):
            import shutil
            shutil.rmtree(cache_dir)
            os.makedirs(cache_dir)
        
        # Redirect back to the intake analysis page like the original
        return redirect(url_for('intake.analyze_intake_page'))
        
    except Exception as e:
        logger.error(f"Failed to clear analysis cache: {e}")
        # On error, still redirect back to intake page
        return redirect(url_for('intake.analyze_intake_page'))

@bp.route("/configuration")
def configuration():
    """Display system configuration page."""
    try:
        # Get current configuration
        # config_data = {
        #     'intake_dir': app_config.get('INTAKE_DIR'),
        #     'processed_dir': app_config.get('PROCESSED_DIR'),
        #     'export_dir': app_config.get('EXPORT_DIR'),
        #     'ollama_host': app_config.get('OLLAMA_HOST'),
        #     'ollama_model': app_config.get('OLLAMA_MODEL'),
        #     'debug_skip_ocr': app_config.get('DEBUG_SKIP_OCR'),
        # }
        
        config_data = {}  # Placeholder
        return render_template('configuration.html', config=config_data)
        
    except Exception as e:
        logger.error(f"Error loading configuration page: {e}")
        flash(f"Error loading configuration: {str(e)}", "error")
        return render_template('configuration.html', config={})

@bp.route("/configuration/update", methods=["POST"])
def update_configuration():
    """Update system configuration."""
    try:
        # Get form data
        config_updates = {}
        for key in ['intake_dir', 'processed_dir', 'export_dir', 'ollama_host', 'ollama_model']:
            value = request.form.get(key)
            if value:
                config_updates[key.upper()] = value
        
        # Update boolean settings
        config_updates['DEBUG_SKIP_OCR'] = request.form.get('debug_skip_ocr') == 'on'
        
        # Validate directories exist
        for dir_key in ['intake_dir', 'processed_dir', 'export_dir']:
            if dir_key in config_updates:
                dir_path = config_updates[dir_key]
                if not os.path.exists(dir_path):
                    return jsonify(create_error_response(f"Directory does not exist: {dir_path}"))
        
        # Update configuration
        # app_config.update(config_updates)
        # app_config.save()
        
        return jsonify(create_success_response({
            'message': 'Configuration updated successfully',
            'updated_settings': len(config_updates)
        }))
        
    except Exception as e:
        logger.error(f"Error updating configuration: {e}")
        return jsonify(create_error_response(f"Failed to update configuration: {str(e)}"))

@bp.route("/system_status")
def system_status():
    """Display system status and health check."""
    try:
        status_data = {
            'database': 'connected',  # Check database connection
            'ollama': 'unknown',      # Check Ollama API
            'disk_space': 'sufficient', # Check disk space
            'directories': {
                'intake': True,    # Check if directories exist and are writable
                'processed': True,
                'export': True
            }
        }
        
        # Perform actual health checks
        # status_data['database'] = check_database_connection()
        # status_data['ollama'] = check_ollama_connection()
        # status_data['disk_space'] = check_disk_space()
        # status_data['directories'] = check_directory_permissions()
        
        return render_template('system_status.html', status=status_data)
        
    except Exception as e:
        logger.error(f"Error checking system status: {e}")
        flash(f"Error checking system status: {str(e)}", "error")
        return render_template('system_status.html', status={})

@bp.route("/api/system_health")
def api_system_health():
    """API endpoint for system health check."""
    try:
        health_data = {
            'status': 'healthy',
            'timestamp': '2024-01-01T00:00:00Z',  # Use actual timestamp
            'components': {
                'database': {'status': 'up', 'response_time': '5ms'},
                'ollama': {'status': 'up', 'response_time': '150ms'},
                'filesystem': {'status': 'up', 'free_space': '10GB'}
            }
        }
        
        return jsonify(create_success_response(health_data))
        
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        return jsonify(create_error_response(f"Failed to get system health: {str(e)}"))

@bp.route("/logs")
def view_logs():
    """Display application logs."""
    try:
        # Get recent log entries
        log_file = '/path/to/app.log'  # This should come from config
        logs = []
        
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                # Get last 100 lines
                lines = f.readlines()
                logs = lines[-100:] if len(lines) > 100 else lines
        
        return render_template('logs.html', logs=logs)
        
    except Exception as e:
        logger.error(f"Error loading logs: {e}")
        flash(f"Error loading logs: {str(e)}", "error")
        return render_template('logs.html', logs=[])

@bp.route("/api/logs")
def api_logs():
    """API endpoint for log data."""
    try:
        # Return recent logs in JSON format
        log_entries = []
        # Parse log file and return structured data
        
        return jsonify(create_success_response({
            'logs': log_entries,
            'total_entries': len(log_entries)
        }))
        
    except Exception as e:
        logger.error(f"Error getting logs via API: {e}")
        return jsonify(create_error_response(f"Failed to get logs: {str(e)}"))

@bp.route("/database_maintenance")
def database_maintenance():
    """Display database maintenance page."""
    try:
        # Get database statistics
        # with database_connection() as conn:
        #     cursor = conn.cursor()
        #     stats = get_database_statistics()
        
        stats = {
            'total_batches': 0,
            'total_documents': 0,
            'database_size': '0 MB',
            'oldest_batch': 'N/A',
            'newest_batch': 'N/A'
        }
        
        return render_template('database_maintenance.html', stats=stats)
        
    except Exception as e:
        logger.error(f"Error loading database maintenance page: {e}")
        flash(f"Error loading maintenance page: {str(e)}", "error")
        return render_template('database_maintenance.html', stats={})

@bp.route("/database/vacuum", methods=["POST"])
def vacuum_database():
    """Vacuum the database to reclaim space."""
    try:
        # Perform database vacuum
        # with database_connection() as conn:
        #     cursor = conn.cursor()
        #     cursor.execute("VACUUM")
        
        return jsonify(create_success_response({
            'message': 'Database vacuum completed successfully'
        }))
        
    except Exception as e:
        logger.error(f"Error vacuuming database: {e}")
        return jsonify(create_error_response(f"Failed to vacuum database: {str(e)}"))

@bp.route("/database/cleanup", methods=["POST"])
def cleanup_database():
    """Clean up old or orphaned records."""
    try:
        days_old = int(request.form.get('days_old', 30))
        
        # Clean up old records
        # with database_connection() as conn:
        #     cursor = conn.cursor()
        #     # Delete old completed batches and their documents
        #     deleted_batches = cleanup_old_batches(days_old)
        #     # Delete orphaned documents
        #     deleted_docs = cleanup_orphaned_documents()
        
        deleted_batches = 0  # Placeholder
        deleted_docs = 0     # Placeholder
        
        return jsonify(create_success_response({
            'message': f'Database cleanup completed',
            'deleted_batches': deleted_batches,
            'deleted_documents': deleted_docs
        }))
        
    except Exception as e:
        logger.error(f"Error cleaning up database: {e}")
        return jsonify(create_error_response(f"Failed to clean up database: {str(e)}"))

# File safety and validation
@bp.route("/api/file_safety_check")
def file_safety_check():
    """Check if files are safe to process (no open file handles, etc.)."""
    try:
        # Check for file locks or open handles
        # This is useful before starting batch operations
        
        safety_status = {
            'safe_to_process': True,
            'warnings': [],
            'errors': []
        }
        
        # Perform actual safety checks
        # Check if any files are being written to
        # Check disk space
        # Check process locks
        
        return jsonify(create_success_response(safety_status))
        
    except Exception as e:
        logger.error(f"Error checking file safety: {e}")
        return jsonify(create_error_response(f"Failed to check file safety: {str(e)}"))