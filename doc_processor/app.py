"""
This module, `app.py`, serves as the central orchestrator and user interface layer for the entire document processing web application.
Built upon the Flask web framework, it defines all the HTTP routes (URLs) that users interact with and manages the flow of data
and control between the frontend (HTML templates) and the backend logic (`processing.py` and `database.py`).

The application guides a user through a multi-stage pipeline to transform raw, scanned documents into organized, categorized, and named files.
Each stage of this pipeline is typically represented by one or more Flask routes and corresponding HTML templates.

**The Document Processing Pipeline Stages:**

1.  **Batch Processing (`/process_new_batch`)**: Initiates the automated ingestion of new PDF documents from a predefined intake directory.
    This stage leverages `processing.py` for heavy-lifting tasks like PDF-to-image conversion, OCR, and initial AI-based categorization.

2.  **Verification (`/verify/<int:batch_id>`)**: The first human-in-the-loop step. Users manually review each page, correcting AI-suggested categories,
    adjusting page rotations, or flagging pages for later review. This is a critical quality control point.

3.  **Review (`/review/<int:batch_id>`)**: A dedicated interface for addressing only the pages that were explicitly "flagged" during verification.
    This allows for focused problem-solving on pages with poor OCR, incorrect orientation, or ambiguous content.

4.  **Grouping (`/group/<int:batch_id>`)**: After all pages are verified, users group individual pages into logical, multi-page documents.
    For example, several pages belonging to a single invoice would be grouped together to form one document.

5.  **Ordering (`/order/<int:batch_id>` and `/order_document/<int:document_id>`)**: For documents composed of multiple pages, users can specify
    the correct sequence of pages. An AI-powered suggestion feature is available to assist in this process, especially for documents with printed page numbers.

6.  **Finalization & Export (`/finalize/<int:batch_id>` and `/export_batch/<int:batch_id>`)**: The concluding stage where users provide final, meaningful filenames
    (often with AI suggestions) for each document and trigger the export. The application generates various output files (standard PDFs, searchable PDFs,
    and Markdown logs) and organizes them into a structured "filing cabinet" directory based on their categories.

This `app.py` module acts as the central nervous system, coordinating interactions between the user interface, the database (`database.py`),
and the core processing logic (`processing.py`) to deliver a cohesive and efficient document management solution.
"""
# Standard library imports
import os  # Used for interacting with the operating system, e.g., file paths and environment variables.

# Third-party imports
from flask import (
    Flask,             # The main Flask class to create the web application instance.
    render_template,   # Function to render Jinja2 HTML templates.
    request,           # Global object to access incoming request data (form data, query parameters, etc.).
    redirect,          # Function to redirect the user to a different URL.
    url_for,           # Function to dynamically build URLs for Flask routes, making them robust to changes.
    send_from_directory, # Securely serves files from a specified directory.
    jsonify,           # Converts Python dictionaries to JSON responses for API endpoints.
    abort,             # Raises an HTTP exception (e.g., 404 Not Found, 500 Internal Server Error).
)

# Local application imports
# These imports bring in the core business logic and database functions
# from other modules in the application, promoting modularity and separation of concerns.
from processing import (
    process_batch,             # Initiates the main document processing pipeline.
    rerun_ocr_on_page,         # Re-runs OCR on a single page, potentially with rotation.
    BROAD_CATEGORIES,          # A list of predefined categories used for AI classification.
    get_ai_suggested_order,    # AI-powered function to suggest page order within a document.
    get_ai_suggested_filename, # AI-powered function to suggest a filename for a document.
    export_document,           # Handles the final generation and saving of document files.
    cleanup_batch_files,       # Deletes temporary files associated with a completed batch.
)
from database import (
    get_pages_for_batch,               # Retrieves all pages for a given batch.
    update_page_data,                  # Updates a page's category, status, and rotation.
    get_flagged_pages_for_batch,       # Retrieves pages marked for review.
    delete_page_by_id,                 # Deletes a page and its associated image file.
    get_all_unique_categories,         # Fetches all unique categories used in the database.
    get_verified_pages_for_grouping,   # Retrieves verified pages not yet grouped into documents.
    create_document_and_link_pages,    # Creates a new document and links pages to it.
    get_created_documents_for_batch,   # Retrieves documents already created for a batch.
    get_batch_by_id,                   # Fetches a specific batch record.
    count_flagged_pages_for_batch,     # Counts flagged pages in a batch.
    get_db_connection,                 # Utility to establish a database connection.
    count_ungrouped_verified_pages,    # Counts verified pages not yet grouped.
    reset_batch_grouping,              # Undoes grouping for an entire batch.
    get_documents_for_batch,           # Retrieves all documents for a batch, with page counts.
    get_pages_for_document,            # Retrieves all pages belonging to a specific document.
    update_page_sequence,              # Updates the order of pages within a document.
    update_document_status,            # Updates the status of a document.
    reset_batch_to_start,              # Resets an entire batch to its initial state.
    update_document_final_filename,    # Saves the user-approved final filename for a document.
)

# Initialize the Flask application instance.
# `__name__` tells Flask where to look for resources like templates and static files.
app = Flask(__name__)

# Set a secret key for session management. This is absolutely crucial for security.
# It's used to cryptographically sign session cookies and other security-related data.
# `os.urandom(24)` generates a strong, random 24-byte key each time the application starts.
# In a production environment, this should be loaded from an environment variable or configuration file
# and remain constant across restarts.
app.secret_key = os.urandom(24)


# --- CORE NAVIGATION AND WORKFLOW ROUTES ---
# These routes define the main pages and initial actions a user takes within the application.

@app.route("/")
def index():
    """
    The root URL of the application.
    This route's sole purpose is to redirect the user to the main "Mission Control" dashboard,
    which serves as the application's central home screen and workflow hub.
    """
    return redirect(url_for("mission_control_page"))


@app.route("/process_new_batch", methods=["POST"])
def handle_batch_processing():
    """
    Handles the HTTP POST request to initiate the processing of a new batch of documents.
    This route is typically triggered by a button click on the Mission Control page.

    It delegates the intensive tasks of OCR, image conversion, and initial AI analysis
    to the `process_batch` function in `processing.py`.
    After the processing is complete, it redirects the user back to the Mission Control page
    so they can see the newly created batch listed.
    """
    process_batch()
    return redirect(url_for("mission_control_page"))


@app.route("/mission_control")
def mission_control_page():
    """
    Displays the main dashboard of the application.
    This page presents a list of all processed batches, along with key statistics for each,
    such as the number of flagged pages and ungrouped verified pages.
    This provides the user with a quick overview of the work that needs to be done and the status of ongoing batches.
    """
    # A new database connection is opened for each request to ensure thread safety and proper resource management.
    conn = get_db_connection()
    # Fetches all batches from the database, ordered by ID in descending order to show the most recent batches first.
    all_batches_raw = conn.execute("SELECT * FROM batches ORDER BY id DESC").fetchall()
    conn.close()

    # The raw data fetched from the database is augmented with additional computed information
    # that is necessary for display in the user interface.
    all_batches = []
    for batch in all_batches_raw:
        batch_dict = dict(batch)  # Convert the `sqlite3.Row` object to a standard Python dictionary.
        batch_id = batch_dict["id"]
        # Augment the batch data with counts of flagged and ungrouped pages.
        # These counts are used to determine which action buttons to display on the dashboard.
        batch_dict["flagged_count"] = count_flagged_pages_for_batch(batch_id)
        batch_dict["ungrouped_count"] = count_ungrouped_verified_pages(batch_id)
        all_batches.append(batch_dict)

    # Renders the `mission_control.html` template, passing the prepared list of batches to be displayed.
    return render_template("mission_control.html", batches=all_batches)


# --- DIRECT ACTION ROUTES (Accessed from Mission Control) ---
# These routes correspond to the primary actions a user can take on a batch directly from the main dashboard.

@app.route("/verify/<int:batch_id>")
def verify_batch_page(batch_id):
    """
    Handles the display of the page-by-page verification interface.
    This is the first manual step in the workflow, allowing users to review each page,
    correct AI-suggested categories, adjust rotation, and flag pages for later review.
    """
    # Pre-check: If the batch's status indicates that verification is already complete,
    # redirect the user to a read-only "revisit" page to prevent accidental re-verification.
    batch = get_batch_by_id(batch_id)
    if batch and batch["status"] != "pending_verification":
        return redirect(url_for("revisit_batch_page", batch_id=batch_id))

    # Fetch all pages associated with this batch from the database.
    pages = get_pages_for_batch(batch_id)
    if not pages:
        # If a batch has no pages, there's nothing to verify. Redirect back to Mission Control.
        return redirect(
            url_for("mission_control_page", message=f"No pages found for Batch #{batch_id}.")
        )

    # The application stores absolute paths to images. For security and portability,
    # we create relative paths to be used in the HTML `src` attribute. This is handled
    # by the `serve_processed_file` route.
    processed_dir = os.getenv("PROCESSED_DIR")
    pages_with_relative_paths = [
        dict(
            p,
            relative_image_path=os.path.relpath(p["processed_image_path"], processed_dir),
        )
        for p in pages
    ]

    # Implement simple pagination to display one page at a time.
    # The current page number is extracted from the URL query parameters (e.g., `?page=2`).
    page_num = request.args.get("page", 1, type=int)
    # Ensure the page number is within valid bounds; default to the first page if invalid.
    if not 1 <= page_num <= len(pages_with_relative_paths):
        page_num = 1
    current_page = pages_with_relative_paths[page_num - 1]

    # Combine predefined broad categories with all unique categories previously saved in the database.
    # This provides a comprehensive list for the category dropdown, allowing for both consistency and flexibility.
    db_categories = get_all_unique_categories()
    combined_categories = sorted(list(set(BROAD_CATEGORIES + db_categories)))

    # Render the `verify.html` template, passing all necessary data for displaying the current page,
    # pagination controls, and category options.
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
    Displays an interface for reviewing all pages that were explicitly flagged during the verification step.
    This provides a focused view to address problematic pages (e.g., poor OCR, incorrect orientation, ambiguous content).
    """
    # Fetch only the pages that have been marked with a 'flagged' status for this specific batch.
    flagged_pages = get_flagged_pages_for_batch(batch_id)
    if not flagged_pages:
        # If there are no flagged pages, there's nothing to review. Redirect the user back to the main dashboard.
        return redirect(url_for("mission_control_page"))

    batch = get_batch_by_id(batch_id)

    # Create relative image paths for the flagged pages to be displayed in the template.
    processed_dir = os.getenv("PROCESSED_DIR")
    pages_with_relative_paths = [
        dict(
            p,
            relative_image_path=os.path.relpath(p["processed_image_path"], processed_dir),
        )
        for p in flagged_pages
    ]

    # The combined category list is also needed here, allowing the user to correct categories for flagged pages.
    db_categories = get_all_unique_categories()
    combined_categories = sorted(list(set(BROAD_CATEGORIES + db_categories)))

    # Render the `review.html` template, which is specifically designed for handling multiple flagged pages.
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
    Provides a read-only view of all pages within a batch that has already completed the verification step.
    This route is intended for reviewing previously completed work without the risk of making accidental changes.
    It functions similarly to the `/verify` route but disables all modification capabilities in the UI.
    """
    pages = get_pages_for_batch(batch_id)
    if not pages:
        return redirect(
            url_for("mission_control_page", message=f"No pages found for Batch #{batch_id}.")
        )

    batch = get_batch_by_id(batch_id)
    processed_dir = os.getenv("PROCESSED_DIR")
    pages_with_relative_paths = [
        dict(
            p,
            relative_image_path=os.path.relpath(p["processed_image_path"], processed_dir),
        )
        for p in pages
    ]

    # Pagination is also applied here for navigating through the pages in this read-only view.
    page_num = request.args.get("page", 1, type=int)
    if not 1 <= page_num <= len(pages_with_relative_paths):
        page_num = 1
    current_page = pages_with_relative_paths[page_num - 1]

    db_categories = get_all_unique_categories()
    combined_categories = sorted(list(set(BROAD_CATEGORIES + db_categories)))

    # The `revisit.html` template is rendered, which is structurally similar to `verify.html`
    # but has its form submission elements disabled to enforce the read-only nature.
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
    Provides a strictly read-only overview of all pages within a completed batch.
    This page is for reviewing the final state of a batch after all workflow steps
    (verification, grouping, ordering, export) are complete. It offers no modification capabilities.
    """
    pages = get_pages_for_batch(batch_id)
    if not pages:
        return redirect(
            url_for("mission_control_page", message=f"No pages found for Batch #{batch_id}.")
        )

    batch = get_batch_by_id(batch_id)
    processed_dir = os.getenv("PROCESSED_DIR")
    pages_with_relative_paths = [
        dict(
            p,
            relative_image_path=os.path.relpath(p["processed_image_path"], processed_dir),
        )
        for p in pages
    ]

    page_num = request.args.get("page", 1, type=int)
    if not 1 <= page_num <= len(pages_with_relative_paths):
        page_num = 1
    current_page = pages_with_relative_paths[page_num - 1]

    # Renders the dedicated read-only template `view_batch.html`.
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
    Displays the interface for the "Grouping" stage of the workflow.
    This page allows users to group individual verified pages into logical documents.
    It presents all verified pages, conveniently organized by their assigned category,
    and also shows documents that have already been created within the current batch.
    """
    # Fetch all verified pages that have not yet been assigned to a document.
    # The data is returned as a dictionary where keys are categories and values are lists of pages.
    ungrouped_pages_data = get_verified_pages_for_grouping(batch_id)
    # Also fetch documents that have already been created for this batch to provide context to the user.
    created_docs = get_created_documents_for_batch(batch_id)

    # Iterate through the ungrouped pages and create relative image paths for display in the browser.
    processed_dir = os.getenv("PROCESSED_DIR")
    for category, pages in ungrouped_pages_data.items():
        for i, page in enumerate(pages):
            page_dict = dict(page)
            page_dict["relative_image_path"] = os.path.relpath(page["processed_image_path"], processed_dir)
            ungrouped_pages_data[category][i] = page_dict

    # Renders the `group.html` template, which is designed to display both the ungrouped pages
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
    Displays a list of documents that require page ordering.
    This is the third major step of the workflow. It filters for documents that have more than one page,
    as single-page documents are inherently ordered and do not require this step.
    If a batch contains only single-page documents, this step is automatically bypassed,
    and the batch status is updated to 'ordering_complete' to streamline the workflow.
    """
    all_documents = get_documents_for_batch(batch_id)

    # Filter the list of all documents to include only those that have more than one page.
    docs_to_order = [doc for doc in all_documents if doc["page_count"] > 1]

    # Optimization: If all documents in the batch are single-page, they are considered "ordered" by default.
    # In this scenario, the batch status is updated, and the user is redirected to Mission Control.
    if not docs_to_order and all_documents:
        conn = get_db_connection()
        conn.execute("UPDATE batches SET status = 'ordering_complete' WHERE id = ?", (batch_id,))
        conn.commit()
        conn.close()
        print(f"Batch {batch_id} automatically marked as ordering_complete as it only contains single-page documents.")
        return redirect(url_for("mission_control_page"))

    # Renders the `order_batch.html` template, which lists documents needing explicit page ordering.
    return render_template("order_batch.html", batch_id=batch_id, documents=docs_to_order)


@app.route("/order_document/<int:document_id>", methods=["GET", "POST"])
def order_document_page(document_id):
    """
    Handles the reordering of pages for a single document.
    -   **GET request**: Displays the user interface with draggable page thumbnails, allowing manual reordering.
    -   **POST request**: Receives the new page order from the UI (typically via JavaScript) and saves it to the database.
    """
    # Retrieve the `batch_id` associated with the document. This is needed for redirection
    # back to the main ordering page after this document's ordering is complete.
    conn = get_db_connection()
    batch_id = conn.execute("SELECT batch_id FROM documents WHERE id = ?", (document_id,)).fetchone()["batch_id"]
    conn.close()

    if request.method == "POST":
        # The new order is submitted by a JavaScript function as a comma-separated string of page IDs (e.g., "3,1,2").
        ordered_page_ids_str = request.form.get("page_order")
        # Convert the string of IDs into a list of integers, filtering out any non-digit entries for robustness.
        page_ids_as_int = [int(pid) for pid in ordered_page_ids_str.split(",") if pid.isdigit()]
        # Update the page sequence in the database using the dedicated function.
        update_page_sequence(document_id, page_ids_as_int)
        # Mark the document's status as having its order set.
        update_document_status(document_id, "order_set")
        # Redirect back to the list of documents to be ordered for the same batch.
        return redirect(url_for("order_batch_page", batch_id=batch_id))

    # For a GET request, prepare data to display the page ordering UI.
    pages_raw = get_pages_for_document(document_id)
    processed_dir = os.getenv("PROCESSED_DIR")
    # Create relative image paths for rendering the page thumbnails in the template.
    pages = [
        dict(
            p,
            relative_image_path=os.path.relpath(p["processed_image_path"], processed_dir),
        )
        for p in pages_raw
    ]
    # Renders the `order_document.html` template, which contains the JavaScript for the drag-and-drop interface.
    return render_template("order_document.html", document_id=document_id, pages=pages, batch_id=batch_id)


# --- API AND FORM ACTION ROUTES ---
# These routes handle form submissions and AJAX requests from the frontend.
# They perform specific actions and then typically redirect or return JSON data.

@app.route("/finalize_batch/<int:batch_id>", methods=["POST"])
def finalize_batch_action(batch_id):
    """
    Marks the entire ordering step for a batch as complete.
    This route is triggered by a button on the `order_batch.html` page when the user
    confirms that all necessary documents have been ordered.
    """
    conn = get_db_connection()
    conn.execute("UPDATE batches SET status = 'ordering_complete' WHERE id = ?", (batch_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("mission_control_page"))


@app.route("/api/suggest_order/<int:document_id>", methods=["POST"])
def suggest_order_api(document_id):
    """
    An API endpoint called via JavaScript (AJAX) from the document ordering page.
    It leverages an AI model (via `processing.py`) to suggest the correct order of pages
    for a given document based on their textual content (e.g., extracted page numbers).
    This is a helper feature to accelerate the manual ordering process.
    """
    pages = get_pages_for_document(document_id)
    if not pages:
        return jsonify({"error": "Document not found or has no pages."} ), 404

    # The core AI ordering logic is encapsulated in the `get_ai_suggested_order` function in `processing.py`.
    suggested_order = get_ai_suggested_order(pages)

    if suggested_order:
        # If the AI successfully suggests an order, return it as a JSON list of page IDs.
        # The frontend JavaScript will then use this list to reorder the visual elements on the page.
        return jsonify({"success": True, "page_order": suggested_order})
    else:
        # If the AI fails to provide a suggestion (e.g., due to insufficient text or model error),
        # return an error message that the frontend can display to the user.
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
    from a selection of pages. It receives the user-provided document name and
    the list of selected page IDs.
    """
    batch_id = request.form.get("batch_id", type=int)
    document_name = request.form.get("document_name", "").strip()
    page_ids = request.form.getlist("page_ids", type=int)

    # Basic validation: ensure the user has provided a document name and selected at least one page.
    if not document_name or not page_ids:
        # If validation fails, redirect back to the grouping page with an error message.
        return redirect(
            url_for(
                "group_batch_page",
                batch_id=batch_id,
                error="Document name and at least one page are required.",
            )
        )

    # Delegate the creation of the document record and linking of pages to the database module.
    create_document_and_link_pages(batch_id, document_name, page_ids)

    # After creating a document, check if all verified pages in the batch have now been grouped.
    # If so, update the batch status to 'grouping_complete', advancing the workflow automatically.
    if count_ungrouped_verified_pages(batch_id) == 0:
        conn = get_db_connection()
        conn.execute("UPDATE batches SET status = 'grouping_complete' WHERE id = ?", (batch_id,))
        conn.commit()
        conn.close()

    # Redirect back to the grouping page to display the newly created document and any remaining ungrouped pages.
    return redirect(url_for("group_batch_page", batch_id=batch_id))


@app.route("/reset_grouping/<int:batch_id>", methods=["POST"])
def reset_grouping_action(batch_id):
    """
    Allows the user to undo the grouping for an entire batch.
    This acts as a "reset" button for the grouping stage: it deletes all documents
    created for the batch and un-links the pages, returning them to their
    ungrouped, verified state, ready to be grouped again.
    """
    reset_batch_grouping(batch_id)
    return redirect(url_for("group_batch_page", batch_id=batch_id))


@app.route("/reset_batch/<int:batch_id>", methods=["POST"])
def reset_batch_action(batch_id):
    """
    Handles the action to completely reset a batch to its initial state (`pending_verification`).
    This is a **destructive** action that undoes any verification, grouping, or ordering work
    for the specified batch, allowing the user to start over from the beginning.
    """
    # The core logic for resetting the batch is encapsulated in the database module for safety
    # and to ensure all related data (documents, page statuses) is reset correctly.
    reset_batch_to_start(batch_id)
    # After the reset, redirect the user back to the main dashboard.
    return redirect(url_for("mission_control_page"))


@app.route("/update_page", methods=["POST"])
def update_page():
    """
    Handles form submissions from the 'verify' and 'review' pages to update
    the status, category, and rotation of a single page. This is one of the
    most critical interactive routes for human verification.
    """
    # Extract all necessary data from the submitted form.
    # `.get()` with default values provides robustness against missing form fields.
    action = request.form.get("action")
    page_id = request.form.get("page_id", type=int)
    batch_id = request.form.get("batch_id", type=int)
    rotation = request.form.get("rotation", 0, type=int)
    current_page_num = request.form.get("current_page_num", type=int)
    total_pages = request.form.get("total_pages", type=int)
    
    category = "" # Initialize category variable.
    status = ""   # Initialize status variable.
    dropdown_choice = request.form.get("category_dropdown")
    other_choice = request.form.get("other_category", "").strip()

    # Determine the new status and category based on the user's action (which button was clicked).
    if action == "flag":
        status = "flagged"
        category = "NEEDS_REVIEW"  # Assign a special category for flagged pages.
    else: # Action is implicitly "save" or "next"
        status = "verified"
        # Logic to determine the final category: user can pick from dropdown or enter a new one.
        if dropdown_choice == "other_new" and other_choice:
            category = other_choice # User entered a new category.
        elif dropdown_choice and dropdown_choice != "other_new":
            category = dropdown_choice # User selected an existing category from the dropdown.
        else:
            # If no explicit choice is made, default to the original AI suggestion.
            category = request.form.get("ai_suggestion")

    # Save the updated page data to the database using the dedicated function.
    update_page_data(page_id, category, status, rotation)

    # --- Redirection Logic ---
    # The application intelligently redirects the user based on their previous location and the workflow state.
    if "revisit" in request.referrer:
        # If the user was on the read-only revisit page, they should remain there.
        return redirect(url_for("revisit_batch_page", batch_id=batch_id, page=current_page_num))
    if "review" in request.referrer:
        # If the user was on the review page, they should return there to continue reviewing other flagged pages.
        return redirect(url_for("review_batch_page", batch_id=batch_id))

    # If in the main verification flow, proceed to the next page.
    if current_page_num < total_pages:
        return redirect(url_for("verify_batch_page", batch_id=batch_id, page=current_page_num + 1))
    else:
        # If this was the last page of the batch, the verification step is complete.
        # Update the batch status and redirect the user to the main dashboard.
        conn = get_db_connection()
        conn.execute("UPDATE batches SET status = 'verification_complete' WHERE id = ?", (batch_id,))
        conn.commit()
        conn.close()
        return redirect(url_for("mission_control_page"))


@app.route("/delete_page/<int:page_id>", methods=["POST"])
def delete_page_action(page_id):
    """
    Permanently deletes a page record from the database and its associated image file
    from the filesystem. This action is typically available on the 'review' page
    for pages deemed unrecoverable, irrelevant, or duplicates.
    """
    batch_id = request.form.get("batch_id")
    # The deletion logic is handled in the database module to ensure atomicity and file cleanup.
    delete_page_by_id(page_id)
    # Redirect back to the review page to continue reviewing other flagged pages.
    return redirect(url_for("review_batch_page", batch_id=batch_id))


@app.route("/rerun_ocr", methods=["POST"])
def rerun_ocr_action():
    """
    Handles a request to re-run the OCR process on a single page, optionally
    applying a rotation first. This is particularly useful if the initial OCR was poor
    due to the page being scanned upside down or sideways.
    """
    page_id = request.form.get("page_id", type=int)
    batch_id = request.form.get("batch_id", type=int)
    rotation = request.form.get("rotation", 0, type=int)
    # The `rerun_ocr_on_page` function in `processing.py` handles the image manipulation
    # and the call to the OCR engine.
    rerun_ocr_on_page(page_id, rotation)
    # After re-running OCR, the user is returned to the review page to see the updated OCR text.
    return redirect(url_for("review_batch_page", batch_id=batch_id))


# --- UTILITY ROUTES ---
# These routes provide helper functionalities, such as securely serving files.

@app.route("/processed_files/<path:filepath>")
def serve_processed_file(filepath):
    """
    A utility route designed to securely serve processed image files (PNGs) to the browser.
    Using Flask's `send_from_directory` is a security best practice as it ensures that
    only files from within the specified `PROCESSED_DIR` can be accessed, effectively
    preventing directory traversal attacks.
    """
    processed_dir = os.getenv("PROCESSED_DIR")
    return send_from_directory(processed_dir, filepath)


# --- FINALIZATION AND EXPORT ROUTES ---
# These routes handle the last stage of the workflow: naming and exporting documents.

@app.route("/finalize/<int:batch_id>")
def finalize_batch_page(batch_id):
    """
    Displays the finalization screen where users can review and edit AI-suggested filenames
    for each document before the final export. This is the last opportunity to make changes
    before the files are written to the "filing cabinet" directory.
    """
    documents_raw = get_documents_for_batch(batch_id)
    documents_for_render = []

    for doc in documents_raw:
        pages = get_pages_for_document(doc["id"])
        if not pages:
            continue  # Skip if a document somehow has no pages (should not happen in normal workflow).
        
        # Concatenate the full OCR text of all pages to provide the AI model with maximum context
        # for generating a descriptive filename.
        full_doc_text = "\n---\n".join([p["ocr_text"] for p in pages])
        # The document's category is also passed to the AI to help generate a more relevant filename.
        doc_category = pages[0]["human_verified_category"]
        # Get an AI-suggested filename from the processing module.
        suggested_filename = get_ai_suggested_filename(full_doc_text, doc_category)
        
        doc_dict = dict(doc)
        doc_dict["suggested_filename"] = suggested_filename
        documents_for_render.append(doc_dict)

    # Renders the `finalize.html` template, which displays a list of documents,
    # each with an editable text input pre-filled with the AI-suggested filename.
    return render_template("finalize.html", batch_id=batch_id, documents=documents_for_render)


@app.route("/export_batch/<int:batch_id>", methods=["POST"])
def export_batch_action(batch_id):
    """
    Handles the final export process for all documents within a batch.
    This route receives the final list of document IDs and their user-approved filenames
    from the finalization page.
    """
    doc_ids = request.form.getlist('document_ids', type=int)
    final_filenames = request.form.getlist('final_filenames')

    # The form submits parallel lists of document IDs and their corresponding final filenames.
    # `zip` is used to iterate over them simultaneously, processing each document.
    for doc_id, final_name in zip(doc_ids, final_filenames):
        pages = get_pages_for_document(doc_id)
        if not pages:
            print(f"Skipping export for document ID {doc_id}: No pages found.")
            continue
        
        category = pages[0]['human_verified_category']
        # Extract the base filename (without extension) from the user-provided final name.
        final_name_base = os.path.splitext(final_name)[0]

        # Save the final, user-approved filename to the database for record-keeping
        # and for the "view exported documents" feature.
        update_document_final_filename(doc_id, final_name_base)
        # Delegate the actual creation of the final PDF and log files to the `export_document` function in `processing.py`.
        export_document(pages, final_name_base, category)

    # After all documents are exported, delete the temporary files (e.g., intermediate PNGs)
    # associated with the batch to free up disk space.
    cleanup_batch_files(batch_id)

    # Mark the batch as 'Exported', its final status in the workflow.
    conn = get_db_connection()
    conn.execute("UPDATE batches SET status = 'Exported' WHERE id = ?", (batch_id,))
    conn.commit()
    conn.close()

    # Redirect the user back to the main dashboard.
    return redirect(url_for("mission_control_page"))


# --- VIEW EXPORTED DOCUMENTS ROUTES ---
# This section provides routes for users to access and download the final exported files.

@app.route('/view_documents/<int:batch_id>')
def view_documents_page(batch_id):
    """
    Displays a list of all documents that have been exported for a given batch,
    providing direct download links to the final PDF and log files.
    """
    documents = get_documents_for_batch(batch_id)
    docs_with_paths = []
    for doc in documents:
        doc_dict = dict(doc)
        if doc_dict.get("final_filename_base"):
            pages = get_pages_for_document(doc_dict["id"])
            if pages:
                category = pages[0]['human_verified_category']
                # Sanitize the category name to match the folder naming convention used during export.
                category_dir_name = "".join(c for c in category if c.isalnum() or c in (' ', '-', '_')).rstrip().replace(' ', '_')
                base = doc_dict["final_filename_base"]
                
                # Construct relative paths for the various exported files.
                doc_dict['pdf_path'] = os.path.join(category_dir_name, f"{base}.pdf")
                doc_dict['ocr_pdf_path'] = os.path.join(category_dir_name, f"{base}_ocr.pdf")
                doc_dict['log_path'] = os.path.join(category_dir_name, f"{base}_log.md")
        docs_with_paths.append(doc_dict)

    return render_template("view_documents.html", documents=docs_with_paths, batch_id=batch_id)


@app.route('/download_export/<path:filepath>')
def download_export_file(filepath):
    """
    Securely serves an exported file for download from the `FILING_CABINET_DIR`.
    This route is essential for providing users with access to their final processed documents.
    """
    filing_cabinet_dir = os.getenv("FILING_CABINET_DIR")
    if not filing_cabinet_dir:
        # If the environment variable is not configured, the application cannot locate the files.
        abort(500, "FILING_CABINET_DIR is not configured.")
    
    # --- Critical Security Measure: Prevent Path Traversal Attacks ---
    # This ensures that the requested `filepath` is genuinely located within the intended
    # `filing_cabinet_dir` and prevents malicious users from attempting to access sensitive
    # files elsewhere on the server (e.g., using `../../` sequences).
    safe_base_path = os.path.abspath(filing_cabinet_dir)
    safe_filepath = os.path.abspath(os.path.join(safe_base_path, filepath))

    if not safe_filepath.startswith(safe_base_path):
        # If the constructed path attempts to go outside the allowed directory, return a 404 Not Found error.
        abort(404)

    # `send_from_directory` is the most robust and secure way to handle file downloads in Flask.
    directory = os.path.dirname(safe_filepath)
    filename = os.path.basename(safe_filepath)
    
    # `as_attachment=True` instructs the browser to prompt the user to download the file
    # rather than attempting to display it directly in the browser window.
    return send_from_directory(directory, filename, as_attachment=True)


# --- MAIN EXECUTION BLOCK ---

if __name__ == "__main__":
    """
    This block allows the Flask application to be run directly using `python app.py`.
    It starts the Flask development server, which is convenient for local testing and development.
    
    For a production deployment, a more robust and performant WSGI server (e.g., Gunicorn, uWSGI)
    would typically be used to serve the Flask application.
    """
    # `debug=True` enables several development-friendly features:
    # 1. Automatic code reloading when changes are detected.
    # 2. Provides detailed interactive debugger in the browser for errors.
    # This should **always** be set to `False` in a production environment for security and performance reasons.
    # `host="0.0.0.0"` makes the server accessible from any IP address on the network, not just localhost.
    # `port=5000` specifies the port on which the server will listen for incoming requests.
    app.run(debug=True, host="0.0.0.0", port=5000)