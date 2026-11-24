# -*- coding: utf-8 -*-
"""Build neptun.in.ua style MapLibre GL interactive radar map and eradicate all emojis."""

def main():
    with open('static/index.html', 'r', encoding='utf-8') as f:
        html = f.read()

    # 1. Add MapLibre GL CSS and JS in <head>
    head_tag = '<head>'
    maplibre_headers = '''<head>
  <link rel="stylesheet" href="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css" />
  <script src="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js"></script>'''
    if head_tag in html:
        html = html.replace(head_tag, maplibre_headers, 1)
        print("1. MapLibre headers added")
    else:
        print("ERROR 1: <head> tag not found")

    # 2. Add Neptun-style map CSS
    neptun_css_target = '/* Tactical Vector Map styles */'
    neptun_css = '''/* NEPTUN.IN.UA MAPLIBRE RADAR STYLES */
    .tactical-canvas-wrap {
      position: relative;
      width: 100%;
      height: 480px;
      border-radius: var(--r-card);
      overflow: hidden;
      background: #0b1319;
      border: 1px solid var(--line);
    }
    #neptunMap {
      width: 100%;
      height: 100%;
    }
    .maplibregl-canvas {
      outline: none;
    }
    /* Home marker */
    .neptun-home-marker {
      position: relative;
      display: flex;
      flex-direction: column;
      align-items: center;
      cursor: pointer;
    }
    .neptun-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--green);
      border: 2px solid #ffffff;
      box-shadow: 0 0 10px var(--green);
    }
    .neptun-pulse-ring {
      position: absolute;
      top: -5px;
      left: 0px;
      width: 20px;
      height: 20px;
      border-radius: 50%;
      border: 1.5px solid var(--green);
      animation: neptunPulse 2s infinite ease-out;
    }
    @keyframes neptunPulse {
      0% { transform: scale(0.5); opacity: 1; }
      100% { transform: scale(2.2); opacity: 0; }
    }
    .neptun-home-label {
      margin-top: 4px;
      font-size: 10.5px;
      font-weight: 700;
      color: #ffffff;
      background: rgba(11, 31, 28, 0.9);
      border: 1px solid var(--green);
      border-radius: 4px;
      padding: 2px 6px;
      white-space: nowrap;
      letter-spacing: 0.3px;
    }

    /* Drone target marker */
    .neptun-drone-marker {
      position: relative;
      width: 28px;
      height: 28px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
    }
    .drone-svg {
      width: 22px;
      height: 22px;
      fill: var(--red);
      filter: drop-shadow(0 0 6px rgba(255, 90, 95, 0.8));
      transition: transform 0.2s;
    }
    .drone-pulse-circle {
      position: absolute;
      inset: -4px;
      border-radius: 50%;
      border: 1.5px solid var(--red);
      animation: dronePulse 1.6s infinite ease-out;
      pointer-events: none;
    }
    @keyframes dronePulse {
      0% { transform: scale(0.6); opacity: 0.9; }
      100% { transform: scale(1.8); opacity: 0; }
    }
    .drone-tag {
      position: absolute;
      left: 28px;
      top: -4px;
      background: rgba(20, 24, 29, 0.92);
      border: 1px solid var(--red);
      border-radius: 4px;
      padding: 2px 6px;
      font-size: 10px;
      color: #fff;
      font-family: var(--font-mono);
      white-space: nowrap;
      pointer-events: none;
      display: flex;
      flex-direction: column;
      gap: 1px;
    }
    .drone-tag b { color: var(--red); font-size: 10px; }
    .drone-tag span { color: rgba(255,255,255,0.7); font-size: 9px; }

    /* Tactical Vector Map styles */'''
    if neptun_css_target in html:
        html = html.replace(neptun_css_target, neptun_css, 1)
        print("2. Neptun CSS injected")
    else:
        print("ERROR 2: neptun_css_target not found")

    # 3. Replace #tab-map HTML with MapLibre container
    old_tab_map_start = '<!-- ================= TAB 2: КАРТА (ТАКТИЧЕСКИЙ РАДАР & ВЕКТОРЫ) ================= -->'
    old_tab_map_end = '<!-- ================= TAB 2: ШКОЛА & ОБУЧЕНИЕ МОДЕЛИ ================= -->'
    
    new_tab_map = '''<!-- ================= TAB 2: КАРТА (НЕПТУН РАДАР ОДЕССЫ) ================= -->
    <div id="tab-map" class="tab-view">
      <div class="motion-card" style="padding: 12px; position: relative;">
        <div class="map-hud-header">
          <div style="display: flex; flex-direction: column;">
            <div style="font-size: 13px; font-weight: 700; letter-spacing: 0.5px; display: flex; align-items: center; gap: 6px;">
              <span class="pulse-dot"></span>
              <span>РАДАР НЕПТУН · СЕКТОР ТАИРОВА</span>
            </div>
            <span style="font-size: 11px; color: var(--muted); font-family: var(--font-mono);">46.3906° N, 30.7090° E · ТАИРОВА / ГАРМОНИЯ</span>
          </div>
          <div class="map-layer-toggles">
            <button id="btnMapCenter" class="map-chip-btn" onclick="centerTacticalMap()">Таирова</button>
            <button id="btnMapTest" class="map-chip-btn active" onclick="toggleMapSimulation()">Симуляция</button>
          </div>
        </div>

        <!-- Real MapLibre GL Container (OpenFreeMap Dark Vector Tiles as in neptun.in.ua) -->
        <div class="tactical-canvas-wrap">
          <div id="neptunMap"></div>

          <!-- Interactive Target Details Card -->
          <div id="targetDetailCard" class="target-popup-card" style="display: none;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
              <b id="targetPopupId" style="color: var(--red); font-size: 12px; font-family: var(--font-mono);">#SH-401 · Shahed-136</b>
              <span id="targetPopupEta" style="font-size: 11px; color: var(--orange); font-weight: 700;">Подлёт ~9 мин</span>
            </div>
            <div id="targetPopupDesc" style="font-size: 11.5px; color: var(--text-2);">Курс 332° (Чёрное море → Черноморск / Таирова), Скорость 185 км/ч, Высота 140м</div>
          </div>
        </div>

        <!-- Tactical Range Legend -->
        <div class="map-legend-row">
          <span class="legend-tag"><span class="legend-color ppo"></span> 10 км (МВГ ППО)</span>
          <span class="legend-tag"><span class="legend-color odesa"></span> 30 км (Одесса / Черноморск)</span>
          <span class="legend-tag"><span class="legend-color approach"></span> 60 км (Рубеж подлёта)</span>
        </div>
      </div>
    </div>

    '''
    if old_tab_map_start in html and old_tab_map_end in html:
        p1 = html.find(old_tab_map_start)
        p2 = html.find(old_tab_map_end)
        html = html[:p1] + new_tab_map + html[p2:]
        print("3. tab-map replaced with MapLibre container")
    else:
        print("ERROR 3: old_tab_map targets not found")

    # 4. Replace emojis with clean military SVGs and badges
    emoji_replacements = [
        ('<b>📱 Для iPhone (Safari):</b>', '<b>[iOS / Safari]</b>'),
        ('<b>🤖 Для Android (Chrome):</b>', '<b>[Android / Chrome]</b>'),
        ('🏫 Очно', '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:middle;margin-right:4px;"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>Очно'),
        ('💻 Дистант', '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:middle;margin-right:4px;"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>Дистант'),
        ('⚠️ Тревога', '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:middle;margin-right:4px;"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>Тревога'),
        ('⚠️ Учебная тревога: 3 БпЛА', '[ВНИМАНИЕ] 3 БпЛА')
    ]
    for old_e, new_e in emoji_replacements:
        if old_e in html:
            html = html.replace(old_e, new_e)
            print(f"4. Replaced emoji '{old_e[:8]}' -> '{new_e[:8]}'")

    # 5. Replace Tactical Canvas JS engine with MapLibre GL engine
    old_engine_marker = '/* ==========================================================================\n       TACTICAL VECTOR MAP ENGINE'
    if old_engine_marker not in html:
        old_engine_marker = 'TACTICAL VECTOR MAP ENGINE'

    neptun_js_engine = """/* ==========================================================================
       NEPTUN.IN.UA MAPLIBRE GL ENGINE
       Real Dark Vector Tiles (OpenFreeMap) + GeoJSON Range Rings + Shahed Vectors
       ========================================================================== */
    function setQuickAttendance(status, btn) {
      document.querySelectorAll('.quick-att-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      submitAttendance(status);
      const badge = document.getElementById('currentStatusBadge');
      if (status === 'IN_PERSON') badge.textContent = 'Очно';
      else if (status === 'REMOTE_OFFICIAL') badge.textContent = 'Дистант';
      else badge.textContent = 'Тревога';
    }

    let neptunMap = null;
    let neptunMarkers = [];
    let neptunSimulate = true;

    const TAIROVO_COORDS = [30.7090, 46.3906]; // [lon, lat]

    const SIM_DRONES = [
      { id: '#SH-401', type: 'Shahed-136', coords: [30.7950, 46.1820], heading: 332, speed: 185, alt: 140, eta: 9, source: 'Чёрное море' },
      { id: '#SH-402', type: 'Shahed-136', coords: [31.3500, 46.5200], heading: 258, speed: 190, alt: 180, eta: 18, source: 'Очаков / Кинбурн' },
      { id: '#SH-403', type: 'Shahed-136', coords: [30.4100, 46.1200], heading: 38, speed: 175, alt: 120, eta: 14, source: 'Затока / Лиман' }
    ];

    function createCircleGeoJson(center, radiusKm, points = 64) {
      const lon = center[0], lat = center[1];
      const distanceX = radiusKm / (111.320 * Math.cos(lat * Math.PI / 180));
      const distanceY = radiusKm / 110.574;
      const ring = [];
      for (let i = 0; i < points; i++) {
        const theta = (i / points) * (2 * Math.PI);
        ring.push([lon + distanceX * Math.cos(theta), lat + distanceY * Math.sin(theta)]);
      }
      ring.push(ring[0]);
      return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [ring] } };
    }

    function initNeptunMapEngine() {
      if (neptunMap || typeof maplibregl === 'undefined') return;
      const el = document.getElementById('neptunMap');
      if (!el) return;

      neptunMap = new maplibregl.Map({
        container: 'neptunMap',
        style: 'https://tiles.openfreemap.org/styles/dark',
        center: TAIROVO_COORDS,
        zoom: 9.8,
        minZoom: 5,
        maxZoom: 16,
        attributionControl: false
      });

      neptunMap.addControl(new maplibregl.NavigationControl({ showCompass: true, showZoom: true }), 'top-right');

      neptunMap.on('load', () => {
        // Range Rings Sources and Layers
        const r10 = createCircleGeoJson(TAIROVO_COORDS, 10);
        const r30 = createCircleGeoJson(TAIROVO_COORDS, 30);
        const r60 = createCircleGeoJson(TAIROVO_COORDS, 60);

        neptunMap.addSource('ring-60', { type: 'geojson', data: r60 });
        neptunMap.addLayer({
          id: 'ring-60-line',
          type: 'line',
          source: 'ring-60',
          paint: { 'line-color': '#ff5a5f', 'line-width': 1.5, 'line-dasharray': [4, 3], 'line-opacity': 0.6 }
        });
        neptunMap.addLayer({
          id: 'ring-60-fill',
          type: 'fill',
          source: 'ring-60',
          paint: { 'fill-color': '#ff5a5f', 'fill-opacity': 0.02 }
        });

        neptunMap.addSource('ring-30', { type: 'geojson', data: r30 });
        neptunMap.addLayer({
          id: 'ring-30-line',
          type: 'line',
          source: 'ring-30',
          paint: { 'line-color': '#ff9f0a', 'line-width': 1.5, 'line-dasharray': [5, 3], 'line-opacity': 0.7 }
        });
        neptunMap.addLayer({
          id: 'ring-30-fill',
          type: 'fill',
          source: 'ring-30',
          paint: { 'fill-color': '#ff9f0a', 'fill-opacity': 0.03 }
        });

        neptunMap.addSource('ring-10', { type: 'geojson', data: r10 });
        neptunMap.addLayer({
          id: 'ring-10-line',
          type: 'line',
          source: 'ring-10',
          paint: { 'line-color': '#34d17a', 'line-width': 1.8, 'line-dasharray': [3, 2], 'line-opacity': 0.8 }
        });
        neptunMap.addLayer({
          id: 'ring-10-fill',
          type: 'fill',
          source: 'ring-10',
          paint: { 'fill-color': '#34d17a', 'fill-opacity': 0.04 }
        });

        // Add Tairovo Center Home Marker
        const homeEl = document.createElement('div');
        homeEl.className = 'neptun-home-marker';
        homeEl.innerHTML = '<div class="neptun-pulse-ring"></div><div class="neptun-dot"></div><div class="neptun-home-label">Таирова · Гармония</div>';
        new maplibregl.Marker({ element: homeEl, anchor: 'center' })
          .setLngLat(TAIROVO_COORDS)
          .addTo(neptunMap);

        // Render Drone Markers
        renderDroneMarkers();
      });
    }

    function renderDroneMarkers() {
      // Clear existing markers
      neptunMarkers.forEach(m => m.remove());
      neptunMarkers = [];

      if (!neptunSimulate || !neptunMap) return;

      SIM_DRONES.forEach(drone => {
        const dEl = document.createElement('div');
        dEl.className = 'neptun-drone-marker';
        dEl.innerHTML = `
          <div class="drone-pulse-circle"></div>
          <svg viewBox="0 0 24 24" class="drone-svg" style="transform: rotate(${drone.heading}deg);">
            <polygon points="12 2 2 22 12 18 22 22"/>
          </svg>
          <div class="drone-tag">
            <b>${drone.id}</b>
            <span>${drone.speed} км/ч · ~${drone.eta}м</span>
          </div>
        `;

        dEl.addEventListener('click', (e) => {
          e.stopPropagation();
          const pop = document.getElementById('targetDetailCard');
          if (pop) {
            document.getElementById('targetPopupId').textContent = `${drone.id} · ${drone.type}`;
            document.getElementById('targetPopupEta').textContent = `Подлёт ~${drone.eta} мин`;
            document.getElementById('targetPopupDesc').textContent = `Сектор: ${drone.source} → Таирова · Курс: ${drone.heading}° · Скорость: ${drone.speed} км/ч · Высота: ${drone.alt}м`;
            pop.style.display = 'block';
          }
          neptunMap.flyTo({ center: drone.coords, zoom: 11, speed: 1.2 });
        });

        const marker = new maplibregl.Marker({ element: dEl, anchor: 'center' })
          .setLngLat(drone.coords)
          .addTo(neptunMap);

        neptunMarkers.push(marker);
      });
    }

    function centerTacticalMap() {
      const pop = document.getElementById('targetDetailCard');
      if (pop) pop.style.display = 'none';
      if (neptunMap) {
        neptunMap.flyTo({ center: TAIROVO_COORDS, zoom: 10, speed: 1.4 });
      }
    }

    function toggleMapSimulation() {
      neptunSimulate = !neptunSimulate;
      const btn = document.getElementById('btnMapTest');
      if (btn) btn.classList.toggle('active', neptunSimulate);
      const pop = document.getElementById('targetDetailCard');
      if (!neptunSimulate && pop) pop.style.display = 'none';
      renderDroneMarkers();
    }

    window.triggerMapResize = () => {
      if (!neptunMap) {
        initNeptunMapEngine();
      } else {
        neptunMap.resize();
      }
    };
"""
    # Replace old canvas engine in html
    idx_engine = html.find('/* ==========================================================================\n       TACTICAL VECTOR MAP ENGINE')
    if idx_engine != -1:
        end_idx = html.rfind('</script>')
        html = html[:idx_engine] + neptun_js_engine + '\n  ' + html[end_idx:]
        print("5. Neptun MapLibre GL engine injected into script")
    else:
        print("ERROR 5: old_engine_marker not found")

    with open('static/index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("ALL UPDATES COMPLETE IN static/index.html")

if __name__ == '__main__':
    main()
