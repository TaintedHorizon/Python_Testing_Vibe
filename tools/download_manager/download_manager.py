import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urljoin, urlparse, unquote
import time # Import time for sleep functionality
import tempfile

def download_files_from_url(url, download_dir, max_retries=3, retry_delay=5):
    """
    Downloads all files found in a given URL's directory listing to a specified directory.
    Includes retry mechanism for failed downloads and skips already downloaded files.

    Args:
        url (str): The URL of the directory listing (e.g., https://example.com/files/).
        download_dir (str): The local directory where files will be saved.
        max_retries (int): Maximum number of retries for each file download attempt.
        retry_delay (int): Delay in seconds between retry attempts.
    """
    # Ensure the download directory exists
    if not os.path.exists(download_dir):
        try:
            os.makedirs(download_dir)
            print(f"Created download directory: {download_dir}")
        except OSError as e:
            print(f"Error creating directory {download_dir}: {e}")
            return

    print(f"Attempting to fetch directory listing from: {url}")
    try:
        response = requests.get(url, stream=True, timeout=10) # Added timeout for initial request
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL {url}: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    links = soup.find_all('a')

    files_processed = 0
    for link in links:
        href = link.get('href')
        if not href:
            continue

        # Ignore parent directory link and directory links (those ending with '/')
        if href == '../' or href.endswith('/'):
            continue

        # Construct the full URL for the file
        file_url = urljoin(url, href)
        # Get the file name and URL-decode it
        file_name = unquote(os.path.basename(urlparse(file_url).path))
        file_path = os.path.join(download_dir, file_name)

        # --- Resume/Skip Logic ---
        if os.path.exists(file_path):
            # Check if the file is non-empty, assuming a non-empty file is complete
            if os.path.getsize(file_path) > 0:
                print(f"Skipping: {file_name} (already downloaded and non-empty)")
                files_processed += 1 # Count as processed/found
                continue
            else:
                # If the file exists but is empty (0 bytes), it indicates a failed/stuck download
                print(f"Found empty file: {file_name}. Will attempt to re-download.")
                try:
                    os.remove(file_path) # Remove the empty file to ensure a clean re-download
                    print(f"Removed empty file: {file_name}")
                except OSError as e:
                    print(f"Warning: Could not remove empty file {file_name}: {e}. Attempting to overwrite.")

        # --- Retry Logic for File Download ---
        for attempt in range(max_retries):
            print(f"Downloading: {file_name} from {file_url} (Attempt {attempt + 1}/{max_retries})")
            try:
                # Use stream=True for large files and a timeout to prevent indefinite hangs
                with requests.get(file_url, stream=True, timeout=30) as r:
                    r.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
                    with open(file_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                print(f"Successfully downloaded: {file_name}")
                files_processed += 1
                break # Break out of the retry loop on successful download
            except requests.exceptions.RequestException as e:
                print(f"Error downloading {file_name}: {e}")
                if attempt < max_retries - 1:
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    print(f"Failed to download {file_name} after {max_retries} attempts.")
            except IOError as e:
                print(f"Error saving {file_name} to disk: {e}")
                if attempt < max_retries - 1:
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    print(f"Failed to save {file_name} after {max_retries} attempts.")

    if files_processed == 0:
        print("No files found or downloaded from the provided URL.")
    else:
        print(f"Finished processing {files_processed} files to {download_dir}.")

if __name__ == "__main__":
    print("--- File Downloader Script ---")

    # Get URL from user
    target_url = input("Please enter the URL of the directory listing (e.g., https://myrient.erista.me/files/No-Intro/Nintendo%20-%20Game%20Boy%20Advance/): ").strip()
    if not target_url:
        print("URL cannot be empty. Exiting.")
    else:
        # Get download directory from user
        download_location = input("Please enter the local directory to save files (e.g., downloads or C:\\Users\\YourUser\\Downloads). Leave empty to use safe default: ").strip()
        if not download_location:
            # Prefer explicit env var for CI or user control; otherwise use system temp directory
            download_location = os.environ.get('DOWNLOAD_MANAGER_DIR') or tempfile.gettempdir()
            print(f"No directory specified. Using safe default: {download_location}")
        else:
            # Extract subdirectory name from the URL
            parsed_url = urlparse(target_url)
            # Split path by '/' and filter out empty strings to get meaningful segments
            path_segments = [s for s in parsed_url.path.split('/') if s]

            # The last segment is typically the directory name for a directory listing URL
            subdirectory_name = "downloaded_content" # Default name if no specific directory can be extracted
            if path_segments:
                subdirectory_name = path_segments[-1]

            # URL-decode the subdirectory name
            subdirectory_name = unquote(subdirectory_name)

            # Construct the full path for the new subdirectory
            final_download_path = os.path.join(download_location, subdirectory_name)

            download_files_from_url(target_url, final_download_path)