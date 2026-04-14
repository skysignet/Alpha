from flask import Flask, request, Response
import json
import os

app = Flask(__name__)

@app.route('/api/calculate')
def calculate():
    return Response(
        json.dumps({"status": "ok", "message": "Flask is alive"}),
        mimetype='application/json',
        headers={"Access-Control-Allow-Origin": "*"}
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting on port {port}", flush=True)
    app.run(host='0.0.0.0', port=port)
