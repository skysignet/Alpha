from http.server import BaseHTTPRequestHandler
import json
import math
from urllib.parse import urlparse, parse_qs
from skyfield.api import load, wgs84
from skyfield.elementslib import osculating_elements_of
from skyfield.framelib import ecliptic_frame
from dateutil import parser
import pytz

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)

        try:
            birth_date = query.get('date')[0]
            birth_time = query.get('time')[0]
            lat        = float(query.get('lat')[0])
            lon        = float(query.get('lon')[0])
            system     = query.get('system', ['tropical'])[0]

            ts  = load.timescale()
            eph = load('de421.bsp')

            # ── Parse UTC datetime ──────────────────────────────────────────
            dt = parser.parse(f"{birth_date} {birth_time}")
            t  = ts.from_datetime(dt.replace(tzinfo=pytz.UTC))

            # ── 7 Classical Planets ─────────────────────────────────────────
            planet_bodies = {
                'Moon':    eph['moon'],
                'Mercury': eph['mercury'],
                'Venus':   eph['venus'],
                'Sun':     eph['sun'],
                'Mars':    eph['mars'],
                'Jupiter': eph['jupiter_barycenter'],
                'Saturn':  eph['saturn_barycenter'],
            }

            results = {}
            for name, body in planet_bodies.items():
                astrometric = eph['earth'].at(t).observe(body)
                _, lon_val, _ = astrometric.apparent().frame_latlon(ecliptic_frame)
                results[name] = lon_val.degrees

            # ── Lunar Nodes (osculating elements from JPL) ──────────────────
            moon_pos = (eph['moon'] - eph['earth']).at(t)
            elements = osculating_elements_of(moon_pos)
            north_node = elements.longitude_of_ascending_node.degrees % 360
            south_node = (north_node + 180) % 360
            results['NorthNode'] = north_node
            results['SouthNode'] = south_node

            # ── Houses (Placidus) ────────────────────────────────────────────
            # Requires lat/lon. If not provided (0,0) we skip.
            houses = None
            if not (lat == 0 and lon == 0):
                houses = placidus_houses(t, lat, lon, eph)

            # ── Vedic correction (Lahiri ayanamsa) ───────────────────────────
            if system == 'vedic':
                ayanamsa = 24.1
                for key in results:
                    results[key] = (results[key] - ayanamsa) % 360
                if houses:
                    houses = [(h - ayanamsa) % 360 for h in houses]

            # ── Round everything ─────────────────────────────────────────────
            results = {k: round(v, 2) for k, v in results.items()}
            if houses:
                houses = [round(h, 2) for h in houses]

            payload = {'planets': results}
            if houses:
                payload['houses'] = houses

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())


def placidus_houses(t, lat_deg, lon_deg, eph):
    """
    Calculate 12 Placidus house cusps.
    Returns list of 12 ecliptic longitudes [H1..H12].
    H1 = Ascendant, H4 = IC, H7 = Descendant, H10 = MC.
    """
    # Obliquity of ecliptic
    earth = eph['earth']
    sun   = eph['sun']
    astr  = earth.at(t).observe(sun).apparent()
    _, sun_lon, _ = astr.frame_latlon(ecliptic_frame)

    # Use Skyfield to get Greenwich Mean Sidereal Time
    # then add geographic longitude to get Local Sidereal Time
    gst = t.gast  # Greenwich Apparent Sidereal Time in hours
    lst = (gst + lon_deg / 15.0) % 24  # Local Sidereal Time in hours
    RAMC = math.radians(lst * 15.0)    # Right Ascension of Midheaven (radians)

    # Obliquity (mean, J2000 + correction)
    T   = (t.tt - 2451545.0) / 36525.0
    eps = math.radians(23.439291111
                       - 0.013004167 * T
                       - 0.000000164 * T * T
                       + 0.000000504 * T * T * T)

    lat = math.radians(lat_deg)

    # ── MC (Midheaven) ───────────────────────────────────────────────────────
    MC_ra = math.atan2(math.tan(RAMC), math.cos(eps))
    MC    = math.degrees(MC_ra) % 360
    if math.cos(RAMC) < 0:
        MC = (MC + 180) % 360

    # ── Ascendant ────────────────────────────────────────────────────────────
    Asc = math.degrees(
        math.atan2(
            math.cos(RAMC),
            -math.sin(RAMC) * math.cos(eps) - math.tan(lat) * math.sin(eps)
        )
    ) + 180
    Asc = Asc % 360

    # ── Placidus intermediate cusps (iterative) ──────────────────────────────
    def placidus_cusp(n, ramc):
        """
        n=1 → H11/H3, n=2 → H12/H2
        ramc: RAMC for upper (above) hemisphere, RAMC+pi for lower
        """
        theta = ramc + math.radians(n * 30)
        for _ in range(30):
            dec = math.asin(math.sin(eps) * math.sin(theta))
            # Ascensional difference
            try:
                ad = math.asin(
                    max(-1.0, min(1.0, math.tan(lat) * math.tan(dec)))
                )
            except ValueError:
                ad = 0
            theta_new = ramc + ad + math.radians(n * 30)
            if abs(theta_new - theta) < 1e-8:
                break
            theta = theta_new
        dec = math.asin(math.sin(eps) * math.sin(theta))
        cusp = math.degrees(
            math.atan2(
                math.tan(dec),
                math.cos(lat) * math.cos(theta) + math.sin(lat) * math.sin(theta) * 0
            )
        )
        # Convert to ecliptic longitude via full formula
        cusp = math.degrees(
            math.atan2(
                math.sin(theta) * math.cos(eps) + math.tan(dec) * math.sin(eps),
                math.cos(theta)
            )
        ) % 360
        return cusp

    H11 = placidus_cusp(1, RAMC)
    H12 = placidus_cusp(2, RAMC)
    H2  = placidus_cusp(1, RAMC + math.pi)
    H3  = placidus_cusp(2, RAMC + math.pi)

    IC  = (MC  + 180) % 360
    Dsc = (Asc + 180) % 360
    H5  = (H11 + 180) % 360
    H6  = (H12 + 180) % 360
    H8  = (H2  + 180) % 360
    H9  = (H3  + 180) % 360

    return [Asc, H2, H3, IC, H5, H6, Dsc, H8, H9, MC, H11, H12]
