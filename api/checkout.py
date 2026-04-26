"""
SkySignet Checkout API — Stripe + Flask
Railway server: /api/checkout  /api/webhook

POST /api/checkout
Returns a PaymentIntent client_secret for Stripe Elements embedded payment.
Body JSON:
  tier       bronze | silver | silver_pd | silver_ox | 14k | 18k | platinum
  band       (optional) dream_portal | moroccan_stars | acanthus | stars_and_diamonds
  birthdate  (optional) e.g. 1985-03-21
  birthtime  (optional) e.g. 14:30
  birthplace (optional) e.g. Boulder, CO
  ring_size  (optional) e.g. 8.5
  initials   (optional) e.g. J·W·P
  tradition  (optional) western | vedic

Charges a 50% deposit. Balance is collected manually before shipping.

POST /api/webhook
Receives Stripe webhook events. On payment_intent.succeeded, appends order
record to orders.json with deposit_paid status.
"""
import json
import math
import os
from datetime import datetime

from flask import Flask, request as flask_request, Response, jsonify
from flask_cors import CORS
import stripe

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": ["https://www.skysignet.co", "https://skysignet.co"]}})
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
ORDERS_FILE = os.path.join(os.path.dirname(__file__), "..", "orders.json")

TIERS = {
    "bronze":     {"name": "SkySignet — Bronze",                  "price":    95000},
    "silver":     {"name": "SkySignet — Sterling Silver",         "price":   150000},
    "silver_ox":  {"name": "SkySignet — Sterling Silver Oxidized","price":   170000},
    "silver_pd":  {"name": "SkySignet — Silver & Palladium",      "price":   190000},
    "14k":        {"name": "SkySignet — 14k Yellow Gold",         "price":   770000},
    "18k":        {"name": "SkySignet — 18k Yellow Gold",         "price":   980000},
    "platinum":   {"name": "SkySignet — Platinum",                "price":  1100000},
    "ether":      {"name": "SkySignet — Ether (test)",            "price":       100},
}

BAND_ADDON = {
    "dream_portal":       "Dream Portal Band (+$500)",
    "moroccan_stars":     "Moroccan Stars Band (+$500)",
    "acanthus":           "Acanthus Band (+$500)",
    "stars_and_diamonds": "Stars & Diamonds Band (+$500)",
}
BAND_PRICE     = 50000   # $500.00
INITIALS_PRICE = 7500    # $75.00



@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


@app.route('/api/checkout', methods=['POST', 'OPTIONS'])
def checkout():
    if flask_request.method == 'OPTIONS':
        response = jsonify({})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response, 204

    try:
        data = flask_request.get_json(force=True)
        tier       = data.get("tier", "").lower()
        band       = data.get("band", "")
        print(f"[DEBUG] band received: {repr(band)}")
        birthdate  = data.get("birthdate", "")
        birthtime  = data.get("birthtime", "")
        birthplace = data.get("birthplace", "")
        ring_size  = data.get("ring_size", "")
        initials   = data.get("initials", "")
        tradition  = data.get("tradition", "western")

        if tier not in TIERS:
            raise ValueError(f"Invalid tier: {tier}")

        # Build order description
        details = []
        if birthdate:  details.append(f"Born {birthdate}")
        if birthtime:  details.append(birthtime)
        if birthplace: details.append(birthplace)
        if tradition:  details.append("Vedic Sidereal" if tradition == "vedic" else "Western Tropical")
        if ring_size:  details.append(f"Size {ring_size}")
        if initials:   details.append(f"Initials: {initials}")
        description = " · ".join(details) if details else "Bespoke natal chart signet ring"

        frontend_total = int(data.get('total_cents', 0))

        # Recalculate server-side for verification
        band_prices = {
            'stars_and_diamonds': 50000,
            'stars-and-diamonds': 50000,
            'band-diamond':       50000,
        }
        band_addon = band_prices.get(str(band).strip().lower(), 0)
        server_total = TIERS.get(tier, {}).get('price', 150000) + band_addon
        if initials:
            server_total += INITIALS_PRICE

        # Log any mismatch
        if frontend_total and abs(frontend_total - server_total) > 100:
            print(f"[WARNING] Total mismatch: frontend={frontend_total} server={server_total}")

        # Use server total as authoritative (prevents manipulation)
        total_cents = server_total
        deposit_cents = math.ceil(total_cents / 2)
        print(f"[DEBUG] tier={tier} band={band} band_addon={band_addon} total={total_cents} deposit={deposit_cents}")

        intent = stripe.PaymentIntent.create(
            amount=deposit_cents,
            currency="usd",
            payment_method_types=["card"],
            receipt_email=data.get("email"),
            description=f"SkySignet {tier} 50% deposit",
            metadata={
                "full_amount_cents":  str(total_cents),
                "deposit_amount_cents": str(deposit_cents),
                "metal":              tier,
                "band":               band or "none",
                "initials":           initials,
                "ring_size":          ring_size,
                "birth_date":         data.get("birthdate", ""),
                "birth_time":         data.get("birthtime", ""),
                "birth_location":     data.get("birthplace", ""),
                "tradition":          data.get("tradition", "western"),
            },
        )

        body = json.dumps({"clientSecret": intent.client_secret})
        status = 200

    except Exception as e:
        body = json.dumps({"error": str(e)})
        status = 400

    return Response(body, status=status, mimetype='application/json')


@app.route('/api/webhook', methods=['POST'])
def webhook():
    payload    = flask_request.get_data()
    sig_header = flask_request.headers.get('Stripe-Signature', '')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        return Response(json.dumps({"error": str(e)}), status=400, mimetype='application/json')

    if event['type'] == 'payment_intent.succeeded':
        intent  = event['data']['object']
        meta    = intent.get('metadata', {})
        order   = {
            "timestamp":          datetime.utcnow().isoformat() + "Z",
            "payment_intent_id":  intent.get("id"),
            "payment_status":     "deposit_paid",
            "customer_email":     (intent.get("charges", {}).get("data") or [{}])[0].get("billing_details", {}).get("email"),
            "amount_paid_cents":  intent.get("amount_received"),
            "full_amount_cents":  meta.get("full_amount_cents"),
            "balance_cents":      meta.get("balance_cents"),
            "tier":               meta.get("tier"),
            "band":               meta.get("band"),
            "birthdate":          meta.get("birthdate"),
            "birthtime":          meta.get("birthtime"),
            "birthplace":         meta.get("birthplace"),
            "ring_size":          meta.get("ring_size"),
            "initials":           meta.get("initials"),
            "tradition":          meta.get("tradition"),
        }

        orders = []
        if os.path.exists(ORDERS_FILE):
            try:
                with open(ORDERS_FILE, 'r') as f:
                    orders = json.load(f)
            except (json.JSONDecodeError, IOError):
                orders = []
        orders.append(order)
        with open(ORDERS_FILE, 'w') as f:
            json.dump(orders, f, indent=2)

    return Response(json.dumps({"received": True}), status=200, mimetype='application/json')

print("=== REGISTERED ROUTES ===")
for rule in app.url_map.iter_rules():
    print(f"  {rule.methods} {rule}")
print("===========================")
