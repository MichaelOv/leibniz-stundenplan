#!/usr/bin/env python3
import subprocess
from pathlib import Path
from flask import Flask, jsonify, send_from_directory

app = Flask(__name__, static_folder='.')
BASE_DIR = Path(__file__).resolve().parent

@app.route('/')
def index():
    return send_from_directory(str(BASE_DIR), 'index.html')

@app.route('/data/<path:filename>')
def data(filename):
    return send_from_directory(str(BASE_DIR / 'data'), filename)

@app.route('/api/refresh', methods=['POST'])
def refresh():
    try:
        subprocess.run(['venv/bin/python', 'scripts/run_all.py'], cwd=str(BASE_DIR))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
