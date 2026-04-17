"""
SkySignet Checkout API — Stripe + Flask
Railway server: /api/checkout

POST /api/checkout
Body JSON:
  tier   silver | silver_pd | 14k | 18k | platinum
  band   (optional) dream_portal | moroccan_stars | acanthus | stars_and_diamonds
"""

import json
import os
import stripe
from flask import Flask, request as flask_request, Response

app = Flask(__name__)

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

TIERS = {
    "silver":     {"name": "SkySignet — Sterling Silver",         "price": 88800},
    "silver_pd":  {"name": "SkySignet — Silver & Palladium",      "price": 111100},
    "14k":        {"name": "SkySignet — 14k Gold",                "price": 333300},
    "18k":        {"name": "SkySignet — 18k Gold",                "price": 444400},
    "platinum":   {"name": "SkySignet — Platinum",                "price": 888800},
}

BAND_ADDON = {
    "dream_portal":     "Dream Portal Band",
    "moroccan_stars":   "Moroccan Stars Band",
    "acanthus":         "Acanthus Band",
    "stars_and_diamonds": "Stars & Diamonds Band",
}

BAND_PRICE = 55500  # $555.00


@app.route('/api/checkout', methods=['POST'])
def checkout():
    try:
        data = flask_request.get_json(force=True)
        tier = data.get("tier", "").lower()
        band = data.get("band", "").lower()

        if tier not in TIERS:
            raise ValueError(f"Invalid tier: {tier}")

        line_items = [{
            "price_data": {
                "currency": "usd",
                "unit_amount": TIERS[tier]["price"],
                "product_data": {"name": TIERS[tier]["name"]},
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

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            success_url="https://skysignet.vercel.app/success",
            cancel_url="https://skysignet.vercel.app/#commission",
        )

        body = json.dumps({"url": session.url})
        status = 200

    except Exception as e:
        body = json.dumps({"error": str(e)})
        status = 400

    return Response(body, status=status, mimetype='application/json',
                    headers={"Access-Control-Allow-Origin": "*"})


@app.route('/api/checkout', methods=['OPTIONS'])
def checkout_options():
    return Response("", status=200, headers={
        "Access-Control-Allow-Origin":  "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    })
