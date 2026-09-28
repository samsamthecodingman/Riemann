// app.js — Riemann v1 frontend. Vanilla JS, no build step.
// Reads docs/v1-build-spec.md as the contract. The zoom algorithm itself
// lives in frontier.js; this file is chrome, rendering, events and state.

(function () {
  "use strict";

  const WPM = 238;
  const REDUCED_MOTION = window.matchMedia("(prefers-motion-reduce), (prefers-reduced-motion: reduce)").matches;
  const IS_FIXTURE = new URLSearchParams(location.search).get("fixture") === "1";

  // ---------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------
  const state = {
    tree: null,
    z: 0,
    sequence: [],
    frontier: [],
    anchorNodeId: null,
    anchorOffset: null,
    minimalChrome: false,
    eventSource: null,
    lastAnnounce: 0,
    announceTimer: null,
    dwellTimer: null,
    dwellStart: 0,
    dwellNode: null,
    idleTimer: null,
    lastInputAt: Date.now(),
    lastDialChangeAt: 0,
    events: [],
  };

  const el = (id) => document.getElementById(id);
  const $startScreen = el("start-screen");
  const $app = el("app");
  const $content = el("content");
  const $rootGist = el("root-gist");
  const $breadcrumb = el("breadcrumb");
  const $dial = el("dial");
  const $dialReadout = el("dial-readout");
  const $liveRegion = el("live-region");
  const $popover = el("source-popover");
  const $resumeCard = el("resume-card");
  const $resumeCardText = el("resume-card-text");
  const $zoomHint = el("zoom-hint");

  // ---------------------------------------------------------------------
  // Pointer tracking — used to resolve "the passage under the pointer" for
  // every zoom gesture (Z-drag, ctrl+wheel/pinch, arrow/+-  keys).
  // ---------------------------------------------------------------------
  const lastMouse = { x: null, y: null };
  window.addEventListener(
    "mousemove",
    (e) => {
      lastMouse.x = e.clientX;
      lastMouse.y = e.clientY;
    },
    { passive: true }
  );

  function isPointOverContent(x, y) {
    if (x == null || y == null) return false;
    const rect = $content.getBoundingClientRect();
    return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
  }

  function nodeAtScreenPoint(x, y) {
    const hit = document.elementFromPoint(x, y);
    const found = hit && hit.closest && hit.closest("[data-node-id]");
    if (found) return found.dataset.nodeId;
    // Fell in the gap between nodes: pick the nearest by vertical distance.
    let best = null;
    let bestDist = Infinity;
    for (const n of $content.querySelectorAll("[data-node-id]")) {
      const r = n.getBoundingClientRect();
      if (y >= r.top && y <= r.bottom) return n.dataset.nodeId;
      const d = y < r.top ? r.top - y : y - r.bottom;
      if (d < bestDist) {
        bestDist = d;
        best = n;
      }
    }
    return best ? best.dataset.nodeId : null;
  }

  // ---------------------------------------------------------------------
  // Event log — batched POST /api/events every 5s, sendBeacon on pagehide
  // ---------------------------------------------------------------------
  function logEvent(type, data) {
    state.events.push(Object.assign({ type }, data));
  }

  function flushEvents(useBeacon) {
    if (state.events.length === 0) return;
    if (IS_FIXTURE) {
      // No backend to receive events in fixture mode; drop rather than
      // spamming the console with failed requests against the static server.
      state.events = [];
      return;
    }
    const payload = state.events;
    state.events = [];
    const body = JSON.stringify(payload);
    if (useBeacon && navigator.sendBeacon) {
      navigator.sendBeacon("/api/events", new Blob([body], { type: "application/json" }));
    } else {
      fetch("/api/events", { method: "POST", headers: { "Content-Type": "application/json" }, body }).catch(() => {
        // best-effort; drop on failure rather than blocking the UI
      });
    }
  }

  setInterval(() => flushEvents(false), 5000);
  window.addEventListener("pagehide", () => {
    if (state.tree) logEvent("close", { tree_id: state.tree.id });
    flushEvents(true);
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      savePosition();
      flushEvents(true);
    }
  });

  // idle tracking: no input for >60s, emitted on return
  function markInput() {
    const now = Date.now();
    const idleMs = now - state.lastInputAt;
    if (idleMs > 60000 && state.tree) {
      logEvent("idle", { tree_id: state.tree.id, ms: idleMs });
    }
    state.lastInputAt = now;
  }

  // ---------------------------------------------------------------------
  // localStorage resume
  // ---------------------------------------------------------------------
  function posKey(treeId) {
    return "riemann:pos:" + treeId;
  }

  function savePosition() {
    if (!state.tree) return;
    try {
      localStorage.setItem(
        posKey(state.tree.id),
        JSON.stringify({ z: state.z, anchor_node_id: state.anchorNodeId, anchor_offset: state.anchorOffset })
      );
    } catch (e) {
      /* storage unavailable; ignore */
    }
  }

  const savePositionDebounced = debounce(savePosition, 400);

  function loadPosition(treeId) {
    try {
      const raw = localStorage.getItem(posKey(treeId));
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  function debounce(fn, ms) {
    let t = null;
    return function (...args) {
      clearTimeout(t);
      t = setTimeout(() => fn.apply(null, args), ms);
    };
  }

  // ---------------------------------------------------------------------
  // Word / reading-time helpers
  // ---------------------------------------------------------------------
  function frontierWords(tree, frontier) {
    let words = 0;
    for (const id of frontier) {
      const n = tree.nodes[id];
      if (n) words += n.words;
    }
    return words;
  }

  function updateReadout() {
    const tree = state.tree;
    if (!tree) return;
    const words = frontierWords(tree, state.frontier);
    const minutes = Math.max(1, Math.round(words / WPM));
    const pct = Math.max(1, Math.round((words / Math.max(1, tree.source_words)) * 100));
    $dialReadout.textContent = `~${minutes} min · ${pct}% of original`;
    const valuetext = `about ${minutes} minute${minutes === 1 ? "" : "s"}, ${pct} percent of original`;
    $dial.setAttribute("aria-valuetext", valuetext);
    $dial.setAttribute("aria-valuenow", String(Math.round(state.z * 100)));
    const fillPct = Math.round(state.z * 100);
    $dial.style.background = `linear-gradient(to right, var(--accent) ${fillPct}%, var(--rule) ${fillPct}%)`;
    scheduleAnnounce(valuetext);
  }

  function scheduleAnnounce(text) {
    clearTimeout(state.announceTimer);
    state.announceTimer = setTimeout(() => {
      $liveRegion.textContent = text;
    }, 400);
  }

  // ---------------------------------------------------------------------
  // Anchor detection
  // ---------------------------------------------------------------------
  function findCentreNodeId() {
    const cx = window.innerWidth / 2;
    const cy = window.innerHeight / 2;
    let node = document.elementFromPoint(cx, cy);
    while (node && node !== document.body) {
      if (node.dataset && node.dataset.nodeId) return node.dataset.nodeId;
      node = node.parentElement;
    }
    // fallback: first rendered node
    return state.frontier[0] || state.tree.root;
  }

  function setAnchor(nodeId) {
    const prev = state.anchorNodeId;
    state.anchorNodeId = nodeId;
    const n = state.tree.nodes[nodeId];
    state.anchorOffset = n ? (n.source_span[0] + n.source_span[1]) / 2 : null;
    if (prev !== nodeId) {
      state.sequence = window.Frontier.buildExpansionSequence(state.tree, nodeId);
      handleDwellChange(nodeId);
    }
    savePositionDebounced();
  }

  function handleDwellChange(newNodeId) {
    const now = Date.now();
    if (state.dwellNode && state.dwellStart) {
      const ms = now - state.dwellStart;
      if (ms > 1500) {
        logEvent("dwell", { tree_id: state.tree.id, node_id: state.dwellNode, ms });
      }
    }
    state.dwellNode = newNodeId;
    state.dwellStart = now;
  }

  // ---------------------------------------------------------------------
  // Rendering
  // ---------------------------------------------------------------------
  function renderNodeHTML(node) {
    const html = window.marked ? window.marked.parse(node.text || "") : escapeHtml(node.text || "");
    if (node.is_leaf) {
      return `<div class="node leaf" data-node-id="${node.id}">${html}</div>`;
    }
    return `<div class="node summary" data-node-id="${node.id}"><span class="source-hint">${html}</span></div>`;
  }

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // Natural (pre-transform) rects from the most recent render, keyed by
  // node id. FLIP applies a `transform` to persisted nodes immediately
  // after layout, which getBoundingClientRect() reflects right away — so
  // anything that needs the node's *true* resting position (the anchor
  // reposition logic in setZ) must read from here, not query the live DOM
  // mid-transition.
  let lastRenderRects = new Map();

  function render(opts) {
    opts = opts || {};
    const tree = state.tree;
    const prevRects = new Map();
    if (!REDUCED_MOTION && !opts.columnCrossfade) {
      // Record rects of nodes that will persist (present in both old and new frontier).
      for (const elNode of $content.querySelectorAll("[data-node-id]")) {
        prevRects.set(elNode.dataset.nodeId, elNode.getBoundingClientRect());
      }
    }

    const newSet = new Set(state.frontier);
    const oldIds = Array.from($content.querySelectorAll("[data-node-id]")).map((n) => n.dataset.nodeId);
    const oldSet = new Set(oldIds);

    if (opts.columnCrossfade && !REDUCED_MOTION) {
      $content.classList.add("column-crossfade");
      $content.style.opacity = "0";
      setTimeout(() => {
        doRender();
        if (opts.onRendered) opts.onRendered();
        requestAnimationFrame(() => {
          $content.style.opacity = "1";
          setTimeout(() => $content.classList.remove("column-crossfade"), 200);
        });
      }, 180);
      return;
    }

    doRender();
    if (opts.onRendered) opts.onRendered();

    function doRender() {
      $content.innerHTML = state.frontier.map((id) => renderNodeHTML(tree.nodes[id])).join("");
      updateRootHeader();
      updateBreadcrumb();

      // Capture true post-layout, pre-transform rects for every rendered
      // node before any FLIP transform is applied below.
      lastRenderRects = new Map();
      for (const elNode of $content.querySelectorAll("[data-node-id]")) {
        lastRenderRects.set(elNode.dataset.nodeId, elNode.getBoundingClientRect());
      }

      if (REDUCED_MOTION) return;

      // FLIP for persisted nodes; fade for new ones.
      for (const elNode of $content.querySelectorAll("[data-node-id]")) {
        const id = elNode.dataset.nodeId;
        if (prevRects.has(id)) {
          const oldRect = prevRects.get(id);
          const newRect = lastRenderRects.get(id);
          const dy = oldRect.top - newRect.top;
          if (Math.abs(dy) > 0.5) {
            elNode.style.transform = `translateY(${dy}px)`;
            elNode.style.transition = "none";
            requestAnimationFrame(() => {
              elNode.style.transition = `transform ${180}ms ease`;
              elNode.style.transform = "";
            });
          }
        } else if (!oldSet.has(id)) {
          elNode.classList.add("fade-enter");
          elNode.addEventListener("animationend", () => elNode.classList.remove("fade-enter"), { once: true });
        }
      }
    }
  }

  function updateRootHeader() {
    const tree = state.tree;
    const root = tree.nodes[tree.root];
    $rootGist.textContent = root ? root.text : "";
    $rootGist.classList.toggle("provisional", !!tree.provisional_root);
  }

  function ancestorsOf(nodeId) {
    const out = [];
    let n = state.tree.nodes[nodeId];
    while (n && n.parent) {
      n = state.tree.nodes[n.parent];
      if (n) out.push(n.id);
    }
    return out; // nearest first
  }

  function firstClause(text) {
    const m = (text || "").match(/^[^.!?\n]{1,80}/);
    return (m ? m[0] : text || "").trim();
  }

  function updateBreadcrumb() {
    if (!state.anchorNodeId) {
      $breadcrumb.classList.remove("visible");
      return;
    }
    const ancestors = ancestorsOf(state.anchorNodeId).filter((id) => id !== state.tree.root);
    // Off-screen ancestors: none of the anchor's ancestors are currently rendered
    // (only frontier nodes are DOM nodes), so show the breadcrumb whenever there
    // is meaningful ancestry between the persistent header and the anchor, and
    // the reading column has scrolled past its start.
    const firstEl = $content.querySelector("[data-node-id]");
    const scrolledPast = firstEl && firstEl.getBoundingClientRect().top < -8;
    if (ancestors.length === 0 || !scrolledPast) {
      $breadcrumb.classList.remove("visible");
      return;
    }
    const nearest = ancestors.slice(0, 2).reverse();
    $breadcrumb.innerHTML = nearest
      .map(
        (id, i) =>
          `<button type="button" data-jump="${id}">${escapeHtml(firstClause(state.tree.nodes[id].text))}</button>` +
          (i < nearest.length - 1 ? '<span class="sep">&rsaquo;</span>' : "")
      )
      .join("");
    $breadcrumb.classList.add("visible");
  }

  $breadcrumb.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-jump]");
    if (!btn) return;
    jumpToNode(btn.dataset.jump);
  });

  el("home-btn").addEventListener("click", () => {
    setZ(0, "home");
  });

  // ---------------------------------------------------------------------
  // Dial control
  // ---------------------------------------------------------------------
  function setZ(newZ, inputType, forcedBeforeY) {
    markInput();
    state.lastDialChangeAt = Date.now();
    const clamped = Math.max(0, Math.min(1, newZ));
    const zFrom = state.z;
    if (!state.anchorNodeId) setAnchor(findCentreNodeId());

    // Record pre-expansion anchor screen position: either the y the caller
    // wants preserved (the pointer's y, for a zoom-at-pointer gesture), or
    // the anchor's own current on-screen position otherwise.
    // The invariant: the exact point in the source text under the pointer
    // (state.anchorOffset, a char offset) stays at the same screen y. A node's
    // text is treated as spread evenly over its box, so a char offset maps to
    // a y inside whichever rendered node currently contains it.
    let beforeY = forcedBeforeY;
    if (beforeY == null) {
      const anchorEl = $content.querySelector(`[data-node-id="${state.anchorNodeId}"]`);
      beforeY = anchorEl ? yOfOffset(state.anchorNodeId, anchorEl.getBoundingClientRect(), state.anchorOffset) : null;
    }

    state.z = clamped;
    const { frontier } = window.Frontier.frontierAtZ(state.tree, state.sequence, state.z);
    state.frontier = frontier;

    // The deferred whole-column crossfade is only for deliberate big jumps
    // (home, clicking the indicator). During a continuous gesture it raced
    // with the next queued step and applied steps to a stale layout.
    const GESTURES = ["zkey", "ctrlwheel", "key"];
    const bigJump = Math.abs(clamped - zFrom) > 0.15 && !GESTURES.includes(inputType);
    // Re-anchor as soon as the new content is actually in the DOM (not on a
    // *separate* rAF after render — a queued next step, e.g. mid Z-drag or
    // wheel burst, must see the corrected scroll position immediately, or
    // pointer-anchoring drifts across consecutive fast steps).
    render({
      columnCrossfade: bigJump,
      onRendered: () => {
        const offset = state.anchorOffset != null ? state.anchorOffset : 0;
        const replacement = window.Frontier.findFrontierNodeAtOffset(state.tree, state.frontier, offset);
        if (replacement) {
          // Keep anchorOffset fixed for the whole gesture; resetting it to the
          // replacement's midpoint each step made the pointed-at text drift.
          state.anchorNodeId = replacement;
          // Use the natural (pre-FLIP-transform) rect, not a live query —
          // a persisted node's live rect right now reflects its transform,
          // i.e. its *old* visual position, not where it will actually
          // rest once the transition finishes.
          const afterRect = lastRenderRects.get(replacement);
          if (afterRect && beforeY != null) {
            window.scrollBy(0, yOfOffset(replacement, afterRect, offset) - beforeY);
          }
        }
      },
    });

    updateReadout();
    savePositionDebounced();
    dismissHint();
    if (state.tree) {
      logEvent("dial", {
        tree_id: state.tree.id,
        z_from: zFrom,
        z_to: clamped,
        input: inputType || "indicator",
        anchor_node_id: state.anchorNodeId,
      });
    }
  }

  // Resolve "the passage under the pointer" (or its fallback: viewport
  // centre) into an anchor node + the y to keep it pinned at, and lock it
  // in as the current anchor (recomputing the expansion sequence once).
  // This is called exactly once per gesture — at the moment Z goes down,
  // or at the first tick of a wheel/pinch burst — never per-step, or every
  // step would re-shuffle the sequence around a slightly different anchor
  // and the frontier would jump instead of moving incrementally.
  function beginPointerGesture(px, py) {
    let x = px;
    let y = py;
    if (x == null || y == null) {
      x = lastMouse.x;
      y = lastMouse.y;
    }
    let anchorId;
    let anchorY;
    if (isPointOverContent(x, y)) {
      anchorId = nodeAtScreenPoint(x, y) || findCentreNodeId();
      anchorY = y;
    } else {
      anchorId = findCentreNodeId();
      const el2 = $content.querySelector(`[data-node-id="${anchorId}"]`);
      anchorY = window.innerHeight / 2;
    }
    if (anchorId && anchorId !== state.anchorNodeId) setAnchor(anchorId);
    // Pin the exact text position under the pointer (not the node's midpoint).
    const el = anchorId && $content.querySelector(`[data-node-id="${anchorId}"]`);
    if (el) state.anchorOffset = offsetAtY(anchorId, el.getBoundingClientRect(), anchorY);
    return anchorY;
  }

  // Char offset <-> screen y inside a rendered node, assuming its text is
  // spread evenly over the node's box (good enough at paragraph scale).
  function offsetAtY(nodeId, rect, y) {
    const [s0, s1] = state.tree.nodes[nodeId].source_span;
    const frac = rect.height > 0 ? Math.min(1, Math.max(0, (y - rect.top) / rect.height)) : 0.5;
    return s0 + frac * (s1 - s0);
  }
  function yOfOffset(nodeId, rect, offset) {
    const [s0, s1] = state.tree.nodes[nodeId].source_span;
    const frac = s1 > s0 ? Math.min(1, Math.max(0, (offset - s0) / (s1 - s0))) : 0.5;
    return rect.top + frac * rect.height;
  }

  // rAF-coalesced step queue for a single locked gesture: steps accumulate
  // here and apply at most once per animation frame (against the fixed
  // anchor + y captured by beginPointerGesture), so rendering never backs
  // up behind a fast stream of mousemove/wheel events.
  let lockedPendingSteps = 0;
  let lockedInput = null;
  let lockedY = null;
  let lockedRaf = false;
  function queueLockedSteps(n, inputType, fixedY) {
    lockedPendingSteps += n;
    lockedInput = inputType;
    lockedY = fixedY;
    if (lockedRaf) return;
    lockedRaf = true;
    requestAnimationFrame(() => {
      lockedRaf = false;
      const n2 = lockedPendingSteps;
      lockedPendingSteps = 0;
      if (n2 === 0 || !state.tree) return;
      const total = Math.max(1, state.sequence.length);
      setZ(state.z + n2 / total, lockedInput, lockedY);
    });
  }

  // A single discrete keyboard action (arrow keys, +/-): resolve the
  // pointer anchor fresh (it's one atomic step, so there's no sequence to
  // keep stable across it) and apply immediately.
  function stepOnce(deltaSteps, inputType) {
    if (!state.tree || deltaSteps === 0) return;
    const anchorY = beginPointerGesture(lastMouse.x, lastMouse.y);
    const total = Math.max(1, state.sequence.length);
    setZ(state.z + deltaSteps / total, inputType, anchorY);
  }

  // ---- Keyboard: arrow keys / Home / End on the focused dial ----
  $dial.addEventListener("keydown", (e) => {
    switch (e.key) {
      case "ArrowRight":
        e.preventDefault();
        stepOnce(e.shiftKey ? 5 : 1, "key");
        break;
      case "ArrowLeft":
        e.preventDefault();
        stepOnce(e.shiftKey ? -5 : -1, "key");
        break;
      case "Home":
        e.preventDefault();
        setZ(0, "key");
        break;
      case "End":
        e.preventDefault();
        setZ(1, "key");
        break;
    }
  });

  // ---- Keyboard: =/- as a global expand/collapse-one-step alternative ----
  document.addEventListener("keydown", (e) => {
    if (!$app.classList.contains("active")) return;
    const tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea") return;
    if (e.key === "=" || e.key === "+") {
      e.preventDefault();
      stepOnce(1, "key");
    } else if (e.key === "-" || e.key === "_") {
      e.preventDefault();
      stepOnce(-1, "key");
    }
  });

  // ---- Gesture 1: hold Z + move the mouse horizontally ----
  // The anchor locks in once, when Z goes down. ~24px per expansion step,
  // accumulated from the position when Z went down. Key auto-repeat is
  // ignored; the gesture ends on keyup or blur.
  const Z_STEP_PX = 24;
  let zHeld = false;
  let zStartX = null;
  let zAppliedSteps = 0;
  let zGestureY = null;
  function zMoveHandler(e) {
    if (!zHeld || zStartX == null) return;
    const totalDeltaX = e.clientX - zStartX;
    const targetSteps = Math.trunc(totalDeltaX / Z_STEP_PX);
    const diff = targetSteps - zAppliedSteps;
    if (diff !== 0) {
      zAppliedSteps = targetSteps;
      queueLockedSteps(diff, "zkey", zGestureY);
    }
  }
  function endZGesture() {
    if (!zHeld) return;
    zHeld = false;
    zStartX = null;
    zAppliedSteps = 0;
    zGestureY = null;
    document.body.classList.remove("zoom-drag-active");
    window.removeEventListener("mousemove", zMoveHandler);
  }
  document.addEventListener("keydown", (e) => {
    if (!$app.classList.contains("active")) return;
    if (e.key !== "z" && e.key !== "Z") return;
    if (e.repeat || zHeld) return;
    const tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea") return;
    zHeld = true;
    zStartX = lastMouse.x;
    zAppliedSteps = 0;
    zGestureY = beginPointerGesture(lastMouse.x, lastMouse.y);
    document.body.classList.add("zoom-drag-active");
    window.addEventListener("mousemove", zMoveHandler);
  });
  document.addEventListener("keyup", (e) => {
    if (e.key === "z" || e.key === "Z") endZGesture();
  });
  window.addEventListener("blur", endZGesture);

  // ---- Gesture 2: Ctrl+wheel and trackpad pinch (arrives as ctrl+wheel) ----
  // ~100 deltaY units per step for a real mouse wheel; pinch deltas are
  // typically small/fractional, so they're scaled more aggressively (a
  // comfortable pinch spans ~6 units per step) so it lands 1-3 steps. The
  // anchor locks in at the first tick of a burst and holds until ~250ms of
  // wheel inactivity, so a rapid run of ticks doesn't re-shuffle mid-burst.
  let wheelAccum = 0;
  let wheelBurstActive = false;
  let wheelGestureY = null;
  let wheelBurstTimer = null;
  window.addEventListener(
    "wheel",
    (e) => {
      if (!$app.classList.contains("active") || !e.ctrlKey) return;
      e.preventDefault();
      if (!wheelBurstActive) {
        wheelGestureY = beginPointerGesture(e.clientX, e.clientY);
        wheelBurstActive = true;
      }
      clearTimeout(wheelBurstTimer);
      wheelBurstTimer = setTimeout(() => {
        wheelBurstActive = false;
      }, 250);

      const magnitude = Math.abs(e.deltaY);
      const looksLikePinch = magnitude > 0 && (magnitude < 4 || !Number.isInteger(e.deltaY));
      const divisor = looksLikePinch ? 6 : 100;
      wheelAccum += -e.deltaY / divisor;
      const steps = Math.trunc(wheelAccum);
      if (steps !== 0) {
        wheelAccum -= steps;
        queueLockedSteps(steps, "ctrlwheel", wheelGestureY);
      }
    },
    { passive: false }
  );

  // ---- The passive indicator: click/drag still sets z directly ----
  $dial.addEventListener("click", (e) => {
    const rect = $dial.getBoundingClientRect();
    const frac = (e.clientX - rect.left) / rect.width;
    setZ(frac, "indicator");
  });

  el("home-btn").addEventListener("click", () => {
    setZ(0, "indicator");
  });

  // hold-and-drag on the readout for fine control
  (function setupReadoutDrag() {
    let dragging = false;
    let startY = 0;
    let startZ = 0;
    $dialReadout.addEventListener("mousedown", (e) => {
      dragging = true;
      startY = e.clientY;
      startZ = state.z;
      e.preventDefault();
    });
    window.addEventListener("mousemove", (e) => {
      if (!dragging) return;
      const dy = startY - e.clientY;
      setZ(startZ + dy / 400, "indicator");
    });
    window.addEventListener("mouseup", () => {
      dragging = false;
    });
  })();

  // ---------------------------------------------------------------------
  // One-time hint: shown on the very first open ever, gone after the first
  // successful zoom gesture or 8s, and never shown again.
  // ---------------------------------------------------------------------
  const HINT_KEY = "riemann:hint-seen";
  let hintTimer = null;
  function hintSeen() {
    try {
      return localStorage.getItem(HINT_KEY) === "1";
    } catch (e) {
      return true;
    }
  }
  function markHintSeen() {
    try {
      localStorage.setItem(HINT_KEY, "1");
    } catch (e) {
      /* storage unavailable; nothing to persist */
    }
  }
  function maybeShowHint() {
    if (!$zoomHint || hintSeen()) return;
    markHintSeen(); // mark now so it can never show twice, even if interrupted
    $zoomHint.hidden = false;
    requestAnimationFrame(() => $zoomHint.classList.add("visible"));
    hintTimer = setTimeout(dismissHint, 8000);
  }
  function dismissHint() {
    if (!$zoomHint || $zoomHint.hidden) return;
    clearTimeout(hintTimer);
    hintTimer = null;
    $zoomHint.classList.remove("visible");
    $zoomHint.hidden = true;
  }

  // ---------------------------------------------------------------------
  // Minimal chrome toggle
  // ---------------------------------------------------------------------
  function toggleMinimalChrome() {
    state.minimalChrome = !state.minimalChrome;
    document.body.classList.toggle("minimal-chrome", state.minimalChrome);
  }
  el("minimal-toggle").addEventListener("click", toggleMinimalChrome);
  document.addEventListener("keydown", (e) => {
    if (e.key === "m" && !e.metaKey && !e.ctrlKey && !e.altKey) {
      const tag = (e.target.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea") return;
      toggleMinimalChrome();
    }
  });

  // ---------------------------------------------------------------------
  // Source hover popover + click-to-jump
  // ---------------------------------------------------------------------
  function firstNSentences(text, n) {
    const parts = (text || "").match(/[^.!?]+[.!?]?/g) || [text];
    return parts.slice(0, n).join(" ").trim();
  }

  let popoverTimer = null;
  $content.addEventListener("mouseover", (e) => {
    const hint = e.target.closest(".source-hint");
    if (!hint) return;
    const nodeEl = hint.closest("[data-node-id]");
    const node = state.tree.nodes[nodeEl.dataset.nodeId];
    if (!node || !node.cites || node.cites.length === 0) return;
    clearTimeout(popoverTimer);
    popoverTimer = setTimeout(() => showPopover(hint, node), 250);
    logEvent("hover_source", { tree_id: state.tree.id, node_id: node.id });
  });
  $content.addEventListener("mouseout", (e) => {
    if (e.target.closest(".source-hint")) {
      clearTimeout(popoverTimer);
      $popover.classList.remove("visible");
    }
  });

  function showPopover(anchorEl, node) {
    const leafId = node.cites[0];
    const leaf = state.tree.nodes[leafId];
    if (!leaf) return;
    const excerpt = firstNSentences(leaf.text, 2);
    $popover.innerHTML = `${escapeHtml(excerpt)}<span class="popover-hint">click to jump to source</span>`;
    const rect = anchorEl.getBoundingClientRect();
    $popover.style.left = `${Math.max(8, rect.left)}px`;
    $popover.style.top = `${rect.bottom + window.scrollY + 6}px`;
    $popover.classList.add("visible");
    $popover.dataset.leafId = leafId;
  }

  $content.addEventListener("click", (e) => {
    const hint = e.target.closest(".source-hint");
    if (!hint) return;
    const nodeEl = hint.closest("[data-node-id]");
    const node = state.tree.nodes[nodeEl.dataset.nodeId];
    if (!node || !node.cites || node.cites.length === 0) return;
    jumpToLeaf(node.cites[0]);
  });

  function jumpToLeaf(leafId) {
    logEvent("jump_source", { tree_id: state.tree.id, leaf_id: leafId });
    jumpToNode(leafId);
  }

  function jumpToNode(nodeId) {
    // Expand along the path to nodeId, then anchor on it.
    setAnchor(nodeId);
    const path = [];
    let n = state.tree.nodes[nodeId];
    while (n && n.parent) {
      path.push(n.parent);
      n = state.tree.nodes[n.parent];
    }
    // k must be large enough that every ancestor in `path` is expanded.
    let neededK = 0;
    path.forEach((id) => {
      const idx = state.sequence.indexOf(id);
      if (idx >= 0) neededK = Math.max(neededK, idx + 1);
    });
    const idxSelf = state.sequence.indexOf(nodeId);
    if (idxSelf >= 0) neededK = Math.max(neededK, 0); // node itself need not expand
    const total = Math.max(1, state.sequence.length);
    setZ(neededK / total, "key");
    $popover.classList.remove("visible");
  }

  // ---------------------------------------------------------------------
  // Not helpful link
  // ---------------------------------------------------------------------
  el("not-helpful").addEventListener("click", () => {
    if (!state.tree) return;
    logEvent("not_helpful", { tree_id: state.tree.id, z: state.z });
    flushEvents(false);
    el("not-helpful").textContent = "noted";
    setTimeout(() => (el("not-helpful").textContent = "not helpful"), 2000);
  });

  // ---------------------------------------------------------------------
  // Tree loading
  // ---------------------------------------------------------------------
  function initialZForTree(tree) {
    // Open near a ~2-minute frontier (or 1.0 if whole source is <=2 min).
    const totalMinutes = tree.source_words / WPM;
    if (totalMinutes <= 2) return 1.0;
    const sequence = window.Frontier.buildExpansionSequence(tree, tree.root);
    const total = Math.max(1, sequence.length);
    let bestK = 0;
    let bestDiff = Infinity;
    for (let k = 0; k <= sequence.length; k++) {
      const frontier = window.Frontier.frontierAtK(tree, sequence, k);
      const words = frontierWords(tree, frontier);
      const minutes = words / WPM;
      const diff = Math.abs(minutes - 2);
      if (diff < bestDiff) {
        bestDiff = diff;
        bestK = k;
      }
    }
    return bestK / total;
  }

  function openTree(tree, opts) {
    opts = opts || {};
    state.tree = tree;
    $startScreen.style.display = "none";
    $app.classList.add("active");

    const saved = !opts.forceFresh ? loadPosition(tree.id) : null;
    const anchorId = (saved && saved.anchor_node_id && tree.nodes[saved.anchor_node_id]) ? saved.anchor_node_id : tree.root;
    state.sequence = window.Frontier.buildExpansionSequence(tree, anchorId);
    state.anchorNodeId = anchorId;
    state.anchorOffset = saved ? saved.anchor_offset : null;

    const z = saved ? saved.z : initialZForTree(tree);
    state.z = 0; // force setZ to do real work below
    const { frontier } = window.Frontier.frontierAtZ(tree, state.sequence, z);
    state.frontier = frontier;
    state.z = z;
    render({});
    updateReadout();

    logEvent("open", { tree_id: tree.id, resumed: !!saved });
    flushEvents(false);

    if (saved) showResumeCard(anchorId);
    maybeShowHint();

    window.addEventListener(
      "scroll",
      debounce(() => {
        // Programmatic scrollBy calls from a dial-driven re-anchor (setZ)
        // also fire native 'scroll' events; picking up viewport-centre here
        // right after one would fight the pointer-anchored gesture that
        // caused the scroll. Skip while that's recent.
        if (Date.now() - state.lastDialChangeAt < 400) return;
        const centreId = findCentreNodeId();
        if (centreId && centreId !== state.anchorNodeId) setAnchor(centreId);
        updateReadout();
      }, 150)
    );
  }

  function showResumeCard(anchorId) {
    const node = state.tree.nodes[anchorId];
    $resumeCardText.textContent = `Back where you left off: ${firstClause(node ? node.text : "")}`;
    $resumeCard.classList.add("visible");
    const timer = setTimeout(() => $resumeCard.classList.remove("visible"), 4000);
    el("resume-card-dismiss").onclick = () => {
      clearTimeout(timer);
      $resumeCard.classList.remove("visible");
    };
  }

  function subscribeEvents(treeId) {
    if (state.eventSource) state.eventSource.close();
    const es = new EventSource(`/api/tree/${treeId}/events`);
    state.eventSource = es;
    const applyNodes = (data) => {
      if (!data || !data.nodes) return;
      Object.assign(state.tree.nodes, data.nodes);
    };
    es.addEventListener("leaves", (e) => applyNodes(JSON.parse(e.data)));
    es.addEventListener("provisional_root", (e) => {
      applyNodes(JSON.parse(e.data));
      state.tree.provisional_root = true;
      updateRootHeader();
    });
    es.addEventListener("level", (e) => {
      applyNodes(JSON.parse(e.data));
      state.sequence = window.Frontier.buildExpansionSequence(state.tree, state.anchorNodeId || state.tree.root);
    });
    es.addEventListener("done", (e) => {
      const data = JSON.parse(e.data);
      if (data.nodes) Object.assign(state.tree.nodes, data.nodes);
      state.tree.status = "done";
      state.tree.provisional_root = false;
      state.sequence = window.Frontier.buildExpansionSequence(state.tree, state.anchorNodeId || state.tree.root);
      const { frontier } = window.Frontier.frontierAtZ(state.tree, state.sequence, state.z);
      state.frontier = frontier;
      render({});
      updateReadout();
      es.close();
    });
    es.addEventListener("error", () => {
      es.close();
    });
  }

  // ---------------------------------------------------------------------
  // Start screen wiring
  // ---------------------------------------------------------------------
  function showStartError(msg) {
    const $err = el("paste-error");
    $err.textContent = msg;
    $err.hidden = false;
  }

  async function submitAbstract(body, isMultipart) {
    try {
      const resp = await fetch("/api/abstract", isMultipart ? { method: "POST", body } : {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!resp.ok) throw new Error("request failed");
      const data = await resp.json();
      const treeResp = await fetch(`/api/tree/${data.tree_id}`);
      const tree = await treeResp.json();
      openTree(tree, { forceFresh: true });
      subscribeEvents(data.tree_id);
    } catch (err) {
      showStartError("Could not build that. Try again.");
    }
  }

  el("paste-submit").addEventListener("click", () => {
    const text = el("paste-text").value.trim();
    if (!text) return showStartError("Paste some text first.");
    submitAbstract({ text });
  });

  el("url-submit").addEventListener("click", () => {
    const url = el("url-input").value.trim();
    if (!url) return showStartError("Enter a URL first.");
    submitAbstract({ url });
  });

  el("file-input").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    submitAbstract(form, true);
  });

  async function loadRecent() {
    if (IS_FIXTURE) return;
    try {
      const resp = await fetch("/api/recent");
      if (!resp.ok) return;
      const items = await resp.json();
      if (!items || items.length === 0) return;
      const $list = el("recent-list");
      $list.innerHTML = items
        .map((it) => `<li><a href="#" data-tree-id="${it.id}">${escapeHtml(it.title)}</a></li>`)
        .join("");
      el("recent-block").hidden = false;
      $list.addEventListener("click", async (e) => {
        const a = e.target.closest("[data-tree-id]");
        if (!a) return;
        e.preventDefault();
        const resp2 = await fetch(`/api/tree/${a.dataset.treeId}`);
        const tree = await resp2.json();
        openTree(tree);
        if (tree.status !== "done") subscribeEvents(tree.id);
      });
    } catch (e) {
      /* ignore */
    }
  }

  // ---------------------------------------------------------------------
  // Boot
  // ---------------------------------------------------------------------
  async function boot() {
    if (IS_FIXTURE) {
      const resp = await fetch("dev-fixture.json");
      const tree = await resp.json();
      openTree(tree);
      return;
    }
    loadRecent();
  }

  boot();
})();
