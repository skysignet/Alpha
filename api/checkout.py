"""
SkySignet Checkout API — Stripe + Flask
Railway server: /api/checkout
POST /api/checkout
Body JSON:
  tier       bronze | silver | silver_pd | 14k | 18k | platinum
  band       (optional) dream_portal | moroccan_stars | acanthus | stars_and_diamonds
  birthdate  (optional) e.g. 1985-03-21
  birthtime  (optional) e.g. 14:30
  birthplace (optional) e.g. Boulder, CO
  ring_size  (optional) e.g. 8.5
  initials   (optional) e.g. J·W·P
  tradition  (optional) western | vedic
"""
import json
import os
import stripe
from flask import Flask, request as flask_request, Response

app = Flask(__name__)
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

TIERS = {
    "bronze":     {"name": "SkySignet — Bronze",                  "price":    55000},
    "silver":     {"name": "SkySignet — Sterling Silver",         "price":   150000},
    "silver_ox":  {"name": "SkySignet — Sterling Silver Oxidized","price":   170000},
    "silver_pd":  {"name": "SkySignet — Silver & Palladium",      "price":   190000},
    "14k":        {"name": "SkySignet — 14k Yellow Gold",         "price":   770000},
    "18k":        {"name": "SkySignet — 18k Yellow Gold",         "price":   960000},
    "platinum":   {"name": "SkySignet — Platinum",                "price":  1110000},
}

BAND_ADDON = {
    "dream_portal":       "Dream Portal Band (+$500)",
    "moroccan_stars":     "Moroccan Stars Band (+$500)",
    "acanthus":           "Acanthus Band (+$500)",
    "stars_and_diamonds": "Stars & Diamonds Band (+$500)",
}
BAND_PRICE   = 50000  # $500.00
INITIALS_PRICE = 7500  # $75.00

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

        if TIERS[tier]["price"] is None:
            raise ValueError("Platinum is priced on request — please email jesseskydesign@gmail.com")

        details = []
        if birthdate:  details.append(f"Born {birthdate}")
        if birthtime:  details.append(birthtime)
        if birthplace: details.append(birthplace)
        if tradition:  details.append("Vedic Sidereal" if tradition == "vedic" else "Western Tropical")
        if ring_size:  details.append(f"Size {ring_size}")
        if initials:   details.append(f"Initials: {initials}")
        description = " · ".join(details) if details else "Bespoke natal chart signet ring"

        line_items = [{
            "price_data": {
                "currency": "usd",
                "unit_amount": TIERS[tier]["price"],
                "product_data": {
                    "name": TIERS[tier]["name"],
                    "description": description,
                },
            },
            "quantity": 1,
        }]

        if band and band in BAND_ADDON:
            line_items.append({
                "price_data": {
                    "currency": "usd",
                    "unit_amount": BAND_PRICE,
                    "product_data": {"name": BAND_ADDON[band]},
                },
                "quantity": 1,
            })

        if initials:
            line_items.append({
                "price_data": {
                    "currency": "usd",
                    "unit_amount": INITIALS_PRICE,
                    "product_data": {"name": "Initial Engraving (+$75)"},
                },
                "quantity": 1,
            })

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            metadata={
                "tier":       tier,
                "band":       band or "none",
                "birthdate":  birthdate,
                "birthtime":  birthtime,
                "birthplace": birthplace,
                "ring_size":  ring_size,
                "initials":   initials,
                "tradition":  tradition,
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
