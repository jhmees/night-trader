/* Interactive tail-spend Pareto exhibit.
   Story: top ~20% of suppliers = ~80% of spend (you keep);
   bottom ~80% of suppliers = ~20% of spend but most of the transactions (we run it). */
(function () {
  const SPEND = [55, 25, 6, 4, 3, 2.4, 1.8, 1.3, 0.9, 0.6];   // % of spend, by supplier decile (desc)
  const POS   = [6, 8, 7, 8, 9, 10, 12, 13, 13, 14];          // % of purchase orders (workload), by decile
  const decileLabel = (i) => `${i * 10}\u2013${i * 10 + 10}%`;

  function render(host) {
    if (!host || host.dataset.rendered) return;
    const W = 1180, H = 470;
    const padL = 8, padR = 8, padT = 28, padB = 64;
    const plotW = W - padL - padR, plotH = H - padT - padB;
    const n = SPEND.length, bw = plotW / n;
    const maxSpend = 56;
    let cumPO = 0; const cum = POS.map(v => (cumPO += v));

    const x = (i) => padL + i * bw + bw / 2;
    const yBar = (v) => padT + plotH - (v / maxSpend) * plotH;
    const yLine = (v) => padT + plotH - (v / 100) * plotH;

    const NS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.setAttribute('width', '100%');
    svg.style.display = 'block';
    svg.style.overflow = 'visible';

    // tail shading (deciles 2..9 -> bottom 80% of suppliers)
    const tailX = padL + 2 * bw;
    const shade = document.createElementNS(NS, 'rect');
    shade.setAttribute('x', tailX); shade.setAttribute('y', padT);
    shade.setAttribute('width', plotW - 2 * bw); shade.setAttribute('height', plotH);
    shade.setAttribute('fill', 'rgba(253,181,21,0.12)');
    svg.appendChild(shade);
    const tailTop = document.createElementNS(NS, 'line');
    tailTop.setAttribute('x1', tailX); tailTop.setAttribute('y1', padT);
    tailTop.setAttribute('x2', tailX); tailTop.setAttribute('y2', padT + plotH);
    tailTop.setAttribute('stroke', '#FDB515'); tailTop.setAttribute('stroke-width', '2');
    tailTop.setAttribute('stroke-dasharray', '5 5');
    svg.appendChild(tailTop);

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
      r.setAttribute('fill', i < 2 ? '#8B0E04' : '#C9A36B');
      r.style.transformBox = 'fill-box';
      r.style.transformOrigin = 'center bottom';
      r.style.transform = 'scaleY(0)';
      r.style.transition = 'transform .8s cubic-bezier(.2,.7,.2,1) ' + (i * 45) + 'ms, fill .15s';
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

    // x labels
    SPEND.forEach((v, i) => {
      const t = document.createElementNS(NS, 'text');
      t.setAttribute('x', x(i)); t.setAttribute('y', padT + plotH + 30);
      t.setAttribute('text-anchor', 'middle');
      t.setAttribute('font-family', "'Space Mono', monospace");
      t.setAttribute('font-size', '17'); t.setAttribute('fill', '#928B80');
      t.textContent = decileLabel(i);
      svg.appendChild(t);
    });
    const axisCap = document.createElementNS(NS, 'text');
    axisCap.setAttribute('x', padL + plotW / 2); axisCap.setAttribute('y', padT + plotH + 56);
    axisCap.setAttribute('text-anchor', 'middle');
    axisCap.setAttribute('font-family', "'Space Mono', monospace");
    axisCap.setAttribute('font-size', '16'); axisCap.setAttribute('fill', '#b3a89a');
    axisCap.setAttribute('letter-spacing', '2');
    axisCap.textContent = 'SUPPLIERS, RANKED BY SPEND  \u2192';
    svg.appendChild(axisCap);

    // hover hit-areas + tooltip
    const tip = host.querySelector('.pareto-tip');
    SPEND.forEach((v, i) => {
      const hit = document.createElementNS(NS, 'rect');
      hit.setAttribute('x', padL + i * bw); hit.setAttribute('y', padT);
      hit.setAttribute('width', bw); hit.setAttribute('height', plotH);
      hit.setAttribute('fill', 'transparent'); hit.style.cursor = 'crosshair';
      hit.addEventListener('mouseenter', () => {
        bars[i].setAttribute('fill', i < 2 ? '#a81406' : '#FDB515');
        if (tip) {
          tip.style.opacity = '1';
          tip.style.left = (x(i) / W * 100) + '%';
          tip.innerHTML = `<b>Suppliers ${decileLabel(i)}</b>` +
            `<span><i style="background:#C9A36B"></i>${v}% of spend</span>` +
            `<span><i style="background:#1A4485"></i>${POS[i]}% of POs</span>`;
        }
      });
      hit.addEventListener('mouseleave', () => {
        bars[i].setAttribute('fill', i < 2 ? '#8B0E04' : '#C9A36B');
        if (tip) tip.style.opacity = '0';
      });
      svg.appendChild(hit);
    });

    host.appendChild(svg);
    host.dataset.rendered = '1';

    // ── entry animation, replayed each time the slide becomes active ──
    var shown = false;
    function show() {
      if (shown) return; shown = true;
      bars.forEach(function (b) { b.style.transform = 'scaleY(1)'; });
      poly.style.strokeDashoffset = '0';
      dots.forEach(function (d) { d.style.opacity = '1'; });
    }
    function reset() {
      shown = false;
      bars.forEach(function (b) { b.style.transform = 'scaleY(0)'; });
      poly.style.strokeDashoffset = lineLen;
      dots.forEach(function (d) { d.style.opacity = '0'; });
    }
    var section = host.closest('section');
    document.addEventListener('slidechange', function (e) {
      var active = e.detail && e.detail.slide;
      if (active === section) { reset(); requestAnimationFrame(show); }
      else reset();
    });
  }

  function boot() {
    document.querySelectorAll('.pareto-chart').forEach(render);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
