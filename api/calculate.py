from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs
from skyfield.api import load
from dateutil import parser
import pytz

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        
        try:
            # Get data from the URL
            birth_date = query.get('date')[0]
            birth_time = query.get('time')[0]
            lat = float(query.get('lat')[0])
            lon = float(query.get('lon')[0])
            system = query.get('system', ['tropical'])[0]
            
            # Setup Skyfield
            ts = load.timescale()
            eph = load('de421.bsp')
            
            # The 7 Classical Planets for the SkySignet Orrery
            planets = {
                'Moon': eph['moon'],
                'Mercury': eph['mercury'],
                'Venus': eph['venus'],
                'Sun': eph['sun'],
                'Mars': eph['mars'],
                'Jupiter': eph['jupiter_barycenter'],
                'Saturn': eph['saturn_barycenter']
            }

            # Parse time (Assuming UTC for the calculation)
            dt = parser.parse(f"{birth_date} {birth_time}")
            t = ts.from_datetime(dt.replace(tzinfo=pytz.UTC))

            results = {}
            for name, body in planets.items():
                # Get ecliptic longitude
                astrometric = eph['earth'].at(t).observe(body)
                _, lon_val, _ = astrometric.ecliptic_latlon()
                
                degrees = lon_val.degrees
                
                # Apply Vedic Correction (Lahiri Ayanamsa approx for 2026)
                if system == 'vedic':
                    ayanamsa = 24.1 
                    degrees = (degrees - ayanamsa) % 360
                
                results[name] = round(degrees, 2)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(results).encode())

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
