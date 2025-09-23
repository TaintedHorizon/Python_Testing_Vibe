"""
Entry point for running doc_processor as a module.
Usage: python -m doc_processor.app
"""

from .app import app

if __name__ == "__main__":
    # Start the Flask development server
    app.run(debug=True, host="0.0.0.0", port=5000)