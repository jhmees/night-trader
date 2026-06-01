/* Interactive tail-spend Pareto exhibit (chemicals).
   Drag the threshold to split the supplier base: what you keep (strategic A/B
   spend) vs. what you hand PHT (the C-material tail). A live readout recomputes
   spend / transaction / supplier shares on each move — an analyst tool, not a
   toy: snap-to-decile boundaries, mono readouts, no springy motion.

   Distribution illustrative; the cited evidence strip carries the published
   McKinsey / Kearney figures. */
(function () {
  const SPEND = [55, 25, 6, 4, 3, 2.4, 1.8, 1.3, 0.9, 0.6];   // % of spend, by supplier decile (desc)
  const POS   = [6, 8, 7, 8, 9, 10, 12, 13, 13, 14];          // % of purchase orders (workload), by decile
  const NS = 'http://www.w3.org/2000/svg';
  const DEFAULT_THR = 2;                                       // deciles kept by default → "top 20%"
  const decileLabel = (i) => `${i * 10}–${i * 10 + 10}%`;
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  const sum = (arr, a, b) => arr.slice(a, b).reduce((s, v) => s + v, 0);
  const round = Math.round;
  function easeOutCubic(p) { return 1 - Math.pow(1 - p, 3); }

  function render(host) {
    if (!host || host.dataset.rendered) return;
    const W = 1180, H = 420;
    const padL = 8, padR = 8, padT = 22, padB = 58;
    const plotW = W - padL - padR, plotH = H - padT - padB;
    const n = SPEND.length, bw = plotW / n;
    const maxSpend = 56;
    let cumPO = 0; const cum = POS.map(v => (cumPO += v));

    const x = (i) => padL + i * bw + bw / 2;
    const bound = (t) => padL + t * bw;                        // x of the boundary after `t` deciles
    const yBar = (v) => padT + plotH - (v / maxSpend) * plotH;
    const yLine = (v) => padT + plotH - (v / 100) * plotH;

    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.setAttribute('width', '100%');
    svg.style.display = 'block';
    svg.style.overflow = 'visible';

    // tail shading — follows the threshold (everything to the right is "handed over")
    const shade = document.createElementNS(NS, 'rect');
    shade.setAttribute('y', padT); shade.setAttribute('height', plotH);
    shade.setAttribute('fill', 'rgba(253,181,21,0.12)');
    svg.appendChild(shade);

    // baseline
    const base = document.createElementNS(NS, 'line');
    base.setAttribute('x1', padL); base.setAttribute('y1', padT + plotH);
    base.setAttribute('x2', padL + plotW); base.setAttribute('y2', padT + plotH);
    base.setAttribute('stroke', 'rgba(24,20,15,0.25)'); base.setAttribute('stroke-width', '1.5');
    svg.appendChild(base);

    // bars
    const bars = [];
    SPEND.forEach((v, i) => {
      const r = document.createElementNS(NS, 'rect');
      const w = bw * 0.62, bx = x(i) - w / 2, by = yBar(v);
      r.setAttribute('x', bx); r.setAttribute('width', w);
      r.setAttribute('y', by); r.setAttribute('height', padT + plotH - by);
      r.setAttribute('rx', '3');
      r.style.transformBox = 'fill-box';
      r.style.transformOrigin = 'center bottom';
      r.style.transform = 'scaleY(0)';
      r.style.transition = 'transform .8s cubic-bezier(.2,.7,.2,1) ' + (i * 45) + 'ms, fill .18s ease';
      svg.appendChild(r); bars.push(r);
    });

    // cumulative PO line (workload)
    const linePts = cum.map((v, i) => `${x(i)},${yLine(v)}`).join(' ');
    const poly = document.createElementNS(NS, 'polyline');
    poly.setAttribute('points', linePts);
    poly.setAttribute('fill', 'none');
    poly.setAttribute('stroke', '#1A4485');
    poly.setAttribute('stroke-width', '3');
    poly.setAttribute('stroke-linejoin', 'round');
    svg.appendChild(poly);
    const lineLen = poly.getTotalLength ? poly.getTotalLength() : 0;
    poly.style.transition = 'stroke-dashoffset 1.1s cubic-bezier(.4,0,.2,1) .35s';
    poly.style.strokeDasharray = lineLen;
    poly.style.strokeDashoffset = lineLen;
    const dots = [];
    cum.forEach((v, i) => {
      const c = document.createElementNS(NS, 'circle');
      c.setAttribute('cx', x(i)); c.setAttribute('cy', yLine(v));
      c.setAttribute('r', '4'); c.setAttribute('fill', '#1A4485');
      c.style.opacity = '0';
      c.style.transition = 'opacity .3s ease ' + (700 + i * 70) + 'ms';
      svg.appendChild(c); dots.push(c);
    });

    // x labels + axis caption
    SPEND.forEach((v, i) => {
      const t = document.createElementNS(NS, 'text');
      t.setAttribute('x', x(i)); t.setAttribute('y', padT + plotH + 28);
      t.setAttribute('text-anchor', 'middle');
      t.setAttribute('font-family', "'Space Mono', monospace");
      t.setAttribute('font-size', '17'); t.setAttribute('fill', '#928B80');
      t.textContent = decileLabel(i);
      svg.appendChild(t);
    });
    const axisCap = document.createElementNS(NS, 'text');
    axisCap.setAttribute('x', padL + plotW / 2); axisCap.setAttribute('y', padT + plotH + 52);
    axisCap.setAttribute('text-anchor', 'middle');
    axisCap.setAttribute('font-family', "'Space Mono', monospace");
    axisCap.setAttribute('font-size', '16'); axisCap.setAttribute('fill', '#b3a89a');
    axisCap.setAttribute('letter-spacing', '2');
    axisCap.textContent = 'SUPPLIERS, RANKED BY SPEND  →';
    svg.appendChild(axisCap);

    // ── threshold divider (drawn last so it sits above the bars) ──
    const divider = document.createElementNS(NS, 'line');
    divider.setAttribute('y1', padT - 4); divider.setAttribute('y2', padT + plotH);
    divider.setAttribute('stroke', '#FDB515'); divider.setAttribute('stroke-width', '2.5');
    divider.setAttribute('stroke-dasharray', '6 5');
    svg.appendChild(divider);
    const grip = document.createElementNS(NS, 'path');   // small downward chevron at the top
    grip.setAttribute('fill', '#FDB515');
    svg.appendChild(grip);

    // transparent drag surface over the plot
    const overlay = document.createElementNS(NS, 'rect');
    overlay.setAttribute('x', padL); overlay.setAttribute('y', padT);
    overlay.setAttribute('width', plotW); overlay.setAttribute('height', plotH);
    overlay.setAttribute('fill', 'transparent');
    overlay.style.cursor = 'ew-resize';
    svg.appendChild(overlay);

    host.appendChild(svg);

    // HTML threshold label (crisp text, unaffected by the SVG's scaling)
    const thumb = document.createElement('div');
    thumb.className = 'pareto-thumb';
    host.appendChild(thumb);

    // readout panel (sibling of the chart, inside .pareto-stage)
    const split = host.parentElement.querySelector('.pareto-split');
    if (split) {
      split.innerHTML =
        '<div class="psplit keep"><div class="ph"><b>You keep</b> · top <span class="kpct"></span></div>' +
          '<div class="pn"></div><div class="px">of spend — the strategic A/B materials only your team should own.</div></div>' +
        '<div class="psplit give"><div class="ph"><b>Hand PHT</b> · bottom <span class="gpct"></span></div>' +
          '<div class="pn"></div><div class="px">of the transactions, for just <b class="gspend"></b> of spend. The tail.</div></div>' +
        '<div class="pareto-hint">◂ drag the line to set the split ▸</div>';
    }
    const keepPn = split && split.querySelector('.keep .pn');
    const givePn = split && split.querySelector('.give .pn');
    const kpct = split && split.querySelector('.kpct');
    const gpct = split && split.querySelector('.gpct');
    const gspend = split && split.querySelector('.gspend');

    host.dataset.rendered = '1';

    let thr = DEFAULT_THR;

    // Paint everything that depends on the threshold. `animateNums` counts the
    // two headline figures up from zero (entry only); drags update instantly.
    function paint(animateNums) {
      const bx = bound(thr);
      divider.setAttribute('x1', bx); divider.setAttribute('x2', bx);
      grip.setAttribute('d', `M${bx - 7} ${padT - 6} L${bx + 7} ${padT - 6} L${bx} ${padT + 4} Z`);
      shade.setAttribute('x', bx); shade.setAttribute('width', padL + plotW - bx);
      thumb.style.left = (bx / W * 100) + '%';
      thumb.textContent = 'TOP ' + (thr * 10) + '%';
      bars.forEach((b, i) => b.setAttribute('fill', i < thr ? '#8B0E04' : '#C9A36B'));

      const keepSpend = round(sum(SPEND, 0, thr));
      const givePOs = round(sum(POS, thr, n));
      if (kpct) kpct.textContent = (thr * 10) + '%';
      if (gpct) gpct.textContent = ((n - thr) * 10) + '%';
      if (gspend) gspend.textContent = (100 - keepSpend) + '%';
      if (animateNums) {
        countNum(keepPn, keepSpend, '%');
        countNum(givePn, givePOs, '%');
      } else {
        if (keepPn) keepPn.textContent = keepSpend + '%';
        if (givePn) givePn.textContent = givePOs + '%';
      }
    }

    function countNum(el, to, suffix) {
      if (!el) return;
      const t0 = performance.now(), dur = 900;
      (function step(now) {
        const p = Math.min(1, (now - t0) / dur);
        el.textContent = round(to * easeOutCubic(p)) + suffix;
        if (p < 1) requestAnimationFrame(step);
      })(performance.now());
    }

    function thrFromClientX(clientX) {
      const r = svg.getBoundingClientRect();
      const fx = (clientX - r.left) / r.width * W;
      return clamp(round((fx - padL) / bw), 1, n - 1);
    }
    function onDrag(clientX) {
      const t = thrFromClientX(clientX);
      if (t !== thr) { thr = t; paint(false); }
    }
    overlay.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      overlay.setPointerCapture(e.pointerId);
      onDrag(e.clientX);
      const move = (ev) => onDrag(ev.clientX);
      const up = () => {
        overlay.removeEventListener('pointermove', move);
        overlay.removeEventListener('pointerup', up);
        overlay.removeEventListener('pointercancel', up);
      };
      overlay.addEventListener('pointermove', move);
      overlay.addEventListener('pointerup', up);
      overlay.addEventListener('pointercancel', up);
    });
    // Keyboard accessibility — ←/→ nudge the threshold when the chart is focused.
    // tabindex also makes deck-stage treat taps here as interactive (no slide nav).
    host.setAttribute('tabindex', '0');
    host.setAttribute('role', 'slider');
    host.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft') { thr = clamp(thr - 1, 1, n - 1); paint(false); e.preventDefault(); e.stopPropagation(); }
      else if (e.key === 'ArrowRight') { thr = clamp(thr + 1, 1, n - 1); paint(false); e.preventDefault(); e.stopPropagation(); }
    });

    // ── entry animation, replayed each time the slide becomes active ──
    let shown = false;
    function show() {
      if (shown) return; shown = true;
      bars.forEach((b) => { b.style.transform = 'scaleY(1)'; });
      poly.style.strokeDashoffset = '0';
      dots.forEach((d) => { d.style.opacity = '1'; });
      divider.style.transition = grip.style.transition = thumb.style.transition = 'opacity .4s ease';
      divider.style.opacity = grip.style.opacity = thumb.style.opacity = '1';
      paint(true);
    }
    function reset() {
      shown = false; thr = DEFAULT_THR;
      bars.forEach((b) => { b.style.transform = 'scaleY(0)'; });
      poly.style.strokeDashoffset = lineLen;
      dots.forEach((d) => { d.style.opacity = '0'; });
      divider.style.transition = grip.style.transition = thumb.style.transition = 'none';
      divider.style.opacity = grip.style.opacity = thumb.style.opacity = '0';
      paint(false);
    }

    reset();
    const section = host.closest('section');
    document.addEventListener('slidechange', function (e) {
      const active = e.detail && e.detail.slide;
      if (active === section) { reset(); requestAnimationFrame(() => requestAnimationFrame(show)); }
      else reset();
    });
    // If the deck loads directly on this slide, no slidechange fires for it.
    if (section && section.hasAttribute('data-deck-active')) {
      requestAnimationFrame(() => requestAnimationFrame(show));
    }
  }

  function boot() {
    document.querySelectorAll('.pareto-chart').forEach(render);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
