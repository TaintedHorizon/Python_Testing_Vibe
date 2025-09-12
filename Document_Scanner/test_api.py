# Import the necessary libraries.
# The 'google.generativeai' library is for interacting with the Gemini API.
import google.generativeai as genai
# The 'os' library helps with interacting with the operating system, like constructing file paths.
import os
# The 'sys' library allows us to modify the Python path.
import sys

# This section makes it possible for this script to find the 'config.py' file.
# It adds the parent directory of the current script's directory to the Python path.
# os.path.dirname(__file__) gets the directory where this script is located.
# os.path.join(..., '..') goes one level up to the parent directory.
# os.path.abspath() gets the full absolute path.
# sys.path.append() adds this path to the list of places Python looks for modules.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the API_KEY variable from the 'config.py' file located in the 'Document_Scanner' directory.
from Document_Scanner.config import API_KEY

# Configure the 'google.generativeai' library with your API key.
# This authenticates your script with the Gemini API.
genai.configure(api_key=API_KEY)

# Print a confirmation message to the console.
print("Successfully configured the API key.")
# Print a header for the list of models.
print("Listing available models:")

# Loop through all the models available in the Gemini API.
for m in genai.list_models():
  # Check if the model supports the 'generateContent' method, which is used for creating text.
  if 'generateContent' in m.supported_generation_methods:
    # If the model can generate content, print its name to the console.
    print(m.name)
