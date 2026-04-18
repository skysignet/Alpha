"""
SkySignet Send Chart API — Resend
Railway server: POST /api/send-chart

Body JSON:
  email         user's email address
  date          YYYY-MM-DD
  time          HH:MM (local, already UTC-converted by client)
  place         birthplace string e.g. "Newport, RI"
  system        western | vedic
  chart_image   base64-encoded PNG captured from the browser canvas
  chart         _natalCache dict (for planet table in email)
"""

import json
import os

import requests
from flask import Blueprint, request as flask_request, Response

send_chart_bp = Blueprint('send_chart', __name__)

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")

# ── Helpers ──────────────────────────────────────────────────────────────────

ZODIAC_GLYPHS = ['♈','♉','♊','♋','♌','♍','♎','♏','♐','♑','♒','♓']
ZODIAC_NAMES  = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo',
                 'Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']

def sign_of(lon):
    idx = int((lon % 360) / 30) % 12
    return ZODIAC_NAMES[idx], ZODIAC_GLYPHS[idx], round(lon % 30, 1)


# ── Planet table rows for email ──────────────────────────────────────────────

def planet_rows_html(chart):
    planets = chart.get('planets', {})
    nodes   = chart.get('nodes', {})
    rows = ''
    order = ['sun','moon','mercury','venus','mars','jupiter','saturn']
    glyphs = {'sun':'☉','moon':'☽','mercury':'☿','venus':'♀','mars':'♂','jupiter':'♃','saturn':'♄'}
    colors = {'sun':'#e8d08a','moon':'#d8cfc0','mercury':'#a8c4d0','venus':'#d4a0c0',
              'mars':'#c87060','jupiter':'#c4a05a','saturn':'#9090a8'}
    for key in order:
        p = planets.get(key)
        if not p:
            continue
        _, sglyph, deg = sign_of(p['lon'])
        glyph = glyphs.get(key, '')
        color = colors.get(key, '#d8cfc0')
        name  = key.capitalize()
        rows += f'''
        <tr>
          <td style="padding:6px 12px; color:{color}; font-size:18px; width:32px;">{glyph}</td>
          <td style="padding:6px 12px; color:#d8cfc0; font-family:Georgia,serif;">{name}</td>
          <td style="padding:6px 12px; font-size:16px;">{sglyph}</td>
          <td style="padding:6px 12px; color:#d8cfc0; font-family:Georgia,serif;">{p["sign"]}</td>
          <td style="padding:6px 12px; color:#7a7468; font-family:Georgia,serif;">{deg:.1f}°</td>
        </tr>'''
    if nodes:
        north = nodes.get('north', {})
        if north:
            _, sglyph, deg = sign_of(north['lon'])
            rows += f'''
        <tr>
          <td style="padding:6px 12px; color:#c4a05a; font-size:18px;">☊</td>
          <td style="padding:6px 12px; color:#d8cfc0; font-family:Georgia,serif;">North Node</td>
          <td style="padding:6px 12px; font-size:16px;">{sglyph}</td>
          <td style="padding:6px 12px; color:#d8cfc0; font-family:Georgia,serif;">{north["sign"]}</td>
          <td style="padding:6px 12px; color:#7a7468; font-family:Georgia,serif;">{deg:.1f}°</td>
        </tr>'''
    return rows


# ── HTML email template ──────────────────────────────────────────────────────

def build_email_html(chart, birthdate, birthplace, system_label):
    planet_rows = planet_rows_html(chart)
    asc  = chart.get('angles', {}).get('ascendant', {})
    asc_str = f"{asc.get('sign','—')} {asc.get('deg_in_sign',0):.1f}°" if asc else '—'
    tradition = 'Vedic Sidereal · Lahiri Ayanamsa' if 'vedic' in system_label.lower() else 'Western Tropical'
    cta_url = 'https://skysignet.co/#commission'

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Your SkySignet Natal Chart</title>
</head>
<body style="margin:0;padding:0;background:#08090c;font-family:Georgia,'Times New Roman',serif;">

<table width="100%" cellpadding="0" cellspacing="0" style="background:#08090c;">
<tr><td align="center" style="padding:40px 20px;">

<table width="580" cellpadding="0" cellspacing="0" style="max-width:580px;width:100%;">

  <!-- Header -->
  <tr>
    <td align="center" style="padding:0 0 32px;">
      <p style="margin:0 0 8px;font-family:'Palatino Linotype',Palatino,serif;font-size:11px;letter-spacing:6px;color:#c4a05a;text-transform:uppercase;">✦ &nbsp; Jesse Sky &nbsp; ✦</p>
      <h1 style="margin:0;font-family:'Palatino Linotype',Palatino,serif;font-size:32px;font-weight:400;color:#f0e8d5;letter-spacing:4px;">SKYSIGNET</h1>
      <p style="margin:8px 0 0;font-family:Georgia,serif;font-style:italic;font-size:15px;color:#7a7468;">The sky on the day you were born</p>
    </td>
  </tr>

  <!-- Divider -->
  <tr><td style="padding:0 0 32px;"><div style="height:1px;background:linear-gradient(to right,transparent,rgba(196,160,90,0.4),transparent);"></div></td></tr>

  <!-- Intro -->
  <tr>
    <td style="padding:0 0 32px;">
      <p style="margin:0 0 16px;font-size:17px;line-height:1.9;color:#d8cfc0;">Here is your natal chart — the precise configuration of the planets at the moment of your arrival.</p>
      <p style="margin:0;font-size:15px;line-height:1.9;color:#7a7468;font-style:italic;">
        {birthplace}{(' · ' + birthdate) if birthdate else ''}<br>
        Ascendant: {asc_str} &nbsp;·&nbsp; {tradition}
      </p>
    </td>
  </tr>

  <!-- Chart image -->
  <tr>
    <td align="center" style="padding:0 0 32px;">
      <img src="cid:orrery" width="480" style="max-width:100%;display:block;border:1px solid rgba(196,160,90,0.2);" alt="Your natal chart orrery">
    </td>
  </tr>

  <!-- Planet table -->
  <tr>
    <td style="padding:0 0 40px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;border:1px solid rgba(196,160,90,0.15);background:#0d0f15;">
        <tr>
          <td colspan="5" style="padding:10px 12px;font-family:'Palatino Linotype',Palatino,serif;font-size:10px;letter-spacing:4px;color:#c4a05a;text-transform:uppercase;border-bottom:1px solid rgba(196,160,90,0.15);">
            Planetary Positions
          </td>
        </tr>
        {planet_rows}
      </table>
    </td>
  </tr>

  <!-- CTA -->
  <tr>
    <td align="center" style="padding:0 0 48px;">
      <p style="margin:0 0 8px;font-family:'Palatino Linotype',Palatino,serif;font-size:11px;letter-spacing:5px;color:#c4a05a;text-transform:uppercase;">✦ &nbsp; Commission Yours &nbsp; ✦</p>
      <p style="margin:0 0 28px;font-size:16px;line-height:1.9;color:#d8cfc0;max-width:420px;">This configuration has never been cast before. It belongs to no one else. Continue your commission to have it rendered in metal.</p>
      <a href="{cta_url}" style="display:inline-block;font-family:'Palatino Linotype',Palatino,serif;font-size:11px;letter-spacing:5px;text-transform:uppercase;color:#08090c;background:#c4a05a;text-decoration:none;padding:16px 40px;">Continue Your Commission</a>
    </td>
  </tr>

  <!-- Divider -->
  <tr><td style="padding:0 0 32px;"><div style="height:1px;background:linear-gradient(to right,transparent,rgba(196,160,90,0.4),transparent);"></div></td></tr>

  <!-- Footer -->
  <tr>
    <td align="center" style="padding:0;">
      <p style="margin:0 0 8px;font-family:'Palatino Linotype',Palatino,serif;font-size:10px;letter-spacing:4px;color:#7a7468;text-transform:uppercase;">Jesse Sky &nbsp;·&nbsp; Lotus Research &amp; Design, LLC</p>
      <p style="margin:0 0 8px;font-size:13px;color:#7a7468;">
        <a href="https://skysignet.co" style="color:#7a7468;text-decoration:none;">skysignet.co</a>
        &nbsp;·&nbsp;
        <a href="https://instagram.com/iamjessesky" style="color:#7a7468;text-decoration:none;">@iamjessesky</a>
      </p>
      <p style="margin:0;font-size:12px;color:#3a3830;">© 2026 Lotus Research &amp; Design, LLC</p>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>'''


# ── Route ────────────────────────────────────────────────────────────────────

@send_chart_bp.route('/api/send-chart', methods=['POST', 'OPTIONS'])
def send_chart():
    if flask_request.method == 'OPTIONS':
        return Response('', status=200, headers={
            'Access-Control-Allow-Origin':  '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        })

    try:
        data        = flask_request.get_json(force=True)
        email       = data.get('email', '').strip()
        birthdate   = data.get('date', '')
        birthplace  = data.get('place', '')
        system      = data.get('system', 'western')
        chart       = data.get('chart', {})
        chart_image = data.get('chart_image', '')  # base64 PNG from browser canvas

        if not email or '@' not in email:
            raise ValueError('Invalid email address')
        if not chart:
            raise ValueError('Chart data is required')
        if not chart_image:
            raise ValueError('Chart image is required')

        system_label = 'Vedic Sidereal' if system == 'vedic' else 'Western Tropical'

        html_body = build_email_html(chart, birthdate, birthplace, system_label)

        payload = {
            'from':    'SkySignet <info@skysignet.co>',
            'to':      [email],
            'subject': f'Your Natal Chart · {birthplace or birthdate}',
            'html':    html_body,
            'attachments': [
                {
                    'filename':     'natal-chart.png',
                    'content':      chart_image,
                    'content_type': 'image/png',
                    'content_id':   'orrery',
                    'inline':       True,
                }
            ]
        }

        res = requests.post(
            'https://api.resend.com/emails',
            headers={
                'Authorization': f'Bearer {RESEND_API_KEY}',
                'Content-Type':  'application/json'
            },
            json=payload,
            timeout=30
        )

        if res.status_code not in (200, 201):
            raise ValueError(f'Resend error {res.status_code}: {res.text}')

        return Response(
            json.dumps({'ok': True}),
            status=200,
            mimetype='application/json',
            headers={'Access-Control-Allow-Origin': '*'}
        )

    except Exception as e:
        return Response(
            json.dumps({'error': str(e)}),
            status=400,
            mimetype='application/json',
            headers={'Access-Control-Allow-Origin': '*'}
        )
