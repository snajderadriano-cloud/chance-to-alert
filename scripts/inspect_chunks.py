# -*- coding: utf-8 -*-
import urllib.request, ssl, re

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

chunks = [
    'https://neptun.in.ua/_next/static/chunks/7343-58c3589c11ad94d3.js',
    'https://neptun.in.ua/_next/static/chunks/5285-39332e65a060e79b.js',
    'https://neptun.in.ua/_next/static/chunks/1255-b8cf77ab14370e57.js',
    'https://neptun.in.ua/_next/static/chunks/4bd1b696-100b9d70ed4e49c1.js'
]

for url in chunks:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            src = r.read().decode('utf-8', errors='ignore')
            name = url.split('/')[-1]
            print(f"{name}: {len(src)} bytes")
            for kw in ['maplibre', 'mapbox', 'openfreemap', 'cartocdn', 'leaflet', 'arcgis', 'tiles']:
                cnt = len(re.findall(kw, src, re.I))
                if cnt > 0:
                    print(f"  keyword '{kw}': {cnt}")
            # Find URLs
            found = set(re.findall(r'https://[^\s"\'\\><]+', src))
            map_urls = [u for u in found if any(k in u for k in ['tile', 'style', 'map', 'api'])]
            if map_urls:
                print("  Map URLs:")
                for u in map_urls[:8]:
                    print("   ", u)
    except Exception as e:
        print(f"Error {url}: {e}")
