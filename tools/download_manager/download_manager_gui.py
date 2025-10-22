import requests # Used for making HTTP requests (GET, HEAD) to download files and get file information.
from bs4 import BeautifulSoup # Used for parsing HTML content to find file links in directory listings.
import os # Provides functions for interacting with the operating system, like creating directories and checking file sizes.
from urllib.parse import urljoin, urlparse, unquote # Utilities for manipulating URLs:
                                                  # urljoin: Combines a base URL with a relative URL.
                                                  # urlparse: Parses a URL into components (scheme, netloc, path, etc.).
                                                  # unquote: Decodes URL-encoded characters (e.g., %20 to space).
import time # Provides time-related functions, specifically used for `time.sleep()` for retry delays.
import tkinter as tk # The standard Python interface to the Tk GUI toolkit. Used for creating the application window and widgets.
from tkinter import filedialog, messagebox # Specific Tkinter modules:
                                         # filedialog: Provides common dialog boxes for file/directory selection.
                                         # messagebox: Provides standard message boxes (e.g., error, info).
from tkinter import ttk # Tkinter "themed widgets" extension, providing more modern-looking widgets like Progressbar.
import threading # Used to run the download process in a separate thread, preventing the GUI from freezing.
import re # Used for regular expressions, specifically for filename sanitization.
import tempfile # Provides functions for creating temporary files and directories.

# --- Configuration Constants ---
# These constants define various parameters for the downloader, making them easy to adjust.
MAX_RETRIES = 3 # Maximum number of times to retry a failed file download.
RETRY_DELAY_SECONDS = 5 # Time in seconds to wait before retrying a failed download.
INITIAL_REQUEST_TIMEOUT_SECONDS = 10 # Timeout for the initial HTTP GET request to fetch the directory listing.
FILE_DOWNLOAD_TIMEOUT_SECONDS = 30 # Timeout for individual file download requests.
HEAD_REQUEST_TIMEOUT_SECONDS = 5 # Timeout for HEAD requests used to get file sizes.
CHUNK_SIZE_BYTES = 8192 # Size of data chunks read from the network and written to disk during download.

# Global flag to signal cancellation across threads.
# `threading.Event` is a thread-safe way to communicate between the main GUI thread
# and the download thread. `set()` signals, `clear()` resets, `is_set()` checks.
cancel_flag = threading.Event()

# --- Security Enhancement: Filename Sanitization ---
# This function removes or replaces characters that are typically invalid or problematic
# in filenames across various operating systems (e.g., Windows, Linux).
def sanitize_filename(filename: str) -> str:
    """
    Sanitizes a string to be used as a safe filename.
    Removes characters that are illegal or reserved in common file systems.
    """
    # Define a regular expression pattern for characters that are generally
    # illegal in filenames on Windows and often problematic on Linux.
    # <>:"/\|?* are common illegal characters.
    # \x00-\x1f are control characters.
    invalid_chars_pattern = r'[<>:"/\\|?*\x00-\x1f]'

    # Replace invalid characters with an underscore.
    sanitized = re.sub(invalid_chars_pattern, '_', filename)

    # Also, remove leading/trailing spaces and periods, which can be problematic on Windows.
    sanitized = sanitized.strip().strip('.')

    # Ensure the filename is not empty after sanitization.
    if not sanitized:
        sanitized = "unnamed_file" # Provide a fallback name if sanitization results in an empty string.

    return sanitized

def get_file_list_with_sizes(url: str, status_callback=None) -> list:
    """
    Fetches the HTML directory listing from the given URL and extracts file links.
    For each file, it attempts to determine its size using HTTP HEAD requests.
    If a HEAD request fails, it falls back to a GET request to try and get the size
    from the 'Content-Length' header.

    Args:
        url (str): The URL of the directory listing (e.g., "https://example.com/files/").
        status_callback (callable, optional): A function (e.g., a GUI method) to call
                                              with string messages to update the application's status log.
                                              Defaults to None, which means messages are printed to console.

    Returns:
        list: A list of dictionaries. Each dictionary represents a file and contains:
              - 'file_name' (str): The URL-decoded and sanitized name of the file.
              - 'file_url' (str): The absolute URL of the file.
              - 'size' (int): The estimated size of the file in bytes. Defaults to 0
                              if the size cannot be determined or if the request fails.
    """
    # Helper function to send status messages, either to a callback or to the console.
    def update_status(message: str):
        if status_callback:
            status_callback(message)
        else:
            print(message)

    update_status(f"Scanning directory for file sizes from: {url}")
    files_to_download = [] # Initialize an empty list to store file information.

    try:
        # Send an HTTP GET request to the provided URL to get the directory listing HTML.
        # `stream=True` means the response content is not immediately downloaded.
        # `timeout` prevents the request from hanging indefinitely.
        response = requests.get(url, stream=True, timeout=INITIAL_REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx status codes).
    except requests.exceptions.RequestException as e:
        # Catch any request-related errors (e.g., network issues, invalid URL).
        update_status(f"Error fetching directory listing {url}: {e}")
        return [] # Return an empty list if the initial fetch fails.

    # Parse the HTML content of the directory listing using BeautifulSoup.
    soup = BeautifulSoup(response.text, 'html.parser')
    links = soup.find_all('a') # Find all anchor (`<a>`) tags, which typically represent links.

    for link in links:
        # Check if a cancellation signal has been received from the GUI thread.
        if cancel_flag.is_set():
            update_status("Scan cancelled by user.")
            return [] # Exit early if cancelled.

        href = link.get('href') # Get the `href` attribute value from the anchor tag.
        if not href:
            continue # Skip links that don't have an href (e.g., empty tags).

        # Skip links that point to the parent directory ('../') or are themselves directories (end with '/').
        if href == '../' or href.endswith('/'):
            continue

        # Construct the full, absolute URL for the file. `urljoin` handles relative paths correctly.
        file_url = urljoin(url, href)
        # Extract the base filename from the URL path, URL-decode it, and then sanitize it.
        file_name = sanitize_filename(unquote(os.path.basename(urlparse(file_url).path)))

        # --- Robust check for problematic file names (retained and enhanced) ---
        # Ensure file_name is not empty or a problematic path component (like '.' or '..')
        # or contains path separators (which would indicate it's a directory or malformed).
        # The `sanitize_filename` function already handles many of these, but this provides
        # an extra layer of explicit checking.
        if not file_name or file_name in ['.', '..'] or os.path.sep in file_name or os.path.altsep in file_name:
            update_status(f"Skipping problematic or sanitized-to-empty file name: '{file_name}' derived from URL: {file_url}")
            continue


        file_size = 0 # Initialize file size to 0.

        try:
            # --- Attempt to get file size using a HEAD request ---
            # A HEAD request only asks for the headers of a resource, not the content.
            # This is efficient for getting 'Content-Length' without downloading the file.
            head_response = requests.head(file_url, timeout=HEAD_REQUEST_TIMEOUT_SECONDS)
            update_status(f"DEBUG: HEAD request for {file_name} - Status: {head_response.status_code}")
            update_status(f"DEBUG: HEAD headers: {head_response.headers}") # Log all headers for debugging.
            head_response.raise_for_status() # Raise an exception for bad status codes.

            content_length = head_response.headers.get('content-length') # Get the 'Content-Length' header.
            if content_length:
                file_size = int(content_length) # Convert content length to an integer.
            update_status(f"Scanned: {file_name} (Size: {file_size / (1024*1024):.2f} MB)")
        except requests.exceptions.RequestException as e:
            # If the HEAD request fails (e.g., server doesn't support HEAD, network error).
            update_status(f"Warning: HEAD request failed for {file_name} (Error: {e}). Attempting GET for size.")
            # --- Fallback to GET request for size determination ---
            try:
                # Make a GET request, but set `stream=True` and a small timeout to avoid downloading the whole file.
                # We are only interested in the headers here.
                get_response_for_size = requests.get(file_url, stream=True, timeout=HEAD_REQUEST_TIMEOUT_SECONDS)
                get_response_for_size.raise_for_status()
                content_length = get_response_for_size.headers.get('content-length')
                if content_length:
                    file_size = int(content_length)
                update_status(f"Scanned (GET fallback): {file_name} (Size: {file_size / (1024*1024):.2f} MB)")
            except requests.exceptions.RequestException as e_get:
                update_status(f"Warning: Could not get size for {file_name} even with GET fallback (Error: {e_get}). Assuming 0 size.")
            except ValueError:
                update_status(f"Warning: Invalid Content-Length for {file_name} (GET fallback). Assuming 0 size.")
        except ValueError:
            # If 'Content-Length' header exists but is not a valid integer.
            update_status(f"Warning: Invalid Content-Length for {file_name} (HEAD). Assuming 0 size.")

        # Add the file's information to the list.
        files_to_download.append({
            'file_name': file_name,
            'file_url': file_url,
            'size': file_size
        })
    update_status("Finished scanning directory.")
    return files_to_download

def download_files_from_url(url: str, download_dir: str, max_retries: int = MAX_RETRIES,
                            retry_delay: int = RETRY_DELAY_SECONDS, status_callback=None, progress_callback=None):
    """
    Downloads all files from a given URL's directory listing to a specified local directory.
    It includes retry mechanisms for failed downloads, skips already complete files,
    and supports resuming partial downloads using HTTP Range headers.

    Args:
        url (str): The base URL of the directory listing.
        download_dir (str): The local directory path where files will be saved.
        max_retries (int): Maximum number of retries for each individual file download.
        retry_delay (int): Delay in seconds between retry attempts.
        status_callback (callable, optional): Function for general status updates.
        progress_callback (callable, optional): Function for detailed progress updates,
                                                receiving (file_name, downloaded_bytes_current_file,
                                                actual_total_file_bytes, files_processed_count, total_files_count).
    """
    def update_status(message: str):
        if status_callback:
            status_callback(message)
        else:
            print(message)

    def update_progress(file_name: str, downloaded_bytes: int, total_file_bytes: int,
                        files_processed_count: int, total_files_count: int):
        if progress_callback:
            progress_callback(file_name, downloaded_bytes, total_file_bytes, files_processed_count, total_files_count)

    # Ensure the target download directory exists. If not, create it.
    if not os.path.exists(download_dir):
        try:
            os.makedirs(download_dir)
            update_status(f"Created download directory: {download_dir}")
        except OSError as e:
            update_status(f"Error creating directory {download_dir}: {e}")
            return # Exit if directory creation fails.

    # Step 1: Get the list of files and their estimated sizes from the URL.
    files_to_download = get_file_list_with_sizes(url, status_callback)
    # If no files are found or the scan was cancelled, abort the download process.
    if not files_to_download and not cancel_flag.is_set():
        update_status("No files found or scan failed. Aborting download.")
        return

    total_files_count = len(files_to_download) # Total number of files identified for processing.
    files_processed_count = 0 # Counter for files that are either skipped (already complete) or successfully downloaded.

    # Adjust `files_processed_count` based on files that already exist and are non-empty.
    # This ensures accurate total progress display from the start if resuming a previous session.
    for file_info in files_to_download:
        file_path = os.path.join(download_dir, file_info['file_name'])
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            files_processed_count += 1
            update_status(f"Adjusting total progress for existing file: {file_info['file_name']}")

    update_status(f"Total files to process: {total_files_count}")
    # Initial progress update to reflect any already processed/existing files.
    update_progress("N/A", 0, 0, files_processed_count, total_files_count)

    # Iterate through each file identified in the directory listing.
    for file_info in files_to_download:
        # Check for cancellation signal before starting processing of each new file.
        if cancel_flag.is_set():
            update_status("Download cancelled by user.")
            break # Exit the loop if cancelled.

        file_name = file_info['file_name']
        file_url = file_info['file_url']
        total_file_bytes_estimated = file_info['size'] # Estimated size from HEAD/GET fallback.
        file_path = os.path.join(download_dir, file_name) # Full local path for the file.

        # --- Resume/Skip Logic ---
        if os.path.exists(file_path):
            current_file_size = os.path.getsize(file_path) # Get the current size of the local file.
            if current_file_size > 0:
                # If the file exists and is not empty, assume it's complete and skip.
                update_status(f"Skipping: {file_name} (already downloaded and non-empty)")
                continue # Move to the next file in the list.
            else:
                # If the file exists but is empty (0 bytes), it indicates a previous failed/stuck download.
                update_status(f"Found empty file: {file_name}. Will attempt to re-download.")
                try:
                    os.remove(file_path) # Remove the empty file to ensure a clean re-download.
                    update_status(f"Removed empty file: {file_name}")
                except OSError as e:
                    update_status(f"Warning: Could not remove empty file {file_name}: {e}. Attempting to overwrite.")

        # --- Retry Logic for File Download ---
        # Attempt to download the file multiple times if it fails.
        for attempt in range(max_retries):
            # Check for cancellation signal before each retry attempt.
            if cancel_flag.is_set():
                update_status("Download cancelled by user.")
                break # Exit the retry loop if cancelled.

            update_status(f"Downloading: {file_name} (Attempt {attempt + 1}/{max_retries})")
            downloaded_bytes_current_file = 0 # Bytes downloaded for the current file in this specific attempt.
            headers = {} # Initialize headers dictionary for the request.

            try:
                # Implement partial download resume using HTTP Range header.
                # If a partial file exists locally, set the 'Range' header to request only the missing bytes.
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    downloaded_bytes_current_file = os.path.getsize(file_path) # Get current size of partial file.
                    headers['Range'] = f'bytes={downloaded_bytes_current_file}-' # Request bytes from this offset to end.
                    update_status(f"Resuming download of {file_name} from {downloaded_bytes_current_file} bytes.")

                # Send the GET request for the file.
                # `stream=True` is crucial for downloading large files in chunks.
                # `timeout` prevents the download from hanging.
                # `headers` include the Range header if resuming.
                with requests.get(file_url, stream=True, timeout=FILE_DOWNLOAD_TIMEOUT_SECONDS, headers=headers) as r:
                    r.raise_for_status() # Check for HTTP errors (4xx/5xx).

                    actual_total_file_bytes = total_file_bytes_estimated # Start with estimated size as fallback.

                    # Check if the server responded with "206 Partial Content", indicating successful resume.
                    if r.status_code == 206:
                        update_status(f"Server supports resume for {file_name}.")
                        content_range = r.headers.get('Content-Range')
                        if content_range:
                            try:
                                # Parse 'Content-Range' header (e.g., "bytes 0-100/200") to get the total file size.
                                total_file_bytes_from_range = int(content_range.split('/')[-1])
                                actual_total_file_bytes = total_file_bytes_from_range # Use actual total size from server.
                            except ValueError:
                                update_status(f"Warning: Invalid Content-Range header for {file_name}.")
                        # If Content-Range is missing, stick with estimated size.
                    else: # Server responded with 200 OK or other status (not 206).
                        actual_total_file_bytes = int(r.headers.get('content-length', total_file_bytes_estimated))
                        # If we tried to resume (downloaded_bytes_current_file > 0) but got 200 OK,
                        # it means the server ignored our Range header and sent the whole file from the start.
                        if downloaded_bytes_current_file > 0 and r.status_code == 200:
                            update_status(f"Server ignored resume request for {file_name}. Restarting download.")
                            downloaded_bytes_current_file = 0 # Reset downloaded bytes as we're starting over.
                            # Overwrite the file if the server didn't resume (truncate it).
                            with open(file_path, 'wb') as f:
                                pass # This effectively clears the file.

                    # Open the local file: 'ab' for append (if resuming), 'wb' for write (if new download/restart).
                    mode = 'ab' if downloaded_bytes_current_file > 0 and r.status_code == 206 else 'wb'

                    # DEBUG: Print the final file_path before attempting to open
                    update_status(f"DEBUG: Attempting to open file_path: '{file_path}' in mode '{mode}'")

                    with open(file_path, mode) as f:
                        # Iterate over the response content in chunks.
                        for chunk in r.iter_content(chunk_size=CHUNK_SIZE_BYTES): # Corrected from CHUNK_BYTES
                            # Check for cancellation signal during the actual chunk download.
                            if cancel_flag.is_set():
                                update_status(f"Cancelled download of {file_name}.")
                                # Clean up the partially downloaded file if cancelled to avoid corrupted files.
                                if os.path.exists(file_path):
                                    try:
                                        os.remove(file_path)
                                        update_status(f"Removed partial file: {file_name}")
                                    except OSError as e:
                                        update_status(f"Error removing partial file {file_name}: {e}")
                                return # Exit the function immediately after cancellation.

                            f.write(chunk) # Write the downloaded chunk to the file.
                            downloaded_bytes_current_file += len(chunk) # Update bytes downloaded for current file.
                            # Update GUI progress: current file's progress and overall file count progress.
                            update_progress(file_name, downloaded_bytes_current_file, actual_total_file_bytes,
                                            files_processed_count, total_files_count)

                update_status(f"Successfully downloaded: {file_name}")
                files_processed_count += 1 # Increment total processed files count only on successful completion.
                break # Break out of the retry loop because the download was successful.
            except requests.exceptions.RequestException as e:
                # Handle network-related errors during download.
                update_status(f"Error downloading {file_name}: {e}")
                if attempt < max_retries - 1: # If there are retries left.
                    update_status(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay) # Wait before retrying.
                else:
                    update_status(f"Failed to download {file_name} after {max_retries} attempts.")
            except IOError as e:
                # Handle errors related to writing the file to disk.
                update_status(f"Error saving {file_name} to disk: {e}")
                if attempt < max_retries - 1: # If there are retries left.
                    update_status(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay) # Wait before retrying.
                else:
                    update_status(f"Failed to save {file_name} after {max_retries} attempts.")

        # If the outer loop (over files) was broken due to a cancellation signal.
        if cancel_flag.is_set():
            break

    # Final status messages after all files have been processed or cancellation occurred.
    if files_processed_count == 0 and not cancel_flag.is_set():
        update_status("No files found or downloaded from the provided URL.")
    elif not cancel_flag.is_set():
        update_status(f"Finished processing {files_processed_count} files.")
    update_status("Download process completed.")
    # Reset the progress bar and labels in the GUI when the download process finishes or is cancelled.
    update_progress("", 0, 0, files_processed_count, total_files_count)


class DownloaderApp:
    """
    The main application class for the GUI-based file downloader.
    Manages the Tkinter window, widgets, and interaction logic.
    """
    def __init__(self, master):
        """
        Initializes the GUI application window and its components.

        Args:
            master (tk.Tk): The root Tkinter window.
        """
        self.master = master # Store the root window reference.
        master.title("File Downloader") # Set the window title.
        master.geometry("650x520") # Set initial window size (width x height).
        master.resizable(True, True) # Allow the user to resize the window.

        # Configure grid layout for better responsiveness.
        # Column 1 (where entry widgets are) expands horizontally.
        master.columnconfigure(1, weight=1)
        # Row 5 (where the log Text widget is) expands vertically.
        master.rowconfigure(6, weight=1) # Note: Adjusted row index due to new progress bar row

        # --- URL Input Section ---
        self.url_label = tk.Label(master, text="URL:")
        # Place label in grid: row 0, column 0, with padding and left alignment.
        self.url_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.url_entry = tk.Entry(master, width=60) # Entry widget for URL input.
        # Place entry in grid: row 0, column 1, with padding and horizontal expansion.
        self.url_entry.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        # Set a default URL for convenience.
        self.url_entry.insert(0, "https://myrient.erista.me/files/No-Intro/Nintendo%20-%20Game%20Boy%20Advance/")

        # --- Download Directory Input Section ---
        self.dir_label = tk.Label(master, text="Download To:")
        self.dir_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.dir_entry = tk.Entry(master, width=50) # Entry widget for download directory path.
        self.dir_entry.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        # Prefill download directory with safe default (env var or system temp) to avoid accidental repo writes.
        safe_default_dir = os.environ.get('DOWNLOAD_MANAGER_DIR') or tempfile.gettempdir()
        self.dir_entry.insert(0, safe_default_dir)

        self.browse_button = tk.Button(master, text="Browse", command=self.browse_directory)
        self.browse_button.grid(row=1, column=2, padx=5, pady=5)

        # --- Progress Display Section ---
        # Label to show the name of the file currently being downloaded.
        self.current_file_label = tk.Label(master, text="Current File: N/A")
        self.current_file_label.grid(row=2, column=0, columnspan=3, padx=10, pady=2, sticky="w")

        # Label to show the progress (percentage and bytes) of the current file.
        self.file_progress_label = tk.Label(master, text="File Progress: 0%")
        self.file_progress_label.grid(row=3, column=0, columnspan=3, padx=10, pady=2, sticky="w")

        # Label to show the overall progress by file count (e.g., "X/Y files (Z%)").
        self.total_progress_label = tk.Label(master, text="Total Progress: 0/0 files (0%)")
        self.total_progress_label.grid(row=4, column=0, columnspan=3, padx=10, pady=2, sticky="w")

        # Progress bar widget for the total download progress (visual representation).
        self.total_progressbar = ttk.Progressbar(master, orient="horizontal", length=500, mode="determinate")
        # `sticky="ew"` makes it expand horizontally with the window.
        self.total_progressbar.grid(row=5, column=0, columnspan=3, padx=10, pady=5, sticky="ew")


        # --- Status/Log Area Section ---
        self.status_label = tk.Label(master, text="Log:")
        self.status_label.grid(row=6, column=0, padx=10, pady=5, sticky="nw")
        # Text widget to display detailed status messages and logs.
        self.status_text = tk.Text(master, height=10, width=70, state='disabled', wrap='word')
        # `sticky="nsew"` allows it to expand in all directions with the window.
        self.status_text.grid(row=6, column=1, columnspan=2, padx=10, pady=5, sticky="nsew")
        # Scrollbar for the text widget.
        self.status_text_scroll = tk.Scrollbar(master, command=self.status_text.yview)
        # Place scrollbar to the right of the text widget.
        self.status_text_scroll.grid(row=6, column=3, sticky='ns', pady=5)
        # Link the scrollbar to the text widget.
        self.status_text['yscrollcommand'] = self.status_text_scroll.set

        # --- Control Buttons Section ---
        self.download_button = tk.Button(master, text="Download", command=self.start_download_thread)
        self.download_button.grid(row=7, column=1, pady=10)

        self.cancel_button = tk.Button(master, text="Cancel Download", command=self.cancel_download_process)
        self.cancel_button.grid(row=7, column=2, pady=10)
        self.cancel_button.config(state='disabled') # Initially disabled, enabled when download starts.

        self.quit_button = tk.Button(master, text="Quit Application", command=master.quit)
        self.quit_button.grid(row=7, column=0, pady=10) # Positioned for clarity.

    def browse_directory(self):
        """
        Opens a directory selection dialog and updates the download directory entry field.
        """
        directory = filedialog.askdirectory() # Opens the native directory browser.
        if directory: # If a directory was selected (not cancelled).
            self.dir_entry.delete(0, tk.END) # Clear current content of the entry.
            self.dir_entry.insert(0, directory) # Insert the selected directory path.

    def update_status_text(self, message: str):
        """
        Updates the log area (Text widget) with new status messages.
        Ensures the widget is editable, inserts text, auto-scrolls, and then disables it.
        `self.master.update_idletasks()` forces a GUI refresh immediately.

        Args:
            message (str): The status message to display.
        """
        self.status_text.config(state='normal') # Enable the text widget for writing.
        self.status_text.insert(tk.END, message + "\n") # Insert message at the end.
        self.status_text.see(tk.END) # Scroll to the end to show the latest message.
        self.status_text.config(state='disabled') # Disable the text widget to prevent user editing.
        self.master.update_idletasks() # Force GUI update to show message immediately.

    def update_file_progress(self, file_name: str, downloaded_bytes: int, total_file_bytes: int,
                             files_processed_count: int, total_files_count: int):
        """
        Updates the progress labels and the total progress bar in the GUI.

        Args:
            file_name (str): Name of the file currently being downloaded.
            downloaded_bytes (int): Bytes downloaded for the current file.
            total_file_bytes (int): Total bytes of the current file.
            files_processed_count (int): Number of files processed so far (skipped or downloaded).
            total_files_count (int): Total number of files to process.
        """
        # Update current file progress (percentage and bytes).
        if total_file_bytes > 0:
            file_percentage = (downloaded_bytes / total_file_bytes) * 100
            self.current_file_label.config(text=f"Current File: {file_name}")
            self.file_progress_label.config(text=f"File Progress: {file_percentage:.2f}% ({downloaded_bytes}/{total_file_bytes} bytes)")
        else:
            # Handle cases where file size is unknown.
            self.current_file_label.config(text=f"Current File: {file_name}")
            self.file_progress_label.config(text="File Progress: N/A (file size unknown)")

        # Update total download progress (by file count and percentage).
        if total_files_count > 0:
            total_percentage_files = (files_processed_count / total_files_count) * 100
            self.total_progress_label.config(text=f"Total Progress: {files_processed_count}/{total_files_count} files ({total_percentage_files:.2f}%)")
            self.total_progressbar['value'] = total_percentage_files # Update the actual progress bar.
        else:
            # Handle cases where no files are found or total count is 0.
            self.total_progress_label.config(text="Total Progress: 0/0 files (0%)")
            self.total_progressbar['value'] = 0 # Reset progress bar.

        self.master.update_idletasks() # Force GUI update.

    def start_download_thread(self):
        """
        Initiates the download process in a separate thread.
        This keeps the GUI responsive while files are being downloaded.
        Performs basic input validation before starting.
        """
        target_url = self.url_entry.get().strip() # Get URL from entry field.
        download_location = self.dir_entry.get().strip() # Get download directory from entry field.

        # Input validation.
        if not target_url:
            messagebox.showerror("Input Error", "Please enter a URL.")
            return
        if not download_location:
            messagebox.showerror("Input Error", "Please select a download directory.")
            return

        # --- Security Enhancement: HTTPS Enforcement ---
        # Warn the user if they are trying to download from an insecure HTTP URL.
        if not target_url.lower().startswith("https://"):
            response = messagebox.askyesno(
                "Security Warning",
                "You are attempting to download from an HTTP (insecure) URL. "
                "This could expose you to risks like corrupted files or malicious content. "
                "Do you want to proceed anyway?"
            )
            if not response: # If the user chooses NOT to proceed.
                self.update_status_text("Download aborted due to insecure URL.")
                return # Stop the download process.


        # Reset the global cancellation flag for a new download operation.
        cancel_flag.clear()

        self.update_status_text("Starting download process...")
        self.download_button.config(state='disabled') # Disable download button to prevent multiple simultaneous downloads.
        self.cancel_button.config(state='normal') # Enable cancel button.
        self.quit_button.config(state='disabled') # Disable quit button during download.
        self.update_file_progress("N/A", 0, 0, 0, 0) # Reset all progress displays at the start.

        # Create and start a new thread to run the `_run_download` method.
        # The `args` tuple passes the URL and download location to the thread's target function.
        download_thread = threading.Thread(target=self._run_download, args=(target_url, download_location))
        download_thread.start() # Begin the thread execution.

    def cancel_download_process(self):
        """
        Sets the global cancellation flag. The download thread periodically checks this flag
        and will gracefully stop if it is set.
        """
        cancel_flag.set() # Signal the download thread to stop.
        self.update_status_text("Cancellation requested. Waiting for current operation to stop...")
        self.cancel_button.config(state='disabled') # Disable the cancel button once pressed.

    def _run_download(self, target_url: str, download_location: str):
        """
        The actual download logic that runs in the separate thread.
        Handles URL parsing for subdirectory, calls the core download function,
        and manages post-download messages and GUI state reset.

        Args:
            target_url (str): The URL of the directory listing.
            download_location (str): The base local directory for downloads.
        """
        try:
            # Extract subdirectory name from the URL path.
            parsed_url = urlparse(target_url)
            # Split the path by '/' and filter out empty strings.
            path_segments = [s for s in parsed_url.path.split('/') if s]
            subdirectory_name = "downloaded_content" # Default subdirectory name.
            if path_segments:
                subdirectory_name = path_segments[-1] # Use the last segment as the subdirectory name.

            # --- Security Enhancement: Sanitize Subdirectory Name ---
            # URL-decode the subdirectory name and then sanitize it to remove problematic characters.
            subdirectory_name = sanitize_filename(unquote(subdirectory_name))

            # Construct the final full path for the download directory.
            final_download_path = os.path.join(download_location, subdirectory_name)

            # --- Security Enhancement: Robust Path Traversal Prevention ---
            # Normalize paths to handle '..' and '.' correctly and get absolute paths.
            abs_download_location = os.path.abspath(download_location)
            abs_final_download_path = os.path.abspath(final_download_path)

            # Check if the resolved download path is actually *within* the intended base download location.
            # This prevents attempts to write files outside the designated directory using path traversal.
            if not abs_final_download_path.startswith(abs_download_location):
                messagebox.showerror(
                    "Security Error",
                    f"Potential path traversal detected! The resolved download path "
                    f"'{abs_final_download_path}' is outside the designated base directory "
                    f"'{abs_download_location}'. Aborting download."
                )
                self.update_status_text("Download aborted due to potential path traversal.")
                return # Abort the download if traversal is detected.


            # Call the core download function, passing callbacks for status and progress updates.
            download_files_from_url(
                target_url,
                final_download_path,
                max_retries=MAX_RETRIES, # Use constant for max retries.
                retry_delay=RETRY_DELAY_SECONDS, # Use constant for retry delay.
                status_callback=self.update_status_text, # Callback for general log messages.
                progress_callback=self.update_file_progress # Callback for detailed progress.
            )
            # After download completes (or is cancelled), show appropriate message.
            if not cancel_flag.is_set(): # If the download was not explicitly cancelled by the user.
                messagebox.showinfo("Download Complete", "All files processed successfully!")
            else:
                messagebox.showinfo("Download Cancelled", "The download process was cancelled.")
        except Exception as e:
            # Catch any unexpected errors during the download thread's execution.
            messagebox.showerror("Download Error", f"An unexpected error occurred: {e}")
        finally:
            # Ensure buttons are re-enabled and progress is reset regardless of success or failure.
            self.download_button.config(state='normal') # Re-enable download button.
            self.cancel_button.config(state='disabled') # Disable cancel button.
            self.quit_button.config(state='normal') # Re-enable quit button.
            # Reset progress display and bar after a short delay to ensure last updates are visible.
            self.master.after(100, lambda: self.update_file_progress("N/A", 0, 0, 0, 0))


if __name__ == "__main__":
    # This block ensures the code runs only when the script is executed directly (not imported as a module).
    root = tk.Tk() # Create the main Tkinter window.
    app = DownloaderApp(root) # Create an instance of the application.
    root.mainloop() # Start the Tkinter event loop, which listens for user interactions and updates the GUI.
