#!/usr/bin/env python3
"""
Simple test server to preview the intake analysis page changes.
This bypasses the import issues in the main app for quick UI testing.
"""

from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return '''
    <h1>UI Test Server</h1>
    <p><a href="/test_intake">Test Intake Analysis Page</a></p>
    '''

@app.route('/test_intake')
def test_intake():
    # Mock data for testing
    return render_template('intake_analysis.html', 
                          intake_dir='/mnt/scans_intake')

@app.route('/mission_control_page')
def mission_control_page():
    return '<h1>Mission Control (Mock)</h1><a href="/test_intake">Back to Intake Analysis</a>'

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)