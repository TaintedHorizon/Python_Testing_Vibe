import tkinter as tk
from tkinter import filedialog, messagebox
import xml.etree.ElementTree as ET
import os
import shutil # For file operations like renaming and moving

# Define the main application class.
# This class encapsulates all the GUI elements and their associated logic for modifying gamelist XML files.
class GamelistProcessorApp:
    # The constructor method. It's automatically called when you create a new instance of this class.
    # 'master' typically refers to the root Tkinter window (the main window of the application).
    def __init__(self, master):
        self.master = master  # Store a reference to the root window for later use (e.g., updating its title).
        master.title("Gamelist XML Modifier") # Set the title that appears in the window's title bar.

        # --- Tkinter Variables for UI Elements ---
        # These variables are special Tkinter objects that can be directly linked to GUI widgets
        # (like Entry fields or Checkbuttons). When the variable's value changes, the widget updates,
        # and vice-versa. This provides a convenient way to get/set widget content.

        # StringVar to hold the file path of the input gamelist.xml selected by the user.
        self.input_file_path = tk.StringVar()
        
        # New StringVar to hold the proposed path for the original gamelist backup.
        # This will be updated dynamically when an input gamelist is selected.
        self.proposed_orig_backup_path = tk.StringVar()

        # StringVar to hold the path to the user-selected System Directory (e.g., 'atari2600').
        self.system_dir_path = tk.StringVar()

        # BooleanVar to control the state of the "Add <image> tags" checkbox.
        # 'value=True' makes the checkbox checked by default when the application starts.
        self.add_image_var = tk.BooleanVar(value=True)
        # BooleanVar to control the state of the "Add <manual> tags" checkbox.
        # Defaulting to checked as per the common use case.
        self.add_manual_var = tk.BooleanVar(value=True)

        # --- GUI Layout: Input Gamelist XML File Selection ---
        self.label_input = tk.Label(master, text="Select gamelist.xml to modify:")
        self.label_input.grid(row=0, column=0, sticky="w", padx=10, pady=5)

        self.entry_input = tk.Entry(master, textvariable=self.input_file_path, width=50, state="readonly")
        self.entry_input.grid(row=0, column=1, padx=10, pady=5)

        self.btn_browse_input = tk.Button(master, text="Browse", command=self.browse_input_file)
        self.btn_browse_input.grid(row=0, column=2, padx=10, pady=5)

        # --- GUI Layout: Proposed Original Backup Path Feedback ---
        self.label_proposed_orig_backup = tk.Label(master, textvariable=self.proposed_orig_backup_path, fg="gray", wraplength=400, justify="left")
        self.label_proposed_orig_backup.grid(row=1, column=0, columnspan=3, sticky="w", padx=10, pady=2)

        # --- GUI Layout: System Directory Selection ---
        self.label_system_dir = tk.Label(master, text="Select System Directory (e.g., 'atari2600'):")
        self.label_system_dir.grid(row=2, column=0, sticky="w", padx=10, pady=5) # Adjusted row

        self.entry_system_dir = tk.Entry(master, textvariable=self.system_dir_path, width=50, state="readonly")
        self.entry_system_dir.grid(row=2, column=1, padx=10, pady=5) # Adjusted row

        self.btn_browse_system_dir = tk.Button(master, text="Browse", command=self.browse_system_directory)
        self.btn_browse_system_dir.grid(row=2, column=2, padx=10, pady=5) # Adjusted row

        # --- GUI Layout: Checkboxes for Tag Inclusion Options ---
        self.check_image = tk.Checkbutton(master, text="Add <image> tags", variable=self.add_image_var)
        self.check_image.grid(row=3, column=0, sticky="w", padx=10, pady=5) # Adjusted row

        self.check_manual = tk.Checkbutton(master, text="Add <manual> tags", variable=self.add_manual_var)
        self.check_manual.grid(row=4, column=0, sticky="w", padx=10, pady=5) # Adjusted row

        # --- GUI Layout: Process Button ---
        self.btn_process = tk.Button(master, text="Process Gamelist (Creates New & Backs Up Original)", command=self.process_gamelist)
        self.btn_process.grid(row=5, column=0, columnspan=3, pady=20) # Adjusted row

        # --- GUI Layout: Status Message Display ---
        self.status_message = tk.StringVar()
        self.label_status = tk.Label(master, textvariable=self.status_message, fg="blue")
        self.label_status.grid(row=6, column=0, columnspan=3, padx=10, pady=5) # Adjusted row

    # --- Event Handler Functions ---

    # Helper function to generate the next available original backup path
    def _generate_orig_backup_path(self, original_file_path):
        gamelist_dir = os.path.dirname(original_file_path)
        base_filename, ext = os.path.splitext(os.path.basename(original_file_path))

        orig_backup_path = os.path.join(gamelist_dir, f"{base_filename}_orig{ext}")
        counter = 1
        while os.path.exists(orig_backup_path):
            orig_backup_path = os.path.join(gamelist_dir, f"{base_filename}_orig.{counter}{ext}")
            counter += 1
        return orig_backup_path

    def browse_input_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Gamelist XML File",
            filetypes=(("XML files", "*.xml"), ("All files", "*.*"))
        )
        if file_path:
            self.input_file_path.set(file_path)
            
            # Update proposed original backup path
            self.proposed_orig_backup_path.set(f"Original will be backed up to: {self._generate_orig_backup_path(file_path)}")

            # Auto-suggest the System Directory based on the selected gamelist's directory
            if not self.system_dir_path.get():
                self.system_dir_path.set(os.path.dirname(file_path))

    def browse_system_directory(self):
        dir_path = filedialog.askdirectory(
            title="Select System Directory (e.g., 'atari2600')"
        )
        if dir_path:
            self.system_dir_path.set(dir_path)

    def process_gamelist(self):
        input_path = self.input_file_path.get()
        system_dir = self.system_dir_path.get()

        add_image = self.add_image_var.get()
        add_manual = self.add_manual_var.get()

        # --- Input Validation Before Processing ---
        if not input_path:
            messagebox.showerror("Error", "Please select an input gamelist.xml file.")
            return
        
        if (add_image or add_manual) and not system_dir:
            messagebox.showerror("Error", "Please select the System Directory if you want to add image or manual tags. This helps the script locate your 'media' folders.")
            return
        
        if (add_image or add_manual) and not os.path.isdir(system_dir):
            messagebox.showerror("Error", f"The selected System Directory does not exist: {system_dir}. Please select a valid directory.")
            return

        if not add_image and not add_manual:
            messagebox.showwarning("Warning", "Neither 'Add <image> tags' nor 'Add <manual> tags' is checked. No tags will be added/updated in the XML.")
            return

        # Disable buttons and update status message
        self.btn_process.config(state=tk.DISABLED)
        self.btn_browse_input.config(state=tk.DISABLED)
        self.btn_browse_system_dir.config(state=tk.DISABLED)
        self.status_message.set("Processing...")
        self.master.update_idletasks()

        # Define gamelist_dir here, outside the try block, as it's derived from input_path
        # which has already been validated. This ensures it's always in scope.
        gamelist_dir = os.path.dirname(input_path) 

        try:
            # --- Safe Backup of Original Gamelist ---
            # Get the exact path for the backup right before moving
            actual_orig_backup_path = self._generate_orig_backup_path(input_path)
            
            if not os.path.exists(input_path):
                raise FileNotFoundError(f"The selected gamelist file '{input_path}' does not exist. It might have been moved or deleted.")

            try:
                shutil.move(input_path, actual_orig_backup_path)
            except shutil.Error as e:
                raise IOError(f"Failed to move original gamelist to backup location: {e}. Please check permissions or if the file is in use by another program.")
            
            # --- XML Reading and Initial Setup ---
            # Now, read the content from the *backed-up original* file.
            with open(actual_orig_backup_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()

            tree = ET.ElementTree(ET.fromstring(xml_content))
            root = tree.getroot()

            # Determine the parent directory of the 'gamelist.xml' file (its containing folder).
            gamelist_xml_parent_dir = os.path.dirname(actual_orig_backup_path)

            # Define the absolute paths to the expected media directories based on the selected System Directory.
            abs_images_root_dir = os.path.join(system_dir, "media", "images")
            abs_manuals_root_dir = os.path.join(system_dir, "media", "manuals")

            modifications = [] 

            # --- Iterate Through Game Entries and Apply Logic ---
            for game in root.findall('.//game'):
                path_element = game.find('path') 
                
                if path_element is not None:
                    path_value = path_element.text 
                    
                    if path_value:
                        path_value_normalized = path_value.replace("\\", "/")
                        base_name, _ = os.path.splitext(os.path.basename(path_value_normalized))

                        # --- Logic for <image> Tag ---
                        if add_image: 
                            image_filename = base_name + ".png" 
                            absolute_image_path = os.path.join(abs_images_root_dir, image_filename)
                            image_path_value = os.path.relpath(absolute_image_path, gamelist_xml_parent_dir).replace("\\", "/")
                            
                            # Ensure relative paths start with "./" or "../"
                            if not image_path_value.startswith(('./', '../')):
                                image_path_value = './' + image_path_value

                            image_element = game.find('image') 
                            if image_element is None: 
                                new_image_element = ET.Element('image') 
                                new_image_element.text = image_path_value 
                                try:
                                    path_index = list(game).index(path_element)
                                    modifications.append((game, path_index + 1, new_image_element))
                                except ValueError:
                                    pass 
                            else: 
                                image_element.text = image_path_value 

                        # --- Logic for <manual> Tag ---
                        if add_manual: 
                            manual_filename = base_name + ".pdf" 
                            absolute_manual_path = os.path.join(abs_manuals_root_dir, manual_filename)
                            manual_path_value = os.path.relpath(absolute_manual_path, gamelist_xml_parent_dir).replace("\\", "/")

                            # Ensure relative paths start with "./" or "../"
                            if not manual_path_value.startswith(('./', '../')):
                                manual_path_value = './' + manual_path_value

                            manual_element = game.find('manual') 
                            if manual_element is None: 
                                new_manual_element = ET.Element('manual') 
                                new_manual_element.text = manual_path_value 
                                
                                current_insert_after = None
                                if add_image: 
                                    current_insert_after = game.find('image') 
                                    if current_insert_after is None: 
                                        current_insert_after = path_element 
                                else: 
                                    current_insert_after = path_element

                                if current_insert_after is not None:
                                    try:
                                        insert_index = list(game).index(current_insert_after) + 1
                                        modifications.append((game, insert_index, new_manual_element))
                                    except ValueError:
                                        pass 
                            else: 
                                manual_element.text = manual_path_value 

            # --- Apply Pending Modifications to the XML Tree ---
            modifications.sort(key=lambda x: (id(x[0]), -x[1]))
            for parent, index, new_element in modifications:
                parent.insert(index, new_element) 
            
            # --- Final XML Formatting and Writing ---
            # Using ET.indent for pretty printing (Python 3.9+)
            ET.indent(tree, space="  ")
            
            # Determine the path for the new gamelist.xml (gamelist_new.xml in the same directory as original).
            new_gamelist_output_path = os.path.join(gamelist_dir, "gamelist_new.xml")

            # Write the modified ElementTree to the new gamelist.xml file (overwrites if exists).
            tree.write(new_gamelist_output_path, encoding='utf-8', xml_declaration=True)

            # --- Success Feedback ---
            self.status_message.set(f"Successfully processed! Original backed up to: '{actual_orig_backup_path}'. New gamelist saved to: '{new_gamelist_output_path}'.")
            messagebox.showinfo("Success", f"Gamelist processed successfully!\nOriginal backed up to: '{actual_orig_backup_path}'\nNew gamelist created: '{new_gamelist_output_path}'")

        # --- Error Handling ---
        except FileNotFoundError as e:
            messagebox.showerror("Error", f"File not found: {e}\nPlease check paths and permissions.")
            self.status_message.set(f"Error: File not found: {e}")
        except ET.ParseError as e:
            messagebox.showerror("Error", f"Error parsing XML file: {e}\nPlease ensure it's a valid XML.")
            self.status_message.set("Error: Invalid XML file.")
        except IOError as e:
            messagebox.showerror("File Operation Error", f"A file operation error occurred: {e}\nPlease ensure no other programs are using the XML files and check permissions.")
            self.status_message.set(f"Error: File operation failed: {e}")
        except Exception as e:
            messagebox.showerror("An Unexpected Error Occurred", str(e))
            self.status_message.set(f"An unexpected error occurred: {e}")
        finally:
            # Re-enable buttons regardless of success or failure
            self.btn_process.config(state=tk.NORMAL)
            self.btn_browse_input.config(state=tk.NORMAL)
            self.btn_browse_system_dir.config(state=tk.NORMAL)


# --- Main Execution Block ---
if __name__ == "__main__":
    root = tk.Tk()
    app = GamelistProcessorApp(root)
    root.mainloop()