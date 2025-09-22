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
)

# Local application imports
from processing import (
    process_batch,
    rerun_ocr_on_page,
    BROAD_CATEGORIES,
    get_ai_suggested_order,
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
    reset_batch_to_start,  # <-- Import the new reset function
)

# Initialize the Flask application
app = Flask(__name__)
# Set a secret key for session management, essential for flashing messages and other session-based functionality.
# os.urandom(24) generates a secure, random key each time the app starts.
app.secret_key = os.urandom(24)


# --- CORE NAVIGATION AND WORKFLOW ROUTES ---

@app.route("/")
def index():
    """
    The root URL of the application.
    Redirects the user to the main "Mission Control" page.
    """
    return redirect(url_for("mission_control_page"))


@app.route("/process_new_batch", methods=["POST"])
def handle_batch_processing():
    """
    Handles the POST request to start processing a new batch of documents.
    This is typically triggered by a button on the Mission Control page.
    It calls the main processing function and then redirects back to Mission Control.
    """
    # The core logic for processing files is in the 'processing.py' module.
    process_batch()
    # After processing, refresh the Mission Control page to show the new batch.
    return redirect(url_for("mission_control_page"))


@app.route("/mission_control")
def mission_control_page():
    """
    Displays the main dashboard, showing a list of all processed batches.
    For each batch, it fetches and displays key statistics like the number of
    flagged pages and ungrouped verified pages.
    """
    # Establish a database connection.
    conn = get_db_connection()
    # Fetch all batches from the database, newest first.
    all_batches_raw = conn.execute("SELECT * FROM batches ORDER BY id DESC").fetchall()
    conn.close()

    # Process the raw database rows into a more usable list of dictionaries.
    all_batches = []
    for batch in all_batches_raw:
        batch_dict = dict(batch)
        batch_id = batch_dict["id"]
        # Augment the batch data with counts of flagged and ungrouped pages.
        batch_dict["flagged_count"] = count_flagged_pages_for_batch(batch_id)
        batch_dict["ungrouped_count"] = count_ungrouped_verified_pages(batch_id)
        all_batches.append(batch_dict)

    # Render the main dashboard template with the list of batches.
    return render_template("mission_control.html", batches=all_batches)


# --- DIRECT ACTION ROUTES (Accessed from Mission Control) ---

@app.route("/verify/<int:batch_id>")
def verify_batch_page(batch_id):
    """
    The first step in the manual workflow: page-by-page verification.
    Allows the user to review each page of a batch, correct the AI-suggested
    category, and flag pages for later review.
    """
    # If the batch has already been verified, redirect to the 'revisit' view.
    batch = get_batch_by_id(batch_id)
    if batch and batch["status"] != "pending_verification":
        return redirect(url_for("revisit_batch_page", batch_id=batch_id))

    # Fetch all pages associated with this batch.
    pages = get_pages_for_batch(batch_id)
    if not pages:
        # If no pages are found, redirect back to Mission Control with a message.
        return redirect(
            url_for(
                "mission_control_page", message=f"No pages found for Batch #{batch_id}."
            )
        )

    # Get the base directory for processed images to construct relative paths.
    processed_dir = os.getenv("PROCESSED_DIR")
    # Create relative paths for images to be used in the HTML templates.
    pages_with_relative_paths = [
        dict(
            p,
            relative_image_path=os.path.relpath(
                p["processed_image_path"], processed_dir
            ),
        )
        for p in pages
    ]

    # Implement pagination to show one page at a time.
    page_num = request.args.get("page", 1, type=int)
    if not 1 <= page_num <= len(pages_with_relative_paths):
        page_num = 1  # Default to the first page if the page number is invalid.
    current_page = pages_with_relative_paths[page_num - 1]

    # Get all existing categories from the database and combine with the default broad categories.
    db_categories = get_all_unique_categories()
    combined_categories = sorted(list(set(BROAD_CATEGORIES + db_categories)))

    # Render the verification template.
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
    verification step. This provides a focused view to handle problematic pages.
    """
    # Fetch only the pages that have been flagged for this batch.
    flagged_pages = get_flagged_pages_for_batch(batch_id)
    if not flagged_pages:
        # If there are no flagged pages, there's nothing to review.
        return redirect(url_for("mission_control_page"))

    batch = get_batch_by_id(batch_id)

    # Create relative image paths for the template.
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

    # Prepare the list of categories for the dropdown menus.
    db_categories = get_all_unique_categories()
    combined_categories = sorted(list(set(BROAD_CATEGORIES + db_categories)))

    # Render the review template.
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
    been verified, without being able to change their status again.
    This is a read-only view of a completed verification step.
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

    # Pagination for revisiting pages.
    page_num = request.args.get("page", 1, type=int)
    if not 1 <= page_num <= len(pages_with_relative_paths):
        page_num = 1
    current_page = pages_with_relative_paths[page_num - 1]

    db_categories = get_all_unique_categories()
    combined_categories = sorted(list(set(BROAD_CATEGORIES + db_categories)))

    return render_template(
        "revisit.html",
        batch_id=batch_id,
        batch=batch,
        current_page=current_page,
        current_page_num=page_num,
        total_pages=len(pages_with_relative_paths),
        categories=combined_categories,
    )

# --- NEW ROUTE FOR READ-ONLY VIEW ---

@app.route("/view/<int:batch_id>")
def view_batch_page(batch_id):
    """
    Provides a strictly read-only view of all pages in a completed batch.
    This page is for reviewing the final state of a batch without the ability
    to make any changes.
    """
    # Fetch all pages associated with this batch.
    pages = get_pages_for_batch(batch_id)
    # If for some reason a completed batch has no pages, redirect to Mission Control.
    if not pages:
        return redirect(
            url_for(
                "mission_control_page", message=f"No pages found for Batch #{batch_id}."
            )
        )

    # Fetch the batch object itself to display its status.
    batch = get_batch_by_id(batch_id)
    # Get the base directory for processed images to construct relative paths for the HTML.
    processed_dir = os.getenv("PROCESSED_DIR")
    # Create a list of page dictionaries, adding the relative image path to each.
    pages_with_relative_paths = [
        dict(
            p,
            relative_image_path=os.path.relpath(
                p["processed_image_path"], processed_dir
            ),
        )
        for p in pages
    ]

    # Implement pagination to show one page at a time.
    page_num = request.args.get("page", 1, type=int)
    # Ensure the page number is valid, defaulting to 1 if it's out of bounds.
    if not 1 <= page_num <= len(pages_with_relative_paths):
        page_num = 1
    # Get the specific page to display based on the page number.
    current_page = pages_with_relative_paths[page_num - 1]

    # Render the new, dedicated read-only template.
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
    The second step of the workflow: grouping verified pages into documents.
    This page displays all verified pages, grouped by their assigned category,
    allowing the user to select pages and create a single document from them.
    """
    # Fetch all verified pages that have not yet been assigned to a document.
    ungrouped_pages_data = get_verified_pages_for_grouping(batch_id)
    # Fetch documents that have already been created for this batch to display them.
    created_docs = get_created_documents_for_batch(batch_id)

    # Create relative image paths for all the ungrouped pages.
    processed_dir = os.getenv("PROCESSED_DIR")
    for category, pages in ungrouped_pages_data.items():
        for i, page in enumerate(pages):
            page_dict = dict(page)
            page_dict["relative_image_path"] = os.path.relpath(
                page["processed_image_path"], processed_dir
            )
            ungrouped_pages_data[category][i] = page_dict

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
    This page lists all documents that have more than one page.
    If a batch contains only single-page documents, it bypasses this step
    and finalizes the batch automatically.
    """
    all_documents = get_documents_for_batch(batch_id)

    # Filter for documents that actually need ordering (more than one page).
    docs_to_order = [doc for doc in all_documents if doc["page_count"] > 1]

    # If all documents were single-page, they are considered "ordered" by default.
    # The batch status is updated and the user is redirected.
    if not docs_to_order:
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
    GET: Displays the UI with draggable pages for ordering.
    POST: Receives the new page order and saves it to the database.
    """
    # Get the batch_id for redirection after the process is complete.
    conn = get_db_connection()
    batch_id = conn.execute(
        "SELECT batch_id FROM documents WHERE id = ?", (document_id,)
    ).fetchone()["batch_id"]
    conn.close()

    if request.method == "POST":
        # The new order is submitted as a comma-separated string of page IDs.
        ordered_page_ids = request.form.get("page_order").split(",")
        # Sanitize the list to ensure they are all integers.
        page_ids_as_int = [int(pid) for pid in ordered_page_ids if pid.isdigit()]
        # Update the sequence in the database.
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
    return render_template(
        "order_document.html", document_id=document_id, pages=pages, batch_id=batch_id
    )


# --- API AND FORM ACTION ROUTES ---

@app.route("/finalize_batch/<int:batch_id>", methods=["POST"])
def finalize_batch_action(batch_id):
    """
    A final action to mark the entire ordering step for a batch as complete.
    This is typically used when a user manually confirms the order of all documents.
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
    It uses an AI model to suggest the correct order of pages for a document.
    """
    pages = get_pages_for_document(document_id)
    if not pages:
        return jsonify({"error": "Document not found or has no pages."}), 404

    # The core AI ordering logic is in the 'processing.py' module.
    suggested_order = get_ai_suggested_order(pages)

    if suggested_order:
        # Return the suggested order as a JSON list of page IDs.
        return jsonify({"success": True, "page_order": suggested_order})
    else:
        # If the AI fails, return an error.
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
    from a selection of pages.
    """
    batch_id = request.form.get("batch_id", type=int)
    document_name = request.form.get("document_name", "").strip()
    page_ids = request.form.getlist("page_ids", type=int)

    # Basic validation.
    if not document_name or not page_ids:
        return redirect(
            url_for(
                "group_batch_page",
                batch_id=batch_id,
                error="Document name and at least one page are required.",
            )
        )

    # Create the document and link the selected pages to it.
    create_document_and_link_pages(batch_id, document_name, page_ids)

    # If all verified pages in the batch have now been grouped, update the batch status.
    if count_ungrouped_verified_pages(batch_id) == 0:
        conn = get_db_connection()
        conn.execute(
            "UPDATE batches SET status = 'grouping_complete' WHERE id = ?", (batch_id,)
        )
        conn.commit()
        conn.close()

    return redirect(url_for("group_batch_page", batch_id=batch_id))


@app.route("/reset_grouping/<int:batch_id>", methods=["POST"])
def reset_grouping_action(batch_id):
    """
    Allows the user to undo the grouping for an entire batch.
    This deletes all documents created for the batch, returning the pages
    to their ungrouped, verified state.
    """
    reset_batch_grouping(batch_id)
    return redirect(url_for("group_batch_page", batch_id=batch_id))


# --- NEW ROUTE FOR RESET BATCH FEATURE ---

@app.route("/reset_batch/<int:batch_id>", methods=["POST"])
def reset_batch_action(batch_id):
    """
    Handles the action to completely reset a batch to the 'pending_verification' state.
    This is a destructive action for any verification, grouping, or ordering work.

    Args:
        batch_id (int): The ID of the batch to reset.
    """
    # The core logic is encapsulated in the database function for safety and reusability.
    reset_batch_to_start(batch_id)
    # After the reset, send the user back to the main dashboard.
    return redirect(url_for("mission_control_page"))


@app.route("/update_page", methods=["POST"])
def update_page():
    """
    Handles form submissions from the 'verify' and 'review' pages to update
    the status, category, and rotation of a single page.
    """
    # Extract all data from the submitted form.
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

    # Determine the new status and category based on the user's action.
    if action == "flag":
        status = "flagged"
        category = "NEEDS_REVIEW"
    else:
        status = "verified"
        # Handle category selection: a new category can be created on the fly.
        if dropdown_choice == "other_new" and other_choice:
            category = other_choice
        elif dropdown_choice and dropdown_choice != "other_new":
            category = dropdown_choice
        else:
            # Default to the AI's suggestion if no other choice is made.
            category = request.form.get("ai_suggestion")

    # Save the updated page data to the database.
    update_page_data(page_id, category, status, rotation)

    # --- Redirection Logic ---
    # Redirect back to the appropriate page based on where the user came from.
    if "revisit" in request.referrer:
        return redirect(
            url_for("revisit_batch_page", batch_id=batch_id, page=current_page_num)
        )
    if "review" in request.referrer:
        return redirect(url_for("review_batch_page", batch_id=batch_id))

    # If in the main verification flow, proceed to the next page or finish.
    if current_page_num < total_pages:
        return redirect(
            url_for("verify_batch_page", batch_id=batch_id, page=current_page_num + 1)
        )
    else:
        # If this was the last page, mark the batch verification as complete.
        conn = get_db_connection()
        conn.execute(
            "UPDATE batches SET status = 'verification_complete' WHERE id = ?",
            (batch_id,),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("mission_control_page"))


@app.route("/delete_page/<int:page_id>", methods=["POST"])
def delete_page_action(page_id):
    """
    Permanently deletes a page from the database and filesystem.
    This action is typically available on the 'review' page for pages
    that are unrecoverable or irrelevant.
    """
    batch_id = request.form.get("batch_id")
    delete_page_by_id(page_id)
    return redirect(url_for("review_batch_page", batch_id=batch_id))


@app.route("/rerun_ocr", methods=["POST"])
def rerun_ocr_action():
    """
    Handles a request to re-run the OCR process on a single page,
    optionally applying a rotation. This is useful if the initial OCR
    was poor due to incorrect page orientation.
    """
    page_id = request.form.get("page_id", type=int)
    batch_id = request.form.get("batch_id", type=int)
    rotation = request.form.get("rotation", 0, type=int)
    rerun_ocr_on_page(page_id, rotation)
    return redirect(url_for("review_batch_page", batch_id=batch_id))


# --- UTILITY ROUTES ---

@app.route("/processed_files/<path:filepath>")
def serve_processed_file(filepath):
    """
    A utility route to serve the processed image files (PNGs) to the browser.
    Flask's 'send_from_directory' is used for security to ensure that only
    files from the intended directory can be accessed.
    """
    processed_dir = os.getenv("PROCESSED_DIR")
    return send_from_directory(processed_dir, filepath)


# --- MAIN EXECUTION ---

if __name__ == "__main__":
    """
    This block runs the Flask development server when the script is executed directly.
    - debug=True: Enables debug mode, which provides detailed error pages and auto-reloads the server on code changes.
    - host='0.0.0.0': Makes the server accessible from any IP address on the network, not just localhost.
    - port=5000: The port the server will listen on.
    """
    app.run(debug=True, host="0.0.0.0", port=5000)