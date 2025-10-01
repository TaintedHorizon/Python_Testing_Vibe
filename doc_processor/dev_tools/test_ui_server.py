#!/usr/bin/env python3
"""
Simple test server to preview the intake analysis page changes.
This bypasses the import issues in the main app for quick UI testing.
"""

import sys
import os

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template
from config_manager import app_config

app = Flask(__name__, template_folder='doc_processor/templates')

@app.route('/')
def index():
    return '''
    <h1>UI Test Server</h1>
    <p><a href="/test_intake">Test Intake Analysis Page</a></p>
    '''

@app.route('/test_intake')
def test_intake():
    # Mock data for testing - use config manager for intake directory
    return render_template('intake_analysis.html', 
                          intake_dir=app_config.INTAKE_DIR)

@app.route('/batch_control_page')
def batch_control_page():
    return '<h1>Batch Control (Mock)</h1><a href="/test_intake">Back to Intake Analysis</a>'

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)