"""
Flask Document Processing Application

This is the main application file for the document processing system.
The application has been refactored to use a modular Blueprint architecture
for improved maintainability and separation of concerns.

🤖 AI ASSISTANTS: See .github/copilot-instructions.md for critical setup patterns!
⚠️  Run with: cd /repo/root && ./start_app.sh (NOT python app.py!)

Key Features:
- Modular Blueprint-based architecture
- Service layer for business logic
- Comprehensive error handling
- Real-time progress tracking
- Support for multiple document formats (PDF, PNG, JPG)

Architecture:
- routes/: Blueprint modules for different functional areas
- services/: Business logic services
- utils/: Utility functions and helpers
- Original modules: database.py, processing.py, etc. (unchanged)
"""

from flask import Flask, render_template, redirect, url_for, flash
import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

# Import configuration FIRST (needed for logging setup)
from .config_manager import app_config

# Global flag to prevent duplicate logging setup
_logging_configured = False

def setup_logging():
    """Configure logging with rotation based on app config."""
    global _logging_configured

    # Prevent duplicate setup
    if _logging_configured:
        return logging.getLogger(__name__)

    # Ensure log directory exists
    log_file_path = app_config.LOG_FILE_PATH
    if not os.path.isabs(log_file_path):
        # Make relative paths relative to this file's directory
        log_file_path = os.path.join(os.path.dirname(__file__), log_file_path)

    log_dir = os.path.dirname(log_file_path)
    os.makedirs(log_dir, exist_ok=True)

    # Configure rotating file handler
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=app_config.LOG_MAX_BYTES,
        backupCount=app_config.LOG_BACKUP_COUNT
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    ))

    # Configure console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    ))

    # Get root logger
    root_logger = logging.getLogger()

    # Set log level
    log_level = getattr(logging, app_config.LOG_LEVEL.upper(), logging.INFO)
    root_logger.setLevel(log_level)

    # Clear any existing handlers to prevent duplicates
    root_logger.handlers.clear()

    # Add our handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Configure werkzeug to prevent duplicate logs
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.propagate = True  # Let root logger handle it
    werkzeug_logger.setLevel(log_level)

    # Mark as configured
    _logging_configured = True

    return logging.getLogger(__name__)

# Initialize logging FIRST, before importing modules that use logging
logger = setup_logging()
logger.info("Logging configuration initialized with rotation")

# NOW import modules that depend on logging being configured
# from .database import initialize_database  # TODO: Create this function if needed
# from .exceptions import DocumentProcessorError  # TODO: Create this if needed

# Import all Blueprint modules (AFTER logging is configured)
from .routes import intake, batch, manipulation, export, admin, api

# Import service layers
from .services.document_service import DocumentService
from .services.batch_service import BatchService
from .services.export_service import ExportService

def create_app():
    """
    Application factory pattern for creating Flask app.

    Returns:
        Flask: Configured Flask application instance
    """
    app = Flask(__name__)

    # Configure Flask app
    app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'  # TODO: Fix config access
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

    # Initialize database
    # TODO: Create initialize_database function if needed
    # try:
    #     initialize_database()
    #     logger.info("Database initialized successfully")
    # except Exception as e:
    #     logger.error(f"Failed to initialize database: {e}")
    #     # Continue anyway - some routes might still work

    # Initialize services (singleton instances)

    app.document_service = DocumentService()
    app.batch_service = BatchService()
    app.export_service = ExportService()

    # Register error handlers
    register_error_handlers(app)

    # Register Blueprint modules
    app.register_blueprint(intake.intake_bp)
    app.register_blueprint(batch.bp)
    app.register_blueprint(manipulation.bp)
    app.register_blueprint(export.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(api.bp)

    # Register core routes (home page and basic functionality)
    register_core_routes(app)
    # Run a safe startup cleanup to remove any empty processing batches left over
    # from previous runs, unless we're in FAST_TEST_MODE where tests manage DB
    # lifecycle and seeding themselves. FAST_TEST_MODE is set in tests via
    # `conftest.py` to avoid background activity interfering with test setup.
    try:
        fast_mode = os.getenv('FAST_TEST_MODE', '0').lower() in ('1', 'true', 't')
        if not fast_mode:
            from .batch_guard import cleanup_empty_processing_batches
            # Run cleanup in a background thread to avoid delaying startup; the function itself is fast.
            import threading
            def _startup_cleanup():
                try:
                    cleaned = cleanup_empty_processing_batches()
                    if cleaned:
                        logger.info(f"Startup cleanup removed empty processing batches: {cleaned}")
                except Exception as e:
                    logger.warning(f"Startup cleanup failed: {e}")
            threading.Thread(target=_startup_cleanup, daemon=True).start()
        else:
            logger.debug("FAST_TEST_MODE active: skipping startup cleanup thread")
    except Exception as e:
        logger.warning(f"Could not start batch cleanup on startup: {e}")

    logger.info("Flask application created and configured successfully")
    return app

def register_blueprints(app):
    """
    Register all Blueprint modules with the Flask app.

    Args:
        app: Flask application instance
    """
    try:
        # Register intake routes (analyze directories, file detection)
        app.register_blueprint(intake.intake_bp)
        logger.info("Registered intake routes blueprint")

        # Register batch management routes (processing, control)
        app.register_blueprint(batch.bp)
        logger.info("Registered batch management routes blueprint")

        # Register document manipulation routes (group, order, verify)
        app.register_blueprint(manipulation.bp)
        logger.info("Registered document manipulation routes blueprint")

        # Register export and finalization routes
        app.register_blueprint(export.bp)
        logger.info("Registered export routes blueprint")

        # Register admin and configuration routes
        app.register_blueprint(admin.bp)
        logger.info("Registered admin routes blueprint")

        # Register API endpoints
        app.register_blueprint(api.bp)
        logger.info("Registered API routes blueprint")

    except Exception as e:
        logger.error(f"Error registering blueprints: {e}")
        # Continue without the failed blueprint

def register_core_routes(app):
    """
    Register core application routes that don't belong to specific blueprints.

    Args:
        app: Flask application instance
    """

    @app.route("/")
    def index():
        """Home page showing system overview and quick actions."""
        try:
            # Get system status overview
            batch_service = app.batch_service
            all_batches = batch_service.get_all_batches()

            # Get recent processing status
            processing_status = batch_service.get_all_processing_status()

            # Get export status
            export_service = app.export_service
            export_status = export_service.get_all_export_status()

            return render_template('index.html',
                                 batches=all_batches.get('batches', []),
                                 processing_status=processing_status,
                                 export_status=export_status)

        except Exception as e:
            logger.error(f"Error loading home page: {e}")
            flash(f"Error loading dashboard: {str(e)}", "error")
            return render_template('index.html',
                                 batches=[],
                                 processing_status={},
                                 export_status={})

    @app.route("/health")
    def health_check():
        """Health check endpoint for monitoring."""
        try:
            # Basic health checks
            health_status = {
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'version': '2.0.0',  # Application version
                'components': {
                    'database': 'up',
                    'file_system': 'up',
                    'services': 'up'
                }
            }

            # Test database connection
            try:
                from .database import get_db_connection
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                conn.close()
                health_status['components']['database'] = 'up'
            except Exception:
                health_status['components']['database'] = 'down'
                health_status['status'] = 'degraded'

            # Test file system access
            try:
                intake_dir = app_config.INTAKE_DIR
                if intake_dir and os.path.exists(intake_dir):
                    health_status['components']['file_system'] = 'up'
                else:
                    health_status['components']['file_system'] = 'warning'
            except Exception:
                health_status['components']['file_system'] = 'down'
                health_status['status'] = 'degraded'

            return health_status, 200 if health_status['status'] == 'healthy' else 503

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {'status': 'error', 'message': str(e)}, 500

def register_error_handlers(app):
    """
    Register error handlers for common HTTP errors and application exceptions.

    Args:
        app: Flask application instance
    """

    @app.errorhandler(404)
    def not_found_error(error):
        """Handle 404 Not Found errors."""
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 Internal Server errors."""
        logger.error(f"Internal server error: {error}")
        return render_template('errors/500.html'), 500

    # TODO: Create DocumentProcessorError class
    # @app.errorhandler(DocumentProcessorError)
    # def handle_document_processor_error(error):
    #     """Handle custom application errors."""
    #     logger.error(f"Document processor error: {error}")
    #     flash(str(error), "error")
    #     return redirect(url_for('index'))

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """Handle unexpected errors."""
        logger.error(f"Unexpected error: {error}", exc_info=True)
        flash("An unexpected error occurred. Please try again.", "error")
        return redirect(url_for('index'))

# Global template filters and context processors
def register_template_helpers(app):
    """
    Register template filters and context processors.

    Args:
        app: Flask application instance
    """

    @app.template_filter('filesize')
    def filesize_filter(size_bytes):
        """Format file size in human readable format."""
        if size_bytes == 0:
            return "0 B"

        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    @app.template_filter('datetime')
    def datetime_filter(timestamp):
        """Format datetime strings."""
        if isinstance(timestamp, str):
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                return timestamp
        return str(timestamp)

    @app.context_processor
    def inject_globals():
        """Inject global variables into all templates."""
        # Database banner metadata (best-effort; tolerate failures quietly)
        db_meta = None
        # Allow operators to hide the DB banner via env var (useful for demos)
        try:
            # Default to hiding the DB banner; set SHOW_DB_BANNER=1 to enable it
            show_db_banner = os.getenv('SHOW_DB_BANNER', '0')
            if show_db_banner.lower() not in ('1', 'true', 't'):
                # Explicitly disable banner
                return {
                    'app_name': 'Document Processor',
                    'app_version': '2.0.0',
                    'current_year': datetime.now().year,
                    'db_meta': None
                }
        except Exception:
            pass
        try:
            from .config_manager import app_config as _cfg
            db_path = _cfg.DATABASE_PATH
            import os as _os
            exists = _os.path.exists(db_path)
            size = _os.path.getsize(db_path) if exists else 0
            # Minimal schema heuristic: few tables
            minimal = False
            if exists:
                try:
                    import sqlite3 as _sq
                    c = _sq.connect(db_path)
                    cur = c.cursor()
                    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
                    c.close()
                    if len(tables) < 6:
                        minimal = True
                except Exception:
                    pass
            db_meta = {'path': _os.path.abspath(db_path), 'size': size, 'minimal_schema': minimal}
            # Don't expose a banner for missing/empty DB files (avoid showing "DB: ( bytes)")
            if not db_path or size == 0:
                db_meta = None
        except Exception:
            pass
        return {
            'app_name': 'Document Processor',
            'app_version': '2.0.0',
            'current_year': datetime.now().year,
            'db_meta': db_meta
        }

# Create the Flask application instance at module level. Tests and older
# call sites import `doc_processor.app.app`, so provide that convenience.
# create_app itself will skip the startup cleanup when FAST_TEST_MODE is set
# (see create_app above), which is enabled in our pytest harness.
app = create_app()
register_template_helpers(app)

if __name__ == '__main__':
    """
    Run the application in development mode.

    For production deployment, use a WSGI server like Gunicorn:
    gunicorn -w 4 -b 0.0.0.0:5000 doc_processor.app:app
    """
    try:
        # Development server configuration
        debug_mode = getattr(app_config, 'DEBUG', False)
        host = getattr(app_config, 'HOST', '0.0.0.0')
        port = int(getattr(app_config, 'PORT', 5000))

        logger.info(f"Starting Flask development server on {host}:{port} (debug={debug_mode})")

        app.run(
            host=host,
            port=port,
            debug=debug_mode,
            threaded=True  # Enable threading for concurrent requests
        )

    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        sys.exit(1)