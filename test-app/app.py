from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "Test app is running 🚀"

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "hostname": os.uname().nodename
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8002)