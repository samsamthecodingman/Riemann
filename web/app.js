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
        requestAnimationFrame(() => {
          $content.style.opacity = "1";
          setTimeout(() => $content.classList.remove("column-crossfade"), 200);
        });
      }, 180);
      return;
    }

    doRender();

    function doRender() {
      $content.innerHTML = state.frontier.map((id) => renderNodeHTML(tree.nodes[id])).join("");
      updateRootHeader();
      updateBreadcrumb();

      if (REDUCED_MOTION) return;

      // FLIP for persisted nodes; fade for new ones.
      for (const elNode of $content.querySelectorAll("[data-node-id]")) {
        const id = elNode.dataset.nodeId;
        if (prevRects.has(id)) {
          const oldRect = prevRects.get(id);
          const newRect = elNode.getBoundingClientRect();
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
  function setZ(newZ, inputType) {
    markInput();
    const clamped = Math.max(0, Math.min(1, newZ));
    const zFrom = state.z;
    if (!state.anchorNodeId) setAnchor(findCentreNodeId());

    // Record pre-expansion anchor screen position.
    const anchorEl = $content.querySelector(`[data-node-id="${state.anchorNodeId}"]`);
    const beforeY = anchorEl ? anchorEl.getBoundingClientRect().top : null;

    state.z = clamped;
    const { frontier } = window.Frontier.frontierAtZ(state.tree, state.sequence, state.z);
    state.frontier = frontier;

    const bigJump = Math.abs(clamped - zFrom) > 0.15;
    render({ columnCrossfade: bigJump });

    // Re-anchor: find replacement for the old anchor and restore its screen y.
    requestAnimationFrame(() => {
      const offset = state.anchorOffset != null ? state.anchorOffset : 0;
      const replacement = window.Frontier.findFrontierNodeAtOffset(state.tree, state.frontier, offset);
      if (replacement) {
        state.anchorNodeId = replacement;
        const n = state.tree.nodes[replacement];
        state.anchorOffset = (n.source_span[0] + n.source_span[1]) / 2;
        const repEl = $content.querySelector(`[data-node-id="${replacement}"]`);
        if (repEl && beforeY != null) {
          const afterY = repEl.getBoundingClientRect().top;
          window.scrollBy(0, afterY - beforeY);
        }
      }
    });

    updateReadout();
    savePositionDebounced();
    if (state.tree) logEvent("dial", { tree_id: state.tree.id, z_from: zFrom, z_to: clamped, input: inputType || "slider" });
  }

  function stepZ(deltaExpansions, inputType) {
    const total = Math.max(1, state.sequence.length);
    setZ(state.z + deltaExpansions / total, inputType);
  }

  $dial.addEventListener("keydown", (e) => {
    switch (e.key) {
      case "ArrowRight":
        e.preventDefault();
        if (e.shiftKey) setZ(state.z + 0.1, "key");
        else stepZ(1, "key");
        break;
      case "ArrowLeft":
        e.preventDefault();
        if (e.shiftKey) setZ(state.z - 0.1, "key");
        else stepZ(-1, "key");
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

  $dial.addEventListener(
    "wheel",
    (e) => {
      if (!e.ctrlKey) return;
      e.preventDefault();
      const total = Math.max(1, state.sequence.length);
      setZ(state.z - Math.sign(e.deltaY) / total, "wheel");
    },
    { passive: false }
  );

  $dial.addEventListener("click", (e) => {
    const rect = $dial.getBoundingClientRect();
    const frac = (e.clientX - rect.left) / rect.width;
    setZ(frac, "slider");
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
      setZ(startZ + dy / 400, "slider");
    });
    window.addEventListener("mouseup", () => {
      dragging = false;
    });
  })();

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

    window.addEventListener("scroll", debounce(() => {
      const centreId = findCentreNodeId();
      if (centreId && centreId !== state.anchorNodeId) setAnchor(centreId);
      updateReadout();
    }, 150));
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
