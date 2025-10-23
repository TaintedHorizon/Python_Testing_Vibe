# Import necessary modules for the script to work.
# The 'os' module provides functions for interacting with the operating system and file system.
# The 're' module provides support for regular expressions in Python.
# The 'shutil' module provides high-level file operations, including copying files.
import os  # Allows interaction with the operating system and file system
import re   # Provides support for regular expressions
import shutil  # Provides high-level file operations
import argparse  # For command-line argument parsing
from typing import List, Tuple # For type hinting
import tempfile
def _select_tmp_dir():
    """Select a safe temporary directory with precedence:
    1. FILE_UTILS_DEST env
    2. TEST_TMPDIR
    3. TMPDIR
    4. system tempdir
    """
    return os.environ.get('FILE_UTILS_DEST') or os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR') or tempfile.gettempdir()

def find_matching_files(source: str, pattern: str) -> List[Tuple[str, str, str]]:
    """
    Finds all files in the source directory that match the given regex pattern.

    Args:
        source (str): Path of the directory to search in
        pattern (str): Regex pattern for file names

    Returns:
        list: List of tuples containing paths of matching files and their relative paths
              Each tuple is (filename, absolute_path, relative_path)
    """
    matches: List[Tuple[str, str, str]] = []  # List to store paths of matching files
    for root, dirs, files in os.walk(source):
        # For each file found
        for file in files:
            # Check if the file matches the pattern (case-insensitive)
            if re.search(pattern, file, re.IGNORECASE):
                # Construct full path of file
                file_path = os.path.join(root, file)
                # Add match to list with its full path and relative path
                matches.append((file, file_path, os.path.relpath(file_path, start=source)))

    return matches  # Return list of matching files

def main() -> None:  # Main function where the program starts execution
    """
    The main entry point for the script.

    This function is responsible for parsing command-line arguments and executing the file copying process.
    """
    # Create an argument parser
    parser = argparse.ArgumentParser(description='Copy files matching a regex pattern from one directory to another.')

    # Add command-line arguments for source directory, destination directory, and regex pattern
    parser.add_argument('-s', '--source', help='Source directory', required=True)
    parser.add_argument('-d', '--destination', help='Destination directory (optional). If omitted, uses FILE_UTILS_DEST env var or system temp directory.', required=False)
    parser.add_argument('-p', '--pattern', help='Regex pattern for file names', required=True)

    # Parse the command-line arguments
    args = parser.parse_args()

    source_path = os.path.abspath(args.source)  # Get absolute path of source directory
    # Determine destination path: prefer provided arg, then env var, then TEST_TMPDIR/TMPDIR, then system temp
    destination_arg = args.destination
    if not destination_arg:
        destination_arg = _select_tmp_dir()
        print(f"No destination provided; using safe default: {destination_arg}")
    destination_path = os.path.abspath(destination_arg)

    if not os.path.exists(source_path):
        print(f"Error: Source directory '{source_path}' does not exist.") # Using f-string for formatted output
        return

    # Create the destination directory if it doesn't exist for a better user experience.
    try:
        os.makedirs(destination_path, exist_ok=True)
    except OSError as e:
        print(f"Warning: could not create destination directory {destination_path}: {e}")

    pattern = args.pattern  # Get regex pattern from command-line argument

    matches = find_matching_files(source_path, pattern)

    if len(matches) == 0:
        print("No matches found.")
    else:
        print("Found matches:")

        for i, (filename, abs_path, rel_path) in enumerate(matches):
            print(f"{i+1}. {rel_path}")  # Display matching files

        response = input("Proceed with copying these files? (y/n): ")

        if response.lower() == 'y':
            # If confirmed, proceed with copying the matching files
            print("Copying matching files...")

            for filename, source_file_path, relative_path in matches:
                try:
                    # Recreate directory structure in the destination
                    destination_file_path = os.path.join(destination_path, relative_path)
                    os.makedirs(os.path.dirname(destination_file_path), exist_ok=True)

                    shutil.copy2(source_file_path, destination_file_path)  # Attempt to copy file from source to destination
                    print(f"Copied {relative_path}")  # Display success message
                except Exception as e:
                    print(f"Failed to copy {filename}: {str(e)}")  # Display error message if copying fails
        else:
            print("Copy operation cancelled.")  # Display cancel message

if __name__ == "__main__":  # Script execution starts here
    main()  # Call the main function to start script execution