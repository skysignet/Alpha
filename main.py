"""
SkySignet API — main entry point
Combines /api/calculate and /api/checkout into one Flask app
"""

import os
from flask import Flask
from api.calculate import app as calculate_app
from api.checkout import app as checkout_app

app = Flask(__name__)

# Register all routes from both modules
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting SkySignet API on port {port}", flush=True)
    app.run(host='0.0.0.0', port=port)
