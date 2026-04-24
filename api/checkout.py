"""
SkySignet Checkout API — Stripe + Flask
Railway server: /api/checkout  /api/webhook

POST /api/checkout
Body JSON:
  tier       bronze | silver | silver_pd | silver_ox | 14k | 18k | platinum
  band       (optional) dream_portal | moroccan_stars | acanthus | stars_and_diamonds
  birthdate  (optional) e.g. 1985-03-21
  birthtime  (optional) e.g. 14:30
  birthplace (optional) e.g. Boulder, CO
  ring_size  (optional) e.g. 8.5
  initials   (optional) e.g. J·W·P
  tradition  (optional) western | vedic

Charges a 50% deposit at checkout. Balance is collected manually before shipping.

POST /api/webhook
Receives Stripe webhook events. On checkout.session.completed, appends order
record to orders.json with deposit_paid status.
"""
import json
import math
import os
from datetime import datetime

import stripe
from flask import Flask, request as flask_request, Response

app = Flask(__name__)
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
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
}

BAND_ADDON = {
    "dream_portal":       "Dream Portal Band (+$500)",
    "moroccan_stars":     "Moroccan Stars Band (+$500)",
    "acanthus":           "Acanthus Band (+$500)",
    "stars_and_diamonds": "Stars & Diamonds Band (+$500)",
}
BAND_PRICE     = 50000   # $500.00
INITIALS_PRICE = 7500    # $75.00


@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.route('/api/checkout', methods=['POST', 'OPTIONS'])
def checkout():
    if flask_request.method == 'OPTIONS':
        return Response("", status=200)

    try:
        data = flask_request.get_json(force=True)
        tier       = data.get("tier", "").lower()
        band       = data.get("band", "").lower()
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

        # Calculate full order total
        total_cents = TIERS[tier]["price"]
        if band and band in BAND_ADDON:
            total_cents += BAND_PRICE
        if initials:
            total_cents += INITIALS_PRICE

        # Charge 50% deposit (round up to nearest cent)
        deposit_cents = math.ceil(total_cents / 2)
        balance_cents = total_cents - deposit_cents

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": deposit_cents,
                    "product_data": {
                        "name": f"{TIERS[tier]['name']} — 50% Deposit",
                        "description": description,
                    },
                },
                "quantity": 1,
            }],
            mode="payment",
            metadata={
                "tier":               tier,
                "band":               band or "none",
                "birthdate":          birthdate,
                "birthtime":          birthtime,
                "birthplace":         birthplace,
                "ring_size":          ring_size,
                "initials":           initials,
                "tradition":          tradition,
                "full_amount_cents":  str(total_cents),
                "deposit_cents":      str(deposit_cents),
                "balance_cents":      str(balance_cents),
                "payment_status":     "deposit_pending",
            },
            success_url="https://skysignet.co/success.html?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="https://skysignet.co/#commission",
        )

        body = json.dumps({"url": session.url})
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

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        meta    = session.get('metadata', {})
        order   = {
            "timestamp":          datetime.utcnow().isoformat() + "Z",
            "session_id":         session.get("id"),
            "payment_status":     "deposit_paid",
            "customer_email":     (session.get("customer_details") or {}).get("email"),
            "amount_paid_cents":  session.get("amount_total"),
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
