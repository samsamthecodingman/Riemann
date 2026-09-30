// cols.js
// -----------------------------------------------------------------------
// Resizable columns on desktop (>= 1100px): a drag handle between the left
// column (the SECTIONS nav, or the map when it is open) and the reader, and
// another between the reader and the right rail (when the rail is showing).
//
// Widths live in CSS custom properties on #app (--col-left, --col-rail) that
// the grid in style.css reads; when unset the CSS defaults apply. They are
// kept separately for "map open" and "map closed", persisted in
// localStorage['riemann:cols'], and re-clamped (never written) when the
// window is resized. While dragging, the reading position is held with the
// reader's keepReadingPosition helper and the map is asked to redraw (rAF).
// -----------------------------------------------------------------------
(function () {
  "use strict";

  const STORE_KEY = "riemann:cols";
  const READER_MIN = 480;
  const LIMITS = {
    nav: { min: 160, max: 420 },
    map: { min: 220, max: 720 },
    rail: { min: 200, max: 420 },
  };
  const STEP = 16;
  const STEP_BIG = 64;
  const wideMQ = window.matchMedia("(min-width: 1100px)");

  let $app, $nav, $panel, $rail, $left, $right;
  let keepPos = (fn) => fn();
  let saved = { open: {}, closed: {} }; // { left?: px, rail?: px } per mode
  let dragging = null;
  let raf = 0;

  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

  function load() {
    try {
      const raw = JSON.parse(localStorage.getItem(STORE_KEY) || "null");
      for (const mode of ["open", "closed"]) {
        const m = raw && raw[mode];
        if (!m) continue;
        for (const k of ["left", "rail"]) if (typeof m[k] === "number" && isFinite(m[k])) saved[mode][k] = m[k];
      }
    } catch (e) {}
  }
  function store() {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(saved));
    } catch (e) {}
  }

  const mode = () => ($app.classList.contains("map-open") ? "open" : "closed");
  const railShown = () => $rail && getComputedStyle($rail).display !== "none";
  const leftLimits = () => (mode() === "open" ? LIMITS.map : LIMITS.nav);

  // The widest the left column may be: the reader keeps READER_MIN.
  function leftMax() {
    const rail = railShown() ? $rail.offsetWidth : 0;
    return Math.max(leftLimits().min, Math.min(leftLimits().max, document.documentElement.clientWidth - rail - READER_MIN));
  }
  function railMax() {
    const left = mode() === "open" ? $panel.offsetWidth : $nav.offsetWidth;
    return Math.max(LIMITS.rail.min, Math.min(LIMITS.rail.max, document.documentElement.clientWidth - left - READER_MIN));
  }

  const currentLeft = () => Math.round((mode() === "open" ? $panel : $nav).getBoundingClientRect().width);
  const currentRail = () => Math.round($rail.getBoundingClientRect().width);

  // Apply the stored widths for the current mode (clamped), or clear the
  // custom properties so the CSS defaults apply.
  function apply() {
    if (!wideMQ.matches) {
      $app.style.removeProperty("--col-left");
      $app.style.removeProperty("--col-rail");
      return;
    }
    const m = saved[mode()];
    if (typeof m.left === "number") $app.style.setProperty("--col-left", `${clamp(m.left, leftLimits().min, leftMax())}px`);
    else $app.style.removeProperty("--col-left");
    if (typeof m.rail === "number") $app.style.setProperty("--col-rail", `${clamp(m.rail, LIMITS.rail.min, railMax())}px`);
    else $app.style.removeProperty("--col-rail");
    aria();
  }

  function aria() {
    if (!wideMQ.matches || !$app.classList.contains("active")) return;
    const l = leftLimits();
    $left.setAttribute("aria-valuemin", String(l.min));
    $left.setAttribute("aria-valuemax", String(Math.round(leftMax())));
    $left.setAttribute("aria-valuenow", String(currentLeft()));
    $left.setAttribute("aria-label", mode() === "open" ? "Resize the map" : "Resize the sections column");
    if (railShown()) {
      $right.setAttribute("aria-valuemin", String(LIMITS.rail.min));
      $right.setAttribute("aria-valuemax", String(Math.round(railMax())));
      $right.setAttribute("aria-valuenow", String(currentRail()));
    }
  }

  function notify() {
    aria();
    if (window.RiemannMap) window.RiemannMap.update();
  }

  // Set one column's width (px) or reset it (null), holding the reading position.
  function setWidth(which, px, persist) {
    const m = saved[mode()];
    if (px == null) delete m[which];
    else {
      const max = which === "left" ? leftMax() : railMax();
      const min = which === "left" ? leftLimits().min : LIMITS.rail.min;
      m[which] = Math.round(clamp(px, min, max));
    }
    keepPos(apply);
    if (persist) store();
    notify();
  }

  function onPointerDown(which, e) {
    if (e.button !== 0 && e.pointerType === "mouse") return;
    const h = which === "left" ? $left : $right;
    e.preventDefault();
    try {
      h.setPointerCapture(e.pointerId);
    } catch (err) {}
    dragging = { which, h, id: e.pointerId, x: e.clientX, w: which === "left" ? currentLeft() : currentRail(), next: null };
    h.classList.add("dragging");
    document.body.classList.add("col-dragging");
  }

  function onPointerMove(e) {
    if (!dragging || e.pointerId !== dragging.id) return;
    const dx = e.clientX - dragging.x;
    dragging.next = dragging.which === "left" ? dragging.w + dx : dragging.w - dx;
    if (!raf) {
      raf = requestAnimationFrame(() => {
        raf = 0;
        if (dragging && dragging.next != null) setWidth(dragging.which, dragging.next, false);
      });
    }
  }

  function onPointerUp(e) {
    if (!dragging || e.pointerId !== dragging.id) return;
    const d = dragging;
    dragging = null;
    if (raf) {
      cancelAnimationFrame(raf);
      raf = 0;
    }
    if (d.next != null) setWidth(d.which, d.next, true);
    d.h.classList.remove("dragging");
    document.body.classList.remove("col-dragging");
    try {
      d.h.releasePointerCapture(e.pointerId);
    } catch (err) {}
  }

  function onKey(which, e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();
      const dir = e.key === "ArrowRight" ? 1 : -1;
      const step = (e.shiftKey ? STEP_BIG : STEP) * dir;
      const cur = which === "left" ? currentLeft() : currentRail();
      // moving the rail's handle right narrows the rail
      setWidth(which, which === "left" ? cur + step : cur - step, true);
    } else if (e.key === "Enter") {
      e.preventDefault();
      setWidth(which, null, true);
    }
  }

  function wire(which, h) {
    h.addEventListener("pointerdown", (e) => onPointerDown(which, e));
    h.addEventListener("pointermove", onPointerMove);
    h.addEventListener("pointerup", onPointerUp);
    h.addEventListener("pointercancel", onPointerUp);
    h.addEventListener("dblclick", () => setWidth(which, null, true));
    h.addEventListener("keydown", (e) => onKey(which, e));
    h.addEventListener("focus", aria);
    h.addEventListener("pointerenter", aria);
  }

  function init(opts) {
    opts = opts || {};
    if (opts.keepReadingPosition) keepPos = opts.keepReadingPosition;
    $app = document.getElementById("app");
    $nav = document.getElementById("section-nav");
    $panel = document.getElementById("map-panel");
    $rail = document.getElementById("rail");
    $left = document.getElementById("col-handle-left");
    $right = document.getElementById("col-handle-rail");
    load();
    wire("left", $left);
    wire("rail", $right);
    apply();
    new MutationObserver(aria).observe($app, { attributes: true, attributeFilter: ["class"] });
    // Re-clamp on window resize (and when crossing the desktop breakpoint);
    // never writes to storage.
    window.addEventListener("resize", () => {
      if (dragging) return;
      apply();
    });
    if (wideMQ.addEventListener) wideMQ.addEventListener("change", apply);
  }

  // Called by the map when it opens or closes (inside keepReadingPosition).
  function refresh() {
    if ($app) apply();
  }

  window.RiemannCols = { init, refresh };
})();
