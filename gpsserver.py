#!/usr/bin/env python3

from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

@app.route('/gps', methods=['POST'])
def receive_gps():
    """Receive and display GPS data"""
    try:
        data = request.get_json()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"\n=== GPS Data Received at {timestamp} ===")
        print(f"From IP: {request.remote_addr}")

        for key, value in data.items():
            print(f"{key}: {value}")

        print("=" * 50)

        return jsonify({"status": "received"}), 200
    
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health')
def health():
    return jsonify({"status": "running"})

if __name__ == '__main__':
    print("GPS Server starting on port 80...")
    print("Waiting for GPS data...\n")
    app.run(host='0.0.0.0', port=80, debug=True)

