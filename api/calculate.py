"""
SkySignet Natal Chart API — pyswisseph backend
Vercel serverless function: /api/calculate

Query params:
  date   YYYY-MM-DD
  time   HH:MM  (local time at birth location)
  lat    decimal degrees (N positive)
  lon    decimal degrees (E positive)
  system tropical | vedic

Returns JSON:
{
  "planets": {
    "sun":     { "lon": 283.32, "sign": "Capricorn", "deg_in_sign": 13.32, "house": 12 },
    "moon":    { ... },
    "mercury": { ... },
    "venus":   { ... },
    "mars":    { ... },
    "jupiter": { ... },
    "saturn":  { ... }
  },
  "nodes": {
    "north": { "lon": 150.20, "sign": "Virgo", "deg_in_sign": 0.20, "house": 8 },
    "south": { "lon": 330.20, "sign": "Pisces", "deg_in_sign": 0.20, "house": 2 }
  },
  "angles": {
    "ascendant": { "lon": 289.97, "sign": "Capricorn", "deg_in_sign": 19.97 },
    "mc":        { "lon": 224.95, "sign": "Scorpio",   "deg_in_sign": 14.95 }
  },
  "houses": {
    "system": "Placidus",
    "cusps": [0.0, 289.97, 320.5, 351.2, 21.4, 52.8, 109.97, 140.5, 171.2, 201.4, 232.8, 260.1, 280.5]
    // cusps[0] unused, cusps[1] = house 1 cusp = Ascendant, ... cusps[12] = house 12 cusp
  },
  "system": "tropical",
  "input": { "date": "1980-01-04", "time": "07:42", "lat": 41.49, "lon": -71.31 }
}
"""

import json
import swisseph as swe
from datetime import datetime, timezone
import math

# ---------------------------------------------------------------------------
# Vercel entry point
# ---------------------------------------------------------------------------
def handler(request, response):
    # CORS
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Content-Type"] = "application/json"

    if request.method == "OPTIONS":
        response.status_code = 200
        return response.send("")

    try:
        params = request.args
        date_str = params.get("date", "")      # YYYY-MM-DD
        time_str = params.get("time", "00:00") # HH:MM UTC (frontend converts to UTC before calling)
        lat      = float(params.get("lat", "0"))
        lon      = float(params.get("lon", "0"))
        system   = params.get("system", "tropical").lower()

        if not date_str:
            raise ValueError("Missing required param: date")

        result = calculate_chart(date_str, time_str, lat, lon, system)
        response.status_code = 200
        return response.send(json.dumps(result))

    except Exception as e:
        response.status_code = 400
        return response.send(json.dumps({"error": str(e)}))


# ---------------------------------------------------------------------------
# Core calculation
# ---------------------------------------------------------------------------
ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

PLANET_IDS = {
    "sun":     swe.SUN,
    "moon":    swe.MOON,
    "mercury": swe.MERCURY,
    "venus":   swe.VENUS,
    "mars":    swe.MARS,
    "jupiter": swe.JUPITER,
    "saturn":  swe.SATURN,
}

def lon_to_sign(lon):
    sign_index = int(lon // 30) % 12
    deg_in_sign = lon % 30
    return ZODIAC_SIGNS[sign_index], round(deg_in_sign, 4)

def which_house(lon, cusps):
    """Return house number (1-12) given ecliptic longitude and house cusps array."""
    for i in range(1, 13):
        next_i = (i % 12) + 1
        cusp_start = cusps[i]
        cusp_end   = cusps[next_i]
        if cusp_end < cusp_start:  # crosses 0°
            if lon >= cusp_start or lon < cusp_end:
                return i
        else:
            if cusp_start <= lon < cusp_end:
                return i
    return 1  # fallback

def calculate_chart(date_str, time_str, lat, lon, system):
    # Parse UTC datetime
    dt_str = f"{date_str} {time_str}"
    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)

    # Julian Day Number (UT)
    jd = swe.julday(dt.year, dt.month, dt.day,
                    dt.hour + dt.minute / 60.0 + dt.second / 3600.0)

    # Ayanamsa for Vedic
    if system == "vedic":
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        flag = swe.FLG_SWIEPH | swe.FLG_SIDEREAL
        ayanamsa = swe.get_ayanamsa(jd)
    else:
        swe.set_sid_mode(swe.SIDM_FAGAN_BRADLEY)  # reset — tropical uses no sidereal mode
        flag = swe.FLG_SWIEPH
        ayanamsa = 0.0

    # ---------- Houses (Placidus) ----------
    # swe.houses returns (cusps_tuple_13, ascmc_tuple_10)
    # cusps[0] = 0.0 (unused), cusps[1] = ASC = house 1, ... cusps[12] = house 12
    # ascmc[0] = Ascendant, ascmc[1] = MC
    cusps_raw, ascmc = swe.houses(jd, lat, lon, b'P')  # b'P' = Placidus
    cusps = list(cusps_raw)  # index 0 unused, 1-12 are house cusps

    # For Vedic: rotate cusps by ayanamsa
    if system == "vedic":
        cusps = [0.0] + [((c - ayanamsa) % 360) for c in cusps[1:]]
        asc_lon = (ascmc[0] - ayanamsa) % 360
        mc_lon  = (ascmc[1] - ayanamsa) % 360
    else:
        asc_lon = ascmc[0]
        mc_lon  = ascmc[1]

    # ---------- Planets ----------
    planets = {}
    for name, pid in PLANET_IDS.items():
        result, _ = swe.calc_ut(jd, pid, flag)
        p_lon = result[0]
        sign, deg_in = lon_to_sign(p_lon)
        planets[name] = {
            "lon":        round(p_lon, 4),
            "sign":       sign,
            "deg_in_sign": round(deg_in, 4),
            "house":      which_house(p_lon, cusps)
        }

    # ---------- True Lunar Node ----------
    node_result, _ = swe.calc_ut(jd, swe.TRUE_NODE, flag)
    north_lon = node_result[0]
    south_lon = (north_lon + 180.0) % 360.0

    north_sign, north_deg = lon_to_sign(north_lon)
    south_sign, south_deg = lon_to_sign(south_lon)

    nodes = {
        "north": {
            "lon":         round(north_lon, 4),
            "sign":        north_sign,
            "deg_in_sign": round(north_deg, 4),
            "house":       which_house(north_lon, cusps)
        },
        "south": {
            "lon":         round(south_lon, 4),
            "sign":        south_sign,
            "deg_in_sign": round(south_deg, 4),
            "house":       which_house(south_lon, cusps)
        }
    }

    # ---------- Angles ----------
    asc_sign, asc_deg = lon_to_sign(asc_lon)
    mc_sign,  mc_deg  = lon_to_sign(mc_lon)
    angles = {
        "ascendant": {"lon": round(asc_lon, 4), "sign": asc_sign, "deg_in_sign": round(asc_deg, 4)},
        "mc":        {"lon": round(mc_lon,  4), "sign": mc_sign,  "deg_in_sign": round(mc_deg,  4)}
    }

    # ---------- House cusps as rounded list ----------
    house_cusps = [round(c, 4) for c in cusps]  # [0] is 0.0 placeholder

    return {
        "planets": planets,
        "nodes":   nodes,
        "angles":  angles,
        "houses": {
            "system": "Placidus",
            "cusps":  house_cusps
        },
        "system": system,
        "input": {
            "date": date_str,
            "time": time_str,
            "lat":  lat,
            "lon":  lon
        }
    }
# ── Flask web server entry point ──
from flask import Flask, request as flask_request, jsonify
app = Flask(__name__)

@app.route('/api/calculate')
def calculate_endpoint():
    class Req:
        method = flask_request.method
        args = flask_request.args
    class Res:
        headers = {}
        status_code = 200
        _body = ''
        def send(self, body):
            self._body = body
            return self._body
    res = Res()
    result = handler(Req(), res)
    return result, res.status_code, {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
