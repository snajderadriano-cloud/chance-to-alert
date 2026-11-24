# -*- coding: utf-8 -*-
import urllib.request, ssl, re

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(
    'https://neptun.in.ua/',
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
)

try:
    with urllib.request.urlopen(req, context=ctx, timeout=12) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
        print(f"Status: {resp.status}, HTML length: {len(html)}")
        with open('scripts/neptun_dump.html', 'w', encoding='utf-8') as out:
            out.write(html)
        print("Wrote scripts/neptun_dump.html")
except Exception as e:
    print(f"Fetch error: {e}")
