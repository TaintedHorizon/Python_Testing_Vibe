"""
This module is the central hub of the document processing web application.
It uses the Flask web framework to create a user interface for a multi-stage
document processing pipeline. The application is designed to guide a user
through a series of steps to take a batch of raw documents (e.g., scans)
and turn them into organized, categorized, and named files.

The pipeline consists of the following major stages, each managed by
one or more routes in this file:

1.  **Batch Processing**: A user initiates the processing of a new batch of
    documents from a predefined source directory. The `processing.py` module
    handles the heavy lifting of OCR, image conversion, and initial AI-based
    categorization.

2.  **Verification**: The user manually reviews each page of the batch. They can
    correct the AI's suggested category, rotate pages, or flag pages that
    require special attention. This is the primary quality control step.

3.  **Review**: A dedicated interface to handle only the "flagged" pages. This
    allows for focused problem-solving on pages that were unclear or had
    issues during verification.

4.  **Grouping**: After all pages are verified, the user groups them into logical
    documents. For example, a 5-page document would be created by grouping five
    individual verified pages.

5.  **Ordering**: For documents with more than one page, the user can specify the
    correct page order. An AI suggestion is available to speed up this process.

6.  **Finalization & Export**: The final step where the user gives each document a
    meaningful filename (with AI suggestions) and exports them. The application
    creates final PDF files (both with and without OCR text layers) and a log
    file, organizing them into a "filing cabinet" directory structure based on
    their category.

This module ties together the database interactions (from `database.py`) and
the core processing logic (from `processing.py`) to create a cohesive user
experience.
"""
# Standard library imports
import os

# Third-party imports
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    send_from_directory,
    jsonify,
    abort,
)

# Local application imports
# These imports bring in the core business logic and database functions
# from other modules in the application.
from processing import (
    process_batch,
    rerun_ocr_on_page,
    BROAD_CATEGORIES,
    get_ai_suggested_order,
    get_ai_suggested_filename,
    export_document,
    cleanup_batch_files,
)
from database import (
    get_pages_for_batch,
    update_page_data,
    get_flagged_pages_for_batch,
    delete_page_by_id,
    get_all_unique_categories,
    get_verified_pages_for_grouping,
    create_document_and_link_pages,
    get_created_documents_for_batch,
    get_batch_by_id,
    count_flagged_pages_for_batch,
    get_db_connection,
    count_ungrouped_verified_pages,
    reset_batch_grouping,
    get_documents_for_batch,
    get_pages_for_document,
    update_page_sequence,
    update_document_status,
    reset_batch_to_start,
    update_document_final_filename,
)

# Initialize the Flask application
# This is the core object that handles web requests and responses.
app = Flask(__name__)

# Set a secret key for session management. This is crucial for security and for
# features like flashed messages that persist across requests.
# os.urandom(24) generates a secure, random key each time the app starts,
# making it difficult to predict and exploit session data.
app.secret_key = os.urandom(24)


# --- CORE NAVIGATION AND WORKFLOW ROUTES ---
# These routes define the main pages and initial actions a user takes.

@app.route("/")
def index():
    """
    The root URL of the application.
    Its only job is to redirect the user to the main "Mission Control" page,
    which serves as the application's home screen.
    """
    return redirect(url_for("mission_control_page"))


@app.route("/process_new_batch", methods=["POST"])
def handle_batch_processing():
    """
    Handles the POST request to start processing a new batch of documents.
    This is triggered by a button on the Mission Control page. It calls the
    main processing function from `processing.py` and then redirects the user
    back to Mission Control to see the newly created batch.
    """
    # The core logic for OCR, image conversion, and AI analysis is encapsulated
    # in the `process_batch` function to keep the Flask app focused on handling
    # web requests and orchestrating the workflow.
    process_batch()
    # After processing, a redirect forces a page refresh, so the user sees
    # the new batch in the list on the Mission Control page.
    return redirect(url_for("mission_control_page"))


@app.route("/mission_control")
def mission_control_page():
    """
    Displays the main dashboard, showing a list of all processed batches.
    For each batch, it fetches and displays key statistics like the number of
    flagged pages and ungrouped verified pages, giving the user a quick
    overview of the work that needs to be done.
    """
    # A new database connection is opened for each request to ensure thread safety
    # and proper connection management.
    conn = get_db_connection()
    # Fetches all batches, ordered by ID descending to show the most recent first.
    all_batches_raw = conn.execute("SELECT * FROM batches ORDER BY id DESC").fetchall()
    conn.close()

    # The data from the database is raw. This loop enriches it with additional
    # information needed for the user interface.
    all_batches = []
    for batch in all_batches_raw:
        batch_dict = dict(batch)  # Convert the database row to a dictionary
        batch_id = batch_dict["id"]
        # Augment the batch data with counts that indicate the status of the
        # verification and grouping stages. This avoids complex queries and
        # keeps the initial fetch fast.
        batch_dict["flagged_count"] = count_flagged_pages_for_batch(batch_id)
        batch_dict["ungrouped_count"] = count_ungrouped_verified_pages(batch_id)
        all_batches.append(batch_dict)

    # Render the main dashboard template, passing the prepared list of batches
    # to be displayed in a table.
    return render_template("mission_control.html", batches=all_batches)


# --- DIRECT ACTION ROUTES (Accessed from Mission Control) ---
# These routes correspond to the primary actions a user can take on a batch
# from the main dashboard.

@app.route("/verify/<int:batch_id>")
def verify_batch_page(batch_id):
    """
    The first step in the manual workflow: page-by-page verification.
    This page allows the user to review each page of a batch, correct the
    AI-suggested category, set the correct rotation, and flag pages for
    later, more detailed review.
    """
    # Check the batch status. If verification is already complete, the user
    # should not be able to re-verify. Instead, they are sent to a read-only
    # "revisit" page to prevent accidental changes.
    batch = get_batch_by_id(batch_id)
    if batch and batch["status"] != "pending_verification":
        return redirect(url_for("revisit_batch_page", batch_id=batch_id))

    # Fetch all pages associated with this batch from the database.
    pages = get_pages_for_batch(batch_id)
    if not pages:
        # If a batch has no pages, there's nothing to verify. Redirect back
        # to Mission Control with a message.
        return redirect(
            url_for(
                "mission_control_page", message=f"No pages found for Batch #{batch_id}."
            )
        )

    # The application stores absolute paths to images. For security and
    # portability, we create relative paths to be used in the HTML `src`
    # attribute. This is handled by the `serve_processed_file` route.
    processed_dir = os.getenv("PROCESSED_DIR")
    pages_with_relative_paths = [
        dict(
            p,
            relative_image_path=os.path.relpath(
                p["processed_image_path"], processed_dir
            ),
        )
        for p in pages
    ]

    # Simple pagination is implemented to show one page at a time. The current
    # page number is taken from the URL query parameters (e.g., ?page=2).
    page_num = request.args.get("page", 1, type=int)
    if not 1 <= page_num <= len(pages_with_relative_paths):
        page_num = 1  # Default to the first page if the page number is invalid.
    current_page = pages_with_relative_paths[page_num - 1]

    # To provide a comprehensive list of categories in the dropdown, we combine
    # a predefined list of broad categories with all categories that have been
    # previously used and saved in the database. This allows for consistency
    # and the ability to introduce new categories organically.
    db_categories = get_all_unique_categories()
    combined_categories = sorted(list(set(BROAD_CATEGORIES + db_categories)))

    # Render the verification template, passing all the necessary data for
    # displaying the current page, pagination controls, and category options.
    return render_template(
        "verify.html",
        batch_id=batch_id,
        current_page=current_page,
        current_page_num=page_num,
        total_pages=len(pages_with_relative_paths),
        categories=combined_categories,
    )


@app.route("/review/<int:batch_id>")
def review_batch_page(batch_id):
    """
    Allows the user to review all pages that were flagged during the
    verification step. This provides a focused view to handle problematic pages,
    such as those with poor OCR quality, incorrect orientation, or ambiguous
    content.
    """
    # Fetch only the pages that have been explicitly flagged for this batch.
    flagged_pages = get_flagged_pages_for_batch(batch_id)
    if not flagged_pages:
        # If there are no flagged pages, there's nothing to review. The user
        # is sent back to the main dashboard.
        return redirect(url_for("mission_control_page"))

    batch = get_batch_by_id(batch_id)

    # As in the verify view, create relative image paths for the template.
    processed_dir = os.getenv("PROCESSED_DIR")
    pages_with_relative_paths = [
        dict(
            p,
            relative_image_path=os.path.relpath(
                p["processed_image_path"], processed_dir
            ),
        )
        for p in flagged_pages
    ]

    # The category list is needed here as well, so the user can correct
    # categories for flagged pages.
    db_categories = get_all_unique_categories()
    combined_categories = sorted(list(set(BROAD_CATEGORIES + db_categories)))

    # Render the review template, which is specifically designed for handling
    # multiple flagged pages at once.
    return render_template(
        "review.html",
        batch_id=batch_id,
        batch=batch,
        flagged_pages=pages_with_relative_paths,
        categories=combined_categories,
    )


@app.route("/revisit/<int:batch_id>")
def revisit_batch_page(batch_id):
    """
    Allows a user to look through all pages of a batch that has already
    been verified. This is a read-only view intended for reviewing work
    that has already been completed, without the risk of making accidental
    changes.
    """
    pages = get_pages_for_batch(batch_id)
    if not pages:
        return redirect(
            url_for(
                "mission_control_page", message=f"No pages found for Batch #{batch_id}."
            )
        )

    batch = get_batch_by_id(batch_id)
    processed_dir = os.getenv("PROCESSED_DIR")
    pages_with_relative_paths = [
        dict(
            p,
            relative_image_path=os.path.relpath(
                p["processed_image_path"], processed_dir
            ),
        )
        for p in pages
    ]

    # Pagination is used here as well for navigating through the pages.
    page_num = request.args.get("page", 1, type=int)
    if not 1 <= page_num <= len(pages_with_relative_paths):
        page_num = 1
    current_page = pages_with_relative_paths[page_num - 1]

    db_categories = get_all_unique_categories()
    combined_categories = sorted(list(set(BROAD_CATEGORIES + db_categories)))

    # The 'revisit.html' template is similar to 'verify.html' but with form
    # submission elements disabled to enforce the read-only nature of this view.
    return render_template(
        "revisit.html",
        batch_id=batch_id,
        batch=batch,
        current_page=current_page,
        current_page_num=page_num,
        total_pages=len(pages_with_relative_paths),
        categories=combined_categories,
    )


@app.route("/view/<int:batch_id>")
def view_batch_page(batch_id):
    """
    Provides a strictly read-only view of all pages in a completed batch.
    This page is for reviewing the final state of a batch after all workflow
    steps (verification, grouping, ordering, export) are complete. It does not
    offer any modification capabilities.
    """
    # Fetch all pages associated with this batch.
    pages = get_pages_for_batch(batch_id)
    # If a completed batch has no pages (an unlikely edge case), redirect.
    if not pages:
        return redirect(
            url_for(
                "mission_control_page", message=f"No pages found for Batch #{batch_id}."
            )
        )

    # Fetch the batch object to display its final status.
    batch = get_batch_by_id(batch_id)
    processed_dir = os.getenv("PROCESSED_DIR")
    # Create relative image paths for rendering in the template.
    pages_with_relative_paths = [
        dict(
            p,
            relative_image_path=os.path.relpath(
                p["processed_image_path"], processed_dir
            ),
        )
        for p in pages
    ]

    # Implement pagination to navigate through the pages of the batch.
    page_num = request.args.get("page", 1, type=int)
    if not 1 <= page_num <= len(pages_with_relative_paths):
        page_num = 1
    current_page = pages_with_relative_paths[page_num - 1]

    # Render the dedicated read-only template 'view_batch.html'.
    return render_template(
        "view_batch.html",
        batch_id=batch_id,
        batch=batch,
        current_page=current_page,
        current_page_num=page_num,
        total_pages=len(pages_with_relative_paths),
    )

@app.route("/group/<int:batch_id>")
def group_batch_page(batch_id):
    """
    The second major step of the workflow: grouping verified pages into documents.
    This page displays all verified pages, conveniently grouped by their assigned
    category. The user can then select pages from within a category and create a
    single, multi-page document from them.
    """
    # Fetch all verified pages that have not yet been assigned to a document.
    # The data is returned as a dictionary where keys are categories.
    ungrouped_pages_data = get_verified_pages_for_grouping(batch_id)
    # Also fetch documents that have already been created for this batch to
    # display them on the same page, giving the user context of what's already done.
    created_docs = get_created_documents_for_batch(batch_id)

    # Create relative image paths for all the ungrouped pages so they can be
    # displayed in the browser.
    processed_dir = os.getenv("PROCESSED_DIR")
    for category, pages in ungrouped_pages_data.items():
        for i, page in enumerate(pages):
            page_dict = dict(page)
            page_dict["relative_image_path"] = os.path.relpath(
                page["processed_image_path"], processed_dir
            )
            ungrouped_pages_data[category][i] = page_dict

    # The 'group.html' template is designed to show both the ungrouped pages
    # (organized by category) and the already created documents.
    return render_template(
        "group.html",
        batch_id=batch_id,
        grouped_pages=ungrouped_pages_data,
        created_docs=created_docs,
    )


@app.route("/order/<int:batch_id>")
def order_batch_page(batch_id):
    """
    The third step of the workflow: ordering pages within multi-page documents.
    This page lists all documents that have more than one page, as single-page
    documents do not require ordering. If a batch contains only single-page
    documents, this step is bypassed, and the batch is automatically marked as
    'ordering_complete' to streamline the workflow.
    """
    all_documents = get_documents_for_batch(batch_id)

    # Filter for documents that actually need ordering.
    docs_to_order = [doc for doc in all_documents if doc["page_count"] > 1]

    # If all documents were single-page, they are considered "ordered" by default.
    # This is a quality-of-life feature to avoid an unnecessary step for the user.
    if not docs_to_order and all_documents:
        conn = get_db_connection()
        conn.execute(
            "UPDATE batches SET status = 'ordering_complete' WHERE id = ?", (batch_id,)
        )
        conn.commit()
        conn.close()
        print(
            f"Batch {batch_id} finalized automatically as it only contains single-page documents."
        )
        return redirect(url_for("mission_control_page"))

    # Render the page that lists documents needing an explicit page order.
    return render_template(
        "order_batch.html", batch_id=batch_id, documents=docs_to_order
    )


@app.route("/order_document/<int:document_id>", methods=["GET", "POST"])
def order_document_page(document_id):
    """
    Handles the reordering of pages for a single document.
    - A GET request displays the user interface with draggable page thumbnails.
    - A POST request receives the new page order from the UI and saves it to the database.
    """
    # The batch_id is needed for redirection back to the main ordering page
    # after this document's ordering is complete.
    conn = get_db_connection()
    batch_id = conn.execute(
        "SELECT batch_id FROM documents WHERE id = ?", (document_id,)
    ).fetchone()["batch_id"]
    conn.close()

    if request.method == "POST":
        # The new order is submitted by a JavaScript function as a comma-separated
        # string of page IDs (e.g., "3,1,2").
        ordered_page_ids = request.form.get("page_order").split(",")
        # Sanitize the list to ensure all IDs are integers before database insertion.
        page_ids_as_int = [int(pid) for pid in ordered_page_ids if pid.isdigit()]
        # The database function handles the complex update of the sequence numbers.
        update_page_sequence(document_id, page_ids_as_int)
        # Mark the document's status as having the order set.
        update_document_status(document_id, "order_set")
        # Redirect back to the list of documents to be ordered for the same batch.
        return redirect(url_for("order_batch_page", batch_id=batch_id))

    # For a GET request, display the page ordering UI.
    pages_raw = get_pages_for_document(document_id)
    processed_dir = os.getenv("PROCESSED_DIR")
    pages = [
        dict(
            p,
            relative_image_path=os.path.relpath(
                p["processed_image_path"], processed_dir
            ),
        )
        for p in pages_raw
    ]
    # The 'order_document.html' template contains the JavaScript for the
    # drag-and-drop interface (e.g., using SortableJS).
    return render_template(
        "order_document.html", document_id=document_id, pages=pages, batch_id=batch_id
    )


# --- API AND FORM ACTION ROUTES ---
# These routes handle form submissions and AJAX requests from the frontend.
# They perform specific actions and then typically redirect or return JSON.

@app.route("/finalize_batch/<int:batch_id>", methods=["POST"])
def finalize_batch_action(batch_id):
    """
    A final action to mark the entire ordering step for a batch as complete.
    This is triggered by a button on the 'order_batch.html' page when the user
    confirms that all necessary documents have been ordered.
    """
    conn = get_db_connection()
    conn.execute(
        "UPDATE batches SET status = 'ordering_complete' WHERE id = ?", (batch_id,)
    )
    conn.commit()
    conn.close()
    return redirect(url_for("mission_control_page"))


@app.route("/api/suggest_order/<int:document_id>", methods=["POST"])
def suggest_order_api(document_id):
    """
    An API endpoint called via JavaScript from the ordering page.
    It uses an AI model (via `processing.py`) to suggest the correct order of
    pages for a given document based on their textual content. This is a helper
    feature to speed up the manual ordering process.
    """
    pages = get_pages_for_document(document_id)
    if not pages:
        return jsonify({"error": "Document not found or has no pages."} ), 404

    # The core AI ordering logic is in the 'processing.py' module.
    suggested_order = get_ai_suggested_order(pages)

    if suggested_order:
        # If successful, return the suggested order as a JSON list of page IDs.
        # The frontend JavaScript will then use this to reorder the elements on the page.
        return jsonify({"success": True, "page_order": suggested_order})
    else:
        # If the AI fails (e.g., due to insufficient text), return an error
        # that the frontend can display to the user.
        return (
            jsonify(
                {
                    "success": False,
                    "error": "AI suggestion failed. Please order manually.",
                }
            ),
            500,
        )


@app.route("/save_document", methods=["POST"])
def save_document_action():
    """
    Handles the form submission from the 'group' page to create a new document
    from a selection of pages. It takes the user-provided document name and
    the list of selected page IDs.
    """
    batch_id = request.form.get("batch_id", type=int)
    document_name = request.form.get("document_name", "").strip()
    page_ids = request.form.getlist("page_ids", type=int)

    # Basic validation to ensure the user has provided a name and selected pages.
    if not document_name or not page_ids:
        # Redirecting with an error message is not implemented here, but would be
        # a good addition for user feedback.
        return redirect(
            url_for(
                "group_batch_page",
                batch_id=batch_id,
                error="Document name and at least one page are required.",
            )
        )

    # The database function handles the creation of the document record and
    # linking the pages to it.
    create_document_and_link_pages(batch_id, document_name, page_ids)

    # After creating a document, check if all verified pages in the batch have
    # now been grouped. If so, the batch status is updated automatically,
    # moving the workflow forward.
    if count_ungrouped_verified_pages(batch_id) == 0:
        conn = get_db_connection()
        conn.execute(
            "UPDATE batches SET status = 'grouping_complete' WHERE id = ?", (batch_id,)
        )
        conn.commit()
        conn.close()

    # Redirect back to the grouping page to show the newly created document.
    return redirect(url_for("group_batch_page", batch_id=batch_id))


@app.route("/reset_grouping/<int:batch_id>", methods=["POST"])
def reset_grouping_action(batch_id):
    """
    Allows the user to undo the grouping for an entire batch.
    This is a "reset" button for the grouping stage. It deletes all documents
    created for the batch and un-links the pages, returning them to their
    ungrouped, verified state, ready to be grouped again.
    """
    reset_batch_grouping(batch_id)
    return redirect(url_for("group_batch_page", batch_id=batch_id))


@app.route("/reset_batch/<int:batch_id>", methods=["POST"])
def reset_batch_action(batch_id):
    """
    Handles the action to completely reset a batch to its initial state
    ('pending_verification'). This is a destructive action that undoes any
    verification, grouping, or ordering work, allowing the user to start over
    from the beginning.
    """
    # The core logic is encapsulated in the database function for safety and
    # to ensure all related data is reset correctly.
    reset_batch_to_start(batch_id)
    # After the reset, send the user back to the main dashboard.
    return redirect(url_for("mission_control_page"))


@app.route("/update_page", methods=["POST"])
def update_page():
    """
    Handles form submissions from the 'verify' and 'review' pages to update
    the status, category, and rotation of a single page. This is one of the
    most critical interactive routes.
    """
    # Extract all data from the submitted form. Using .get() with defaults
    # provides robustness against missing form fields.
    action = request.form.get("action")
    page_id = request.form.get("page_id", type=int)
    batch_id = request.form.get("batch_id", type=int)
    rotation = request.form.get("rotation", 0, type=int)
    current_page_num = request.form.get("current_page_num", type=int)
    total_pages = request.form.get("total_pages", type=int)
    category = ""
    status = ""
    dropdown_choice = request.form.get("category_dropdown")
    other_choice = request.form.get("other_category", "").strip()

    # Determine the new status and category based on which button the user clicked
    # ('Flag for Review' vs. 'Save and Next').
    if action == "flag":
        status = "flagged"
        category = "NEEDS_REVIEW"  # A special category for flagged pages.
    else:
        status = "verified"
        # This logic handles the category selection, allowing a user to either
        # pick an existing category from the dropdown or create a new one by
        # typing into the "other" text field.
        if dropdown_choice == "other_new" and other_choice:
            category = other_choice
        elif dropdown_choice and dropdown_choice != "other_new":
            category = dropdown_choice
        else:
            # If the user doesn't make an explicit choice, the system defaults
            # to using the original AI suggestion.
            category = request.form.get("ai_suggestion")

    # Save the updated page data to the database.
    update_page_data(page_id, category, status, rotation)

    # --- Redirection Logic ---
    # The application needs to intelligently redirect the user back to where
    # they came from.
    if "revisit" in request.referrer:
        # If they were on the revisit page, they should stay on that page.
        return redirect(
            url_for("revisit_batch_page", batch_id=batch_id, page=current_page_num)
        )
    if "review" in request.referrer:
        # If they were on the review page, they should return there to see the
        # list of remaining flagged pages.
        return redirect(url_for("review_batch_page", batch_id=batch_id))

    # If in the main verification flow, proceed to the next page.
    if current_page_num < total_pages:
        return redirect(
            url_for("verify_batch_page", batch_id=batch_id, page=current_page_num + 1)
        )
    else:
        # If this was the last page of the batch, the verification step is
        # considered complete. The batch status is updated, and the user is
        # returned to the main dashboard.
        conn = get_db_connection()
        conn.execute(
            "UPDATE batches SET status = 'verification_complete' WHERE id = ?",
            (batch_id,)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("mission_control_page"))


@app.route("/delete_page/<int:page_id>", methods=["POST"])
def delete_page_action(page_id):
    """
    Permanently deletes a page from the database and its associated image file
    from the filesystem. This action is typically available on the 'review'
    page for pages that are determined to be unrecoverable, irrelevant, or duplicates.
    """
    batch_id = request.form.get("batch_id")
    # The deletion logic is handled in the database module to ensure atomicity.
    delete_page_by_id(page_id)
    # Redirect back to the review page to continue reviewing other flagged pages.
    return redirect(url_for("review_batch_page", batch_id=batch_id))


@app.route("/rerun_ocr", methods=["POST"])
def rerun_ocr_action():
    """
    Handles a request to re-run the OCR process on a single page, optionally
    applying a rotation first. This is useful if the initial OCR was poor due
    to the page being scanned upside down or sideways.
    """
    page_id = request.form.get("page_id", type=int)
    batch_id = request.form.get("batch_id", type=int)
    rotation = request.form.get("rotation", 0, type=int)
    # The `rerun_ocr_on_page` function in `processing.py` handles the image
    # manipulation and the call to the OCR engine.
    rerun_ocr_on_page(page_id, rotation)
    # After re-running OCR, the user is returned to the review page to see
    # the updated OCR text and re-evaluate the page.
    return redirect(url_for("review_batch_page", batch_id=batch_id))


# --- UTILITY ROUTES ---
# These routes provide helper functionalities, like serving files.

@app.route("/processed_files/<path:filepath>")
def serve_processed_file(filepath):
    """
    A utility route to serve the processed image files (PNGs) to the browser.
    Using Flask's `send_from_directory` is a security best practice. It ensures
    that only files from within the specified `PROCESSED_DIR` can be accessed,
    preventing directory traversal attacks where a user might try to access
    sensitive files elsewhere on the server.
    """
    processed_dir = os.getenv("PROCESSED_DIR")
    return send_from_directory(processed_dir, filepath)


# --- FINALIZATION AND EXPORT ROUTES ---
# These routes handle the last stage of the workflow: naming and exporting.

@app.route("/finalize/<int:batch_id>")
def finalize_batch_page(batch_id):
    """
    Displays the new finalization screen where users can review and edit
    AI-suggested filenames for each document before the final export. This is
    the last chance to make changes before the files are written to the
    "filing cabinet".
    """
    documents_raw = get_documents_for_batch(batch_id)
    documents_for_render = []

    for doc in documents_raw:
        pages = get_pages_for_document(doc["id"])
        if not pages:
            continue  # Skip if a document somehow has no pages.
        # The full text of all pages is concatenated to give the AI model
        # maximum context for generating a good filename.
        full_doc_text = "\n---\n".join([p["ocr_text"] for p in pages])
        # The category is also provided to the AI to help it generate a more
        # relevant and structured filename.
        doc_category = pages[0]["human_verified_category"]
        suggested_filename = get_ai_suggested_filename(full_doc_text, doc_category)
        
        doc_dict = dict(doc)
        doc_dict["suggested_filename"] = suggested_filename
        documents_for_render.append(doc_dict)

    # The 'finalize.html' template will display a list of documents, each with
    # an editable text input pre-filled with the AI-suggested filename.
    return render_template(
        "finalize.html",
        batch_id=batch_id,
        documents=documents_for_render
    )


@app.route("/export_batch/<int:batch_id>", methods=["POST"])
def export_batch_action(batch_id):
    """
    Handles the final export process for all documents in a batch. This route
    receives the final list of document IDs and their user-approved filenames
    from the finalization page.
    """
    doc_ids = request.form.getlist('document_ids', type=int)
    final_filenames = request.form.getlist('final_filenames')

    # The form submits parallel lists of document IDs and their corresponding
    # final filenames. We zip them together to process them one by one.
    for doc_id, final_name in zip(doc_ids, final_filenames):
        pages = get_pages_for_document(doc_id)
        if not pages:
            print(f"Skipping export for document ID {doc_id}: No pages found.")
            continue
        
        category = pages[0]['human_verified_category']
        # The filename from the form might include an extension, but the export
        # function expects a base name.
        final_name_base = os.path.splitext(final_name)[0]

        # The final, user-approved filename is saved to the database for
        # record-keeping and for the "view exported documents" feature.
        update_document_final_filename(doc_id, final_name_base)
        # The `export_document` function in `processing.py` handles the creation
        # of the final PDF files and the log file.
        export_document(pages, final_name_base, category)

    # After all documents are exported, the temporary files associated with the
    # batch (like the intermediate PNGs) are deleted to save space.
    cleanup_batch_files(batch_id)

    # The batch is marked as 'Exported', its final status.
    conn = get_db_connection()
    conn.execute("UPDATE batches SET status = 'Exported' WHERE id = ?", (batch_id,))
    conn.commit()
    conn.close()

    # The user is returned to the main dashboard.
    return redirect(url_for("mission_control_page"))


# --- VIEW EXPORTED DOCUMENTS ROUTES ---
# This section provides a way for users to access the final exported files.

@app.route('/view_documents/<int:batch_id>')
def view_documents_page(batch_id):
    """
    Displays a list of all documents that have been exported for a given batch,
    providing direct download links to the final PDF and log files.
    """
    documents = get_documents_for_batch(batch_id)
    # The database stores the base filename. This code reconstructs the full
    # relative paths to the exported files so they can be used in the template's
    # download links.
    docs_with_paths = []
    for doc in documents:
        doc_dict = dict(doc)
        if doc_dict.get("final_filename_base"):
            pages = get_pages_for_document(doc_dict["id"])
            if pages:
                category = pages[0]['human_verified_category']
                # The category name is sanitized to match the folder naming
                # convention used during the export process.
                category_dir_name = "".join(c for c in category if c.isalnum() or c in (' ', '-', '_')).rstrip().replace(' ', '_')
                base = doc_dict["final_filename_base"]
                
                # Create relative paths for the various exported files.
                doc_dict['pdf_path'] = os.path.join(category_dir_name, f"{base}.pdf")
                doc_dict['ocr_pdf_path'] = os.path.join(category_dir_name, f"{base}_ocr.pdf")
                doc_dict['log_path'] = os.path.join(category_dir_name, f"{base}_log.md")
        docs_with_paths.append(doc_dict)

    return render_template("view_documents.html", documents=docs_with_paths, batch_id=batch_id)


@app.route('/download_export/<path:filepath>')
def download_export_file(filepath):
    """
    Securely serves an exported file for download from the FILING_CABINET_DIR.
    This route is essential for providing access to the final documents.
    """
    filing_cabinet_dir = os.getenv("FILING_CABINET_DIR")
    if not filing_cabinet_dir:
        # If the environment variable is not set, the application cannot find
        # the files, so it aborts with a server error.
        abort(500, "FILING_CABINET_DIR is not configured.")
    
    # --- Security Measure ---
    # This is a critical security check to prevent "path traversal" attacks.
    # It ensures that the requested file path is genuinely inside the intended
    # `filing_cabinet_dir` and not somewhere else on the filesystem (e.g.,
    # using `../../` to access system files).
    safe_base_path = os.path.abspath(filing_cabinet_dir)
    safe_filepath = os.path.abspath(os.path.join(safe_base_path, filepath))

    if not safe_filepath.startswith(safe_base_path):
        abort(404) # If the path is outside the allowed directory, return Not Found.

    # `send_from_directory` is used again here as it is the most robust and
    # secure way to handle file downloads in Flask.
    directory = os.path.dirname(safe_filepath)
    filename = os.path.basename(safe_filepath)
    
    # `as_attachment=True` tells the browser to prompt the user for a download
    # rather than trying to display the file in the browser window.
    return send_from_directory(directory, filename, as_attachment=True)


# --- MAIN EXECUTION ---

if __name__ == "__main__":
    """
    This block allows the script to be run directly using `python app.py`.
    It starts the Flask development server, which is convenient for testing
    and local development. For a production deployment, a more robust WSGI
    server like Gunicorn or uWSGI would be used instead.
    """
    # `debug=True` enables automatic reloading when code changes and provides
    # detailed error pages. This should be set to `False` in production.
    # `host="0.0.0.0"` makes the server accessible from any IP address on the
    # network, not just localhost.
    app.run(debug=True, host="0.0.0.0", port=5000)
