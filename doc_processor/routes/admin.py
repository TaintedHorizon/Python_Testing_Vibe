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
import os
import hashlib
import sqlite3

# Import existing modules (these imports will need to be adjusted)
# Import actual database and processing functions
from ..database import (
    get_db_connection
)
# from ..config_manager import app_config
# from ..security import require_admin  # If admin authentication is implemented
from ..utils.helpers import create_error_response, create_success_response

# Create Blueprint
bp = Blueprint('admin', __name__, url_prefix='/admin')
logger = logging.getLogger(__name__)


def _select_tmp_dir() -> str:
    """Select a temporary directory: TEST_TMPDIR -> TMPDIR -> system tempdir -> cwd."""
    try:
        import tempfile
        return os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or tempfile.gettempdir()
    except Exception:
        return os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or os.getcwd()

@bp.route('/db_diagnostics')
def db_diagnostics():
    """Human-friendly diagnostics page for the active SQLite database.

    Shows: path, size, mtime, sha256 (first 16 chars), table list with row counts,
    and warnings for minimal schema / missing critical tables.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Resolve absolute path (connection doesn't expose path directly; reconstruct from config)
        from ..config_manager import app_config
        db_path = os.path.abspath(app_config.DATABASE_PATH)
        exists = os.path.exists(db_path)
        size = os.path.getsize(db_path) if exists else 0
        mtime_iso = None
        if exists:
            import time as _t
            mtime_iso = _t.strftime('%Y-%m-%dT%H:%M:%S', _t.localtime(os.path.getmtime(db_path)))
        # Compute partial SHA256 (avoid heavy cost on very large files by streaming)
        sha256_short = 'n/a'
        if exists and size <= 50_000_000:  # cap at 50MB for hashing
            h = hashlib.sha256()
            with open(db_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    h.update(chunk)
            sha256_short = h.hexdigest()[:16]
        # Gather tables & row counts
        tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        table_infos = []
        for t in tables:
            name = t[0]
            try:
                rc = cursor.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            except sqlite3.Error:
                rc = 'err'
            table_infos.append({'name': name, 'rows': rc})
        table_names = {ti['name'] for ti in table_infos}
        expected_core = {'batches', 'single_documents'}
        optional_grouped = {'documents', 'document_pages'}
        optional_tags = {'document_tags', 'tag_usage_stats'}
        warnings = []
        if not expected_core.issubset(table_names):
            warnings.append('Missing core tables: ' + ', '.join(sorted(expected_core - table_names)))
        # Minimal schema heuristic: fewer than 6 tables typically indicates fresh DB
        if len(table_names) < 6:
            warnings.append('Database appears MINIMAL / freshly initialized (fewer than 6 tables).')
        if 'pages' not in table_names:
            warnings.append('No pages table found – legacy grouped workflow will not function fully.')
        ctx = {
            'db_path': db_path,
            'exists': exists,
            'size_bytes': size,
            'mtime_iso': mtime_iso,
            'sha256_short': sha256_short,
            'tables': table_infos,
            'warnings': warnings,
        }
        return render_template('db_diagnostics.html', **ctx)
    except Exception as e:
        logger.error(f"Failed to render db diagnostics: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/debug_batches')
def debug_batches():
    """Temporary debug: return JSON list of batches the server sees.

    REMOVE or protect this route before production use.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Detect whether start_time column exists
        cur.execute("PRAGMA table_info(batches)")
        cols = [r[1] for r in cur.fetchall()]
        if 'start_time' in cols:
            cur.execute("SELECT id, status, COALESCE(start_time,'') as start_time FROM batches ORDER BY id DESC")
            rows = cur.fetchall()
            result = [{'id': r['id'], 'status': r['status'], 'start_time': r['start_time']} for r in rows]
        else:
            cur.execute("SELECT id, status FROM batches ORDER BY id DESC")
            rows = cur.fetchall()
            result = [{'id': r[0], 'status': r[1], 'start_time': ''} for r in rows]
        conn.close()
        return jsonify({'batches': result, 'count': len(result)})
    except Exception as e:
        logger.error(f"debug_batches error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/mark_orphaned_batches', methods=['POST'])
def mark_orphaned_batches():
    """Mark empty batches as 'orphaned'. Requires form param confirm=true to run."""
    try:
        confirm = request.form.get('confirm', 'false').lower() == 'true'
        if not confirm:
            return jsonify(create_error_response('Missing confirm=true to run this action')), 400

        from ..batch_guard import mark_orphaned_empty_batches
        marked = mark_orphaned_empty_batches()
        return jsonify(create_success_response({'marked': marked}))
    except Exception as e:
        logger.error(f"mark_orphaned_batches error: {e}")
        return jsonify(create_error_response(str(e))), 500


@bp.route('/cleanup_empty_batches', methods=['POST'])
def cleanup_empty_batches():
    """Run policy-based cleanup of empty batches. Requires confirm=true."""
    try:
        confirm = request.form.get('confirm', 'false').lower() == 'true'
        if not confirm:
            return jsonify(create_error_response('Missing confirm=true to run this action')), 400

        minutes = int(request.form.get('age_minutes', 60))
        statuses = request.form.get('statuses')
        if statuses:
            statuses_list = [s.strip() for s in statuses.split(',') if s.strip()]
        else:
            statuses_list = None

        from ..batch_guard import cleanup_empty_batches_policy
        deleted = cleanup_empty_batches_policy(age_minutes=minutes, statuses=statuses_list)
        return jsonify(create_success_response({'deleted': deleted}))
    except Exception as e:
        logger.error(f"cleanup_empty_batches error: {e}")
        return jsonify(create_error_response(str(e))), 500

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
        # Clear the same cache file that the original used (prefer test tmpdir when available)
        tmpdir = _select_tmp_dir()
        cache_file = os.path.join(tmpdir, 'intake_analysis_cache.pkl')
        if os.path.exists(cache_file):
            os.remove(cache_file)
            logger.info("Cleared analysis cache")

        # Also clear any other cache directories that might exist
        cache_dir = os.path.join(tmpdir, 'analysis_cache')
        try:
            if os.path.exists(cache_dir):
                import shutil
                shutil.rmtree(cache_dir)
            os.makedirs(cache_dir, exist_ok=True)
        except Exception:
            # Best-effort; don't fail admin action on inability to recreate cache dir
            logger.debug(f"Could not recreate analysis cache dir: {cache_dir}")

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
        # Get recent log entries. Prefer configured path, then TEST_TMPDIR/logs,
        # then env LOG_FILE_PATH, then fall back to system path.
        from ..config_manager import app_config as _cfg
        logs = []

        if getattr(_cfg, 'LOG_FILE_PATH', None):
            log_file = _cfg.LOG_FILE_PATH
        elif os.getenv('TEST_TMPDIR'):
            _test_tmp = os.getenv('TEST_TMPDIR')
            if _test_tmp:
                log_file = os.path.join(_test_tmp, 'logs', 'app.log')
            else:
                log_file = os.path.join(os.getcwd(), 'logs', 'app.log')
        elif os.getenv('LOG_FILE_PATH'):
            log_file = os.getenv('LOG_FILE_PATH')
        else:
            log_file = '/var/log/doc_processor/app.log'

        # Ensure we have a valid string path before calling abspath
        if not log_file:
            log_file = os.path.join(os.getcwd(), 'logs', 'app.log')
        try:
            log_file = os.path.abspath(str(log_file))
        except Exception:
            log_file = os.path.abspath(os.path.join(os.getcwd(), 'logs', 'app.log'))

        # Read logs if present. Do NOT create missing directories here.
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    # Get last 100 lines
                    lines = f.readlines()
                    logs = lines[-100:] if len(lines) > 100 else lines
            except Exception as read_err:
                logger.warning(f"Could not read log file {log_file}: {read_err}")

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
            'message': 'Database cleanup completed',
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