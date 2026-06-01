/* Slide motion layer — count-up numbers + growing bars on slide entry.
   Listens to deck-stage's `slidechange` event and animates the active slide.
   Reads each element's authored text/width as the target, so slide markup
   stays static and directly editable; the script only animates the display. */
(function () {
  // Elements whose text is a number to count up from zero.
  var COUNT_SEL = '.stat-n, .vs-big, .cafter, .am-v, .vbar-val, .pc-n';

  function easeOutCubic(p) { return 1 - Math.pow(1 - p, 3); }

  function countUp(el) {
    if (!el.dataset.target) el.dataset.target = el.textContent.trim();
    var target = el.dataset.target;
    // Special case: two-number values like "20% / 70%" or a range like "80–90%".
    // Both numbers climb together; the separator (slash or en/em-dash/hyphen) is kept.
    var two = target.match(/^(\d+)(%?)\s*([\/–—-])\s*(\d+)(%?)$/);
    var dur = 1050;
    if (two) {
      var a = +two[1], s1 = two[2], sep = two[3], b = +two[4], s2 = two[5], t0 = performance.now();
      var join = sep === '/' ? ' / ' : sep;
      var stepTwo = function (now) {
        var p = Math.min(1, (now - t0) / dur), e = easeOutCubic(p);
        el.textContent = Math.round(a * e) + s1 + join + Math.round(b * e) + s2;
        if (p < 1) requestAnimationFrame(stepTwo); else el.textContent = target;
      };
      requestAnimationFrame(stepTwo);
      return;
    }
    var m = target.match(/^([^\d.\-]*)(-?\d+(?:\.\d+)?)(.*)$/);
    if (!m) return;
    var prefix = m[1], numStr = m[2], suffix = m[3];
    var end = parseFloat(numStr);
    var dec = (numStr.split('.')[1] || '').length;
    var start = performance.now();
    var step = function (now) {
      var p = Math.min(1, (now - start) / dur), e = easeOutCubic(p);
      el.textContent = prefix + (end * e).toFixed(dec) + suffix;
      if (p < 1) requestAnimationFrame(step); else el.textContent = target;
    };
    requestAnimationFrame(step);
  }

  function growBar(el) {
    if (!el.dataset.w) el.dataset.w = el.style.width || getComputedStyle(el).width;
    el.style.transition = 'none';
    el.style.width = '0%';
    void el.offsetWidth; // reflow
    el.style.transition = 'width 1.05s cubic-bezier(.2,.7,.2,1)';
    requestAnimationFrame(function () { el.style.width = el.dataset.w; });
  }

  function animateSlide(slide) {
    if (!slide) return;
    slide.querySelectorAll(COUNT_SEL).forEach(countUp);
    slide.querySelectorAll('.vbar-fill').forEach(growBar);
  }

  // Trending hashtag ticker (slide 02) — one hashtag at a time, crossfading
  // in place beside a persistent pulse beacon, while the stat counters climb.
  var driverTimer = null;
  function cycleDrivers(slide) {
    if (driverTimer) { clearInterval(driverTimer); driverTimer = null; }
    if (!slide) return;
    var tags = slide.querySelectorAll('.trending-stage .tag');
    if (!tags.length) return;
    var idx = 0;
    tags.forEach(function (t) { t.classList.remove('on'); });
    setTimeout(function () { tags[0].classList.add('on'); }, 280);
    driverTimer = setInterval(function () {
      tags[idx].classList.remove('on');
      idx = (idx + 1) % tags.length;
      tags[idx].classList.add('on');
    }, 1700);
  }

  // Staggered fade-up of the slide's main blocks on entry.
  var REVEAL_SEL = '.cv-kick, .cv-h, .cv-dek, .cv-foot, .div-num, .div-ch, .div-t, .topbar, .head, .hairline, .body-area';
  function reveal(slide) {
    if (!slide) return;
    var els = slide.querySelectorAll(REVEAL_SEL);
    els.forEach(function (el, i) {
      el.style.transition = 'none';
      el.style.opacity = '0';
      el.style.transform = 'translateY(18px)';
      void el.offsetWidth;
      var d = i * 70;
      el.style.transition = 'opacity .55s ease ' + d + 'ms, transform .6s cubic-bezier(.2,.7,.2,1) ' + d + 'ms';
      requestAnimationFrame(function () { el.style.opacity = '1'; el.style.transform = 'translateY(0)'; });
    });
  }

  function updateProgress(e) {
    var bar = document.querySelector('.deck-progress');
    if (bar && e.detail && e.detail.total) {
      bar.style.width = ((e.detail.index + 1) / e.detail.total * 100) + '%';
    }
  }

  document.addEventListener('slidechange', function (e) {
    var slide = e.detail && e.detail.slide;
    reveal(slide);
    animateSlide(slide);
    cycleDrivers(slide);
    updateProgress(e);
  });

  // Kick the trending ticker on initial load too, so it's animating even when
  // the deck opens directly on slide 02 (no slidechange has fired yet).
  window.addEventListener('load', function () {
    var stage = document.querySelector('.trending-stage');
    if (stage) cycleDrivers(stage.closest('.slide'));
  });

  // Chapter tab bar — replaces each slide's plain "NN — Title" kicker with a
  // persistent 4-chapter nav. The active chapter is read from the kicker's
  // leading number; earlier chapters are marked done; tabs jump to each
  // chapter's entry slide. Edit CHAPTERS / ENTRY to retitle or re-map.
  var CHAPTERS = ['Pressure', 'Thesis', 'Operator', 'Why PHT'];
  var ENTRY = { 1: 1, 2: 3, 3: 7, 4: 12 }; // chapter → 0-based slide index
  function buildChapterNav() {
    var deck = document.querySelector('deck-stage');
    document.querySelectorAll('.topbar .kick').forEach(function (kick) {
      var m = (kick.textContent || '').match(/\d+/);
      if (!m) return;
      var active = parseInt(m[0], 10);
      var nav = document.createElement('nav');
      nav.className = 'chapnav';
      CHAPTERS.forEach(function (name, i) {
        var n = i + 1;
        var tab = document.createElement('span');
        tab.className = 'chaptab' + (n === active ? ' active' : (n < active ? ' done' : ''));
        tab.innerHTML = '<i>' + String(n).padStart(2, '0') + '</i>' + name;
        tab.addEventListener('click', function () {
          if (deck && typeof deck.goTo === 'function' && ENTRY[n] != null) deck.goTo(ENTRY[n]);
        });
        nav.appendChild(tab);
      });
      kick.replaceWith(nav);
    });
  }
  window.addEventListener('load', buildChapterNav);
})();
