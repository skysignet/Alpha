"""
SkySignet API — main entry point
Combines /api/calculate, /api/checkout, and /api/send-chart into one Flask app
"""
import os
from flask import Flask
from api.calculate import app as calculate_app
from api.checkout import app as checkout_app
from api.send_chart import send_chart_bp

app = Flask(__name__)

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

# Register all routes from calculate and checkout modules
for rule in calculate_app.url_map.iter_rules():
    app.add_url_rule(
        rule.rule,
        endpoint=rule.endpoint + '_calc',
        view_func=calculate_app.view_functions[rule.endpoint],
        methods=rule.methods
    )
for rule in checkout_app.url_map.iter_rules():
    app.add_url_rule(
        rule.rule,
        endpoint=rule.endpoint + '_checkout',
        view_func=checkout_app.view_functions[rule.endpoint],
        methods=rule.methods
    )

# Register send-chart blueprint
app.register_blueprint(send_chart_bp)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting SkySignet API on port {port}", flush=True)
    app.run(host='0.0.0.0', port=port)
