"""
Batch Routes Blueprint

This module contains all routes related to batch control, processing, and management.
Extracted from the monolithic app.py to improve maintainability.
"""
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
import logging
import os
import json
import uuid
import time
import threading

# Import existing modules (these imports will need to be adjusted based on the actual module structure)
from ..database import (
    insert_grouped_document
)
from ..database import get_db_connection
from ..batch_guard import get_or_create_intake_batch, create_new_batch
from ..processing import process_batch, database_connection
from ..config_manager import app_config
from typing import Optional
from ..utils.helpers import create_error_response, create_success_response
from ..document_detector import get_detector, DocumentAnalysis
from ..processing import _process_single_documents_as_batch_with_progress, is_image_file, _process_docs_into_fixed_batch_with_progress

# Create Blueprint
bp = Blueprint('batch', __name__, url_prefix='/batch')
logger = logging.getLogger(__name__)

# Global variables for tracking processing state (these should eventually move to a service class)
processing_status = {}
processing_lock = threading.Lock()
# In-memory token store for smart processing orchestration
smart_tokens: dict[str, dict] = {}
SMART_TOKEN_TTL_SECONDS = 3600  # 1 hour expiry
_smart_cleanup_started = False

def _start_smart_token_cleanup_thread():
    """Start background thread to purge expired smart processing tokens."""
    global _smart_cleanup_started
    if _smart_cleanup_started:
        return
    _smart_cleanup_started = True
    def _cleanup_loop():
        # Sleep in short increments but exit quickly if the app requests shutdown
        while True:
            try:
                now = time.time()
                expired = [t for t, meta in list(smart_tokens.items()) if now - meta.get('created', 0) > SMART_TOKEN_TTL_SECONDS]
                for t in expired:
                    smart_tokens.pop(t, None)
                if expired:
                    logger.info(f"[smart] Cleanup removed {len(expired)} expired tokens")
            except Exception as e:
                logger.warning(f"[smart] Token cleanup error: {e}")
            # Check shutdown event periodically (every 5 seconds x 60 = ~5 minutes)
            for _ in range(60):
                try:
                        from flask import current_app
                        try:
                            shutdown_ev = current_app.extensions.get('doc_processor', {}).get('shutdown_event')
                        except Exception:
                            shutdown_ev = None
                        if shutdown_ev and getattr(shutdown_ev, 'is_set', lambda: False)():
                            logger.info("[smart] Token cleanup thread detected shutdown event; exiting")
                            return
                except Exception:
                    # If we can't access current_app, continue sleeping
                    pass
                time.sleep(5)
    threading.Thread(target=_cleanup_loop, daemon=True, name='SmartTokenCleanup').start()


def _load_cached_intake_analyses(intake_dir: str) -> dict:
    """Attempt to load cached intake analyses from pickle, return mapping path->DocumentAnalysis."""
    import os
    import pickle
    import logging as _logging
    cache_file = "/tmp/intake_analysis_cache.pkl"
    if not os.path.exists(cache_file):
        return {}
    try:
        with open(cache_file, 'rb') as f:
            raw_list = pickle.load(f)
        converted = {}
        for item in raw_list:
            if isinstance(item, DocumentAnalysis):
                converted[item.file_path] = item
            elif isinstance(item, dict):
                # Legacy key fix: filename -> file_path
                if 'filename' in item and 'file_path' not in item:
                    item['file_path'] = os.path.join(intake_dir, item['filename'])
                    item.pop('filename', None)
                try:
                    converted[item['file_path']] = DocumentAnalysis(**item)
                except Exception as conv_e:
                    _logging.warning(f"[smart] Failed to convert cached analysis entry: {conv_e}")
        return converted
    except Exception as e:
        _logging.warning(f"[smart] Could not load cached analyses: {e}")
        return {}


def _orchestrate_smart_processing(batch_id: Optional[int], strategy_overrides: dict, token: str):
    """Generator that replicates legacy smart processing progress flow using SSE-friendly yields."""
    import os
    import logging as _logging
    from ..config_manager import app_config as _cfg

    intake_dir = _cfg.INTAKE_DIR
    logger.info(f"[smart] Orchestrator start: batch_id={batch_id} token={token} intake_dir={intake_dir}")
    yield {'message': 'Initializing smart processing...', 'progress': 0, 'total': 0}

    if not os.path.exists(intake_dir):
        yield {'error': f'Intake directory missing: {intake_dir}', 'complete': True}
        return

    supported = []
    for f in os.listdir(intake_dir):
        ext = os.path.splitext(f)[1].lower()
        if ext in ['.pdf', '.png', '.jpg', '.jpeg']:
            supported.append(os.path.join(intake_dir, f))
    total_files = len(supported)
    logger.info(f"[smart] Found {total_files} supported intake files: {supported[:10]}")
    if total_files == 0:
        yield {'message': 'No intake files found', 'progress': 0, 'total': 0, 'complete': True}
        return
    yield {'message': f'Loading analysis for {total_files} files...', 'progress': 0, 'total': total_files}

    # Load cached or fresh analysis
    analyses: list[DocumentAnalysis] = []
    cached_map = _load_cached_intake_analyses(intake_dir)
    detector = None
    for idx, path in enumerate(supported, start=1):
        fname = os.path.basename(path)
        analysis = cached_map.get(path)
        if analysis is None:
            if detector is None:
                detector = get_detector(use_llm_for_ambiguous=True)
            yield {'message': f'Analyzing: {fname}', 'progress': idx-1, 'total': total_files, 'current_file': fname}
            try:
                analysis = detector.analyze_pdf(path)
            except Exception as e:
                _logging.error(f"[smart] Analysis failed for {fname}: {e}")
                analysis = DocumentAnalysis(
                    file_path=path,
                    file_size_mb=0.0,
                    page_count=0,
                    processing_strategy='batch_scan',
                    confidence=0.0,
                    reasoning=[f'Analysis error: {e}', 'Defaulting to batch scan']
                )
        # Hard rule: raw images always treated as single_document for downstream logic
        if is_image_file(path):
            if analysis.processing_strategy != 'single_document':
                original_strategy = analysis.processing_strategy
                analysis.processing_strategy = 'single_document'
                if analysis.reasoning:
                    analysis.reasoning.append(f'Forced to single_document (image file, was {original_strategy})')
                else:
                    analysis.reasoning = [f'Forced to single_document (image file, was {original_strategy})']
        analyses.append(analysis)
        # Respect global shutdown request between heavy items
        try:
            from ..config_manager import SHUTDOWN_EVENT
            if SHUTDOWN_EVENT is not None and SHUTDOWN_EVENT.is_set():
                logger.info(f"[smart] Orchestrator detected shutdown event; aborting analysis loop at index {idx}")
                yield {'message': 'Shutdown requested', 'complete': True, 'aborted': True}
                return
        except Exception:
            pass
        yield {'message': f'Analyzed ({idx}/{total_files}): {fname}', 'progress': idx, 'total': total_files}

    # Apply overrides
    if strategy_overrides:
        changed = 0
        for a in analyses:
            fname = os.path.basename(a.file_path)
            if fname in strategy_overrides:
                new_strat = strategy_overrides[fname]
                if new_strat in ('single_document', 'batch_scan') and a.processing_strategy != new_strat:
                    orig = a.processing_strategy
                    a.processing_strategy = new_strat
                    if a.reasoning:
                        a.reasoning.append(f'User override: {orig} -> {new_strat}')
                    else:
                        a.reasoning = [f'User override: {orig} -> {new_strat}']
                    changed += 1
        yield {'message': f'Applied {changed} strategy overrides', 'progress': total_files, 'total': total_files}

    single_docs = [a for a in analyses if a.processing_strategy == 'single_document']
    batch_scans = [a for a in analyses if a.processing_strategy == 'batch_scan']
    yield {'message': f'{len(single_docs)} single docs, {len(batch_scans)} batch scans', 'progress': total_files, 'total': total_files}

    # Unified progress across both passes
    processing_total = len(single_docs) + len(batch_scans)
    processed = 0
    if processing_total == 0:
        yield {'message': 'Nothing to process after analysis', 'complete': True}
        return

    def _relay(generator, label):
        nonlocal processed
        for update in generator:
            # Cancellation check (lightweight) before yielding heavy updates
            token_meta = smart_tokens.get(token)
            if token_meta and token_meta.get('cancelled'):
                yield {'message': 'Cancellation acknowledged', 'phase': label, 'cancelled': True, 'complete': True}
                return
            if 'document_complete' in update:
                processed = update.get('documents_completed', processed + 1)
            # Map update to unified fields
            mapped = {
                'phase': label,
                'progress': processed,
                'total': processing_total,
                'message': update.get('message') or update.get('status') or update.get('error') or (
                    f"Processing {update.get('filename')}" if update.get('document_start') else None
                ),
                'current_file': update.get('filename'),
            }
            mapped.update({k: v for k, v in update.items() if k not in mapped})
            yield mapped

    single_batch_id = None
    batch_scan_batch_id = None

    # First pass: single docs
    if single_docs:
        yield {'message': f'Processing {len(single_docs)} single documents...', 'progress': processed, 'total': processing_total}
        # If caller supplied a batch_id, we should NOT put single documents into
        # that fixed batch (batch_scans are typically the 'grouped' set). Instead
        # create/reuse a processing batch for single-documents to keep them
        # separated from the supplied batch. This prevents mixed-state batches.
        if batch_id is not None:
            # Use processing guard to obtain/allocate a processing batch for singles
            from ..batch_guard import get_or_create_processing_batch
            proc_batch = get_or_create_processing_batch()
            for out in _relay(_process_docs_into_fixed_batch_with_progress(single_docs, proc_batch), 'single'):
                if 'batch_id' in out and single_batch_id is None:
                    single_batch_id = out['batch_id']
                if 'documents_completed' in out:
                    processed = out.get('documents_completed', processed + 1)
                    out['progress'] = processed
                if out.get('cancelled'):
                    yield {
                        'message': 'Smart processing cancelled (single documents phase)',
                        'progress': processed,
                        'total': processing_total,
                        'complete': True,
                        'single_batch_id': single_batch_id,
                        'batch_scan_batch_id': batch_scan_batch_id,
                        'cancelled': True
                    }
                    return
                yield out
        else:
            for out in _relay(_process_single_documents_as_batch_with_progress(single_docs), 'single'):
                if 'batch_id' in out and single_batch_id is None:
                    single_batch_id = out['batch_id']
                # Early stop if cancelled propagated
                if out.get('cancelled'):
                    yield {
                        'message': 'Smart processing cancelled (single documents phase)',
                        'progress': processed,
                        'total': processing_total,
                        'complete': True,
                        'single_batch_id': single_batch_id,
                        'batch_scan_batch_id': batch_scan_batch_id,
                        'cancelled': True
                    }
                    return
                yield out

    # Second pass: batch scans (process into the resolved batch)
    if batch_scans:
        # If no batch_id was provided by the caller but we created one during
        # the single-docs pass, reuse that batch to avoid creating duplicates.
        if batch_id is None and single_batch_id is not None:
            batch_id = single_batch_id

        # Use the resolved batch_id for batch_scans.
        batch_scan_batch_id = batch_id
        try:
            with database_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute("UPDATE batches SET status = 'processing' WHERE id = ?", (batch_scan_batch_id,))
                    conn.commit()
                except Exception as upd_err:
                    logger.debug(f"[smart] Could not mark batch {batch_scan_batch_id} as processing: {upd_err}")
        except Exception as e:
            logger.error(f"[smart] Error while updating batch status for batch_scans: {e}")

        yield {'message': f'Processing {len(batch_scans)} batch-scan documents in batch {batch_scan_batch_id}...', 'progress': processed, 'total': processing_total}
        # Ensure batch_scan_batch_id is an int; if it's None or invalid, bail out
        try:
            if batch_scan_batch_id is None:
                raise ValueError("No batch id available for batch_scan phase")
            batch_scan_bid = int(batch_scan_batch_id)
        except Exception as e:
            logger.error(f"[smart] Invalid batch id for batch_scan phase: {e}")
            yield {
                'message': 'Batch scan aborted (invalid batch id)',
                'complete': True,
                'error': str(e)
            }
            return

        for out in _relay(_process_docs_into_fixed_batch_with_progress(batch_scans, batch_scan_bid), 'batch_scan'):
                if 'documents_completed' in out:
                    processed = out['documents_completed'] + (len(single_docs) if single_docs else 0)
                    out['progress'] = processed
                if out.get('cancelled'):
                    yield {
                        'message': 'Smart processing cancelled (batch-scan phase)',
                        'progress': processed,
                        'total': processing_total,
                        'complete': True,
                        'single_batch_id': single_batch_id,
                        'batch_scan_batch_id': batch_scan_batch_id,
                        'cancelled': True
                    }
                    return
                yield out

    yield {
        'message': 'Smart processing complete',
        'progress': processing_total,
        'total': processing_total,
        'complete': True,
        'redirect': '/batch/control',
        'single_batch_id': single_batch_id,
        'batch_scan_batch_id': batch_scan_batch_id
    }


@bp.route('/api/smart_processing_progress')
def smart_processing_progress_sse():
    """SSE endpoint streaming smart processing progress based on issued token."""
    from flask import Response, stream_with_context
    token = request.args.get('token')
    if not token or token not in smart_tokens:
        return jsonify(create_error_response('Invalid or expired token'))
    meta = smart_tokens.get(token)
    if not meta:
        return jsonify(create_error_response('Token metadata unavailable (expired)'))
    # Defensive access to satisfy static analysis (meta keys validated at creation)
    batch_id = meta.get('batch_id')
    if batch_id is None:
        return jsonify(create_error_response('Token missing batch reference'))
    # Prefer a numeric batch_id when possible for typed downstream calls
    try:
        batch_id_int = int(batch_id) if not isinstance(batch_id, int) and batch_id is not None else batch_id
    except Exception:
        batch_id_int = None
    strategy_overrides = meta.get('strategy_overrides', {})

    def event_stream():
        import time as _t
        last_emit = _t.time()
        yield f"data: {json.dumps({'message':'Token accepted','progress':0,'total':0})}\n\n"
        for update in _orchestrate_smart_processing(batch_id_int if batch_id_int is not None else batch_id, strategy_overrides, token):
            yield f"data: {json.dumps(update)}\n\n"
            last_emit = _t.time()
            if update.get('complete'):
                break

            # Allow early termination if shutdown requested
            try:
                from ..config_manager import SHUTDOWN_EVENT
                if SHUTDOWN_EVENT is not None and SHUTDOWN_EVENT.is_set():
                    yield f"data: {json.dumps({'message': 'Shutdown requested by server', 'complete': True})}\n\n"
                    break
            except Exception:
                pass

            # Heartbeat if silence > 15s (rare because generator usually emits)
            if _t.time() - last_emit > 15:
                yield f"data: {json.dumps({'heartbeat': True, 'ts': _t.time()})}\n\n"
                last_emit = _t.time()

        # Cleanup token when finished or aborted
        try:
            smart_tokens.pop(token, None)
        except Exception:
            pass

    headers = {
        'Cache-Control': 'no-cache',
        'Content-Type': 'text/event-stream',
        'X-Accel-Buffering': 'no'
    }
    return Response(stream_with_context(event_stream()), headers=headers)


@bp.route('/api/debug/batch_documents/<int:batch_id>')
def api_debug_batch_documents(batch_id: int):
    """Test-only: return single_documents rows for a batch.

    This endpoint is intentionally restricted to FAST_TEST_MODE or local-only
    requests to avoid exposing internal DB structure in production.
    """
    try:
        # Allow only when tests run in FAST_TEST_MODE or from localhost
        from ..config_manager import app_config as _cfg
        if not getattr(_cfg, 'FAST_TEST_MODE', False):
            if request.remote_addr not in ('127.0.0.1', '::1', None):
                return jsonify(create_error_response('Debug API disabled')), 403

        with database_connection() as conn:
            cur = conn.cursor()
            # single_documents (preferred)
            try:
                cur.execute("SELECT id, original_filename, original_pdf_path FROM single_documents WHERE batch_id = ? ORDER BY id", (batch_id,))
                single_rows = cur.fetchall()
            except Exception:
                single_rows = []
            # grouped documents table fallback
            try:
                cur.execute("SELECT id, document_name FROM documents WHERE batch_id = ? ORDER BY id", (batch_id,))
                grouped_rows = cur.fetchall()
            except Exception:
                grouped_rows = []

        single_docs = []
        for r in single_rows:
            try:
                single_docs.append({'id': int(r[0]), 'original_filename': r[1], 'original_pdf_path': r[2]})
            except Exception:
                continue

        grouped_docs = []
        for r in grouped_rows:
            try:
                grouped_docs.append({'id': int(r[0]), 'document_name': r[1]})
            except Exception:
                continue

        return jsonify(create_success_response({'single_documents': single_docs, 'grouped_documents': grouped_docs}))
    except Exception as e:
        logger.error(f"Debug batch_documents failed: {e}")
        return jsonify(create_error_response(str(e)))


@bp.route('/api/debug/latest_document')
def api_debug_latest_document():
    """Test-only: return the latest single_documents row (id + batch_id + filename).

    This is useful for tests that start processing asynchronously and need to
    discover which batch/document was created without relying on UI links.
    Access restricted to FAST_TEST_MODE or localhost to avoid exposing internals.
    """
    try:
        from ..config_manager import app_config as _cfg
        if not getattr(_cfg, 'FAST_TEST_MODE', False):
            if request.remote_addr not in ('127.0.0.1', '::1', None):
                return jsonify(create_error_response('Debug API disabled')), 403

        with database_connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute("SELECT id, batch_id, original_filename, original_pdf_path FROM single_documents ORDER BY id DESC LIMIT 1")
                row = cur.fetchone()
            except Exception:
                row = None

        if not row:
            return jsonify(create_success_response({'latest_document': None}))

        doc = {'id': int(row[0]), 'batch_id': int(row[1]) if row[1] is not None else None, 'original_filename': row[2], 'original_pdf_path': row[3]}
        return jsonify(create_success_response({'latest_document': doc}))
    except Exception as e:
        logger.error(f"Debug latest_document failed: {e}")
        return jsonify(create_error_response(str(e)))


@bp.route('/api/debug/force_create_single_documents', methods=['POST'])
def api_debug_force_create_single_documents():
    """Test-only: create single_documents rows for given filenames in intake for a batch.

    Payload: {"batch_id": int, "filenames": ["a.pdf", ...]} - if filenames omitted, create for all files in intake.
    Restricted to FAST_TEST_MODE or localhost.
    """
    try:
        from ..config_manager import app_config as _cfg
        if not getattr(_cfg, 'FAST_TEST_MODE', False):
            if request.remote_addr not in ('127.0.0.1', '::1', None):
                return jsonify(create_error_response('Debug API disabled')), 403

        data = request.get_json(silent=True) or {}
        batch_id = data.get('batch_id')
        filenames = data.get('filenames')

        if not batch_id:
            return jsonify(create_error_response('batch_id required')), 400

        # Determine intake directory from config
        from ..config_manager import app_config as cfg
        intake_dir = getattr(cfg, 'INTAKE_DIR', None) or '/mnt/scans_intake'

        created = []
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            if filenames and isinstance(filenames, list):
                candidates = [os.path.join(intake_dir, f) for f in filenames]
            else:
                candidates = [os.path.join(intake_dir, f) for f in os.listdir(intake_dir)]
            for path in candidates:
                try:
                    if not os.path.exists(path):
                        continue
                    fname = os.path.basename(path)
                    size = os.path.getsize(path)
                    # Insert a single_documents row if not exists (by original_pdf_path)
                    cur.execute("SELECT id FROM single_documents WHERE original_pdf_path = ?", (path,))
                    if cur.fetchone():
                        continue
                    cur.execute(
                        "INSERT INTO single_documents (batch_id, original_filename, original_pdf_path, page_count, file_size_bytes, status) VALUES (?,?,?,?,?, 'completed')",
                        (batch_id, fname, path, 1, size)
                    )
                    created.append({'id': cur.lastrowid, 'original_filename': fname, 'original_pdf_path': path})
                except Exception:
                    continue
            conn.commit()
        finally:
            if conn:
                conn.close()

        return jsonify(create_success_response({'created': created}))
    except Exception as e:
        logger.error(f"force_create_single_documents failed: {e}")
        return jsonify(create_error_response(str(e))), 500

@bp.route('/admin/cleanup_empty_processing_batches', methods=['POST'])
def admin_cleanup_empty_processing_batches():
    """Admin-only endpoint to cleanup empty processing batches.

    Returns the list of cleaned batch IDs.
    """
    # For safety, allow only local requests in this dev environment
    if request.remote_addr not in ('127.0.0.1', '::1', None):
        return jsonify(create_error_response('Not allowed from remote hosts')), 403
    try:
        from ..batch_guard import cleanup_empty_processing_batches
        cleaned = cleanup_empty_processing_batches()
        return jsonify(create_success_response({'cleaned_batches': cleaned}))
    except Exception as e:
        logger.error(f"cleanup_empty_processing_batches failed: {e}")
        return jsonify(create_error_response(str(e))), 500

@bp.route('/api/smart_processing_cancel', methods=['POST'])
def smart_processing_cancel():
    """Allow client to request cancellation of an in-flight smart processing run."""
    data = request.get_json(silent=True) or {}
    token = data.get('token') or request.form.get('token')
    if not token or token not in smart_tokens:
        return jsonify(create_error_response('Invalid or expired token'))
    smart_tokens[token]['cancelled'] = True
    logger.info(f"[smart] Cancellation requested for token {token}")
    return jsonify(create_success_response({'message': 'Cancellation requested', 'token': token}))
export_status = {}
export_lock = threading.Lock()

@bp.route("/control")
def batch_control():
    """Main batch control page showing all batches and their status."""
    try:
        with database_connection() as conn:
            cursor = conn.cursor()
            # Some schemas (older/minimal) do not have a start_time column; build a resilient query.
            # Attempt to detect start_time, otherwise synthesize a timestamp via rowid ordering.
            cursor.execute("PRAGMA table_info(batches)")
            batch_cols = [r[1] for r in cursor.fetchall()]
            has_start_time = 'start_time' in batch_cols
            time_select = 'b.start_time' if has_start_time else 'NULL as start_time'
            time_group = ', b.start_time' if has_start_time else ''
            time_order = 'b.start_time DESC' if has_start_time else 'b.id DESC'
            query = f"""
                SELECT b.id, b.status, {time_select},
                       COUNT(d.id) as document_count,
                       SUM(CASE WHEN d.status = 'completed' THEN 1 ELSE 0 END) as completed_count
                FROM batches b
                LEFT JOIN documents d ON b.id = d.batch_id
                GROUP BY b.id, b.status{time_group}
                ORDER BY {time_order}
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            batches = []
            for row in rows:
                batch_id, status, start_time, doc_count, completed_count = row
                # Derive progress
                progress_percent = (completed_count / doc_count * 100) if doc_count else 0
                batches.append({
                    'id': batch_id,
                    'name': f'Batch {batch_id}',
                    'status': status,
                    'start_time': start_time,
                    'created_at': start_time,
                    'document_count': doc_count,
                    'completed_count': completed_count,
                    'progress_percent': progress_percent,
                    # Placeholders for grouped workflow counts (hydrated later if needed)
                    'ungrouped_count': None,
                    'flagged_count': 0,
                    'audit_url': url_for('batch.batch_audit', batch_id=batch_id)
                })
            return render_template('batch_control.html', batches=batches)

    except Exception as e:
        logger.error(f"Error loading batch control page: {e}")
        flash(f"Error loading batches: {str(e)}", "error")
        return render_template('batch_control.html', batches=[])

@bp.route("/process_new", methods=["POST"])
def process_new_batch():
    """Create and process a new batch from intake directory."""
    try:
        intake_dir = app_config.INTAKE_DIR
        if not intake_dir or not os.path.exists(intake_dir):
            return jsonify(create_error_response("Intake directory not configured or doesn't exist"))

        # Create new batch
        # Create new intake batch via helper to centralize INSERT semantics
        batch_id = create_new_batch('intake')

        # Start processing in background
        def process_batch_async():
            try:
                with processing_lock:
                    processing_status[batch_id] = {
                        'status': 'processing',
                        'progress': 0,
                        'message': 'Starting batch processing...'
                    }

                # Process the batch
                result = process_batch()

                with processing_lock:
                    if result:
                        processing_status[batch_id] = {
                            'status': 'completed',
                            'progress': 100,
                            'message': 'Batch processing completed successfully'
                        }
                    else:
                        processing_status[batch_id] = {
                            'status': 'error',
                            'progress': 0,
                            'message': 'Batch processing failed'
                        }

            except Exception as e:
                logger.error(f"Error in async batch processing: {e}")
                with processing_lock:
                    processing_status[batch_id] = {
                        'status': 'error',
                        'progress': 0,
                        'message': f"Processing error: {str(e)}"
                    }

        thread = threading.Thread(target=process_batch_async)
        thread.start()

        return jsonify(create_success_response({
            'batch_id': batch_id,
            'message': f'Batch {batch_id} created and processing started'
        }))

    except Exception as e:
        logger.error(f"Error creating new batch: {e}")
        return jsonify(create_error_response(f"Failed to create batch: {str(e)}"))

@bp.route('/start_new', methods=['POST'])
def start_new_batch():
    """Lightweight batch creation endpoint for UI 'Start New Batch' button.

    Creates a batch with status 'intake' (or 'ready' if you prefer immediate processing later)
    and redirects back to control page. Avoids triggering processing automatically to let
    user choose smart vs traditional.
    """
    try:
        # Use centralized batch creation to avoid duplicate insert logic
        try:
            new_id = create_new_batch('intake')
        except Exception as e:
            logger.error(f"start_new_batch: failed to create batch via helper: {e}")
            # As a resilient fallback, try get_or_create_intake_batch which may reuse existing intake
            try:
                new_id = get_or_create_intake_batch()
            except Exception:
                # Final fallback: try a raw insert but keep it minimal and logged
                with database_connection() as conn:
                    cursor = conn.cursor()
                    try:
                        cursor.execute("INSERT INTO batches (status) VALUES ('intake')")
                        conn.commit()
                        new_id = cursor.lastrowid
                    except Exception as raw_e:
                        logger.error(f"start_new_batch: raw fallback insert failed: {raw_e}")
                        new_id = None
        flash(f"Created Batch {new_id}", 'success')
    except Exception as e:
        logger.error(f"start_new_batch failed: {e}")
        flash(f"Failed to create batch: {e}", 'error')
    return redirect(url_for('batch.batch_control'))

@bp.route('/dev/simulate_grouped/<int:batch_id>', methods=['POST'])
def dev_simulate_grouped(batch_id: int):
    """Dev-only helper: create a fake grouped document with up to first 3 page ids in batch.

    Safe no-op if pages table unavailable. Not for production use.
    """
    # Allow simulation only when debugging explicitly enabled via environment flag
    if not (os.getenv('FLASK_DEBUG') == '1' or os.getenv('APP_DEBUG') == '1'):
        flash('Simulation disabled (set FLASK_DEBUG=1 to enable)', 'warning')
        return redirect(url_for('batch.batch_control'))
    try:
        with database_connection() as conn:
            cur = conn.cursor()
            try:
                pids = [r[0] for r in cur.execute("SELECT id FROM pages WHERE batch_id = ? ORDER BY id LIMIT 3", (batch_id,)).fetchall()]
            except Exception:
                pids = []
        if pids:
            insert_grouped_document(batch_id, f"SimDoc_{batch_id}_{int(time.time())}", pids)
            flash(f"Created simulated grouped document with {len(pids)} page(s)", 'success')
        else:
            flash('No pages available to simulate grouped document', 'info')
    except Exception as e:
        logger.error(f"simulate_grouped failed: {e}")
        flash(f"Simulation error: {e}", 'error')
    return redirect(url_for('batch.batch_control'))

@bp.route("/process_smart", methods=["POST"])
def process_batch_smart():
    """Start smart processing for a batch."""
    try:
        # Accept both JSON and form submissions; avoid forcing JSON content-type
        data = request.get_json(silent=True) or {}
        batch_id = data.get('batch_id') or request.form.get('batch_id')
        raw_overrides = data.get('strategy_overrides') or request.form.get('strategy_overrides')

        # If no batch_id supplied, attempt to reuse an existing intake/ready batch or create one
        if not batch_id:
            try:
                batch_id = get_or_create_intake_batch()
                logger.info(f"[smart] Using intake batch {batch_id} (auto-created or reused)")
            except Exception as e:
                logger.error(f"Failed to auto-create or reuse batch for smart processing: {e}")
                return jsonify(create_error_response(f"Could not create or reuse batch: {e}"))

        # Attempt to parse strategy overrides if present (JSON string in form submission)
        strategy_overrides = {}
        if raw_overrides:
            try:
                if isinstance(raw_overrides, str):
                    strategy_overrides = json.loads(raw_overrides)
                elif isinstance(raw_overrides, dict):
                    strategy_overrides = raw_overrides
            except Exception as e:
                logger.warning(f"Invalid strategy_overrides payload ignored: {e}")
        if strategy_overrides:
            logger.info(f"[smart] Received {len(strategy_overrides)} strategy overrides for batch {batch_id}")

        # Validate batch exists (after auto-create logic, so should exist)
        with database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM batches WHERE id = ?", (batch_id,))
            result = cursor.fetchone()
            if not result:
                # Extremely unlikely if auto-create succeeded; treat as recoverable by creating again
                try:
                    batch_id = create_new_batch('intake')
                    logger.warning(f"[smart] Batch vanished; re-created as {batch_id}")
                    cursor.execute("UPDATE batches SET status = 'ready' WHERE id = ?", (batch_id,))
                    try:
                        conn.commit()
                    except Exception:
                        # best-effort commit; if it fails the caller will handle
                        pass
                except Exception:
                    try:
                        # Try the intake guard to reuse any existing intake batch first
                        batch_id = get_or_create_intake_batch()
                        logger.warning(f"[smart] Batch vanished; get_or_create returned {batch_id}")
                        cursor.execute("UPDATE batches SET status = 'ready' WHERE id = ?", (batch_id,))
                        try:
                            conn.commit()
                        except Exception:
                            pass
                    except Exception:
                        try:
                            # Final raw fallback
                            cursor.execute("INSERT INTO batches (status) VALUES ('intake')")
                            conn.commit()
                            batch_id = cursor.lastrowid
                            logger.warning(f"[smart] Batch vanished; re-created as {batch_id} (raw fallback)")
                            cursor.execute("UPDATE batches SET status = 'ready' WHERE id = ?", (batch_id,))
                            try:
                                conn.commit()
                            except Exception:
                                pass
                        except Exception as re_e3:
                            return jsonify(create_error_response(f"Batch not found and re-create failed: {re_e3}"))
            else:
                if result[0] not in ['ready', 'processed', 'intake']:
                    return jsonify(create_error_response(f"Batch is not ready for smart processing (status: {result[0]})"))
                if result[0] == 'intake':
                    try:
                        cursor.execute("UPDATE batches SET status = 'ready' WHERE id = ?", (batch_id,))
                        try:
                            conn.commit()
                        except Exception:
                            pass
                        logger.info(f"[smart] Elevated batch {batch_id} status from 'intake' to 'ready'")
                    except Exception as e:
                        logger.warning(f"Failed to update batch status to ready: {e}")

        # Instead of starting processing here, create a token & stash parameters for SSE orchestrator
        # Persist per-document strategies if documents already exist for this batch (best-effort)
        if strategy_overrides:
            try:
                with database_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id, original_filename FROM documents WHERE batch_id = ?", (batch_id,))
                    rows = cursor.fetchall()
                    name_to_id = {r[1]: r[0] for r in rows if r[1]}
                    applied = 0
                    for fname, strat in strategy_overrides.items():
                        if strat in ('single_document', 'batch_scan') and fname in name_to_id:
                            try:
                                cursor.execute("UPDATE documents SET processing_strategy = ? WHERE id = ?", (strat, name_to_id[fname]))
                                applied += 1
                            except Exception as ue:
                                logger.warning(f"[smart] Failed to persist strategy override for {fname}: {ue}")
                    conn.commit()
                    if applied:
                        logger.info(f"[smart] Persisted {applied} strategy overrides to documents table for batch {batch_id}")
            except Exception as persist_e:
                logger.warning(f"[smart] Strategy persistence skipped: {persist_e}")
        token = uuid.uuid4().hex
        smart_tokens[token] = {
            'created': time.time(),
            'batch_id': batch_id,
            'strategy_overrides': strategy_overrides or {},
        }
        # Lightweight cleanup of expired tokens
        now = time.time()
        expired = [t for t, meta in smart_tokens.items() if now - meta.get('created', 0) > SMART_TOKEN_TTL_SECONDS]
        for t in expired:
            smart_tokens.pop(t, None)
        logger.info(f"[smart] Issued token {token} for batch {batch_id} with {len(strategy_overrides)} overrides (expired cleaned: {len(expired)})")

        # Optional: allow API callers to request immediate processing without
        # establishing an SSE connection (useful for scripted or UI-less runs).
        # Default to starting processing immediately when called from UI
        # unless caller explicitly sets start_immediately=false.
        start_now = True
        if isinstance(data, dict) and ('start_immediately' in data):
            start_now = bool(data.get('start_immediately'))
        if start_now:
            def _run_now(tok: str):
                try:
                    logger.info(f"[smart] Immediate run thread starting for token {tok}")
                    # Ensure batch_id is an int for the orchestrator
                    # Safely coerce batch_id to int if possible; preserve None and non-int values
                    try:
                        if isinstance(batch_id, int):
                            bid = batch_id
                        elif batch_id is None:
                            bid = None
                        else:
                            bid = int(batch_id)
                    except Exception:
                        bid = batch_id
                    from typing import cast
                    for _ in _orchestrate_smart_processing(cast('Optional[int]', bid), strategy_overrides or {}, tok):
                        # consume generator to drive processing; we don't need to stream
                        # results here, just ensure it runs to completion.
                        pass
                    logger.info(f"[smart] Immediate run thread completed for token {tok}")
                except Exception as e:
                    logger.error(f"[smart] Immediate run failed for token {tok}: {e}")
                finally:
                    # Best-effort cleanup of token
                    try:
                        smart_tokens.pop(tok, None)
                    except Exception:
                        pass

            threading.Thread(target=_run_now, args=(token,), daemon=True, name=f"SmartRun-{token[:6]}").start()
        return jsonify(create_success_response({
            'message': 'Smart processing token issued',
            'batch_id': batch_id,
            'token': token,
            'strategy_overrides_count': len(strategy_overrides)
        }))

    except Exception as e:
        logger.error(f"Error starting smart processing: {e}")
        return jsonify(create_error_response(f"Failed to start smart processing: {str(e)}"))

@bp.route("/process_all_single", methods=["POST"])
def process_batch_all_single():
    """Process all documents in a batch as single-page documents."""
    try:
        batch_id = request.json.get('batch_id') if request.json else None
        if not batch_id:
            return jsonify(create_error_response("Batch ID is required"))

        # Start single document processing
        def process_single_async():
            try:
                with processing_lock:
                    processing_status[batch_id] = {
                        'status': 'processing_single',
                        'progress': 0,
                        'message': 'Processing as single documents...'
                    }

                # Get all documents in batch
                with database_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM documents WHERE batch_id = ?", (batch_id,))
                    document_ids = [row[0] for row in cursor.fetchall()]

                total_docs = len(document_ids)
                processed = 0

                for doc_id in document_ids:
                    try:
                        # TODO: Fix this function call - process_single_document needs correct implementation
                        # process_single_document(doc_id)
                        processed += 1

                        with processing_lock:
                            processing_status[batch_id]['progress'] = int(processed / total_docs * 100)
                            processing_status[batch_id]['message'] = f'Processed {processed}/{total_docs} documents'

                    except Exception as e:
                        logger.error(f"Error processing document {doc_id}: {e}")

                with processing_lock:
                    processing_status[batch_id] = {
                        'status': 'completed',
                        'progress': 100,
                        'message': f'Completed processing {processed}/{total_docs} documents'
                    }

            except Exception as e:
                logger.error(f"Error in single document processing: {e}")
                with processing_lock:
                    processing_status[batch_id] = {
                        'status': 'error',
                        'progress': 0,
                        'message': f"Processing error: {str(e)}"
                    }

        thread = threading.Thread(target=process_single_async)
        thread.start()

        return jsonify(create_success_response({
            'message': 'Single document processing started',
            'batch_id': batch_id
        }))

    except Exception as e:
        logger.error(f"Error starting single document processing: {e}")
        return jsonify(create_error_response(f"Failed to start processing: {str(e)}"))

@bp.route("/force_traditional", methods=["POST"])
def process_batch_force_traditional():
    """Force traditional (non-smart) processing for a batch."""
    try:
        batch_id = request.json.get('batch_id') if request.json else None
        if not batch_id:
            return jsonify(create_error_response("Batch ID is required"))

        # Start traditional processing
        def traditional_process_async():
            try:
                with processing_lock:
                    processing_status[batch_id] = {
                        'status': 'traditional_processing',
                        'progress': 0,
                        'message': 'Starting traditional processing...'
                    }

                # Process with traditional methods (no AI)
                result = process_batch()

                with processing_lock:
                    if result:
                        processing_status[batch_id] = {
                            'status': 'completed',
                            'progress': 100,
                            'message': 'Traditional processing completed'
                        }
                    else:
                        processing_status[batch_id] = {
                            'status': 'error',
                            'progress': 0,
                            'message': 'Traditional processing failed'
                        }

            except Exception as e:
                logger.error(f"Error in traditional processing: {e}")
                with processing_lock:
                    processing_status[batch_id] = {
                        'status': 'error',
                        'progress': 0,
                        'message': f"Processing error: {str(e)}"
                    }

        thread = threading.Thread(target=traditional_process_async)
        thread.start()

        return jsonify(create_success_response({
            'message': 'Traditional processing started',
            'batch_id': batch_id
        }))

    except Exception as e:
        logger.error(f"Error starting traditional processing: {e}")
        return jsonify(create_error_response(f"Failed to start processing: {str(e)}"))

@bp.route("/<int:batch_id>/reset", methods=["POST"])
def reset_batch(batch_id: int):
    """Reset a batch to initial state."""
    try:
        with database_connection() as conn:
            cursor = conn.cursor()

            # Reset batch status
            cursor.execute("UPDATE batches SET status = 'intake' WHERE id = ?", (batch_id,))

            # Reset all documents in batch
            cursor.execute("UPDATE documents SET status = 'pending' WHERE batch_id = ?", (batch_id,))

            # Clear any processing status
            with processing_lock:
                if batch_id in processing_status:
                    del processing_status[batch_id]

        return jsonify(create_success_response({
            'message': f'Batch {batch_id} has been reset',
            'batch_id': batch_id
        }))

    except Exception as e:
        logger.error(f"Error resetting batch {batch_id}: {e}")
        return jsonify(create_error_response(f"Failed to reset batch: {str(e)}"))

@bp.route("/<int:batch_id>/reset_grouping", methods=["POST"])
def reset_grouping(batch_id: int):
    """Reset grouping for a batch."""
    try:
        with database_connection() as conn:
            cursor = conn.cursor()

            # Reset grouping information
            cursor.execute("""
                UPDATE documents
                SET group_id = NULL, group_position = NULL
                WHERE batch_id = ?
            """, (batch_id,))

            # Update batch status if needed
            cursor.execute("UPDATE batches SET status = 'processed' WHERE id = ?", (batch_id,))

        return jsonify(create_success_response({
            'message': f'Grouping reset for batch {batch_id}',
            'batch_id': batch_id
        }))

    except Exception as e:
        logger.error(f"Error resetting grouping for batch {batch_id}: {e}")
        return jsonify(create_error_response(f"Failed to reset grouping: {str(e)}"))

@bp.route("/<int:batch_id>/audit")
def batch_audit(batch_id: int):
    """Display audit information for a batch."""
    try:
        with database_connection() as conn:
            cursor = conn.cursor()

            # Get batch info
            cursor.execute("SELECT * FROM batches WHERE id = ?", (batch_id,))
            batch = cursor.fetchone()

            if not batch:
                flash("Batch not found", "error")
                return redirect(url_for('batch.batch_control'))

            # Get detailed document information
            cursor.execute("""
                SELECT id, filename, status, category, confidence_score,
                       ocr_text, created_at, updated_at
                FROM documents
                WHERE batch_id = ?
                ORDER BY id
            """, (batch_id,))

            documents = cursor.fetchall()

            # Get processing statistics
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM documents
                WHERE batch_id = ?
                GROUP BY status
            """, (batch_id,))

            status_counts = dict(cursor.fetchall())

            return render_template('batch_audit.html',
                                 batch=batch,
                                 documents=documents,
                                 status_counts=status_counts)

    except Exception as e:
        logger.error(f"Error loading batch audit for {batch_id}: {e}")
        flash(f"Error loading audit: {str(e)}", "error")
        return redirect(url_for('batch.batch_control'))

# Progress tracking routes
@bp.route("/processing_progress")
def batch_processing_progress():
    """Page to display batch processing progress."""
    return render_template('batch_processing_progress.html')

@bp.route("/api/processing_progress")
def api_batch_processing_progress():
    """API endpoint for batch processing progress."""
    try:
        with processing_lock:
            return jsonify(create_success_response(processing_status))
    except Exception as e:
        logger.error(f"Error getting processing progress: {e}")
        return jsonify(create_error_response(f"Failed to get progress: {str(e)}"))

@bp.route("/smart_processing_progress")
def smart_processing_progress():
    """Page to display smart processing progress."""
    return render_template('smart_processing_progress.html')

@bp.route("/api/smart_processing_progress")
def api_smart_processing_progress():
    """API endpoint for smart processing progress."""
    try:
        with processing_lock:
            smart_status = {k: v for k, v in processing_status.items()
                          if v.get('status') == 'smart_processing'}
            return jsonify(create_success_response(smart_status))
    except Exception as e:
        logger.error(f"Error getting smart processing progress: {e}")
        return jsonify(create_error_response(f"Failed to get progress: {str(e)}"))