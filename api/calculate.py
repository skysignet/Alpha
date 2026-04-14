"""
SkySignet Natal Chart API — pyswisseph + Flask
Railway server: /api/calculate

Query params:
  date   YYYY-MM-DD
  time   HH:MM  (UTC)
  lat    decimal degrees (N positive)
  lon    decimal degrees (E positive)
  system tropical | vedic
"""

import json
import os
import swisseph as swe
from datetime import datetime, timezone
from flask import Flask, request as flask_request, Response

app = Flask(__name__)

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
    lon = ((lon % 360) + 360) % 360
    sign_index = int(lon // 30) % 12
    deg_in_sign = lon % 30
    return ZODIAC_SIGNS[sign_index], round(deg_in_sign, 4)

def which_house(lon, cusps):
    lon = ((lon % 360) + 360) % 360
    for i in range(1, 13):
        next_i = (i % 12) + 1
        start = cusps[i]
        end   = cusps[next_i]
        if end < start:
            if lon >= start or lon < end:
                return i
        else:
            if start <= lon < end:
                return i
    return 1

def calculate_chart(date_str, time_str, lat, lon, system):
    dt_str = f"{date_str} {time_str}"
    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    jd = swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute / 60.0)

    if system == "vedic":
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        flag = swe.FLG_SWIEPH | swe.FLG_SIDEREAL
        ayanamsa = swe.get_ayanamsa(jd)
    else:
        swe.set_sid_mode(swe.SIDM_FAGAN_BRADLEY)
        flag = swe.FLG_SWIEPH
        ayanamsa = 0.0

    h_result  = swe.houses(jd, lat, lon, b'P')
    raw_cusps = list(h_result[0])
    ascmc     = h_result[1]
    cusps = [0.0] + raw_cusps

    if system == "vedic":
        cusps   = [0.0] + [((c - ayanamsa) % 360) for c in cusps[1:]]
        asc_lon = (ascmc[0] - ayanamsa) % 360
        mc_lon  = (ascmc[1] - ayanamsa) % 360
    else:
        asc_lon = ascmc[0]
        mc_lon  = ascmc[1]

    planets = {}
    for name, pid in PLANET_IDS.items():
        res   = swe.calc_ut(jd, pid, flag)
        p_lon = res[0][0]
        sign, deg_in = lon_to_sign(p_lon)
        planets[name] = {
            "lon":         round(p_lon, 4),
            "sign":        sign,
            "deg_in_sign": round(deg_in, 4),
            "house":       which_house(p_lon, cusps)
        }

    node_res  = swe.calc_ut(jd, swe.TRUE_NODE, flag)
    north_lon = node_res[0][0]
    south_lon = (north_lon + 180.0) % 360.0
    north_sign, north_deg = lon_to_sign(north_lon)
    south_sign, south_deg = lon_to_sign(south_lon)

    nodes = {
        "north": {"lon": round(north_lon,4), "sign": north_sign, "deg_in_sign": round(north_deg,4), "house": which_house(north_lon, cusps)},
        "south": {"lon": round(south_lon,4), "sign": south_sign, "deg_in_sign": round(south_deg,4), "house": which_house(south_lon, cusps)}
    }

    asc_sign, asc_deg = lon_to_sign(asc_lon)
    mc_sign,  mc_deg  = lon_to_sign(mc_lon)
    angles = {
        "ascendant": {"lon": round(asc_lon,4), "sign": asc_sign, "deg_in_sign": round(asc_deg,4)},
        "mc":        {"lon": round(mc_lon, 4), "sign": mc_sign,  "deg_in_sign": round(mc_deg, 4)}
    }

    return {
        "planets": planets,
        "nodes":   nodes,
        "angles":  angles,
        "houses":  {"system": "Placidus", "cusps": [round(c,4) for c in cusps]},
        "system":  system,
        "input":   {"date": date_str, "time": time_str, "lat": lat, "lon": lon}
    }


@app.route('/api/calculate', methods=['GET'])
def calculate_endpoint():
    try:
        date_str = flask_request.args.get("date", "")
        time_str = flask_request.args.get("time", "00:00")
        lat      = float(flask_request.args.get("lat", "0"))
        lon      = float(flask_request.args.get("lon", "0"))
        system   = flask_request.args.get("system", "tropical").lower()
        if not date_str:
            raise ValueError("Missing required param: date")
        result = calculate_chart(date_str, time_str, lat, lon, system)
        body, status = json.dumps(result), 200
    except Exception as e:
        body, status = json.dumps({"error": str(e)}), 400
    return Response(body, status=status, mimetype='application/json',
                    headers={"Access-Control-Allow-Origin": "*"})


@app.route('/api/calculate', methods=['OPTIONS'])
def calculate_options():
    return Response("", status=200, headers={
        "Access-Control-Allow-Origin":  "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    })


@app.route('/')
def health():
    return Response(json.dumps({"status": "ok"}), mimetype='application/json')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting SkySignet API on port {port}", flush=True)
    app.run(host='0.0.0.0', port=port)
