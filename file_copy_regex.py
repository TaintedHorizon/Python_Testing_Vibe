# Import necessary modules for the script to work.
# The 'os' module provides functions for interacting with the operating system and file system.
# The 're' module provides support for regular expressions in Python.
# The 'shutil' module provides high-level file operations, including copying files.
import os  # Allows interaction with the operating system and file system
import re   # Provides support for regular expressions
import shutil  # Provides high-level file operations
import argparse  # Import the argparse module for command-line argument parsing

def get_path(prompt):  # Function to ask user for a path and verify it exists
    """
    Asks for a path from user and checks if it exists.
    
    Args:
        prompt (str): Prompt message to display to the user
    
    Returns:
        str: The valid path entered by the user
    """
    while True:  # Loop until the path is valid
        # Ask user for a path with the given prompt
        path = input(prompt)
        
        # Check if the path exists as a directory
        if os.path.exists(path) and os.path.isdir(path):
            return path  # Return the valid path
        else:
            print("Invalid path. Please enter the correct directory path.")  # Display error message

def copy_matching_files(source, destination, pattern):  # Function to find matching files and copy them
    """
    Copies all files from the source directory to the destination that match the given regex pattern.
    
    Args:
        source (str): Path of the directory to search in
        destination (str): Path where you want to copy matching files
        pattern (str): Regex pattern for file names
        
    Returns:
        list: List of tuples containing paths of matching files and their relative paths
    """
    matches = []  # List to store paths of matching files
    for root, dirs, files in os.walk(source):
        # For each file found
        for file in files:
            # Construct full path of file
            file_path = os.path.join(root, file)
            
            # Check if the file matches the pattern (case-insensitive)
            if re.search(pattern, file, re.IGNORECASE):
                # Add match to list with its full path and relative path
                matches.append((file, file_path, os.path.relpath(file_path, start=source)))

    return matches  # Return list of matching files

def main():  # Main function where the program starts execution
    """
    The main entry point for the script.
    
    This function is responsible for parsing command-line arguments and executing the file copying process.
    """
    # Create an argument parser
    parser = argparse.ArgumentParser(description='Copy files matching a regex pattern from one directory to another.')
    
    # Add command-line arguments for source directory, destination directory, and regex pattern
    parser.add_argument('-s', '--source', help='Source directory', required=True)
    parser.add_argument('-d', '--destination', help='Destination directory', required=True)
    parser.add_argument('-p', '--pattern', help='Regex pattern for file names', required=True)

    # Parse the command-line arguments
    args = parser.parse_args()

    source_path = os.path.abspath(args.source)  # Get absolute path of source directory
    destination_path = os.path.abspath(args.destination)  # Get absolute path of destination directory

    if not os.path.exists(source_path):
        print(f"Error: Source directory '{source_path}' does not exist.")
        return

    if not os.path.exists(destination_path):
        print(f"Error: Destination directory '{destination_path}' does not exist.")
        return

    pattern = args.pattern  # Get regex pattern from command-line argument

    matches = copy_matching_files(source_path, destination_path, pattern)

    if len(matches) == 0:
        print("No matches found.")
    else:
        print("Found matches:")
        
        for i, (file, path, rel_path) in enumerate(matches):
            print(f"{i+1}. {rel_path} ({path})")  # Display matching files

        response = input("Proceed with copying these files? (y/n): ")
        
        if response.lower() == 'y':
            # If confirmed, proceed with copying the matching files
            print("Copying matching files...")
            
            for match in matches:
                try:
                    shutil.copy2(match[1], destination_path)  # Attempt to copy file from source to destination
                    print(f"Copied {match[0]} to {destination_path}")  # Display success message
                except Exception as e:
                    print(f"Failed to copy {match[0]}: {str(e)}")  # Display error message if copying fails
        else:
            print("Copy operation cancelled.")  # Display cancel message

if __name__ == "__main__":  # Script execution starts here
    main()  # Call the main function to start script execution