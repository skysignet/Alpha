"""
SkySignet Send Chart API — Resend + cairosvg
Railway server: POST /api/send-chart

Body JSON:
  email       user's email address
  date        YYYY-MM-DD
  time        HH:MM (local, already UTC-converted by client)
  place       birthplace string e.g. "Newport, RI"
  lat         float
  lon         float
  system      western | vedic
  planets     dict from _natalCache (keyed by planet name, value has lon, sign, deg_in_sign)
  nodes       dict with north/south node data
  angles      dict with ascendant/mc data
  houses      dict with cusps array
"""

import json
import math
import os
import base64
import re

import cairosvg
import requests
from flask import Blueprint, request as flask_request, Response

send_chart_bp = Blueprint('send_chart', __name__)

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
RAILWAY_URL    = "https://alpha-production-1b1b.up.railway.app"

# ── SVG orrery renderer ──────────────────────────────────────────────────────

ZODIAC_GLYPHS = ['♈','♉','♊','♋','♌','♍','♎','♏','♐','♑','♒','♓']
ZODIAC_NAMES  = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo',
                 'Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']

_STARSIGNS_B64 = (
    'T1RUTwALAIAAAwAwQ0ZGIKR6xDkAAAXQAAANIERTSUcAAAABAAAS/AAAAAhHU1VCAAEAAAAAEvAA'
    'AAAKT1MvMmkSaWYAAAFoAAAAYGNtYXAA4wBIAAAFZAAAAExoZWFkFrGF+QAAAMQAAAA2aGhlYQht'
    'AjUAAAFEAAAAJGhtdHg3CQbbAAAA/AAAAEhtYXhwABJQAAAAALwAAAAGbmFtZbSsEgkAAAHIAAAD'
    'nHBvc3T/uAAyAAAFsAAAACAAAFAAABIAAAABAAAAAQAAKRTCkF8PPPUAAwPoAAAAANn4IS4AAAAA'
    '2fghLgB1//8DNQK+AAAAAwACAAAAAAAAAmwAdQAyAAAA+gAAAPoAAAOhAHUDkgB1A6IAdQOYAHUD'
    'pgB1A5gAdQOgAHUDmgB1A6AAdQOeAHUDkQB1A4sAdQOOAHUDqgB1AAEAAATB/gMAAAOqAHUAdQM1'
    'AAEAAAAAAAAAAAAAAAAAAAASAAMDDgGQAAUACAKKAlgAAABLAooCWAAAAV4AMgAyAAAAAAUAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAFVLV04AQAAAAG4C0P/0AfEEwQH9AAAAAQAAAAABXwK+AAAAIAAA'
    'AAAAGgE+AAEAAAAAAAAADgAAAAEAAAAAAAEACQAOAAEAAAAAAAIABwAXAAEAAAAAAAMAHAAeAAEA'
    'AAAAAAQAEQA6AAEAAAAAAAUAMgBLAAEAAAAAAAYAEQB9AAEAAAAAAAcADgAAAAEAAAAAAAgADgAA'
    'AAEAAAAAAAkADgCOAAEAAAAAAAwAFQCcAAEAAAAAAA0ADwCxAAEAAAAAAA4ACgDAAAMAAQQJAAAA'
    'HADKAAMAAQQJAAEAEgDmAAMAAQQJAAIADgD4AAMAAQQJAAMAOAEGAAMAAQQJAAQAIgE+AAMAAQQJ'
    'AAUAZAFgAAMAAQQJAAYAIgHEAAMAAQQJAAcAHADKAAMAAQQJAAgAHADKAAMAAQQJAAkAHAHmAAMA'
    'AQQJAAwAKgICAAMAAQQJAA0AHgIsAAMAAQQJAA4AFAJKVGFyYWxsbyBEZXNpZ25TdGFyc2lnbnNS'
    'ZWd1bGFyMS4wMDA7VUtXTjtTdGFyc2lnbnMtUmVndWxhclN0YXJzaWducyBSZWd1bGFyVmVyc2lv'
    'biAxLjAwMDtob3Rjb252IDEuMC4xMDk7bWFrZW90ZmV4ZSAyLjUuNjU1OTZTdGFyc2lnbnMtUmVn'
    'dWxhckRvbmFsZCBUYXJhbGxvd3d3LnRhcmFsbG9kZXNpZ24uY29tU2VlIHZlbmRvciBFVUxBU2Vl'
    'IHZlbmRvcgBUAGEAcgBhAGwAbABvACAARABlAHMAaQBnAG4AUwB0AGEAcgBzAGkAZwBuAHMAUgBl'
    'AGcAdQBsAGEAcgAxAC4AMAAwADAAOwBVAEsAVwBOADsAUwB0AGEAcgBzAGkAZwBuAHMALQBSAGUA'
    'ZwB1AGwAYQByAFMAdABhAHIAcwBpAGcAbgBzACAAUgBlAGcAdQBsAGEAcgBWAGUAcgBzAGkAbwBu'
    'ACAAMQAuADAAMAAwADsAaABvAHQAYwBvAG4AdgAgADEALgAwAC4AMQAwADkAOwBtAGEAawBlAG8A'
    'dABmAGUAeABlACAAMgAuADUALgA2ADUANQA5ADYAUwB0AGEAcgBzAGkAZwBuAHMALQBSAGUAZwB1'
    'AGwAYQByAEQAbwBuAGEAbABkACAAVABhAHIAYQBsAGwAbwB3AHcAdwAuAHQAYQByAGEAbABsAG8A'
    'ZABlAHMAaQBnAG4ALgBjAG8AbQBTAGUAZQAgAHYAZQBuAGQAbwByACAARQBVAEwAQQBTAGUAZQAg'
    'AHYAZQBuAGQAbwByAAAAAgAAAAMAAAAUAAMAAQAAABQABAA4AAAACgAIAAIAAgAAAA0AIABu//8A'
    'AAAAAA0AIABh//8AAf/1/+P/owABAAAAAAAAAAAAAAADAAAAAAAA/7UAMgAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAQAEAgABAQESU3RhcnNpZ25zLVJlZ3VsYXIAAQEBJfgPAPgdAfgeAvgYBBwAdRz//xwD'
    'NRwCvgX3Bg/3EBGcHA0GEgAEAQEFBxUmTlVMTENSVGFyYWxsbyBEZXNpZ25TdGFyc2lnbnMgUmVn'
    'dWxhcgAAAQGHAQABAABCDQASAgABACUAKAApACoBdwKLAzAD5gTfBcYGgweyCKMJqwp1C1ULwgxi'
    '/B6LuPj5tyAKuPe8uAP3CRb4FvlS/BYGuP0lFfj597z8+QcO/lgODg42ivdr97H3XhL3CfcEEwAT'
    '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'
    '9wkLAAEAAAAAAAAAAAAAAAAAAQAAAAA='
)

PLANET_DEFS = [
    {'key':'sun',     'label':'Sun',     'glyph':'☉', 'color':'#e8d08a', 'ringFrac':0.38, 'big':True},
    {'key':'moon',    'label':'Moon',    'glyph':'☽', 'color':'#d8cfc0', 'ringFrac':0.32, 'big':True},
    {'key':'mercury', 'label':'Mercury', 'glyph':'☿', 'color':'#a8c4d0', 'ringFrac':0.44, 'big':False},
    {'key':'venus',   'label':'Venus',   'glyph':'♀', 'color':'#d4a0c0', 'ringFrac':0.50, 'big':False},
    {'key':'mars',    'label':'Mars',    'glyph':'♂', 'color':'#c87060', 'ringFrac':0.56, 'big':False},
    {'key':'jupiter', 'label':'Jupiter', 'glyph':'♃', 'color':'#c4a05a', 'ringFrac':0.64, 'big':True},
    {'key':'saturn',  'label':'Saturn',  'glyph':'♄', 'color':'#9090a8', 'ringFrac':0.70, 'big':False},
]

def lon_to_rad(lon, north_lon=0):
    """Convert ecliptic longitude to SVG angle, rotated so north node is at top."""
    rotated = lon - north_lon - 90
    return math.radians(rotated)

def sign_of(lon):
    idx = int((lon % 360) / 30) % 12
    return ZODIAC_NAMES[idx], ZODIAC_GLYPHS[idx], round(lon % 30, 1)

def render_orrery_svg(chart, size=520):
    cx = cy = size / 2
    R  = size * 0.46   # outer zodiac ring radius

    planets = chart.get('planets', {})
    nodes   = chart.get('nodes', {})
    angles  = chart.get('angles', {})
    houses  = chart.get('houses', {})

    north_lon = nodes.get('north', {}).get('lon', 0) if nodes else 0
    south_lon = (north_lon + 180) % 360

    # Ring radii (fractions of R)
    RING_FRACS = [p['ringFrac'] for p in PLANET_DEFS]
    NODE_R     = R * 0.25

    s = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">'

    # Embed Starsigns font so cairosvg can render zodiac/planet glyphs
    s += (
        '<defs><style>'
        '@font-face{'
        'font-family:\'Starsigns\';'
        f'src:url(\'data:font/otf;base64,{_STARSIGNS_B64}\') format(\'opentype\');'
        'font-weight:normal;font-style:normal;}'
        '</style></defs>'
    )

    # Background
    s += f'<rect width="{size}" height="{size}" fill="#08090c"/>'
    s += f'<circle cx="{cx}" cy="{cy}" r="{R*1.02}" fill="#0d0f15" stroke="#c4a05a" stroke-width="0.8" stroke-opacity="0.3"/>'

    # Zodiac band
    ZO = R
    ZI = R * 0.88
    for i in range(12):
        a1 = math.radians(i * 30 - north_lon - 90)
        a2 = math.radians((i + 1) * 30 - north_lon - 90)
        x1o = cx + math.cos(a1) * ZO; y1o = cy + math.sin(a1) * ZO
        x2o = cx + math.cos(a2) * ZO; y2o = cy + math.sin(a2) * ZO
        x1i = cx + math.cos(a1) * ZI; y1i = cy + math.sin(a1) * ZI
        x2i = cx + math.cos(a2) * ZI; y2i = cy + math.sin(a2) * ZI
        fill = 'rgba(196,160,90,0.04)' if i % 2 == 0 else 'rgba(196,160,90,0.02)'
        s += f'<path d="M{x1i:.1f},{y1i:.1f} L{x1o:.1f},{y1o:.1f} A{ZO:.1f},{ZO:.1f} 0 0,1 {x2o:.1f},{y2o:.1f} L{x2i:.1f},{y2i:.1f} A{ZI:.1f},{ZI:.1f} 0 0,0 {x1i:.1f},{y1i:.1f} Z" fill="{fill}" stroke="rgba(196,160,90,0.15)" stroke-width="0.5"/>'
        # Zodiac glyph
        mid_a = math.radians((i + 0.5) * 30 - north_lon - 90)
        gr = (ZO + ZI) / 2
        gx = cx + math.cos(mid_a) * gr; gy = cy + math.sin(mid_a) * gr
        fs = size * 0.028
        s += f'<text x="{gx:.1f}" y="{gy:.1f}" text-anchor="middle" dominant-baseline="central" fill="rgba(196,160,90,0.6)" font-size="{fs:.1f}" font-family="Starsigns,serif">{ZODIAC_GLYPHS[i]}</text>'

    # Orbital rings
    for p in PLANET_DEFS:
        r = R * p['ringFrac']
        s += f'<circle cx="{cx}" cy="{cy}" r="{r:.1f}" fill="none" stroke="rgba(196,160,90,0.12)" stroke-width="0.6"/>'

    # Node ring
    s += f'<circle cx="{cx}" cy="{cy}" r="{NODE_R:.1f}" fill="none" stroke="rgba(196,160,90,0.18)" stroke-width="0.7" stroke-dasharray="3,3"/>'

    # House spokes — handle both dict {'cusps': [...]} and raw list
    if isinstance(houses, dict):
        cusps = houses.get('cusps', [])
    elif isinstance(houses, list):
        cusps = houses
    else:
        cusps = []
    if cusps and len(cusps) >= 13:
        for h in range(1, 13):
            a = lon_to_rad(cusps[h], north_lon)
            x2 = cx + math.cos(a) * ZI * 0.87
            y2 = cy + math.sin(a) * ZI * 0.87
            lw = '1.0' if h in (1, 4, 7, 10) else '0.5'
            op = '0.35' if h in (1, 4, 7, 10) else '0.18'
            s += f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="rgba(196,160,90,{op})" stroke-width="{lw}"/>'

    # North / South nodes
    na = lon_to_rad(north_lon, north_lon)  # always top
    sa = lon_to_rad(south_lon, north_lon)  # always bottom
    ns = size * 0.032
    for a, glyph, color in [(na, '☊', '#c4a05a'), (sa, '☋', '#9090a8')]:
        nx = cx + math.cos(a) * NODE_R; ny = cy + math.sin(a) * NODE_R
        s += f'<circle cx="{nx:.1f}" cy="{ny:.1f}" r="{ns*0.8:.1f}" fill="rgba(8,9,12,0.7)"/>'
        s += f'<text x="{nx:.1f}" y="{ny:.1f}" text-anchor="middle" dominant-baseline="central" fill="{color}" font-size="{ns:.1f}" font-family="Starsigns,serif" opacity="0.9">{glyph}</text>'

    # Planets
    FP = size * 0.038
    for p in PLANET_DEFS:
        pdata = planets.get(p['key'])
        if not pdata:
            continue
        lon = pdata['lon']
        a   = lon_to_rad(lon, north_lon)
        r   = R * p['ringFrac']
        px  = cx + math.cos(a) * r
        py  = cy + math.sin(a) * r
        fs  = FP if p['big'] else FP * 0.85
        s += f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{fs*0.7:.1f}" fill="rgba(8,9,12,0.75)"/>'
        s += f'<text x="{px:.1f}" y="{py:.1f}" text-anchor="middle" dominant-baseline="central" fill="{p["color"]}" font-size="{fs:.1f}" font-family="Starsigns,serif" opacity="0.97">{p["glyph"]}</text>'

    # ASC / MC markers
    asc_lon = angles.get('ascendant', {}).get('lon') if angles else None
    mc_lon  = angles.get('mc', {}).get('lon') if angles else None
    for alon, lbl, color in [(asc_lon, 'Asc', '#e8d08a'), (mc_lon, 'MC', '#a8c4d0')]:
        if alon is None:
            continue
        a  = lon_to_rad(alon, north_lon)
        r  = ZI * 0.94
        ax = cx + math.cos(a) * r; ay = cy + math.sin(a) * r
        fs = size * 0.022
        s += f'<text x="{ax:.1f}" y="{ay:.1f}" text-anchor="middle" dominant-baseline="central" fill="{color}" font-size="{fs:.1f}" font-family="Cinzel,serif" opacity="0.85">{lbl}</text>'

    # Earth crosshair
    s += f'<circle cx="{cx}" cy="{cy}" r="5" fill="rgba(196,160,90,0.85)"/>'
    s += f'<line x1="{cx-8}" y1="{cy}" x2="{cx+8}" y2="{cy}" stroke="rgba(8,9,12,0.85)" stroke-width="2"/>'
    s += f'<line x1="{cx}" y1="{cy-8}" x2="{cx}" y2="{cy+8}" stroke="rgba(8,9,12,0.85)" stroke-width="2"/>'

    s += '</svg>'
    return s


def svg_to_png_b64(svg_str):
    png_bytes = cairosvg.svg2png(bytestring=svg_str.encode('utf-8'), output_width=520, output_height=520)
    return base64.b64encode(png_bytes).decode('utf-8')


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
    # Nodes
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
    year = birthdate[:4] if birthdate else ''
    tradition = 'Vedic Sidereal · Lahiri Ayanamsa' if 'vedic' in system_label.lower() else 'Western Tropical'

    # CTA URL — back to commission wizard
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
        data      = flask_request.get_json(force=True)
        email     = data.get('email', '').strip()
        birthdate = data.get('date', '')
        birthtime = data.get('time', '')
        birthplace = data.get('place', '')
        system    = data.get('system', 'western')
        chart     = data.get('chart', {})   # full _natalCache from client

        if not email or '@' not in email:
            raise ValueError('Invalid email address')
        if not chart:
            raise ValueError('Chart data is required')

        system_label = 'Vedic Sidereal' if system == 'vedic' else 'Western Tropical'

        # Render orrery SVG → PNG → base64
        svg_str  = render_orrery_svg(chart)
        png_b64  = svg_to_png_b64(svg_str)

        # Build email HTML
        html_body = build_email_html(chart, birthdate, birthplace, system_label)

        # Send via Resend
        payload = {
            'from':    'SkySignet <info@skysignet.co>',
            'to':      [email],
            'subject': f'Your Natal Chart · {birthplace or birthdate}',
            'html':    html_body,
            'attachments': [
                {
                    'filename':    'natal-chart.png',
                    'content':     png_b64,
                    'content_type': 'image/png',
                    'content_id':  'orrery',
                    'inline':      True,
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
