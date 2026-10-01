// Browser checks for tests/e2e. Usage: node runner.js <playwright dir> <base url> <tree id> <check> [args]
// Prints one JSON line: {ok: true|false, ...details}. Each check gets a fresh browser context.
const [pwDir, BASE, TREE, CHECK, ...ARGS] = process.argv.slice(2);
const { chromium } = require(pwDir);
const fs = require("fs");
const path = require("path");

// Build one of tests/fixtures/*.md on the (fake) server and wait until it is done.
async function buildFixture(name) {
  const text = fs.readFileSync(path.join(__dirname, "..", "fixtures", name + ".md"), "utf8");
  return buildText(text);
}
async function buildText(text, extra = {}) {
  const r = await fetch(BASE + "/api/abstract", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text, ...extra }) });
  const { tree_id } = await r.json();
  for (let i = 0; i < 100; i++) {
    const t = await (await fetch(`${BASE}/api/tree/${tree_id}`)).json();
    if (t.status === "done") return tree_id;
    await new Promise((res) => setTimeout(res, 100));
  }
  throw new Error("build did not finish");
}

const words = (page) =>
  page.evaluate(() =>
    [...document.querySelectorAll("#content [data-node-id]")]
      .map((n) => n.innerText.trim().split(/\s+/).filter(Boolean).length)
      .reduce((a, b) => a + b, 0)
  );

async function openReader(page, id = TREE) {
  await page.goto(`${BASE}/#/t/${id}`);
  await page.waitForSelector("#content .node, .root-hero", { timeout: 15000 });
  await page.waitForTimeout(500);
}

const overflow = (page) => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

function watch(page) {
  const errors = [];
  page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push("console: " + m.text());
  });
  return errors;
}

// Characters on the first rendered line of the longest source paragraph on screen.
const firstLineChars = (page) =>
  page.evaluate(() => {
    const ps = [...document.querySelectorAll("#content .node.leaf .node-body p")].filter((p) => p.textContent.length > 200);
    const p = ps[0];
    if (!p) return null;
    const tn = document.createTreeWalker(p, NodeFilter.SHOW_TEXT).nextNode();
    const r = document.createRange();
    r.setStart(tn, 0);
    let top = null;
    for (let i = 1; i <= tn.length; i++) {
      r.setEnd(tn, i);
      const rects = r.getClientRects();
      const t = rects[rects.length - 1].top;
      if (top == null) top = t;
      if (Math.abs(t - top) > 4) return { chars: i - 1, width: Math.round(p.getBoundingClientRect().width) };
    }
    return null;
  });

async function deepZoom(page) {
  for (let i = 0; i < 30; i++) {
    await page.keyboard.press("=");
    await page.waitForTimeout(60);
  }
  await page.waitForTimeout(400);
}

// A document long enough to open collapsed, with a distinctive word in every leaf.
function longDoc() {
  let out = "# Harbour survey\n\n";
  for (let s = 1; s <= 6; s++) {
    out += `## Section ${s}\n\n`;
    for (let p = 1; p <= 6; p++) {
      out += `Paragraph ${p} of section ${s} mentions marker${s}x${p} and then ` + "the tide moved sand along the northern beach while the survey team measured it. ".repeat(7) + "\n\n";
    }
  }
  return out;
}

const DATA = process.env.RIEMANN_E2E_DATA; // the server's scratch data folder (set by conftest.py)

const checks = {
  async zoom_grows_words(page) {
    await openReader(page);
    const seq = [await words(page)];
    for (let i = 0; i < 12; i++) {
      await page.keyboard.press("=");
      await page.waitForTimeout(350);
      seq.push(await words(page));
    }
    const grew = seq.every((w, i) => i === 0 || w >= seq[i - 1]);
    return { ok: grew && seq[seq.length - 1] > seq[0] * 1.5, seq };
  },

  async pin_drift_under_2px(page) {
    await openReader(page);
    for (let i = 0; i < 3; i++) {
      await page.keyboard.press("=");
      await page.waitForTimeout(300);
    }
    await page.mouse.wheel(0, 900);
    await page.waitForTimeout(400);
    await page.mouse.move(600, 400);
    await page.keyboard.down("z");
    await page.waitForTimeout(300);
    const pin = () =>
      page.evaluate(() => {
        const n = document.querySelector("#content .node.pinned");
        return n ? n.getBoundingClientRect().top : null;
      });
    const tops = [await pin()];
    for (let s = 1; s <= 5; s++) {
      await page.mouse.move(600 + s * 26, 400);
      await page.waitForTimeout(250);
      tops.push(await pin());
    }
    for (let s = 4; s >= -2; s--) {
      await page.mouse.move(600 + s * 26, 400);
      await page.waitForTimeout(250);
      tops.push(await pin());
    }
    await page.keyboard.up("z");
    const seen = tops.filter((t) => t != null);
    const drift = seen.length ? Math.max(...seen) - Math.min(...seen) : null;
    return { ok: seen.length >= 5 && drift < 2, drift, samples: seen.length };
  },

  async map_toggle_and_jump(page) {
    await openReader(page);
    for (let i = 0; i < 4; i++) {
      await page.keyboard.press("=");
      await page.waitForTimeout(250);
    }
    await page.keyboard.press("g");
    await page.waitForTimeout(700);
    const open = await page.evaluate(() => ({ shown: !document.querySelector("#map-panel").hidden, tiles: document.querySelectorAll(".map-tile").length }));
    const y0 = await page.evaluate(() => scrollY);
    const tile = await page.evaluate(() => {
      const ts = [...document.querySelectorAll(".map-tile")].filter((t) => t.dataset.nodeId);
      const t = ts[Math.floor(ts.length * 0.8)];
      const r = t.getBoundingClientRect();
      return { id: t.dataset.nodeId, x: r.left + r.width / 2, y: r.top + Math.min(r.height / 2, 20) };
    });
    await page.mouse.click(tile.x, tile.y);
    await page.waitForTimeout(1200);
    const y1 = await page.evaluate(() => scrollY);
    await page.keyboard.press("g");
    await page.waitForTimeout(400);
    const closed = await page.evaluate(() => document.querySelector("#map-panel").hidden);
    return { ok: open.shown && open.tiles > 0 && y1 > y0 + 200 && closed, open, y0, y1, closed };
  },

  async columns_drag_persists(page) {
    await openReader(page);
    const width = () => page.evaluate(() => Math.round(document.querySelector("#section-nav").getBoundingClientRect().width));
    const w0 = await width();
    const h = await (await page.$("#col-handle-left")).boundingBox();
    await page.mouse.move(h.x + h.width / 2, h.y + 200);
    await page.mouse.down();
    await page.mouse.move(h.x + h.width / 2 + 60, h.y + 200, { steps: 5 });
    await page.mouse.up();
    await page.waitForTimeout(300);
    const w1 = await width();
    await page.reload();
    await page.waitForSelector("#content .node, .root-hero");
    await page.waitForTimeout(600);
    const w2 = await width();
    return { ok: w1 > w0 + 40 && Math.abs(w2 - w1) <= 1, w0, w1, w2 };
  },

  async palette_and_highlight_persist(page) {
    await openReader(page);
    for (let i = 0; i < 6; i++) {
      await page.keyboard.press("=");
      await page.waitForTimeout(200);
    }
    await page.click("#palette-btn");
    await page.click('[data-preset="Garden"]');
    await page.keyboard.press("Escape");
    await page.mouse.wheel(0, 600);
    await page.waitForTimeout(400);
    const t = await page.evaluate(() => {
      const e = [...document.querySelectorAll("#content .node-body")].find((e) => {
        const r = e.getBoundingClientRect();
        return r.top > 120 && r.top < 600 && e.innerText.length > 100;
      });
      const r = e.getBoundingClientRect();
      return { x: r.left + 20, y: r.top + 12 };
    });
    await page.mouse.move(t.x, t.y + 6);
    await page.mouse.down();
    await page.mouse.move(t.x + 200, t.y + 6, { steps: 5 });
    await page.mouse.up();
    await page.waitForTimeout(300);
    await page.click("#highlight-toolbar .hl-swatch >> nth=0");
    await page.waitForTimeout(300);
    const marks0 = await page.evaluate(() => document.querySelectorAll("mark").length);
    await page.reload();
    await page.waitForSelector("#content .node, .root-hero");
    await page.waitForTimeout(800);
    const after = await page.evaluate(() => ({
      marks: document.querySelectorAll("mark").length,
      preset: JSON.parse(localStorage.getItem("riemann:palette")).preset,
      sec1: getComputedStyle(document.documentElement).getPropertyValue("--sec-1").trim().toUpperCase(),
    }));
    return { ok: marks0 >= 1 && after.marks >= 1 && after.preset === "Garden" && after.sec1 === "#E1ECCB", marks0, after };
  },

  async poisoned_localstorage_is_harmless(page) {
    await page.goto(BASE + "/");
    await page.evaluate((id) => {
      localStorage.setItem(
        "riemann:palette",
        JSON.stringify({ sections: ['red"><img src=x onerror="window.__pwn=1">', "#F6D5D1", "#D5E6CF", "#F7E8B5", "#D3E4F2"], hl: "#F9D3E3;x", preset: "<b onmouseover=window.__pwn=1>x</b>" })
      );
      localStorage.setItem("riemann:hl:" + id, JSON.stringify([{ id: 'x"><img src=x onerror=window.__pwn=1>', nodeId: "n1", start: "a", end: null, colour: 'red"><img src=x onerror=window.__pwn=1>' }]));
      localStorage.setItem("riemann:pos:" + id, JSON.stringify({ anchor_node_id: "<img>", z: "NaN", anchor_offset: {} }));
      localStorage.setItem("riemann:cols", '{"open":"x","closed":{"left":"<b>","rail":1e999}}');
      localStorage.setItem("riemann:checkin", '{"ts":"x","capacity":{"a":1}}');
      localStorage.setItem("riemann:reading", '{"spacing":"<b>yes","width":"constructor"}');
      localStorage.setItem("riemann:experiment", '{"condition":"Z","phase":"<img src=x onerror=window.__pwn=1>","doc_label":"<b onmouseover=window.__pwn=1>x"}');
    }, TREE);
    await openReader(page);
    await page.reload();
    await page.waitForSelector("#content .node, .root-hero");
    await page.waitForTimeout(600);
    await page.click("#palette-btn");
    await page.waitForTimeout(300);
    const r = await page.evaluate(() => ({
      pwn: window.__pwn || 0,
      imgs: document.querySelectorAll("img").length,
      nodes: document.querySelectorAll("#content [data-node-id]").length,
      hero: !!document.querySelector(".root-hero"),
      readEm: getComputedStyle(document.documentElement).getPropertyValue("--read-em").trim(),
      readLs: getComputedStyle(document.documentElement).getPropertyValue("--reading-ls").trim(),
      spacingOn: document.querySelector("#ls-toggle").getAttribute("aria-pressed"),
      expState: document.querySelector("#experiment-state").textContent,
    }));
    return { ok: r.pwn === 0 && r.imgs === 0 && (r.nodes > 0 || r.hero) && r.readEm === "40" && r.readLs === "0" && r.spacingOn === "false" && r.expState === "off", ...r };
  },

  async xss_payload_in_tree_text_is_escaped(page) {
    const P = '<img src=x onerror="window.__pwn=(window.__pwn||0)+1">';
    const text = `# ${P}\n\n` + Array.from({ length: 6 }, (_, i) => `## ${P} ${i}\n\n${P} ` + "Some ordinary words to fill the paragraph out. ".repeat(20)).join("\n\n");
    const r = await fetch(BASE + "/api/abstract", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text }) });
    const { tree_id } = await r.json();
    await openReader(page, tree_id);
    for (let i = 0; i < 6; i++) {
      await page.keyboard.press("=");
      await page.waitForTimeout(200);
    }
    await page.keyboard.press("g");
    await page.waitForTimeout(500);
    await page.goto(BASE + "/");
    await page.waitForTimeout(500);
    const res = await page.evaluate(() => ({ pwn: window.__pwn || 0, imgs: document.querySelectorAll("img").length }));
    return { ok: res.pwn === 0 && res.imgs === 0, ...res };
  },

  async overview_card_renders(page) {
    await openReader(page);
    const r = await page.evaluate(() => {
      const c = document.querySelector(".overview-card");
      const items = [...document.querySelectorAll(".ov-item")];
      return {
        card: !!c,
        title: c && c.querySelector(".ov-title").innerText,
        kind: c && c.querySelector(".ov-kind").innerText,
        essentials: items.length,
        labelled: items.every((i) => i.querySelector("dt span") && i.querySelector("dd").innerText.trim()),
        clamped: items.some((i) => getComputedStyle(i.querySelector("dd > span")).webkitLineClamp !== "none"),
      };
    });
    return { ok: r.card && r.essentials >= 3 && r.labelled && !r.clamped, ...r };
  },

  async cjk_word_count_agrees_with_server(page) {
    await page.goto(BASE + "/");
    // 11 Han characters + 2 Kana + 3 spaced words + CJK punctuation: 16 words by the server's rule.
    const text = "今天天氣很好我們去公園。ひら 3 words here";
    await page.fill("#paste-text", text);
    await page.waitForTimeout(200);
    const shown = await page.innerText("#paste-count");
    const py = await page.evaluate((t) => window.Frontier.countWords(t), text);
    return { ok: py === 16 && /^16 words/.test(shown), shown, py };
  },

  async columns_switch_to_one_when_lines_get_short(page) {
    const out = {};
    let ok = true;
    for (const w of [1366, 1600, 1920]) {
      await page.setViewportSize({ width: w, height: 900 });
      await openReader(page);
      await deepZoom(page);
      await page.evaluate(() => document.fonts.ready);
      await page.waitForTimeout(300);
      const info = await page.evaluate(() => ({ workSans: document.fonts.check('17px "Work Sans"') && [...document.fonts].some((f) => f.family.includes("Work Sans") && f.status === "loaded"), cols: document.querySelector("#content").dataset.cols, est: +document.querySelector("#content").dataset.cpl, grid: getComputedStyle(document.querySelector(".section-grid")).gridTemplateColumns.split(" ").length }));
      const m = await firstLineChars(page);
      out[w] = { ...info, measured: m && m.chars, colWidth: m && m.width };
      // never two columns under ~45 characters, and never one column where two would have fit
      if (info.cols === "2" && !(m && m.chars >= 45)) ok = false;
      if (info.grid !== (info.cols === "2" ? 2 : 1)) ok = false;
    }
    if (out[1366].cols !== "1") ok = false;
    if (out[1920].cols !== "2") ok = false;
    return { ok, out };
  },

  async doit_tiles_start_due_size_and_relative_days(page) {
    const id = await buildFixture("assignment_brief");
    const tiles = () =>
      page.evaluate(() => {
        const items = [...document.querySelectorAll(".overview-card .ov-item")];
        const card = document.querySelector(".overview-card").getBoundingClientRect();
        return {
          classes: items.map((i) => i.className.replace(/ov-item\s*/, "").trim()),
          labels: items.map((i) => i.querySelector("dt span").innerText.trim().toLowerCase()),
          due: (document.querySelector(".ov-due dd") || {}).innerText,
          start: (document.querySelector(".ov-start dd") || {}).innerText,
          size: (document.querySelector(".ov-size dd") || {}).innerText,
          startLinks: document.querySelectorAll(".ov-start .source-link").length,
          clamped: items.some((i) => getComputedStyle(i.querySelector("dd > span")).webkitLineClamp !== "none"),
          clipped: items.some((i) => i.querySelector("dd").scrollWidth > i.querySelector("dd").clientWidth + 1 || i.scrollHeight > i.clientHeight + 1),
          cardRight: Math.round(card.right),
          tilesRight: Math.max(...items.map((i) => Math.round(i.getBoundingClientRect().right))),
          overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        };
      });
    const at = async (iso) => {
      await page.goto("about:blank");
      await page.clock.setFixedTime(new Date(iso));
      await openReader(page, id);
      return tiles();
    };
    const five = await at("2025-11-09T12:00:00");
    const today = await at("2025-11-14T08:00:00");
    const tomorrow = await at("2025-11-13T23:30:00");
    const late = await at("2025-11-16T09:00:00");
    const order = five.labels.slice(0, 3).join(",") === "start here,due,size of the job";
    const ok =
      order &&
      /Due in 5 days\s*·\s*Fri 14 Nov, 5 pm/.test(five.due) &&
      /^Due today/.test(today.due) &&
      /^Due tomorrow/.test(tomorrow.due) &&
      /Overdue by 2 days/.test(late.due) &&
      five.startLinks === 1 && /sessions/.test(five.size) &&
      !five.clamped && !five.clipped && five.overflow <= 0 && five.tilesRight <= five.cardRight;
    return { ok, order, five, today: today.due, tomorrow: tomorrow.due, late: late.due };
  },

  async meeting_actions_list_with_relative_days(page) {
    const id = await buildFixture("meeting");
    await page.clock.setFixedTime(new Date("2025-10-13T10:00:00"));
    await openReader(page, id);
    const r = await page.evaluate(() => {
      const rows = [...document.querySelectorAll(".ov-action")];
      return {
        head: (document.querySelector(".ov-actions-head") || {}).innerText,
        who: rows.map((r) => r.querySelector(".act-who").innerText),
        due: rows.map((r) => (r.querySelector(".act-due") || {}).innerText || null),
        links: rows.map((r) => r.querySelectorAll(".source-link").length),
        overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        rowOverflow: rows.some((r) => r.scrollWidth > r.clientWidth + 1),
      };
    });
    // earliest first, undated last; the first is Aisha, due Wed 15 Oct = in 2 days from Mon 13 Oct
    const ok =
      /^actions$/i.test(r.head) && r.who.length === 5 && r.who[0] === "Aisha Rahman" &&
      /Due in 2 days/.test(r.due[0]) && /Due in 3 days/.test(r.due[1]) && r.due[4] === null &&
      r.links.every((n) => n === 1) && r.overflow <= 0 && !r.rowOverflow;
    return { ok, ...r };
  },

  async search_whole_document_and_navigate(page) {
    const id = await buildText(longDoc());
    const posted = [];
    page.on("request", (r) => { if (r.url().endsWith("/api/events") && r.method() === "POST") posted.push(r.postData() || ""); });
    await openReader(page, id);
    const before = await page.evaluate(() => document.querySelectorAll("#content .node.leaf").length);
    await page.keyboard.press("/");
    const open = await page.evaluate(() => ({ shown: !document.querySelector("#search-bar").hidden, focused: document.activeElement && document.activeElement.id, label: document.querySelector('label[for="search-input"]').textContent }));
    await page.keyboard.type("marker4x5");
    await page.waitForTimeout(1500);
    const hit = await page.evaluate(() => {
      const c = document.querySelector(".search-current");
      const r = c && c.getBoundingClientRect();
      return {
        count: document.querySelector("#search-count").textContent,
        live: document.querySelector("#search-count").getAttribute("aria-live"),
        text: c && c.textContent,
        inLeaf: !!(c && c.closest(".node.leaf")),
        inView: !!r && r.top >= 0 && r.bottom <= innerHeight,
        marks: document.querySelectorAll(".search-hit").length,
      };
    });
    // a word that only occurs deep in the source opens just enough: some leaf is now on the page
    const after = await page.evaluate(() => document.querySelectorAll("#content .node.leaf").length);
    // next / previous wrap around the single match; a second query finds many
    await page.fill("#search-input", "survey team");
    await page.waitForTimeout(500);
    const many = await page.evaluate(() => document.querySelector("#search-count").textContent);
    const total = +(/of (\d+)/.exec(many) || [])[1];
    await page.keyboard.press("Enter");
    await page.waitForTimeout(300);
    const second = await page.evaluate(() => document.querySelector("#search-count").textContent);
    await page.keyboard.press("Shift+Enter");
    await page.keyboard.press("Shift+Enter");
    await page.waitForTimeout(300);
    const wrapped = await page.evaluate(() => document.querySelector("#search-count").textContent);
    await page.keyboard.press("Escape");
    await page.waitForTimeout(200);
    const closed = await page.evaluate(() => ({ hidden: document.querySelector("#search-bar").hidden, marks: document.querySelectorAll(".search-hit").length, value: document.querySelector("#search-input").value }));
    // Ctrl+F: opens ours; pressed again inside the box it is left to the browser
    await page.keyboard.press("Control+f");
    const ours = await page.evaluate(() => !document.querySelector("#search-bar").hidden);
    await page.evaluate(() => { window.__dp = []; document.addEventListener("keydown", (e) => { if ((e.ctrlKey || e.metaKey) && e.key === "f") window.__dp.push(e.defaultPrevented); }); });
    await page.keyboard.press("Control+f");
    const dp = await page.evaluate(() => window.__dp);
    await page.keyboard.press("Escape");
    await page.evaluate(() => fetch("/api/events", { method: "POST", headers: { "content-type": "application/json" }, body: "[]" }));
    await page.waitForTimeout(5600);
    const body = posted.join("\n");
    const searchEv = (body.match(/"type":"search"[^}]*/g) || []);
    const ok =
      open.shown && open.focused === "search-input" && /search/i.test(open.label) &&
      hit.count === "1 of 1" && hit.live === "polite" && /marker4x5/.test(hit.text) && hit.inLeaf && hit.inView &&
      after > before && total > 3 && second === `2 of ${total}` && wrapped === `${total} of ${total}` &&
      closed.hidden && closed.marks === 0 && closed.value === "" &&
      ours && dp.length === 1 && dp[0] === false &&
      searchEv.length >= 2 && searchEv.every((e) => /"query_length":\d+/.test(e)) && !/marker4x5|survey team/.test(body);
    return { ok, open, hit, before, after, many, second, wrapped, closed, ours, dp, searchEv };
  },

  async search_at_every_depth_never_errors_and_finds_summaries(page) {
    const id = await buildText(longDoc());
    await openReader(page, id);
    await deepZoom(page);
    await page.keyboard.press("/");
    await page.keyboard.type("moved sand");
    await page.waitForTimeout(500);
    const n = await page.evaluate(() => document.querySelector("#search-count").textContent);
    const seen = new Set();
    for (let i = 0; i < 12; i++) {
      await page.keyboard.press("Enter");
      await page.waitForTimeout(150);
      seen.add(await page.evaluate(() => document.querySelector("#search-count").textContent));
    }
    const state = await page.evaluate(() => ({ overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth, cur: !!document.querySelector(".search-current") }));
    return { ok: /of \d+/.test(n) && seen.size === 12 && state.overflow <= 0, n, seen: seen.size, state };
  },

  async zoom_history_alt_arrows_restore_level_and_position(page) {
    const id = await buildText(longDoc());
    await openReader(page, id);
    const snap = () =>
      page.evaluate(() => ({
        page: [...document.querySelectorAll("#content [data-node-id]")].map((n) => n.dataset.nodeId + ":" + n.dataset.form).join(","),
        y: Math.round(scrollY),
        back: !document.querySelector("#hist-back").hidden,
        hash: location.hash,
      }));
    const s0 = await snap();
    for (let i = 0; i < 6; i++) {
      await page.keyboard.press("=");
      await page.waitForTimeout(120);
    }
    await page.waitForTimeout(1300);
    const s1 = await snap(); // six steps in one gesture: one entry, and a big jump (>= 3 steps)
    const backShown = s1.back;
    await page.click(".nav-item >> nth=3");
    await page.waitForTimeout(1500);
    const s2 = await snap();
    await page.keyboard.press("Alt+ArrowLeft");
    await page.waitForTimeout(500);
    const b1 = await snap();
    await page.keyboard.press("Alt+ArrowLeft");
    await page.waitForTimeout(500);
    const b2 = await snap();
    await page.keyboard.press("Alt+ArrowRight");
    await page.waitForTimeout(500);
    const f1 = await snap();
    await page.keyboard.press("Alt+ArrowRight");
    await page.waitForTimeout(500);
    const f2 = await snap(); // the section jump: same level, same place down the page
    // hash routing still follows the browser's own Back: home, then Back returns to the document
    await page.click("#home-btn");
    await page.waitForTimeout(300);
    const home = await page.evaluate(() => getComputedStyle(document.querySelector("#start-screen")).display !== "none");
    await page.goBack();
    await page.waitForSelector("#content .node, .root-hero", { timeout: 8000 });
    // the back button goes away by itself
    await page.keyboard.press("Home"); // focus is on the page: use the pill instead
    for (let i = 0; i < 8; i++) {
      await page.keyboard.press("-");
      await page.waitForTimeout(90);
    }
    await page.waitForTimeout(1200);
    const shown = await page.evaluate(() => !document.querySelector("#hist-back").hidden);
    await page.waitForTimeout(6500);
    const gone = await page.evaluate(() => document.querySelector("#hist-back").hidden);
    const ok =
      backShown && s2.y > s1.y + 500 && b1.page === s1.page && b2.page === s0.page &&
      Math.abs(b2.y - s0.y) < 40 && f1.page === s1.page && Math.abs(f2.y - s2.y) < 80 && b1.hash === s0.hash && home && shown && gone;
    return { ok, backShown, same: { b1: b1.page === s1.page, b2: b2.page === s0.page, f1: f1.page === s1.page }, y: [s0.y, s1.y, s2.y, b1.y, b2.y, f1.y, f2.y], home, shown, gone };
  },

  async reading_settings_persist_and_change_the_columns(page) {
    const id = await buildText(longDoc());
    await page.setViewportSize({ width: 1366, height: 900 });
    await openReader(page, id);
    await deepZoom(page);
    const read = () =>
      page.evaluate(() => {
        const b = document.querySelector("#content .node-body");
        return {
          ls: parseFloat(getComputedStyle(b).letterSpacing) || 0,
          maxw: getComputedStyle(document.querySelector(".section-grid")).maxWidth,
          cols: document.querySelector("#content").dataset.cols,
          stored: localStorage.getItem("riemann:reading"),
          overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        };
      });
    const base = await read();
    await page.click("#palette-btn");
    await page.click("#ls-toggle");
    await page.click('[data-width="narrow"]');
    const narrow = await read();
    await page.click('[data-width="wide"]');
    const wide = await read();
    await page.click('[data-width="normal"]');
    await page.keyboard.press("Escape");
    // reload: both persist
    await page.reload();
    await page.waitForSelector("#content .node, .root-hero");
    await page.waitForTimeout(600);
    const after = await page.evaluate(() => ({
      spacing: document.querySelector("#ls-toggle").getAttribute("aria-pressed"),
      width: document.querySelector('#read-width [aria-checked="true"]').dataset.width,
      ls: getComputedStyle(document.documentElement).getPropertyValue("--reading-ls").trim(),
    }));
    // letter-spacing makes each column hold fewer characters, so the one-column switch comes sooner
    const colsAt = async (w, on) => {
      await page.setViewportSize({ width: w, height: 900 });
      await page.evaluate((v) => {
        localStorage.setItem("riemann:reading", JSON.stringify({ spacing: v, width: "normal" }));
      }, on);
      await page.reload();
      await page.waitForSelector("#content .node, .root-hero");
      await page.waitForTimeout(500);
      return page.evaluate(() => document.querySelector("#content").dataset.cols);
    };
    const flips = [];
    let wrongWay = false;
    for (const w of [1740, 1760, 1780, 1800, 1820]) {
      const off = await colsAt(w, false);
      const on = await colsAt(w, true);
      flips.push(`${w}:${off}/${on}`);
      if (off === "1" && on === "2") wrongWay = true;
    }
    const ok =
      base.ls === 0 && Math.abs(narrow.ls - 0.68) < 0.05 && narrow.maxw === "578px" && wide.maxw === "816px" &&
      /"spacing":true/.test(wide.stored) && after.spacing === "true" && after.width === "normal" && after.ls === "0.04em" &&
      narrow.overflow <= 0 && wide.overflow <= 0 && !wrongWay && flips.some((f) => /:2\/1$/.test(f));
    return { ok, base, narrow, wide, after, flips };
  },

  async maths_render_and_highlights_around_a_formula_restore(page) {
    // A stand-in for KaTeX whose output is much longer than the LaTeX source, so any highlight
    // offsets that counted the rendered text would drift. (The real library is a CDN script.)
    await page.route("**/katex*.js", (route) =>
      route.fulfill({
        contentType: "application/javascript",
        body: 'window.katex={renderToString:function(t,o){return \'<span class="katex"><span class="katex-html" aria-hidden="true">\'+"GLYPH".repeat(12)+\'</span><span class="katex-mathml">\'+t.replace(/</g,"&lt;")+\'</span></span>\';}};',
      })
    );
    await page.route("**/katex*.css", (route) => route.fulfill({ contentType: "text/css", body: "" }));
    const lead = "Before the formula the energy is ";
    const tail = " and then some trailing words follow after the formula here.";
    const para = (n) => `Paragraph ${n}. ` + lead + "$E = mc^2$" + tail + " The tide moved sand along the northern beach. ".repeat(6);
    const text = "# Maths\n\n" + [1, 2, 3, 4, 5, 6].map((s) => `## Part ${s}\n\n${para(s)}\n\nIt costs $5 and $10 in total, said the quartermaster ${s}.\n\n$$\\int_0^1 x\\,dx = \\frac12$$\n\n` + "Filler text about harbours. ".repeat(40)).join("\n\n");
    const id = await buildText(text);
    await openReader(page, id);
    await deepZoom(page);
    const info = await page.evaluate(() => {
      const maths = [...document.querySelectorAll("#content .node-body .math")];
      const price = [...document.querySelectorAll("#content .node-body p")].find((p) => /quartermaster/.test(p.textContent));
      return {
        n: maths.length,
        inline: maths.filter((m) => m.classList.contains("math-inline")).length,
        display: maths.filter((m) => m.classList.contains("math-display")).length,
        rendered: maths.every((m) => m.querySelector(".katex")),
        lens: [...new Set(maths.map((m) => m.dataset.len))],
        priceIsText: !!price && !price.querySelector(".math") && /\$5 and \$10/.test(price.textContent),
      };
    });
    // highlight a stretch before the formula, then one after it, in the same block
    const select = async (which) => {
      await page.evaluate((which) => {
        const p = [...document.querySelectorAll("#content .node.leaf .node-body p")].find((p) => p.querySelector(".math-inline") && /Paragraph 3\./.test(p.textContent));
        p.scrollIntoView({ block: "center" });
        const walker = document.createTreeWalker(p, NodeFilter.SHOW_TEXT, { acceptNode: (n) => (n.parentElement.closest(".math") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT) });
        const first = walker.nextNode();
        const last = (() => { let n, l; while ((n = walker.nextNode())) l = n; return l; })();
        const r = document.createRange();
        if (which === "before") {
          const i = first.nodeValue.indexOf("formula the energy");
          r.setStart(first, i);
          r.setEnd(first, i + "formula the energy".length);
        } else {
          const i = last.nodeValue.indexOf("trailing words");
          r.setStart(last, i);
          r.setEnd(last, i + "trailing words".length);
        }
        const sel = getSelection();
        sel.removeAllRanges();
        sel.addRange(r);
        document.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
      }, which);
      await page.waitForTimeout(250);
      await page.click("#highlight-toolbar .hl-swatch >> nth=0");
      await page.waitForTimeout(250);
    };
    await select("before");
    await select("after");
    const marks = () => page.evaluate(() => [...document.querySelectorAll("#content mark[data-hl-id]")].map((m) => m.textContent));
    const before = await marks();
    const stored = await page.evaluate((id) => JSON.parse(localStorage.getItem("riemann:hl:" + id)).map((h) => [h.start, h.end]), id);
    await page.reload();
    await page.waitForSelector("#content .node, .root-hero");
    await page.waitForTimeout(800);
    const after = await marks();
    const mathAfter = await page.evaluate(() => document.querySelectorAll("#content .node-body .math").length);
    // the offsets are the LaTeX source's: "$E = mc^2$" is 10 characters long, however it is drawn
    const src = lead.length + 10 + tail.length;
    const ok =
      info.n >= 12 && info.inline >= 6 && info.display >= 6 && info.rendered && info.priceIsText &&
      before.length === 2 && before[0] === "formula the energy" && before[1] === "trailing words" &&
      after.length === 2 && after[0] === before[0] && after[1] === before[1] && mathAfter === info.n &&
      stored.length === 2 && stored[1][0] - stored[0][1] === ("Paragraph 3. " + lead + "$E = mc^2$" + tail).indexOf("trailing words") - ("Paragraph 3. " + lead).indexOf("formula the energy") - "formula the energy".length;
    return { ok, info, before, after, stored, src };
  },

  async rebuild_menu_confirms_hints_at_old_version_and_rebuilds(page) {
    const x = await buildText(longDoc());
    const trees = path.join(DATA, "cache", "trees");
    const current = fs.readdirSync(trees).find((d) => fs.existsSync(path.join(trees, d, x + ".json")));
    const tree = JSON.parse(fs.readFileSync(path.join(trees, current, x + ".json"), "utf8"));
    const oldId = "feedfacecafe0001";
    const oldDir = path.join(trees, "r3-leaf120-gist25-stop34-schema1");
    fs.mkdirSync(oldDir, { recursive: true });
    fs.writeFileSync(path.join(oldDir, oldId + ".json"), JSON.stringify({ ...tree, id: oldId, source_text: tree.source_text + "\n\nA closing paragraph added so the rebuilt copy is a new document." }));
    const posts = [];
    page.on("request", (r) => { if (r.method() === "POST" && /\/rebuild$/.test(r.url())) posts.push(r.url()); });
    // a tree built by this version: the menu has no older-version hint
    await openReader(page, x);
    await page.click("#doc-menu-btn");
    const fresh = await page.evaluate(() => ({ open: !document.querySelector("#doc-menu").hidden, stale: !document.querySelector("#doc-menu-stale").hidden }));
    await page.keyboard.press("Escape");
    // an older-version tree: the hint shows
    await page.goto("about:blank");
    await openReader(page, oldId);
    await page.evaluate(() => {
      window.__sawLoading = false;
      new MutationObserver(() => { if (!document.querySelector("#loading-screen").hidden) window.__sawLoading = true; }).observe(document.querySelector("#loading-screen"), { attributes: true });
    });
    await page.click("#doc-menu-btn");
    const old = await page.evaluate(() => ({ stale: !document.querySelector("#doc-menu-stale").hidden, note: document.querySelector("#doc-menu-stale").textContent }));
    await page.click("#rebuild-btn");
    const confirm = await page.evaluate(() => ({ shown: !document.querySelector("#rebuild-confirm").hidden, text: document.querySelector("#rebuild-confirm").innerText }));
    await page.click("#rebuild-cancel");
    const cancelled = await page.evaluate(() => document.querySelector("#rebuild-confirm").hidden && !document.querySelector("#rebuild-btn").hidden);
    const noPostYet = posts.length === 0;
    await page.click("#rebuild-btn");
    await page.click("#rebuild-go");
    await page.waitForSelector("#content .node, .root-hero", { timeout: 15000 });
    await page.waitForTimeout(500);
    const after = await page.evaluate(() => ({ hash: location.hash, saw: window.__sawLoading, menuClosed: document.querySelector("#doc-menu").hidden, reader: document.querySelector("#app").classList.contains("active") }));
    const newId = after.hash.replace("#/t/", "");
    const stale = (await (await fetch(`${BASE}/api/tree/${newId}`)).json()).stale;
    const ok =
      fresh.open && !fresh.stale && old.stale && /older version/.test(old.note) &&
      confirm.shown && /Uses one full build of your Claude usage/.test(confirm.text) && cancelled && noPostYet &&
      posts.length === 1 && posts[0].includes(oldId) && after.reader && after.menuClosed && newId !== oldId && stale === false;
    return { ok, fresh, old, confirm, cancelled, posts, after, newId, stale };
  },

  async interrupted_build_offers_to_build_it_again(page) {
    const id = (Date.now().toString(16) + "0123456789abcdef").slice(0, 16); // a fresh id each run
    const dir = path.join(DATA, "cache", "building");
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, id + ".json"), JSON.stringify({ id, title: "Interrupted notes", source_text: longDoc(), objective: null, model: "claude-sonnet-5-5", started: Date.now() / 1000 - 90 }));
    await page.goto(`${BASE}/#/t/${id}`);
    await page.waitForSelector("#loading-interrupted:not([hidden])", { timeout: 10000 });
    const shown = await page.evaluate(() => ({
      heading: document.querySelector("#loading-heading").innerText,
      text: document.querySelector("#loading-interrupted-text").innerText,
      startError: !document.querySelector("#paste-error").hidden,
      startShown: getComputedStyle(document.querySelector("#start-screen")).display !== "none",
      steps: getComputedStyle(document.querySelector("#loading-steps")).display,
    }));
    await page.click("#loading-resume");
    await page.waitForSelector("#content .node, .root-hero", { timeout: 15000 });
    const done = await page.evaluate(() => ({ hash: location.hash, title: document.title }));
    const ok =
      /interrupted/i.test(shown.heading) && /This build was interrupted \(Riemann restarted\)\. Build it again\?/.test(shown.text) &&
      !shown.startError && !shown.startShown && shown.steps === "none" && done.hash === "#/t/" + id;
    return { ok, shown, done };
  },

  async experiment_is_invisible_when_off_and_records_session_numbers(page) {
    const id = await buildText(longDoc());
    const sent = [];
    page.on("request", (r) => {
      if (r.url().endsWith("/api/events") && r.method() === "POST") {
        try { sent.push(...JSON.parse(r.postData() || "[]")); } catch (e) {}
      }
    });
    await page.goto(BASE + "/");
    await page.waitForTimeout(400);
    const off = await page.evaluate(() => ({
      open: document.querySelector("#experiment").open,
      state: document.querySelector("#experiment-state").textContent,
      prompt: !document.querySelector("#exp-prompt").hidden,
      form: !document.querySelector("#exp-outcome").hidden,
    }));
    await openReader(page, id);
    for (let i = 0; i < 4; i++) { await page.keyboard.press("="); await page.waitForTimeout(150); }
    await page.waitForTimeout(300);
    await page.click("#home-btn");
    await page.waitForTimeout(500);
    const promptOff = await page.evaluate(() => !document.querySelector("#exp-prompt").hidden);
    await page.evaluate(() => fetch("/api/events", { method: "POST", headers: { "content-type": "application/json" }, body: "[]" }));
    const close = sent.find((e) => e.type === "close");
    const numbers =
      close && typeof close.session_ms === "number" && close.session_ms >= 0 && typeof close.first_zoom_ms === "number" &&
      close.first_zoom_ms <= close.session_ms && close.max_z >= 0 && close.max_z <= 1 && Number.isInteger(close.source_checks) && !("condition" in close);
    return { ok: !off.open && off.state === "off" && !off.prompt && !off.form && !promptOff && !!numbers, off, promptOff, close };
  },

  async experiment_switch_prompts_and_outcome_events(page) {
    const id = await buildText(longDoc());
    const sent = [];
    page.on("request", (r) => {
      if (r.url().endsWith("/api/events") && r.method() === "POST") {
        try { sent.push(...JSON.parse(r.postData() || "[]")); } catch (e) {}
      }
    });
    await page.goto(BASE + "/");
    await page.click("#experiment summary");
    await page.click('[data-phase="B1"]');
    const cond = await page.evaluate(() => document.querySelector('[data-cond="B"]').getAttribute("aria-checked"));
    await page.fill("#exp-label", "week1-brief");
    await page.click("#exp-start");
    await page.reload();
    const kept = await page.evaluate(() => document.querySelector("#experiment-state").textContent);
    await openReader(page, id);
    for (let i = 0; i < 3; i++) { await page.keyboard.press("="); await page.waitForTimeout(150); }
    await page.click("#home-btn");
    await page.waitForSelector("#exp-prompt:not([hidden])", { timeout: 4000 });
    await page.click('[data-help="yes"]');
    await page.click("#exp-prompt-dismiss");
    const dismissed = await page.evaluate(() => document.querySelector("#exp-prompt").hidden);
    // the outcome numbers: only what is filled in is sent
    await page.click("#experiment summary");
    await page.click("#exp-outcome-open");
    await page.fill("#out-minutes", "7");
    await page.fill("#out-checklist", "4");
    await page.evaluate(() => { const r = document.querySelector('[data-tlx="tlx_effort"]'); r.value = "35"; r.dispatchEvent(new Event("input", { bubbles: true })); });
    await page.selectOption("#out-missed", "no");
    await page.click('#exp-outcome button[type="submit"]');
    await page.waitForTimeout(300);
    await page.click("#exp-end");
    const endState = await page.evaluate(() => ({ state: document.querySelector("#experiment-state").textContent, stored: localStorage.getItem("riemann:experiment") }));
    await page.evaluate(() => fetch("/api/events", { method: "POST", headers: { "content-type": "application/json" }, body: "[]" }));
    const by = (t) => sent.filter((e) => e.type === t);
    const set = by("experiment").find((e) => e.action === "set");
    const end = by("experiment").find((e) => e.action === "end");
    const help = by("did_it_help")[0];
    const outcome = by("outcome")[0];
    const close = by("close")[0];
    const ok =
      cond === "true" && set && set.condition === "B" && set.phase === "B1" && set.doc_label === "week1-brief" && end &&
      /B1/.test(kept) && /week1-brief/.test(kept) && dismissed &&
      help && help.value === true && help.tree_id === id && help.condition === "B" &&
      outcome && outcome.doc_label === "week1-brief" && outcome.minutes_to_know === 7 && outcome.checklist_score === 4 &&
      outcome.tlx_effort === 35 && !("tlx_mental" in outcome) && outcome.missed_later === false && !("started_within_24h" in outcome) &&
      close && close.condition === "B" && close.phase === "B1" && close.doc_label === "week1-brief" && typeof close.session_ms === "number" &&
      endState.state === "off" && endState.stored === null;
    return { ok, set, end, kept, help, outcome, close, endState };
  },

  async failed_build_shows_message_and_retries(page) {
    const text = "FAILME-ONCE " + Array.from({ length: 60 }, (_, i) => `Sentence ${i} about the harbour and its tides.`).join(" ")
      + "\n\n" + Array.from({ length: 60 }, (_, i) => `Another ${i} point about the survey boats.`).join(" ");
    await page.goto(BASE + "/");
    const id = await page.evaluate(async (t) => {
      const r = await fetch("/api/abstract", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: t }) });
      return (await r.json()).tree_id;
    }, text);
    await page.goto(`${BASE}/#/t/${id}`);
    await page.waitForSelector("#loading-error:not([hidden])", { timeout: 10000 });
    const msg = await page.innerText("#loading-error-text");
    const heading = await page.innerText("#loading-heading");
    // Reload on the failed build: still the same panel, not a dead end.
    await page.reload();
    await page.waitForSelector("#loading-error:not([hidden])", { timeout: 10000 });
    await page.click("#loading-retry");
    await page.waitForSelector("#content .node, .root-hero", { timeout: 15000 });
    return { ok: /rate-limiting/.test(msg) && heading === "The build stopped", msg, heading };
  },

  async phone_layout_no_overflow(page) {
    await page.setViewportSize({ width: 390, height: 844 });
    await openReader(page);
    const seen = [await overflow(page)];
    for (let i = 0; i < 8; i++) {
      await page.keyboard.press("=");
      await page.waitForTimeout(200);
      seen.push(await overflow(page));
    }
    const header = await page.evaluate(() => {
      const h = document.querySelector("#app-header").getBoundingClientRect();
      return { top: h.top, h: h.height };
    });
    return { ok: seen.every((o) => o <= 0) && header.h > 40, seen, header };
  },

  async monkey_seed(page, errors) {
    const seed = +(ARGS[0] || 7);
    const N = +(ARGS[1] || 60);
    let a = seed;
    const R = () => {
      a |= 0;
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
    const pick = (x) => x[Math.floor(R() * x.length)];
    const ri = (lo, hi) => lo + Math.floor(R() * (hi - lo + 1));
    await openReader(page);
    const acts = {
      zoomIn: () => page.keyboard.press("="),
      zoomOut: () => page.keyboard.press("-"),
      burst: async () => {
        const k = pick(["=", "-"]);
        for (let i = 0; i < ri(2, 5); i++) await page.keyboard.press(k);
      },
      scroll: async () => {
        await page.mouse.move(ri(300, 900), ri(150, 650));
        await page.mouse.wheel(0, ri(-1200, 1200));
      },
      zHold: async () => {
        await page.mouse.move(ri(300, 900), ri(150, 650));
        await page.keyboard.down("z");
        for (let i = 0; i < ri(1, 4); i++) await page.mouse.move(ri(200, 1000), ri(150, 650), { steps: 3 });
        await page.keyboard.up("z");
      },
      map: () => page.keyboard.press("g"),
      navJump: async () => {
        const n = await page.$$(".nav-item");
        if (n.length) await pick(n).click({ timeout: 1500 }).catch(() => {});
      },
      palette: async () => {
        await page.click("#palette-btn", { timeout: 1500 }).catch(() => {});
        await page.keyboard.press("Escape");
      },
      minimal: () => page.keyboard.press("m"),
      resize: () => page.setViewportSize(pick([{ width: 1366, height: 768 }, { width: 1100, height: 700 }, { width: 390, height: 844 }, { width: 1920, height: 1080 }])),
      home: async () => {
        await page.click("#home-btn", { timeout: 1500 }).catch(() => {});
        await page.waitForTimeout(150);
        await page.goto(`${BASE}/#/t/${TREE}`);
      },
    };
    const names = Object.keys(acts);
    const log = [];
    for (let i = 0; i < N; i++) {
      const name = pick(names);
      log.push(name);
      errors.length = 0;
      await acts[name]().catch(() => {});
      await page.waitForTimeout(200);
      const bad = await page.evaluate(() => {
        const out = [];
        const de = document.documentElement;
        if (de.scrollWidth - de.clientWidth > 1) out.push("horizontal overflow " + (de.scrollWidth - de.clientWidth));
        const app = document.querySelector("#app");
        if (app && app.classList.contains("active") && !document.body.classList.contains("minimal-chrome")) {
          const h = document.querySelector("#app-header").getBoundingClientRect();
          if (h.top < -1 || h.height < 40) out.push("header not visible");
        }
        return out;
      });
      if (bad.length || errors.length) return { ok: false, seed, step: i, action: name, issues: [...bad, ...errors], last: log.slice(-5) };
    }
    return { ok: true, seed, actions: N };
  },
};

(async () => {
  const fn = checks[CHECK];
  if (!fn) {
    console.log(JSON.stringify({ ok: false, error: "unknown check " + CHECK }));
    process.exit(2);
  }
  const browser = await chromium.launch();
  try {
    const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
    const page = await ctx.newPage();
    const errors = watch(page);
    const result = await fn(page, errors);
    // The browser logs every non-2xx fetch; an interrupted build is answered 409 by design.
    const allowed = { interrupted_build_offers_to_build_it_again: /status of 409/ }[CHECK];
    const unexpected = allowed ? errors.filter((e) => !allowed.test(e)) : errors;
    if (result.ok && CHECK !== "monkey_seed" && unexpected.length) {
      result.ok = false;
      result.errors = unexpected;
    }
    console.log(JSON.stringify(result));
  } catch (e) {
    console.log(JSON.stringify({ ok: false, error: String(e && e.stack || e).slice(0, 800) }));
  } finally {
    await browser.close();
  }
})();
