# -*- coding: utf-8 -*-
"""Script to apply frontend upgrade: 5 tabs, tactical map, weather & power grid, quick attendance."""

def main():
    with open('static/index.html', 'r', encoding='utf-8') as f:
        html = f.read()

    # 1. Insert Environmental and Quick Attendance into tab-radar before the School card
    radar_metrics_target = """      <!-- Key Tactical Metrics -->
      <div class="metrics-row">
        <div class="metric-cell">
          <span class="metric-cell-label">Подлёт к сектору</span>
          <span id="valEta" class="metric-cell-val">—</span>
        </div>
        <div class="metric-cell">
          <span class="metric-cell-label">Цели в воздухе</span>
          <span id="valCount" class="metric-cell-val">0</span>
        </div>
        <div class="metric-cell">
          <span class="metric-cell-label">Главная цель</span>
          <span id="valType" class="metric-cell-val" style="font-size: 13px;">Чисто</span>
        </div>
      </div>"""

    radar_addons = """      <!-- Key Tactical Metrics -->
      <div class="metrics-row">
        <div class="metric-cell">
          <span class="metric-cell-label">Подлёт к сектору</span>
          <span id="valEta" class="metric-cell-val">—</span>
        </div>
        <div class="metric-cell">
          <span class="metric-cell-label">Цели в воздухе</span>
          <span id="valCount" class="metric-cell-val">0</span>
        </div>
        <div class="metric-cell">
          <span class="metric-cell-label">Главная цель</span>
          <span id="valType" class="metric-cell-val" style="font-size: 13px;">Чисто</span>
        </div>
      </div>

      <!-- Environmental Criteria & Grid -->
      <div class="env-row">
        <div class="env-card">
          <div class="env-header">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M9.59 4.59A2 2 0 1 1 11 8H2m10.59 11.41A2 2 0 1 0 14 16H2m15.73-8.27A2.5 2.5 0 1 1 19.5 12H2"/></svg>
            <span>Ветер и курс БпЛА</span>
          </div>
          <div class="env-main">С-В 6 м/с (22 км/ч)</div>
          <div class="env-sub">Встречный с моря (+3 мин к подлёту). Облачность 280м.</div>
        </div>
        <div class="env-card">
          <div class="env-header">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
            <span>Энергосеть (ДТЭК)</span>
          </div>
          <div class="env-main">1 группа · СВЕТ ЕСТЬ</div>
          <div class="env-sub">Королёва / Таирова стабильно. Сирены и вышки запитаны.</div>
        </div>
      </div>

      <!-- Quick Attendance Switcher -->
      <div class="motion-card" style="padding: 14px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <span style="font-size: 13px; font-weight: 700; display: flex; align-items: center; gap: 6px;">
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
            Лицей «Гармония» · Ваш статус
          </span>
          <span id="currentStatusBadge" style="font-size: 11.5px; color: var(--green); font-weight: 700;">Очно</span>
        </div>
        <div style="font-size: 12px; color: var(--muted); margin-bottom: 10px;">
          Случайно выбрали не то? Переключите в 1 тап — статус для расчётов сразу обновится:
        </div>
        <div class="quick-att-row">
          <button class="quick-att-btn active" id="btnAttInPerson" onclick="setQuickAttendance('IN_PERSON', this)">🏫 Очно</button>
          <button class="quick-att-btn" id="btnAttRemote" onclick="setQuickAttendance('REMOTE_OFFICIAL', this)">💻 Дистант</button>
          <button class="quick-att-btn" id="btnAttMissed" onclick="setQuickAttendance('MISSED_ALARM', this)">⚠️ Тревога</button>
        </div>
      </div>"""

    if radar_metrics_target in html:
        html = html.replace(radar_metrics_target, radar_addons)
        print('1. Radar addons inserted')
    else:
        print('ERROR 1: radar_metrics_target not found')

    # 2. Insert tab-map between tab-radar and tab-school
    tab_school_target = '    <!-- ================= TAB 2: ШКОЛА & ОБУЧЕНИЕ МОДЕЛИ ================= -->'
    tab_map_html = """    <!-- ================= TAB 2: КАРТА (ТАКТИЧЕСКИЙ РАДАР & ВЕКТОРЫ) ================= -->
    <div id="tab-map" class="tab-view">
      <div class="motion-card" style="padding: 14px;">
        <div class="map-hud-header">
          <div style="display: flex; flex-direction: column;">
            <span style="font-size: 13px; font-weight: 700; letter-spacing: 0.5px; display: flex; align-items: center; gap: 6px;">
              <span class="pulse-dot"></span>
              ТАКТИЧЕСКИЙ РАДАР · СЕКТОР ТАИРОВА
            </span>
            <span style="font-size: 11px; color: var(--muted); font-family: var(--font-mono);">46.3906° N, 30.7090° E · ЛИЦЕЙ «ГАРМОНИЯ»</span>
          </div>
          <div class="map-layer-toggles">
            <button id="btnMapCenter" class="map-chip-btn" onclick="centerTacticalMap()">Центр</button>
            <button id="btnMapTest" class="map-chip-btn active" onclick="toggleMapSimulation()">Симуляция</button>
          </div>
        </div>

        <!-- Tactical Canvas Container -->
        <div class="tactical-canvas-wrap">
          <canvas id="tacticalMapCanvas" width="400" height="400" class="tactical-canvas"></canvas>

          <!-- Interactive Target Details Card -->
          <div id="targetDetailCard" class="target-popup-card" style="display: none;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
              <b id="targetPopupId" style="color: var(--red); font-size: 12px; font-family: var(--font-mono);">#SH-401</b>
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

    """

    if tab_school_target in html:
        html = html.replace(tab_school_target, tab_map_html + tab_school_target)
        print('2. tab-map inserted')
    else:
        print('ERROR 2: tab_school_target not found')

    # 3. Update mainBar buttons to 5 tabs
    bar_target = """    <nav class="bar" id="mainBar" role="tablist" aria-label="Main">
      <span class="hl" id="hl"></span>
      <button class="it" role="tab" aria-selected="true" aria-label="Радар">
        <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>
        <span class="nm">Радар</span>
      </button>
      <button class="it" role="tab" aria-selected="false" aria-label="Школа">
        <svg viewBox="0 0 24 24"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>
        <span class="nm">Школа</span>
      </button>
      <button class="it" role="tab" aria-selected="false" aria-label="Эфир">
        <svg viewBox="0 0 24 24"><path d="M4 11a9 9 0 0 1 9 9M4 4a16 16 0 0 1 16 16"/><circle cx="5" cy="19" r="1"/></svg>
        <span class="nm">Эфир</span>
      </button>
      <button class="it" role="tab" aria-selected="false" aria-label="Копилот">
        <svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        <span class="nm">Копилот</span>
      </button>
    </nav>"""

    bar_replacement = """    <nav class="bar" id="mainBar" role="tablist" aria-label="Main">
      <span class="hl" id="hl"></span>
      <button class="it" role="tab" aria-selected="true" aria-label="Радар">
        <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>
        <span class="nm">Радар</span>
      </button>
      <button class="it" role="tab" aria-selected="false" aria-label="Карта">
        <svg viewBox="0 0 24 24"><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/></svg>
        <span class="nm">Карта</span>
      </button>
      <button class="it" role="tab" aria-selected="false" aria-label="Школа">
        <svg viewBox="0 0 24 24"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>
        <span class="nm">Школа</span>
      </button>
      <button class="it" role="tab" aria-selected="false" aria-label="Эфир">
        <svg viewBox="0 0 24 24"><path d="M4 11a9 9 0 0 1 9 9M4 4a16 16 0 0 1 16 16"/><circle cx="5" cy="19" r="1"/></svg>
        <span class="nm">Эфир</span>
      </button>
      <button class="it" role="tab" aria-selected="false" aria-label="Копилот">
        <svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        <span class="nm">Копилот</span>
      </button>
    </nav>"""

    if bar_target in html:
        html = html.replace(bar_target, bar_replacement)
        print('3. mainBar updated to 5 tabs')
    else:
        print('ERROR 3: bar_target not found')

    # 4. Update tabViews and switchTab in JS
    js_tabviews_target = "const tabViews = ['tab-radar', 'tab-school', 'tab-feed', 'tab-ai'].map(id => document.getElementById(id));"
    js_tabviews_replacement = "const tabViews = ['tab-radar', 'tab-map', 'tab-school', 'tab-feed', 'tab-ai'].map(id => document.getElementById(id));"

    if js_tabviews_target in html:
        html = html.replace(js_tabviews_target, js_tabviews_replacement)
        print('4. tabViews updated in JS')
    else:
        print('ERROR 4: js_tabviews_target not found')

    # 5. Update switchTab inside JS
    switch_tab_target = """      if (idx === 2) loadFeed();
      if (idx === 3 && window.triggerSphereResize) window.triggerSphereResize();"""

    switch_tab_replacement = """      if (idx === 1 && window.triggerMapResize) {
        requestAnimationFrame(() => window.triggerMapResize());
      }
      if (idx === 3) loadFeed();
      if (idx === 4 && window.triggerSphereResize) {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => window.triggerSphereResize());
        });
      }"""

    if switch_tab_target in html:
        html = html.replace(switch_tab_target, switch_tab_replacement)
        print('5. switchTab logic updated')
    else:
        print('ERROR 5: switch_tab_target not found')

    # 6. Add Tactical Map JS Engine and Attendance helper right before </script>
    script_end_target = "  </script>"
    tactical_engine_js = """
    /* ==========================================================================
       TACTICAL VECTOR MAP ENGINE (НЕПТУН & AIR DEFENSE RADAR)
       60 FPS Vector Canvas with Coastline, Range Rings, Targets & Interactivity
       ========================================================================== */
    function setQuickAttendance(status, btn) {
      document.querySelectorAll('.quick-att-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      submitAttendance(status);
      const badge = document.getElementById('currentStatusBadge');
      if (status === 'IN_PERSON') badge.textContent = 'Очно';
      else if (status === 'REMOTE_OFFICIAL') badge.textContent = 'Дистант';
      else badge.textContent = 'Дома / Тревога';
    }

    let mapCanvas = document.getElementById('tacticalMapCanvas');
    let mapCtx = mapCanvas ? mapCanvas.getContext('2d') : null;
    let mapSweepAngle = 0;
    let mapSimulate = true;
    let mapTargets = [
      { id: '#SH-401', type: 'Shahed-136', distKm: 28, angleDeg: 155, heading: 332, speed: 185, alt: 140, eta: 9 },
      { id: '#SH-402', type: 'Shahed-136', distKm: 56, angleDeg: 68, heading: 258, speed: 190, alt: 180, eta: 18 },
      { id: '#SH-403', type: 'Shahed-136', distKm: 42, angleDeg: 220, heading: 38, speed: 175, alt: 120, eta: 14 }
    ];
    let selectedTarget = null;

    function resizeTacticalMap() {
      if (!mapCanvas) return;
      const rect = mapCanvas.parentElement.getBoundingClientRect();
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      mapCanvas.width = Math.round(rect.width * dpr);
      mapCanvas.height = Math.round(rect.height * dpr);
    }
    window.triggerMapResize = resizeTacticalMap;
    window.addEventListener('resize', resizeTacticalMap);
    setTimeout(resizeTacticalMap, 150);

    function centerTacticalMap() {
      selectedTarget = null;
      const pop = document.getElementById('targetDetailCard');
      if (pop) pop.style.display = 'none';
      resizeTacticalMap();
    }

    function toggleMapSimulation() {
      mapSimulate = !mapSimulate;
      const btn = document.getElementById('btnMapTest');
      if (btn) btn.classList.toggle('active', mapSimulate);
      const pop = document.getElementById('targetDetailCard');
      if (!mapSimulate && pop) pop.style.display = 'none';
    }

    if (mapCanvas) {
      mapCanvas.addEventListener('click', (e) => {
        const rect = mapCanvas.getBoundingClientRect();
        const dpr = Math.min(2, window.devicePixelRatio || 1);
        const clickX = (e.clientX - rect.left) * dpr;
        const clickY = (e.clientY - rect.top) * dpr;
        const cx = mapCanvas.width / 2;
        const cy = mapCanvas.height / 2;
        const scale = (mapCanvas.width / 2) / 70; // 70 km radius

        let clicked = null;
        if (mapSimulate) {
          mapTargets.forEach(t => {
            const rad = t.angleDeg * Math.PI / 180;
            const tx = cx + Math.sin(rad) * t.distKm * scale;
            const ty = cy - Math.cos(rad) * t.distKm * scale;
            const dist = Math.hypot(clickX - tx, clickY - ty);
            if (dist < 24 * dpr) clicked = t;
          });
        }

        const pop = document.getElementById('targetDetailCard');
        if (clicked && pop) {
          selectedTarget = clicked;
          document.getElementById('targetPopupId').textContent = clicked.id + ' · ' + clicked.type;
          document.getElementById('targetPopupEta').textContent = 'Подлёт ~' + clicked.eta + ' мин';
          document.getElementById('targetPopupDesc').textContent = 'Дистанция: ' + clicked.distKm + ' км · Курс: ' + clicked.heading + '° · Скорость: ' + clicked.speed + ' км/ч · Высота: ' + clicked.alt + 'м';
          pop.style.display = 'block';
        } else if (pop) {
          pop.style.display = 'none';
          selectedTarget = null;
        }
      });
    }

    function renderTacticalMapLoop() {
      if (mapCanvas && mapCtx && mapCanvas.width > 0) {
        const W = mapCanvas.width;
        const H = mapCanvas.height;
        const cx = W / 2;
        const cy = H / 2;
        const maxKm = 70;
        const scale = (W / 2) / maxKm;

        // Background clear
        mapCtx.fillStyle = '#06090d';
        mapCtx.fillRect(0, 0, W, H);

        // Coastline approximation for Odessa region
        mapCtx.strokeStyle = 'rgba(62, 201, 255, 0.22)';
        mapCtx.lineWidth = 1.5;
        mapCtx.beginPath();
        // Points relative to Tairovo in km: [east_km, north_km]
        const coastKm = [
          [-35, -30], [-25, -20], [-15, -12], [-5, -6], [2, -2],
          [5, 4], [8, 12], [9, 18], [14, 25], [25, 27], [38, 26], [55, 23]
        ];
        coastKm.forEach((pt, idx) => {
          const px = cx + pt[0] * scale;
          const py = cy - pt[1] * scale;
          if (idx === 0) mapCtx.moveTo(px, py);
          else mapCtx.lineTo(px, py);
        });
        mapCtx.stroke();

        // Fill sea area lightly
        mapCtx.lineTo(W, H);
        mapCtx.lineTo(0, H);
        mapCtx.closePath();
        mapCtx.fillStyle = 'rgba(62, 201, 255, 0.025)';
        mapCtx.fill();

        // Range rings (10km, 30km, 60km)
        const rings = [
          { km: 10, col: 'rgba(52, 209, 122, 0.28)', dash: [4, 4], label: '10 км (МВГ ППО)' },
          { km: 30, col: 'rgba(255, 159, 10, 0.24)', dash: [6, 4], label: '30 км (Одесса / Черноморск)' },
          { km: 60, col: 'rgba(255, 90, 95, 0.22)', dash: [8, 6], label: '60 км (Рубеж подлёта)' }
        ];

        rings.forEach(r => {
          const radiusPx = r.km * scale;
          mapCtx.save();
          mapCtx.strokeStyle = r.col;
          mapCtx.lineWidth = 1;
          mapCtx.setLineDash(r.dash);
          mapCtx.beginPath();
          mapCtx.arc(cx, cy, radiusPx, 0, Math.PI * 2);
          mapCtx.stroke();

          // Range Label
          mapCtx.setLineDash([]);
          mapCtx.fillStyle = r.col;
          mapCtx.font = '10px Inter, monospace';
          mapCtx.fillText(r.label, cx + 6, cy - radiusPx + 11);
          mapCtx.restore();
        });

        // Crosshairs
        mapCtx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
        mapCtx.lineWidth = 1;
        mapCtx.beginPath();
        mapCtx.moveTo(cx, 0); mapCtx.lineTo(cx, H);
        mapCtx.moveTo(0, cy); mapCtx.lineTo(W, cy);
        mapCtx.stroke();

        // Compass degree markers
        mapCtx.fillStyle = 'rgba(255, 255, 255, 0.35)';
        mapCtx.font = '10px monospace';
        mapCtx.textAlign = 'center';
        mapCtx.fillText('000° N', cx, 14);
        mapCtx.fillText('180° S', cx, H - 6);
        mapCtx.textAlign = 'left';
        mapCtx.fillText('090° E', W - 38, cy - 4);
        mapCtx.textAlign = 'right';
        mapCtx.fillText('270° W', 42, cy - 4);

        // Center Marker: Таирова / Гармония
        mapCtx.fillStyle = 'var(--green)';
        mapCtx.beginPath();
        mapCtx.arc(cx, cy, 4, 0, Math.PI * 2);
        mapCtx.fill();
        mapCtx.strokeStyle = 'rgba(52, 209, 122, 0.6)';
        mapCtx.strokeRect(cx - 8, cy - 8, 16, 16);
        mapCtx.fillStyle = '#ffffff';
        mapCtx.font = 'bold 11px Inter, sans-serif';
        mapCtx.textAlign = 'center';
        mapCtx.fillText('ТАИРОВА · ГАРМОНИЯ', cx, cy + 22);

        // Rotating Sweep line
        mapSweepAngle += 0.022;
        const sweepX = cx + Math.cos(mapSweepAngle) * (W / 2);
        const sweepY = cy + Math.sin(mapSweepAngle) * (H / 2);
        const sweepGrad = mapCtx.createLinearGradient(cx, cy, sweepX, sweepY);
        sweepGrad.addColorStop(0, 'rgba(52, 209, 122, 0.45)');
        sweepGrad.addColorStop(1, 'rgba(52, 209, 122, 0)');
        mapCtx.strokeStyle = sweepGrad;
        mapCtx.lineWidth = 2;
        mapCtx.beginPath();
        mapCtx.moveTo(cx, cy);
        mapCtx.lineTo(sweepX, sweepY);
        mapCtx.stroke();

        // Render Targets (if simulate is on)
        if (mapSimulate) {
          const now = performance.now();
          mapTargets.forEach((t, i) => {
            const rad = t.angleDeg * Math.PI / 180;
            const tx = cx + Math.sin(rad) * t.distKm * scale;
            const ty = cy - Math.cos(rad) * t.distKm * scale;

            // Pulsing threat circle
            const pulse = 1 + 0.3 * Math.sin(now * 0.006 + i);
            mapCtx.strokeStyle = 'rgba(255, 90, 95, ' + (0.5 / pulse).toFixed(2) + ')';
            mapCtx.lineWidth = 1.5;
            mapCtx.beginPath();
            mapCtx.arc(tx, ty, 10 * pulse, 0, Math.PI * 2);
            mapCtx.stroke();

            // Delta wing target marker
            mapCtx.fillStyle = 'var(--red)';
            mapCtx.beginPath();
            mapCtx.arc(tx, ty, 4.5, 0, Math.PI * 2);
            mapCtx.fill();

            // Vector trajectory line
            const headRad = (t.heading - 90) * Math.PI / 180;
            const vecLen = 30;
            const vx = tx + Math.cos(headRad) * vecLen;
            const vy = ty + Math.sin(headRad) * vecLen;
            mapCtx.strokeStyle = 'var(--red)';
            mapCtx.lineWidth = 2;
            mapCtx.beginPath();
            mapCtx.moveTo(tx, ty);
            mapCtx.lineTo(vx, vy);
            mapCtx.stroke();

            // Target Text tag
            mapCtx.fillStyle = '#ff5a5f';
            mapCtx.font = 'bold 10px monospace';
            mapCtx.textAlign = 'left';
            mapCtx.fillText(t.id + ' ▲', tx + 8, ty - 4);
            mapCtx.fillStyle = 'rgba(255, 255, 255, 0.7)';
            mapCtx.font = '9px monospace';
            mapCtx.fillText(t.speed + ' км/ч · ~' + t.eta + 'м', tx + 8, ty + 7);
          });
        }
      }
      requestAnimationFrame(renderTacticalMapLoop);
    }
    requestAnimationFrame(renderTacticalMapLoop);
  </script>"""

    if script_end_target in html:
        html = html.replace(script_end_target, tactical_engine_js)
        print('6. Tactical Map Engine JS appended')
    else:
        print('ERROR 6: script_end_target not found')

    with open('static/index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print('Upgrade complete: static/index.html successfully updated!')

if __name__ == '__main__':
    main()
