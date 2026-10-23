/* Roshan Bharti — portfolio behaviour.
   Source: src/main.js. tools/build_site.py copies it to assets/site.js.
   Classic script (no modules, no fetch) so the page also works opened straight from disk.
   Everything here is an enhancement: without it the page is complete and readable. */
(function () {
  'use strict';

  var d = document;
  var root = d.documentElement;
  var $ = function (s, c) { return (c || d).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || d).querySelectorAll(s)); };
  var mq = function (q) { return window.matchMedia ? window.matchMedia(q) : { matches: false, addEventListener: function () {} }; };
  var reduceMQ = mq('(prefers-reduced-motion: reduce)');
  var pad2 = function (n) { return (n < 10 ? '0' : '') + n; };
  var onMQ = function (m, fn) { if (m.addEventListener) m.addEventListener('change', fn); else if (m.addListener) m.addListener(fn); };
  // Prev / next buttons are switched off with aria-disabled, not the disabled property, so a
  // button that reaches the end of a board keeps keyboard focus instead of dropping it to <body>.
  var setOff = function (b, off) { if (b) b.setAttribute('aria-disabled', off ? 'true' : 'false'); };
  var isOff = function (b) { return b.getAttribute('aria-disabled') === 'true'; };

  /* ------------------------------------------------------------------
     Motion: one "Pause motion" toggle (aria-pressed) freezes every
     looping mark, swaps in the still PNG and turns off smooth scrolling
     and transitions. The choice is remembered; with no choice stored,
     the system's reduced-motion setting decides.
     ------------------------------------------------------------------ */
  var KEY = 'rb-motion';
  function stored() { try { return window.localStorage.getItem(KEY); } catch (e) { return null; } }
  function store(v) { try { window.localStorage.setItem(KEY, v); } catch (e) { /* private mode: not remembered */ } }
  function paused() { var s = stored(); return s ? s === 'paused' : reduceMQ.matches; }
  // The hero mark ships as the front-facing still (data-anim-srcset holds the animation), so the
  // first view isn't spent on a 260-435 KB animation. Once the page has loaded, and only while
  // motion is on, the animation is swapped in; it starts on that same frame, so the swap is invisible.
  var loaded = false;
  function wake() {
    if (!loaded || root.classList.contains('still')) return;
    $$('img[data-anim-srcset]').forEach(function (im) {
      im.srcset = im.getAttribute('data-anim-srcset');
      im.removeAttribute('data-anim-srcset');
    });
  }
  function applyMotion(p) {
    root.classList.toggle('still', p);
    $$('[data-motion]').forEach(function (b) { b.setAttribute('aria-pressed', p ? 'true' : 'false'); });
    // The first <source> of each animated mark serves the still PNG. Without JS it follows
    // prefers-reduced-motion; here it follows the toggle.
    $$('source[data-still]').forEach(function (s) { s.media = p ? 'all' : 'not all'; });
    wake();
  }
  applyMotion(paused());
  $$('[data-motion]').forEach(function (b) {
    b.addEventListener('click', function () {
      var p = !root.classList.contains('still');
      store(p ? 'paused' : 'playing');
      applyMotion(p);
    });
  });
  onMQ(reduceMQ, function () { if (!stored()) applyMotion(paused()); });
  var smooth = function () { return !root.classList.contains('still') && !reduceMQ.matches ? 'smooth' : 'auto'; };

  // After load: the deep-link jump (if any) has happened instantly, so smooth scrolling can be
  // switched on for in-page links (html.ready in styles.css), and the hero mark can start turning.
  function settle() {
    requestAnimationFrame(function () {
      root.classList.add('ready');
      loaded = true;
      if (window.requestIdleCallback) requestIdleCallback(wake, { timeout: 1500 }); else setTimeout(wake, 200);
    });
  }
  if (d.readyState === 'complete') settle(); else window.addEventListener('load', settle, { once: true });

  /* Wordmark: fitted to the measure in CSS. If the reader's own text spacing (WCAG 1.4.12) or a
     font fallback makes a line wider than the measure, it scales down to fit instead of running
     off the page. Measured only once the fonts are in, so first paint never shifts. */
  var wm = $('.wm');
  if (wm && window.ResizeObserver && d.fonts && d.fonts.ready) {
    var fitNow = 1, fitRaf = 0, span = d.createRange();
    var fit = function () {
      fitRaf = 0;
      var box = wm.getBoundingClientRect();
      if (!box.width) return;
      span.selectNodeContents(wm);
      // how far the furthest line reaches, as a share of the measure, at the natural size
      var natural = (span.getBoundingClientRect().right - box.left) / box.width / fitNow;
      var f = natural > 1.01 ? Math.max(0.5, Math.floor(1000 / natural) / 1000) : 1;
      if (Math.abs(f - fitNow) < 0.002) return;
      fitNow = f;
      if (f === 1) wm.style.removeProperty('--wm-fit'); else wm.style.setProperty('--wm-fit', String(f));
    };
    var queueFit = function () { if (!fitRaf) fitRaf = requestAnimationFrame(fit); };
    d.fonts.ready.then(function () {
      fit();
      var ro = new ResizeObserver(queueFit);
      $$('.wm-w', wm).forEach(function (w) { ro.observe(w); });
      ro.observe(wm);
    });
  }

  /* Header mark: still by default, turns its head on hover or focus. */
  var brand = $('.chrome .brand');
  var bm = brand && $('img[data-anim]', brand);
  if (bm) {
    var still = bm.getAttribute('src');
    var turn = function () { if (!root.classList.contains('still')) bm.src = bm.getAttribute('data-anim'); };
    var rest = function () { bm.src = still; };
    brand.addEventListener('mouseenter', turn);
    brand.addEventListener('focus', turn);
    brand.addEventListener('mouseleave', rest);
    brand.addEventListener('blur', rest);
  }

  /* ------------------------------------------------------------------
     Now showing: sections are painted statically in their own palettes;
     only the header indicator follows the section in view.
     ------------------------------------------------------------------ */
  var label = $('.now-label');
  var dots = $$('.seq i');
  var navLinks = $$('[data-nav]');
  var blocks = $$('[data-now]');
  function show(el) {
    if (label) label.textContent = el.getAttribute('data-now');
    var k = el.getAttribute('data-key');
    dots.forEach(function (i) { i.classList.toggle('on', i.getAttribute('data-k') === k); });
    var nk = el.getAttribute('data-nav-key');
    navLinks.forEach(function (a) {
      if (a.getAttribute('data-nav') === nk) a.setAttribute('aria-current', 'true');
      else a.removeAttribute('aria-current');
    });
  }
  if ('IntersectionObserver' in window && blocks.length) {
    var nio = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) show(e.target); });
    }, { rootMargin: '-45% 0px -54% 0px', threshold: 0 });
    blocks.forEach(function (b) { nio.observe(b); });
  }

  /* ------------------------------------------------------------------
     Board strips: one component for every board.
     ------------------------------------------------------------------ */
  var viewer = $('#viewer');
  var openViewer = function () {};

  $$('[data-board]').forEach(function (board) {
    var sc = $('.strip-scroller', board);
    var tiles = $$('.tile', sc);
    var count = $('[data-count]', board);
    var total = tiles.length;
    var prev = $('[data-step="-1"]', board);
    var next = $('[data-step="1"]', board);
    var ruler = $('.ruler-in', board);
    var thumb = $('.ruler-thumb', board);
    var raf = 0;

    // Tiles are reached with the region's arrow keys, not one Tab stop each.
    tiles.forEach(function (t) { t.setAttribute('tabindex', '-1'); });

    function bounds() {
      var pl = parseFloat(getComputedStyle(sc).paddingLeft) || 0;
      var first = tiles[0], last = tiles[total - 1];
      var start = first.offsetLeft, end = last.offsetLeft + last.offsetWidth;
      return { pl: pl, start: start, len: end - start };
    }
    // Tiles in view, measured against the scroller's content box (the slivers in the gutters
    // either side don't count). A tile counts when at least 40% of it, or of the box on screens
    // narrower than a tile, is showing; `best` is the one showing most. The counter reads the
    // range and Enter opens `best`, so both agree with what fills the view.
    function visible() {
      var pl = bounds().pl, L = sc.scrollLeft + pl, R = sc.scrollLeft + sc.clientWidth - pl, a = 0, b = 0, best = 0, most = -1;
      tiles.forEach(function (t, i) {
        var x = t.offsetLeft, w = t.offsetWidth, shown = Math.min(x + w, R) - Math.max(x, L);
        if (shown >= 0.4 * Math.min(w, R - L)) { if (!a) a = i + 1; b = i + 1; }
        if (shown > most) { most = shown; best = i + 1; }
      });
      return [a || best || 1, b || best || 1, best || 1];
    }
    function update() {
      raf = 0;
      var max = sc.scrollWidth - sc.clientWidth;
      var scrollable = max > 1;
      if (scrollable) sc.setAttribute('tabindex', '0'); else sc.removeAttribute('tabindex');
      setOff(prev, !scrollable || sc.scrollLeft <= 2);
      setOff(next, !scrollable || sc.scrollLeft >= max - 2);
      var v = visible();
      if (count) count.textContent = v[0] === v[1] ? 'Tile ' + pad2(v[0]) + ' of ' + pad2(total) : 'Tiles ' + pad2(v[0]) + '–' + pad2(v[1]) + ' of ' + pad2(total);
      if (thumb && ruler) {
        var bd = bounds(), rw = ruler.clientWidth;
        var x0 = Math.max(0, sc.scrollLeft - bd.start), x1 = Math.min(bd.len, sc.scrollLeft + sc.clientWidth - bd.start);
        thumb.style.width = Math.max(6, (x1 - x0) / bd.len * rw) + 'px';
        thumb.style.transform = 'translateX(' + (x0 / bd.len * rw).toFixed(2) + 'px)';
      }
    }
    var queue = function () { if (!raf) raf = requestAnimationFrame(update); };
    sc.addEventListener('scroll', queue, { passive: true });
    window.addEventListener('resize', queue);
    tiles.forEach(function (t) { var im = $('img', t); if (im && !im.complete) im.addEventListener('load', queue, { once: true }); });
    // Boards whose first panel repeats the cover shown just above open past that panel, on new
    // material (data-start: the panel's width in px at the 1440 px tile height). The panel's edge
    // goes to the viewport edge, not the gutter, so the strip bleeds evenly both sides and the
    // gutter never shows a fragment of the skipped panel. It stays one Prev away.
    var start = +sc.getAttribute('data-start') || 0;
    if (start && tiles[0]) sc.scrollLeft = Math.round(start * tiles[0].offsetHeight / 1440 + bounds().pl);
    update();

    // Move to the start of the next / previous tile that is not fully in view. Repeated presses
    // during a smooth scroll count from where that scroll is heading, not from where it is now.
    var heading = null, headingTimer = 0;
    function step(dir) {
      var L = heading !== null ? heading : sc.scrollLeft, R = L + sc.clientWidth, pl = bounds().pl, target = null, i, t;
      if (dir > 0) {
        for (i = 0; i < total; i++) { t = tiles[i]; if (t.offsetLeft + t.offsetWidth > R + 2) { target = t.offsetLeft - pl; break; } }
        if (target !== null && target <= L + 2) target = L + sc.clientWidth * 0.85;
      } else {
        for (i = total - 1; i >= 0; i--) { t = tiles[i]; if (t.offsetLeft < L - 2) { target = t.offsetLeft - pl; break; } }
      }
      if (target === null) target = dir > 0 ? sc.scrollWidth - sc.clientWidth : 0;
      target = Math.max(0, Math.min(sc.scrollWidth - sc.clientWidth, target));
      eager();
      heading = target;
      clearTimeout(headingTimer);
      headingTimer = setTimeout(function () { heading = null; }, 700);
      sc.scrollTo({ left: target, behavior: smooth() });
    }
    if (prev) prev.addEventListener('click', function () { if (!isOff(prev)) step(-1); });
    if (next) next.addEventListener('click', function () { if (!isOff(next)) step(1); });

    // Keyboard on the focused region: arrows move a tile, Home / End jump, Enter enlarges the first tile in view.
    sc.addEventListener('keydown', function (e) {
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      var k = e.key;
      if (k === 'ArrowRight' || k === 'ArrowLeft') { e.preventDefault(); step(k === 'ArrowRight' ? 1 : -1); }
      else if (k === 'Home' || k === 'End') { e.preventDefault(); sc.scrollTo({ left: k === 'Home' ? 0 : sc.scrollWidth, behavior: smooth() }); }
      else if (k === 'Enter' && e.target === sc) { e.preventDefault(); openViewer(board, visible()[2] - 1); }
    });

    // Ruler: click anywhere to centre that part of the board.
    if (ruler) ruler.addEventListener('click', function (e) {
      eager();
      var r = ruler.getBoundingClientRect(), bd = bounds();
      var p = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
      sc.scrollTo({ left: bd.start + p * bd.len - sc.clientWidth / 2, behavior: smooth() });
    });

    // Mouse drag (touch and trackpads already scroll natively; the vertical wheel is never taken over).
    var drag = null, swallow = false;
    sc.addEventListener('pointerdown', function (e) {
      if (e.pointerType !== 'mouse' || e.button !== 0) return;
      drag = { x: e.clientX, l: sc.scrollLeft, id: e.pointerId, moved: false };
    });
    sc.addEventListener('pointermove', function (e) {
      if (!drag) return;
      var dx = e.clientX - drag.x;
      if (!drag.moved && Math.abs(dx) > 5) {
        drag.moved = true;
        try { sc.setPointerCapture(drag.id); } catch (err) {}
        sc.classList.add('dragging');
      }
      if (drag.moved) sc.scrollLeft = drag.l - dx;
    });
    var endDrag = function () {
      if (!drag) return;
      swallow = drag.moved; drag = null;
      sc.classList.remove('dragging');
      setTimeout(function () { swallow = false; }, 0);
    };
    sc.addEventListener('pointerup', endDrag);
    sc.addEventListener('pointercancel', endDrag);
    sc.addEventListener('click', function (e) {
      if (swallow) { e.preventDefault(); e.stopPropagation(); swallow = false; return; }
      var t = e.target.closest && e.target.closest('.tile');
      if (!t || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || !viewer || !viewer.showModal) return;
      e.preventDefault();
      openViewer(board, tiles.indexOf(t));
    }, true);

    // Load the whole strip once the reader stops within ~1000 px of it (or reaches for it), so
    // dragging never shows blank tiles. A smooth scroll that only passes by doesn't load it.
    var eager = function () {
      if (!tiles.length || $('img', tiles[0]).loading === 'eager') return;
      tiles.forEach(function (t) { var im = $('img', t); if (im) im.loading = 'eager'; });
      if (lio) lio.disconnect();
    };
    var lio = null, dwell = 0;
    if ('IntersectionObserver' in window) {
      lio = new IntersectionObserver(function (entries) {
        clearTimeout(dwell);
        if (entries[entries.length - 1].isIntersecting) dwell = setTimeout(eager, 700);
      }, { rootMargin: '1000px 0px 1000px 0px' });
      lio.observe(sc);
    } else {
      eager();
    }
    ['pointerenter', 'focusin', 'touchstart'].forEach(function (ev) { board.addEventListener(ev, eager, { passive: true }); });
  });

  /* ------------------------------------------------------------------
     Tile viewer: a <dialog> with the 1440 px tile so board text can be read.
     ------------------------------------------------------------------ */
  if (viewer && viewer.showModal) {
    var vFig = $('.viewer-fig', viewer);
    var vImg = null;            // made on first open, so the page never ships an <img> without a src
    var vTitle = $('#viewer-t');
    var vPrev = $('[data-vstep="-1"]', viewer);
    var vNext = $('[data-vstep="1"]', viewer);
    var vClose = $('[data-vclose]', viewer);
    var cur = { board: null, i: 0, tiles: [] };

    var render = function () {
      var t = cur.tiles[cur.i], im = $('img', t), n = cur.tiles.length;
      var name = $('.strip-scroller', cur.board).getAttribute('data-name');
      if (!vImg) { vImg = d.createElement('img'); vImg.decoding = 'async'; vFig.appendChild(vImg); }
      vImg.removeAttribute('src');
      vImg.width = +im.getAttribute('width');
      vImg.height = +im.getAttribute('height');
      vImg.src = t.getAttribute('href');
      vImg.alt = name + ' board, tile ' + pad2(cur.i + 1) + ' of ' + pad2(n);
      vTitle.textContent = name + ' board — tile ' + pad2(cur.i + 1) + ' of ' + pad2(n);
      vFig.scrollTop = 0;
      vFig.scrollLeft = fromEnd ? vFig.scrollWidth : 0;
      fromEnd = false;
      setOff(vPrev, cur.i === 0);
      setOff(vNext, cur.i === n - 1);
      panMode();
    };
    // On small screens the tile is shown taller than the box and the figure pans (styles.css).
    // Then it is a named, focusable group, so it can be reached and panned from the keyboard.
    var fromEnd = false;
    var pans = function () { return vFig.scrollWidth > vFig.clientWidth + 1; };
    var panMode = function () {
      if (pans()) {
        vFig.setAttribute('tabindex', '0');
        vFig.setAttribute('role', 'group');
        vFig.setAttribute('aria-label', 'Tile image, scroll sideways to see all of it');
      } else {
        ['tabindex', 'role', 'aria-label'].forEach(function (a) { vFig.removeAttribute(a); });
      }
    };
    window.addEventListener('resize', function () { if (viewer.open) panMode(); });
    // Arrow keys work wherever focus is while the viewer is open. Where the tile pans, they pan
    // it first and step to the next / previous tile only from its edge.
    var onKey = function (e) {
      if (!viewer.open || e.altKey || e.ctrlKey || e.metaKey) return;
      var dir = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
      if (!dir) return;
      e.preventDefault();
      if (pans()) {
        var max = vFig.scrollWidth - vFig.clientWidth;
        var atEdge = dir > 0 ? vFig.scrollLeft >= max - 2 : vFig.scrollLeft <= 2;
        if (!atEdge) { vFig.scrollBy({ left: dir * vFig.clientWidth * 0.8, behavior: smooth() }); return; }
        if (dir < 0 && cur.i > 0) fromEnd = true;
      }
      go(dir);
    };
    openViewer = function (board, i) {
      cur.board = board;
      cur.tiles = $$('.tile', board);
      cur.i = Math.max(0, Math.min(cur.tiles.length - 1, i));
      render();
      viewer.showModal();
      panMode();
      vClose.focus();
      d.addEventListener('keydown', onKey);
    };
    var go = function (dir) {
      var j = cur.i + dir;
      if (j < 0 || j >= cur.tiles.length) return;
      cur.i = j; render();
    };
    vPrev.addEventListener('click', function () { go(-1); });
    vNext.addEventListener('click', function () { go(1); });
    vClose.addEventListener('click', function () { viewer.close(); });
    // A click on the dark surround (not the image or the controls) closes, like a backdrop.
    viewer.addEventListener('click', function (e) {
      if (e.target === viewer || e.target === vFig) viewer.close();
    });
    // Esc closes natively; either way focus goes back to the tile last shown.
    viewer.addEventListener('close', function () {
      d.removeEventListener('keydown', onKey);
      var t = cur.tiles[cur.i];
      if (!t) return;
      var sc = t.parentNode.parentNode;
      var L = sc.scrollLeft, R = L + sc.clientWidth, pl = parseFloat(getComputedStyle(sc).paddingLeft) || 0;
      if (t.offsetLeft < L || t.offsetLeft + t.offsetWidth > R) sc.scrollLeft = t.offsetLeft - pl;
      t.focus({ preventScroll: true });
    });
  }

  /* ------------------------------------------------------------------
     Palette: select a colour to copy its HEX.
     ------------------------------------------------------------------ */
  var toast = $('.toast');
  var toastTimer = 0, writeTimer = 0, clearTimer = 0;
  // Empty the live region first and write the message a moment later, so the same message twice
  // is announced twice; once the toast has faded its text is removed too, so nothing stale is left.
  function say(msg, hex) {
    if (!toast) return;
    clearTimeout(toastTimer); clearTimeout(writeTimer); clearTimeout(clearTimer);
    toast.textContent = '';
    writeTimer = setTimeout(function () {
      var sw = d.createElement('i');
      sw.setAttribute('aria-hidden', 'true');
      sw.style.setProperty('--c', hex);
      toast.appendChild(sw);
      toast.appendChild(d.createTextNode(msg));
      toast.classList.add('on');
      toastTimer = setTimeout(function () {
        toast.classList.remove('on');
        clearTimer = setTimeout(function () { toast.textContent = ''; }, 300);
      }, 2600);
    }, 60);
  }
  function fallbackCopy(text) {
    var ok = false;
    try {
      var ta = d.createElement('textarea');
      ta.value = text; ta.setAttribute('readonly', '');
      ta.style.cssText = 'position:fixed;top:0;left:-9999px;opacity:0';
      d.body.appendChild(ta); ta.select();
      ok = d.execCommand('copy');
      d.body.removeChild(ta);
    } catch (e) { ok = false; }
    return ok;
  }
  $$('.chip[data-hex]').forEach(function (b) {
    b.addEventListener('click', function () {
      var hex = b.getAttribute('data-hex');
      var done = function (ok) { say(ok ? 'Copied ' + hex : 'Couldn’t copy — the HEX is ' + hex, hex); };
      if (navigator.clipboard && navigator.clipboard.writeText && window.isSecureContext) {
        navigator.clipboard.writeText(hex).then(function () { done(true); }, function () { done(fallbackCopy(hex)); });
      } else {
        done(fallbackCopy(hex));
      }
    });
  });
})();
