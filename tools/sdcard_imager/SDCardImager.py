import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import threading
import ctypes
import sys
import traceback # Used for detailed error logging
import datetime # Used for timestamping log entries
import time # Used for time tracking in imaging process

# --- CRITICAL: Verify ctypes.wintypes exists before proceeding ---
# ctypes.wintypes provides Windows-specific data types (like HANDLE, DWORD)
# which are essential for defining function signatures when calling Windows API functions directly.
# If this submodule is missing, it indicates a problem with the Python installation itself.
try:
    # Attempt to import wintypes directly. This will raise an ImportError if the submodule
    # is not found, or an AttributeError if 'wintypes' exists but doesn't contain expected types.
    from ctypes import wintypes
    _ = wintypes.HANDLE # Just try to access a common type (HANDLE) to verify it's loaded.
except ImportError as e:
    # If wintypes cannot be imported, show a critical error and exit.
    messagebox.showerror("Initialization Error",
                         f"Critical Python component 'ctypes.wintypes' is missing (ImportError).\n"
                         f"This indicates a corrupted Python installation or environment issue.\n"
                         f"Please try recreating your virtual environment or reinstalling Python.\n"
                         f"Error: {e}\n\nApplication will exit.")
    sys.exit(1)
except AttributeError as e:
    # If wintypes is found but doesn't contain expected attributes, show a critical error and exit.
    messagebox.showerror("Initialization Error",
                         f"Critical Python component 'ctypes.wintypes' is missing (AttributeError).\n"
                         f"This indicates a corrupted Python installation or environment issue.\n"
                         f"Please try recreating your virtual environment or reinstalling Python.\n"
                         f"Error: {e}\n\nApplication will exit.")
    sys.exit(1)
except Exception as e:
    # Catch any other unexpected errors during this critical verification step.
    messagebox.showerror("Initialization Error",
                         f"An unexpected error occurred while verifying 'ctypes.wintypes'.\n"
                         f"Error: {e}\n\nApplication will exit.")
    sys.exit(1)


# --- CRITICAL: Import win32api/win32file/win32con and ctypes for Windows API calls ---
# This section sets up all necessary Windows API interfaces.
# We use a mix of pywin32 (for higher-level functions like GetLogicalDriveStrings)
# and ctypes (for direct kernel32.dll calls for GetDriveTypeW and DeviceIoControl)
# to ensure maximum compatibility and bypass issues with pywin32's exposure of certain constants/functions.
try:
    import win32api # Provides access to many Windows API functions (e.g., GetLogicalDriveStrings, GetVolumeInformation, CloseHandle)
    import win32file # Provides file-related Windows API functions (e.g., CreateFile, ReadFile)
    import win32con # Provides Windows constants (e.g., DRIVE_REMOVABLE, GENERIC_READ, FILE_SHARE_READ)

    # Load kernel32.dll: This DLL contains core Windows API functions like GetDriveTypeW and DeviceIoControl.
    kernel32 = ctypes.WinDLL('kernel32')

    # Define the signature for GetDriveTypeW function:
    # UINT GetDriveTypeW(LPCWSTR lpRootPathName);
    # lpRootPathName: A pointer to a null-terminated string that specifies the root directory of the drive.
    # ctypes.c_wchar_p: Represents a pointer to a wide character string (Unicode).
    # ctypes.c_uint: Represents an unsigned integer (return type UINT).
    kernel32.GetDriveTypeW.argtypes = [ctypes.c_wchar_p]
    kernel32.GetDriveTypeW.restype = ctypes.c_uint

    # Define the signature for DeviceIoControl function:
    # BOOL DeviceIoControl(HANDLE hDevice, DWORD dwIoControlCode, LPVOID lpInBuffer, DWORD nInBufferSize, LPVOID lpOutBuffer, DWORD nOutBufferSize, LPDWORD lpBytesReturned, LPOVERLAPPED lpOverlapped);
    # This function sends a control code directly to a specified device driver.
    kernel32.DeviceIoControl.argtypes = [
        wintypes.HANDLE,      # hDevice: A handle to the device on which to perform the operation.
        wintypes.DWORD,       # dwIoControlCode: The control code for the operation to perform.
        wintypes.LPVOID,      # lpInBuffer: A pointer to the input buffer.
        wintypes.DWORD,       # nInBufferSize: The size of the input buffer, in bytes.
        wintypes.LPVOID,      # lpOutBuffer: A pointer to the output buffer.
        wintypes.DWORD,       # nOutBufferSize: The size of the output buffer, in bytes.
        ctypes.POINTER(wintypes.DWORD), # lpBytesReturned: A pointer to a variable that receives the size of the data stored in the output buffer, in bytes.
        wintypes.LPVOID       # lpOverlapped: A pointer to an OVERLAPPED structure (not used for synchronous calls, so None).
    ]
    kernel32.DeviceIoControl.restype = wintypes.BOOL # Returns TRUE (non-zero) for success, FALSE (zero) for failure.

    # Define constants for drive types:
    # These constants are returned by GetDriveTypeW and are used to filter for removable drives.
    DRIVE_UNKNOWN = 0       # The drive type cannot be determined.
    DRIVE_NO_ROOT_DIR = 1   # The root directory does not exist.
    DRIVE_REMOVABLE = 2     # The drive is a removable storage device (e.g., floppy drive, USB flash drive, SD card).
    DRIVE_FIXED = 3         # The drive is a fixed hard disk.
    DRIVE_REMOTE = 4        # The drive is a remote (network) drive.
    DRIVE_CDROM = 5         # The drive is a CD-ROM drive.
    DRIVE_RAMDISK = 6       # The drive is a RAM disk.

    # Define IOCTL_DISK_GET_LENGTH_INFO constant:
    # This is a DeviceIoControl code used to retrieve the length (size) of a disk.
    # It's defined directly here as it was previously problematic to get from win32file.
    IOCTL_DISK_GET_LENGTH_INFO = 0x0007405C

except ImportError as e:
    # This block catches errors if pywin32 components (win32api, win32file, win32con) cannot be imported.
    messagebox.showerror("Initialization Error",
                         f"Required 'pywin32' library components could not be loaded.\n"
                         f"Please ensure 'pywin32' is correctly installed in your Python environment.\n"
                         f"Error: {e}\n\nApplication will exit.")
    sys.exit(1) # Exit the application as it cannot function without these core components.
except Exception as e:
    # This block catches any other unexpected errors during the setup of Windows API functions.
    messagebox.showerror("Initialization Error",
                         f"An unexpected error occurred during critical Windows API setup.\n"
                         f"Error: {e}\n\nApplication will exit.")
    sys.exit(1) # Exit the application.

# Define a log file path:
# This log file will record application events, debug messages, and errors.
# Prefer explicit env var overrides for tests/CI. Fallbacks:
# 1) env SDCARD_IMAGER_LOG or LOG_FILE_PATH
# 2) TEST_TMPDIR/TMPDIR + 'sd_card_imager_error.log'
# 3) repo-local default: tools/sdcard_imager/sd_card_imager_error.log
_env_log = os.environ.get('SDCARD_IMAGER_LOG') or os.environ.get('LOG_FILE_PATH')
_test_tmp = os.getenv('TEST_TMPDIR') or os.getenv('TMPDIR')
if _env_log:
    LOG_FILE_PATH = _env_log
elif _test_tmp:
    LOG_FILE_PATH = os.path.join(_test_tmp, 'sd_card_imager_error.log')
else:
    LOG_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sd_card_imager_error.log")


def _ensure_log_dir():
    try:
        os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    except Exception:
        # Best-effort: if we can't create the dir, logging will fallback to console
        pass

_ensure_log_dir()

def log_message(message, level="INFO"):
    """
    Helper function to write timestamped messages to the global log file.
    Args:
        message (str): The message string to log.
        level (str): The severity level of the message (e.g., "INFO", "DEBUG", "ERROR", "CRITICAL").
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}\n"
    try:
        with open(LOG_FILE_PATH, "a") as log_f: # Open in append mode ('a')
            log_f.write(log_entry)
    except Exception as e:
        # Fallback print to console if logging to file fails.
        print(f"FATAL ERROR: Could not write to log file {LOG_FILE_PATH}: {e}")
        print(log_entry) # Print the original log entry to console as a last resort.

def log_exception(exc_type, exc_value, exc_traceback):
    """
    Custom exception hook to log unhandled exceptions to the log file.
    This function is called automatically by Python when an unhandled exception occurs.
    Args:
        exc_type: The type of the exception.
        exc_value: The exception instance.
        exc_traceback: A traceback object encapsulating the call stack.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    error_message = f"[{timestamp}] [ERROR] Unhandled Exception:\n"
    # Format the exception and traceback into a string.
    error_message += "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    error_message += "\n" + "="*50 + "\n" # Add a separator for readability.
    try:
        with open(LOG_FILE_PATH, "a") as log_f:
            log_f.write(error_message)
        # Attempt to show a messagebox to the user, but only if Tkinter's root window is initialized.
        # This prevents errors if an exception occurs very early before the GUI is ready.
        if tk._default_root is not None:
            messagebox.showerror("Application Error (Admin)",
                                 f"An unhandled error occurred in the application. "
                                 f"Details logged to:\n{LOG_FILE_PATH}")
    except Exception as e:
        # Fallback print to console if logging to file or showing messagebox fails.
        print(f"FATAL ERROR: Could not log exception to file or show messagebox: {e}")
        print(error_message) # Print the original error to console.

# Set the custom exception hook immediately upon script startup.
sys.excepthook = log_exception

def is_admin():
    """
    Checks if the current Python script is running with administrator privileges.
    Uses ctypes.windll.shell32.IsUserAnAdmin() Windows API call.
    Returns:
        bool: True if running as administrator, False otherwise.
    """
    try:
        # IsUserAnAdmin() returns a non-zero value if the current user is an administrator.
        is_user_admin = ctypes.windll.shell32.IsUserAnAdmin()
        log_message(f"IsUserAnAdmin() returned: {is_user_admin}", "DEBUG")
        return is_user_admin
    except Exception as e:
        # Log any errors encountered while checking admin status.
        log_message(f"Error checking admin status (IsUserAnAdmin failed): {e}", "ERROR")
        log_exception(type(e), e, e.__traceback__) # Log the full traceback for this error.
        return False

class SDCardImager(tk.Tk):
    """
    A GUI application for creating a raw image of an SD card.

    This application provides a user-friendly interface to:
    - Select an SD card from a list of available drives.
    - Choose a destination file to save the image to.
    - Start the imaging process, which reads the entire SD card and writes it to the file.
    - Display the progress of the imaging process.
    """

    def __init__(self):
        """
        Initializes the main application window and its widgets.
        This is the constructor for the SDCardImager class, inheriting from tk.Tk.
        """
        log_message("SDCardImager.__init__ started.", "DEBUG")
        super().__init__() # Call the constructor of the parent class (tk.Tk).
        log_message("tk.Tk() initialized.", "DEBUG")

        # --- Window Configuration ---
        self.title("SD Card Imager") # Set the window title.
        self.geometry("500x300")     # Set the initial window size.
        self.resizable(True, True)   # Allow the window to be resized horizontally and vertically.
        log_message("Window configured.", "DEBUG")

        # --- Member Variables ---
        # tk.StringVar() are special Tkinter variables that automatically update linked widgets.
        self.source_drive = tk.StringVar()      # Stores the selected source drive letter.
        self.destination_file = tk.StringVar()  # Stores the selected destination image file path.
        self.estimated_drive_size = tk.StringVar(value="Size: N/A") # Displays the estimated size of the selected drive.
        self.current_speed = tk.StringVar(value="Speed: N/A") # Displays current read/write speed.
        self.time_remaining = tk.StringVar(value="ETA: N/A") # Displays estimated time remaining.

        # Event for controlling the cancellation of the imaging thread.
        self.cancel_event = threading.Event()
        self.imaging_thread = None # Placeholder for the imaging thread.

        log_message("Member variables initialized.", "DEBUG")

        # --- UI Element Creation ---
        self.create_widgets() # Call a method to build the GUI elements.
        log_message("Widgets created.", "DEBUG")

    def create_widgets(self):
        """
        Creates and arranges all the GUI widgets within the main window.
        Uses ttk (themed Tkinter) widgets for a more modern look.
        """
        log_message("create_widgets started.", "DEBUG")
        # --- Main Frame ---
        # A main frame to contain all other UI elements, providing padding.
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True) # Makes the frame fill and expand with the window.

        # --- Source Drive Selection Section ---
        source_frame = ttk.LabelFrame(main_frame, text="1. Select SD Card Drive")
        source_frame.pack(fill=tk.X, padx=5, pady=5) # Fills horizontally, with internal padding.

        drive_label = ttk.Label(source_frame, text="Drive Letter:")
        drive_label.pack(side=tk.LEFT, padx=5, pady=5) # Places label to the left.

        # Combobox for selecting the drive. 'state="readonly"' prevents manual text input.
        self.drive_menu = ttk.Combobox(source_frame, textvariable=self.source_drive, state="readonly")
        self.drive_menu.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.X, expand=True)
        # Bind an event: When a new item is selected in the combobox, call update_drive_size_display.
        self.drive_menu.bind("<<ComboboxSelected>>", self.update_drive_size_display)

        refresh_button = ttk.Button(source_frame, text="Refresh", command=self.populate_drives)
        refresh_button.pack(side=tk.LEFT, padx=5, pady=5) # Button to re-scan for drives.

        # Label to display the estimated size of the currently selected drive.
        self.size_label = ttk.Label(source_frame, textvariable=self.estimated_drive_size)
        self.size_label.pack(side=tk.RIGHT, padx=5, pady=5)


        # --- Destination File Selection Section ---
        destination_frame = ttk.LabelFrame(main_frame, text="2. Select Destination")
        destination_frame.pack(fill=tk.X, padx=5, pady=5)

        destination_label = ttk.Label(destination_frame, text="Image File:")
        destination_label.pack(side=tk.LEFT, padx=5, pady=5)

        # Entry widget to display the chosen file path. 'state="readonly"' prevents manual editing.
        destination_entry = ttk.Entry(destination_frame, textvariable=self.destination_file, state="readonly")
        destination_entry.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.X, expand=True)

        browse_button = ttk.Button(destination_frame, text="Browse...", command=self.browse_destination)
        browse_button.pack(side=tk.LEFT, padx=5, pady=5) # Button to open file dialog.

        # --- Action Buttons Frame ---
        action_buttons_frame = ttk.Frame(main_frame)
        action_buttons_frame.pack(pady=10)

        # Button to start the imaging process.
        self.start_button = ttk.Button(action_buttons_frame, text="Create Image", command=self.start_imaging_thread)
        self.start_button.pack(side=tk.LEFT, padx=5)

        # Button to cancel the imaging process. Initially disabled.
        self.cancel_button = ttk.Button(action_buttons_frame, text="Cancel", command=self.cancel_imaging, state="disabled")
        self.cancel_button.pack(side=tk.LEFT, padx=5)

        # Button to view the log file.
        self.view_log_button = ttk.Button(action_buttons_frame, text="View Log", command=self.view_log_file)
        self.view_log_button.pack(side=tk.LEFT, padx=5)

        # --- Progress Bar ---
        # Displays the progress of the imaging operation.
        self.progress = ttk.Progressbar(main_frame, orient="horizontal", length=300, mode="determinate")
        self.progress.pack(pady=5, fill=tk.X, padx=5) # Fills horizontally.

        # --- Status Labels Frame ---
        status_labels_frame = ttk.Frame(main_frame)
        status_labels_frame.pack(fill=tk.X, padx=5)

        # Displays messages to the user about the application's current state.
        self.status_label = ttk.Label(status_labels_frame, text="Ready")
        self.status_label.pack(side=tk.LEFT, expand=True, fill=tk.X)

        # Displays current read/write speed.
        self.speed_label = ttk.Label(status_labels_frame, textvariable=self.current_speed)
        self.speed_label.pack(side=tk.LEFT, padx=10)

        # Displays estimated time remaining.
        self.eta_label = ttk.Label(status_labels_frame, textvariable=self.time_remaining)
        self.eta_label.pack(side=tk.LEFT, padx=10)


        # --- Initial Population of Drives ---
        self.populate_drives() # Call this method to fill the drive combobox when the app starts.
        log_message("create_widgets finished.", "DEBUG")

    def format_bytes(self, bytes_value):
        """
        Formats a byte value into a human-readable string (B, KB, MB, GB).
        Args:
            bytes_value (int or None): The number of bytes.
        Returns:
            str: Formatted string (e.g., "1.23 GB") or "N/A" if input is None.
        """
        if bytes_value is None:
            return "N/A"
        if bytes_value < 1024:
            return f"{bytes_value} B"
        elif bytes_value < 1024**2:
            return f"{bytes_value / 1024:.2f} KB"
        elif bytes_value < 1024**3:
            return f"{bytes_value / (1024**2):.2f} MB"
        else:
            return f"{bytes_value / (1024**3):.2f} GB"

    def format_seconds_to_hms(self, seconds):
        """
        Formats a number of seconds into a human-readable H:MM:SS string.
        Args:
            seconds (float): The number of seconds.
        Returns:
            str: Formatted string (e.g., "1h 05m 30s").
        """
        if seconds is None or seconds < 0:
            return "N/A"

        seconds = int(seconds)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        remaining_seconds = seconds % 60

        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes:02d}m")
        parts.append(f"{remaining_seconds:02d}s") # Always show seconds

        return " ".join(parts) if parts else "0s"


    def populate_drives(self):
        """
        Populates the drive selection dropdown with available removable drives and their sizes.
        It iterates through logical drives, checks their type using ctypes, and gets their size.
        """
        log_message("populate_drives started.", "DEBUG")
        # Get a string containing all logical drive letters (e.g., "C:\\\0D:\\\0E:\\\0\0").
        drives = win32api.GetLogicalDriveStrings()
        drive_list = []
        for drive in drives.split('\000'): # Split by null terminator to get individual drive paths.
            if drive: # Ensure the drive string is not empty.
                try:
                    # Use ctypes.kernel32.GetDriveTypeW for drive type detection.
                    # The path needs to be the root directory, e.g., "C:\\".
                    root_path = drive.rstrip('\0') # Remove any trailing null terminators.
                    drive_type = kernel32.GetDriveTypeW(root_path)

                    # Only show removable drives (e.g., USB flash drives, SD card readers).
                    if drive_type == DRIVE_REMOVABLE: # Compare with the ctypes-defined constant.
                        raw_path = r'\\.\{}'.format(drive.rstrip('\\')) # Format for raw device access (e.g., "\\.\D:").
                        size = self.get_drive_size(raw_path) # Get the size of the raw drive.
                        if size is not None:
                            # Get volume information using win32api for a more descriptive name (e.g., "My USB Drive").
                            try:
                                volume_info = win32api.GetVolumeInformation(drive)
                                volume_name = volume_info[0] if volume_info[0] else "No Label" # Use volume label or "No Label".
                                drive_list.append(f"{drive} ({volume_name} - {self.format_bytes(size)})")
                            except Exception as e:
                                log_message(f"Error getting volume info for {drive}: {e}", "ERROR")
                                drive_list.append(f"{drive} ({self.format_bytes(size)})") # Fallback if volume info fails.
                        else:
                            drive_list.append(f"{drive} (Size Unknown)") # If size cannot be determined.
                except Exception as e:
                    # Log any errors encountered for a specific drive but continue processing other drives.
                    log_message(f"Could not get info for drive {drive}: {e}", "ERROR")
                    pass # Do not add to list if info cannot be retrieved.

        self.drive_menu['values'] = drive_list # Update the combobox with the found drives.
        log_message(f"Drives populated: {drive_list}", "DEBUG")

        # Logic to manage the current selection if drives are refreshed.
        if not drive_list:
            self.source_drive.set("") # Clear selection if no drives are found.
            self.estimated_drive_size.set("Size: N/A")
        elif self.source_drive.get() not in drive_list:
            # If the previously selected drive is no longer available, clear selection.
            self.source_drive.set("")
            self.estimated_drive_size.set("Size: N/A")
        else:
            # If a drive was already selected and is still in the list, update its size display.
            self.update_drive_size_display()
        log_message("populate_drives finished.", "DEBUG")


    def update_drive_size_display(self, event=None):
        """
        Updates the estimated drive size label based on the currently selected drive in the combobox.
        This method is called when the combobox selection changes.
        Args:
            event (tk.Event, optional): The event object (ignored).
        """
        log_message("update_drive_size_display started.", "DEBUG")
        selected_text = self.source_drive.get()
        if selected_text:
            # Extract just the drive letter (e.g., "D:") from the full descriptive text.
            drive_letter = selected_text.split(' ')[0]
            raw_path = r'\\.\{}'.format(drive_letter.rstrip('\\'))
            size = self.get_drive_size(raw_path) # Get the size using the raw path.
            self.estimated_drive_size.set(f"Size: {self.format_bytes(size)}") # Update the size label.
            log_message(f"Updated size display for {drive_letter} to {self.format_bytes(size)}", "DEBUG")
        else:
            self.estimated_drive_size.set("Size: N/A") # Set to N/A if no drive is selected.
            log_message("Cleared size display (no drive selected).", "DEBUG")
        log_message("update_drive_size_display finished.", "DEBUG")


    def browse_destination(self):
        """
        Opens a file dialog to allow the user to select or specify the destination
        file path for saving the disk image.
        """
        log_message("browse_destination started.", "DEBUG")
        file_path = filedialog.asksaveasfilename(
            title="Save Image As",          # Title of the dialog window.
            defaultextension=".img",       # Default file extension.
            filetypes=[("Image Files", "*.img"), ("All Files", "*.*")] # Filter for file types.
        )
        if file_path:
            self.destination_file.set(file_path) # Set the selected path to the StringVar.
            log_message(f"Destination file selected: {file_path}", "DEBUG")
        else:
            log_message("Destination file selection cancelled.", "DEBUG")


    def start_imaging_thread(self):
        """
        Initiates the imaging process in a separate thread to prevent the GUI from freezing.
        Includes a confirmation dialog and a check for sufficient destination space.
        """
        log_message("start_imaging_thread started.", "DEBUG")
        source_full_text = self.source_drive.get()
        destination = self.destination_file.get()

        # Input validation: Check if a source drive and destination file are selected.
        if not source_full_text:
            messagebox.showerror("Error", "Please select a source drive.")
            log_message("Error: No source drive selected.", "ERROR")
            return
        if not destination:
            messagebox.showerror("Error", "Please select a destination file.")
            log_message("Error: No destination file selected.", "ERROR")
            return

        # Extract just the drive letter (e.g., "D:") from the full descriptive text.
        source_drive_letter = source_full_text.split(' ')[0]

        # Get the size of the source drive for space check.
        raw_source_path = r'\\.\{}'.format(source_drive_letter.rstrip('\\'))
        source_size = self.get_drive_size(raw_source_path)

        if source_size is None or source_size == 0:
            messagebox.showerror("Error", "Could not determine source drive size or drive is empty. Cannot proceed.")
            log_message(f"Error: Could not determine source drive size for {raw_source_path} or drive is empty.", "ERROR")
            return

        # --- Destination Space Check ---
        destination_dir = os.path.dirname(destination)
        if not destination_dir: # If no directory specified, assume current working directory.
            destination_dir = os.getcwd()

        try:
            # Get free space on the destination drive/partition.
            # win32api.GetDiskFreeSpaceEx returns (FreeBytesAvailableToCaller, TotalNumberOfBytes, TotalNumberOfFreeBytes)
            free_bytes_available, _, _ = win32api.GetDiskFreeSpaceEx(destination_dir)
            log_message(f"Free space on {destination_dir}: {self.format_bytes(free_bytes_available)}", "DEBUG")

            if free_bytes_available < source_size:
                messagebox.showerror("Error",
                                     f"Not enough free space on destination drive.\n"
                                     f"Required: {self.format_bytes(source_size)}\n"
                                     f"Available: {self.format_bytes(free_bytes_available)}")
                log_message(f"Error: Insufficient space on destination {destination_dir}. Required: {source_size}, Available: {free_bytes_available}", "ERROR")
                return
        except Exception as e:
            messagebox.showerror("Error", f"Could not check free space on destination: {e}")
            log_message(f"Error checking free space on {destination_dir}: {e}", "ERROR")
            return


        # Confirmation dialog: Crucial for preventing accidental data loss.
        confirm_msg = (
            f"You are about to create a raw image from:\n"
            f"Source Drive: {source_full_text}\n"
            f"To Destination File: {destination}\n\n"
            f"WARNING: This operation will read the entire drive. "
            f"Ensure you have selected the correct source drive as imaging the wrong drive "
            f"could lead to unexpected behavior or data corruption if the drive is actively being used.\n\n"
            f"Do you want to proceed?"
        )
        if not messagebox.askyesno("Confirm Imaging Operation", confirm_msg):
            log_message("Imaging operation cancelled by user.", "INFO")
            return # User cancelled the operation.

        # Reset cancellation event and disable/enable buttons.
        self.cancel_event.clear() # Clear any previous cancellation state.
        self.start_button.config(state="disabled") # Disable the start button to prevent multiple clicks.
        self.cancel_button.config(state="normal") # Enable the cancel button.

        log_message("Starting imaging thread...", "INFO")

        # Create and start a new thread for the imaging process.
        # This keeps the main GUI thread responsive.
        self.imaging_thread = threading.Thread(target=self.create_image, args=(source_drive_letter, destination, source_size))
        self.imaging_thread.daemon = True # Set as daemon so it terminates when the main app exits.
        self.imaging_thread.start()
        log_message("Imaging thread started.", "DEBUG")

    def cancel_imaging(self):
        """
        Sets the cancellation event, signaling the imaging thread to stop.
        """
        log_message("Cancellation requested by user.", "INFO")
        self.cancel_event.set() # Set the event to signal cancellation.
        self.status_label.config(text="Cancelling...") # Update status label.
        self.cancel_button.config(state="disabled") # Disable cancel button immediately.


    def get_drive_size(self, drive_path):
        """
        Gets the total size of a raw disk device using the Windows API DeviceIoControl.
        This function directly calls kernel32.dll to query disk length information.
        Args:
            drive_path (str): The raw path to the drive (platform-specific raw device path for the target drive).
        Returns:
            int or None: The total size of the drive in bytes, or None if an error occurs.
        """
        log_message(f"get_drive_size called for: {drive_path}", "DEBUG")
        py_handle = None # Variable to store the pywin32 handle object.
        raw_handle = None # Variable to store the raw integer handle for ctypes.
        try:
            # Open the raw device handle using win32file.CreateFile.
            # GENERIC_READ: Request read access.
            # FILE_SHARE_READ | FILE_SHARE_WRITE: Allow other processes to read/write while we have the handle open.
            # OPEN_EXISTING: The device must already exist.
            # FILE_FLAG_BACKUP_SEMANTICS: Required for opening directories and devices for backup/restore operations.
            py_handle = win32file.CreateFile(
                drive_path,
                win32file.GENERIC_READ,
                win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE,
                None, # lpSecurityAttributes
                win32file.OPEN_EXISTING,
                win32con.FILE_FLAG_BACKUP_SEMANTICS,
                None  # hTemplateFile
            )
            # Detach the raw integer handle from the pywin32 PyHANDLE object.
            # This is necessary because ctypes.DeviceIoControl expects a raw integer handle,
            # not a PyHANDLE object. After Detach(), py_handle no longer manages the OS handle.
            raw_handle = py_handle.Detach()
            log_message(f"Opened handle for {drive_path}. Raw handle: {raw_handle}", "DEBUG")

            # Prepare output buffer for DISK_LENGTH_INFO:
            # The DISK_LENGTH_INFO structure contains a LARGE_INTEGER (64-bit value) for Length.
            # We create an 8-byte buffer to receive this 64-bit integer.
            output_buffer = ctypes.create_string_buffer(8)
            bytes_returned = wintypes.DWORD(0) # A DWORD (32-bit unsigned int) to store the number of bytes returned.

            # Call DeviceIoControl using ctypes:
            # hDevice: The raw integer handle to the device.
            # dwIoControlCode: IOCTL_DISK_GET_LENGTH_INFO to get the disk's total length.
            # lpInBuffer: None, as no input data is required for this control code.
            # nInBufferSize: 0, as no input data.
            # lpOutBuffer: The buffer to receive the output data (DISK_LENGTH_INFO).
            # nOutBufferSize: The size of the output buffer.
            # lpBytesReturned: A pointer to bytes_returned, where the actual bytes written will be stored.
            # lpOverlapped: None, for synchronous operation.
            success = kernel32.DeviceIoControl(
                raw_handle,
                IOCTL_DISK_GET_LENGTH_INFO,
                None,
                0,
                output_buffer,
                ctypes.sizeof(output_buffer),
                ctypes.byref(bytes_returned), # Pass a pointer to bytes_returned.
                None
            )

            if not success:
                # If DeviceIoControl fails, get the Windows error code and message.
                last_error = ctypes.get_last_error()
                error_message = ctypes.FormatError(last_error).strip()
                # Raise a Python exception to be caught by the outer try-except block.
                raise ctypes.WinError(last_error, f"DeviceIoControl failed: {error_message}")

            # Parse the output buffer to get the 64-bit length:
            # The raw bytes from the buffer are converted to an integer, assuming little-endian byte order.
            total_size = int.from_bytes(output_buffer.raw, byteorder='little')

            log_message(f"Successfully got size for {drive_path}: {self.format_bytes(total_size)}", "DEBUG")
            return total_size
        except Exception as e:
            # Log any error that occurs during the size retrieval process.
            win_error = getattr(e, 'winerror', 'N/A') # Try to get the Windows error code.
            log_message(f"Error getting size for {drive_path}. WinError: {win_error}, Error: {e}", "ERROR")
            return None # Return None to indicate failure.
        finally:
            # Ensure the raw handle is closed if it was successfully detached.
            if raw_handle:
                try:
                    win32api.CloseHandle(raw_handle) # Use win32api.CloseHandle for raw integer handles.
                    log_message(f"Closed raw handle for {drive_path} in get_drive_size finally block.", "DEBUG")
                except Exception as e:
                    log_message(f"Error closing raw handle for {drive_path} in get_drive_size finally block: {e}", "ERROR")
            # The original py_handle object does not need to be explicitly closed here
            # because its underlying OS handle was detached and is now managed by raw_handle.


    def create_image(self, source_drive_letter, destination_file_path, total_size):
        """
        Performs the actual block-by-block copy from the source drive to the destination file.
        This method is designed to run in a separate thread to keep the GUI responsive.
        Args:
            source_drive_letter (str): The drive letter of the source (e.g., "D:").
            destination_file_path (str): The full path to the output image file.
            total_size (int): The total size of the source drive in bytes.
        """
        log_message(f"create_image started for source: {source_drive_letter}, dest: {destination_file_path}", "INFO")
        raw_source_path = r'\\.\{}'.format(source_drive_letter.rstrip('\\')) # Format for raw device access.

        # The total_size is now passed as an argument, already checked in start_imaging_thread.
        # No need to re-check here, but keep the log message if it's still somehow zero.
        if total_size is None or total_size == 0:
            log_message(f"Could not determine drive size for {raw_source_path} or drive is empty. Imaging aborted.", "ERROR")
            self.after(0, lambda: messagebox.showerror("Imaging Error", "Could not determine drive size or drive is empty. Cannot proceed."))
            self.after(0, lambda: self.start_button.config(state="normal"))
            self.after(0, lambda: self.status_label.config(text="Ready"))
            self.after(0, lambda: self.cancel_button.config(state="disabled"))
            return

        source_handle = None # Will store the handle to the source drive.
        image_file_handle = None # Will store the file object for the destination image.
        start_time = time.time() # Record the start time for speed and ETA calculation.
        last_update_time = time.time() # For periodic updates.
        last_bytes_read = 0 # For calculating speed.

        try:
            log_message(f"Attempting to open source drive: {raw_source_path}", "DEBUG")
            # Open the source drive for raw binary read access.
            source_handle = win32file.CreateFile(
                raw_source_path,
                win32file.GENERIC_READ,
                win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE,
                None,
                win32file.OPEN_EXISTING,
                win32con.FILE_FLAG_BACKUP_SEMANTICS, # Essential for device access.
                None
            )
            log_message("Source drive opened successfully.", "DEBUG")

            log_message(f"Attempting to open destination file: {destination_file_path}", "DEBUG")
            # Open the destination file in binary write mode.
            image_file_handle = open(destination_file_path, 'wb')
            log_message("Destination file opened successfully.", "DEBUG")

            # Update GUI status and progress bar on the main thread.
            self.after(0, lambda: self.status_label.config(text="Imaging in progress..."))
            self.after(0, lambda: self.progress.config(value=0))
            self.after(0, lambda: self.current_speed.set("Speed: 0 B/s"))
            self.after(0, lambda: self.time_remaining.set("ETA: N/A"))
            log_message("UI status updated to 'Imaging in progress'.", "DEBUG")

            chunk_size = 1024 * 1024 * 4  # Define a 4 MB chunk size for reading/writing.
            bytes_read = 0               # Counter for bytes read so far.

            log_message("Starting read/write loop.", "DEBUG")
            while True:
                # Check for cancellation request periodically.
                if self.cancel_event.is_set():
                    log_message("Imaging cancelled by user.", "INFO")
                    self.after(0, lambda: self.status_label.config(text="Cancelled!"))
                    self.after(0, lambda: messagebox.showinfo("Cancelled", "Imaging operation was cancelled by the user."))
                    break # Exit the loop if cancelled.

                # Read a chunk of data from the source drive.
                # ReadFile returns (bytes_read_count, data_buffer).
                hr, chunk = win32file.ReadFile(source_handle, chunk_size)
                if not chunk: # If chunk is empty, it means end of file/device has been reached.
                    log_message("End of source drive reached.", "DEBUG")
                    break

                image_file_handle.write(chunk) # Write the read chunk to the destination file.
                bytes_read += len(chunk)       # Update the total bytes read.

                current_time = time.time()
                elapsed_total_time = current_time - start_time

                # Update progress, speed, and ETA on the main thread periodically (e.g., every 0.5 seconds).
                if current_time - last_update_time >= 0.5:
                    progress_percent = (bytes_read / total_size) * 100

                    # Calculate speed
                    bytes_since_last_update = bytes_read - last_bytes_read
                    time_since_last_update = current_time - last_update_time
                    speed_bps = bytes_since_last_update / time_since_last_update if time_since_last_update > 0 else 0

                    # Calculate ETA
                    remaining_bytes = total_size - bytes_read
                    eta_seconds = remaining_bytes / speed_bps if speed_bps > 0 else float('inf')

                    self.after(0, lambda p=progress_percent: self.progress.config(value=p))
                    self.after(0, lambda b=bytes_read: self.status_label.config(text=f"Imaging: {self.format_bytes(b)} / {self.format_bytes(total_size)}"))
                    self.after(0, lambda s=speed_bps: self.current_speed.set(f"Speed: {self.format_bytes(s)}/s"))
                    self.after(0, lambda e=eta_seconds: self.time_remaining.set(f"ETA: {self.format_seconds_to_hms(e)}"))

                    last_update_time = current_time
                    last_bytes_read = bytes_read

                    log_message(f"Progress: {progress_percent:.2f}% ({self.format_bytes(bytes_read)} read, Speed: {self.format_bytes(speed_bps)}/s, ETA: {self.format_seconds_to_hms(eta_seconds)})", "DEBUG")

                # Small sleep to yield control and allow GUI updates/cancellation check.
                time.sleep(0.01) # Sleep for 10ms

            else: # This 'else' block executes if the while loop completes normally (not broken by 'break')
                log_message("Read/write loop finished successfully.", "DEBUG")
                # Update GUI for completion.
                self.after(0, lambda: self.status_label.config(text="Imaging complete!"))
                self.after(0, lambda: messagebox.showinfo("Success", "The SD card image has been created successfully."))
                log_message("Imaging complete success message shown.", "INFO")

        except Exception as exc:
            # Catch and log any errors that occur during the imaging process.
            log_message(f"An error occurred during imaging: {exc}", "CRITICAL")
            log_exception(type(exc), exc, exc.__traceback__) # Log the full traceback for debugging.
            # Update GUI to show error.
            self.after(0, lambda: self.status_label.config(text="Error!", foreground="red"))
            # Use captured exception variable `exc` for message; bind it into the lambda to avoid late-binding issues
            self.after(0, lambda exc=exc: messagebox.showerror("Imaging Error", f"An error occurred during imaging: {exc}"))
        finally:
            log_message("Imaging process finally block entered.", "DEBUG")
            # Ensure all open handles and files are closed, regardless of success or failure.
            if source_handle:
                try:
                    win32file.CloseHandle(source_handle)
                    log_message("Source handle closed.", "DEBUG")
                except Exception as e:
                    log_message(f"Error closing source handle: {e}", "ERROR")
            if image_file_handle:
                try:
                    image_file_handle.close()
                    log_message("Image file handle closed.", "DEBUG")
                except Exception as e:
                    log_message(f"Error closing image file handle: {e}", "ERROR")

            # Reset GUI elements to their initial state.
            self.after(0, lambda: self.start_button.config(state="normal"))
            self.after(0, lambda: self.cancel_button.config(state="disabled")) # Disable cancel button.
            self.after(0, lambda: self.progress.config(value=0))
            self.after(0, lambda: self.current_speed.set("Speed: N/A"))
            self.after(0, lambda: self.time_remaining.set("ETA: N/A"))
            # Only reset status to "Ready" if not already "Cancelled!" or "Error!"
            if not self.cancel_event.is_set() and "Error!" not in self.status_label.cget("text"):
                 self.after(0, lambda: self.status_label.config(text="Ready"))
            log_message("UI reset to ready state.", "DEBUG")
            log_message("create_image finished.", "INFO")

    def view_log_file(self):
        """
        Opens the application's log file in the default text editor.
        """
        log_message("Attempting to open log file.", "INFO")
        try:
            os.startfile(LOG_FILE_PATH) # Opens the file using the default associated application.
            log_message(f"Log file opened: {LOG_FILE_PATH}", "INFO")
        except FileNotFoundError:
            messagebox.showerror("Error", f"Log file not found at: {LOG_FILE_PATH}")
            log_message(f"Error: Log file not found at {LOG_FILE_PATH}", "ERROR")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open log file: {e}")
            log_message(f"Error opening log file {LOG_FILE_PATH}: {e}", "ERROR")


if __name__ == "__main__":
    # This block handles the initial execution and privilege elevation.

    # Initialize the log file with a new run separator for clarity.
    if os.path.exists(LOG_FILE_PATH):
        with open(LOG_FILE_PATH, "a") as log_f:
            log_f.write("\n" + "#"*80 + "\n")
            log_f.write(f"[{datetime.datetime.now()}] Starting new run.\n")
            log_f.write("#"*80 + "\n\n")
    else:
        log_message("Log file initialized.", "INFO")

    log_message("Script started (main execution block).", "INFO")

    # Check if the script is currently running with administrator privileges.
    if not is_admin():
        log_message("Not running as administrator. Attempting to elevate privileges...", "INFO")

        # Determine the Python executable path for elevation.
        # sys.exec_prefix is typically the virtual environment root.
        python_exe = os.path.join(sys.exec_prefix, "python.exe")
        if not os.path.exists(python_exe):
            # Fallback to sys.executable if python.exe isn't found in the typical venv location.
            python_exe = sys.executable
            log_message(f"Warning: python.exe not found at {os.path.join(sys.exec_prefix, 'python.exe')}. Falling back to sys.executable: {python_exe}", "WARNING")

        # Prepare the command line parameters for the elevated process.
        # sys.argv[0] is the script's own path. sys.argv[1:] are any additional arguments.
        script_path = f'"{sys.argv[0]}"'
        other_args = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
        params = f"{script_path} {other_args}".strip()
        log_message(f"Elevation command: {python_exe} {params}", "DEBUG")

        try:
            # Use ShellExecuteW to re-run the script with "runas" verb (administrator privileges).
            # The '1' at the end means SW_SHOWNORMAL, showing the new window normally.
            ctypes.windll.shell32.ShellExecuteW(None, "runas", python_exe, params, None, 1)
            log_message("Elevation command issued. Original process exiting.", "INFO")
        except Exception as e:
            # If elevation fails, show an error message.
            messagebox.showerror("Elevation Error", f"Failed to elevate privileges: {e}")
            log_message(f"Failed to elevate privileges: {e}", "CRITICAL")
            log_exception(type(e), e, e.__traceback__) # Log the full traceback.
        finally:
            sys.exit() # The original (non-elevated) process exits after attempting elevation.
    else:
        # This code block executes if the script IS running with administrator privileges.
        log_message("Running as administrator. Initializing application (elevated process).", "INFO")
        try:
            app = SDCardImager() # Create an instance of the main application.
            log_message("SDCardImager app created. Starting mainloop...", "INFO")
            app.mainloop() # Start the Tkinter event loop, which runs the GUI.
            log_message("Application mainloop exited cleanly.", "INFO")
        except Exception as e:
            # Catch any unhandled exceptions that occur within the main elevated application.
            log_message(f"Unhandled exception in main elevated application block: {e}", "CRITICAL")
            log_exception(type(e), e, e.__traceback__) # Log the full traceback.
        finally:
            sys.exit() # Ensure the elevated process exits cleanly when the GUI closes.
