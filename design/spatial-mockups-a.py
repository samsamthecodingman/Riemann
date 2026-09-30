"""Map A variations for the Riemann spatial view (Sam liked the region map):
A2 mirrors the reader, A3 map-first, A4 map along the bottom. Reuses the
shared pieces and content from gen_spatial.py."""
import math

from importlib import import_module  # expects design/spatial-mockups.py copied beside it as gen_spatial.py
from gen_spatial import (BODY, BORDER, CHIP, EDGE, FONT, HUE, INK, LABEL, MAPBG, MED, MUTED, PANEL, ROOT,
                         S2_PARTS, SECTIONS, SERIF, box, crumb, e, header, here_tag, map_panel, nn, rail, reader,
                         strip, strip_split)

SEC_HOOKS = {
    1: "Working-memory deficits and erratic response times shape which reading and focus features are likely to help.",
    2: "Popular ADHD frameworks and interventions differ sharply in how well the evidence supports them.",
    3: "Which design choices have solid support, and which rest on blogs, reviews or one trial.",
    4: "Much of the ADHD evidence behind Riemann is preliminary, so the design should measure and adapt per user.",
}
MED_TITLE = MED["title"]
SHORT = {
    "Design for unpredictable attention, not constant": "Unpredictable attention",
    "Fidgeting, chunking, emotion and medication confounds": "Fidgeting & confounds",
    "Three cognitive findings behind adult ADHD": "Three findings",
    "Interest-based, DMN and time-blindness frameworks rated": "Frameworks rated",
    "Text plus audio helps weaker readers": "Text + audio",
    "Bionic reading debunked; noise helps unevenly": "Bionic & noise",
    "Fidgeting helps ADHD focus; COGA offers patterns": "Fidgeting & COGA",
    "Strong guidance, weak bullet-point claims, one RCT": "Guidance vs claims",
    "ADHD HCI overlooks text summarization; apps show patterns": "HCI gap",
    "RSD is practitioner shorthand, not diagnosis": "RSD",
    "Wall of Awful and body doubling lack evidence": "Wall of Awful",
    "Passive behavioral signals and research caveats": "Behaviour signals",
    "Medication windows and resulting design guidance": "Medication windows",
    "Evidence limits for Riemann's target user": "Evidence limits",
    "Stimulants create time-bounded cognitive windows": "Time windows",
    "Strong pharmacokinetics, weaker learning-outcome evidence": "Evidence strength",
    "Eleven design recommendations for adaptive reading": "11 design rules",
}


def fit_title(title, w, h, px=13):
    """Full title if it fits the tile, else its short name (semantic zoom)."""
    return title if est_lines(title, w - 20, px) * px * 1.3 + 18 <= h else SHORT.get(title, title)


def est_lines(text, width, px):
    return max(1, math.ceil(len(text) / max(6, width / (px * 0.66))))


def ring(on):
    return f"outline: 3px solid {INK}; outline-offset: 2px;" if on else ""


# ---------------------------------------------------------------- one region renderer, reused by every variation
def part_tile(x, y, w, h, title, n, here=False, sources=None):
    out = []
    label = fit_title(title, w, h if not sources else min(h, 58))
    tl = est_lines(label, w - 20, 13)
    inner = f'<span style="font-size: 13px; line-height: 1.3; font-weight: 700; color: {INK}">{e(label)}</span>'
    padv = 8 if h >= 44 else 4
    out.append(box(x, y, w, h, f"border: none; border-radius: 10px; background: rgba(255,253,250,0.78); padding: {padv}px 10px; text-align: left; overflow: hidden; display: flex; flex-direction: column; justify-content: flex-start; align-items: flex-start; {FONT}; {ring(here)}",
                   inner, tag="button", label=title))
    if sources:
        top = y + padv + tl * 17 + 6
        room = y + h - top - 6
        stacked = room >= 3 * 24 + 10
        cells = strip_split([(s[0], 1) for s in sources], x + 8, top, w - 16, room if stacked else min(room, 26), 5, horizontal=not stacked)
        for (st, prov), sx, sy, sw, sh in [((s[0], s[2]), *r[1:]) for s, r in zip(sources, cells)]:
            if not stacked:
                out.append(box(sx, sy, sw, sh, f"border: none; border-radius: 8px; background: {HUE[n]}; padding: 0; font-size: 13px; line-height: {sh:.0f}px; text-align: center; color: {BODY}; {FONT}", prov, tag="button", label=st))
                continue
            out.append(box(sx, sy, sw, sh, f"border: none; border-radius: 8px; background: {HUE[n]}; padding: 4px 8px; text-align: left; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; font-size: 13px; line-height: 1.35; color: {BODY}; {FONT}",
                           f'<span style="color: {LABEL}">{prov}</span> {e(SHORT.get(st, st) if sw < 260 else st)}', tag="button", label=st))
    return out


def section_region(s, x, y, w, h, opened=False, open_parts=(), here_parts=(), here=False, compact=False):
    n = s["n"]
    out = []
    title = s["short"] if compact else s["title"]
    side = w > 1.8 * h and opened  # wide district: header on the left, parts on the right
    hw = (150 if compact else 200) if side else w
    tl = est_lines(title, hw - 28, 15)
    num = 30 if compact else 40
    head_h = 12 + num + 6 + tl * 19.5 + (6 + 17 if not compact else 0) + 10
    show_hook = not opened and not compact and (h - head_h) > 70 and w > 160
    hook = f'<span style="font-size: 13px; line-height: 1.4; color: {MUTED}">{e(SEC_HOOKS[n])}</span>' if show_hook else ""
    head = (f'<div style="position: absolute; left: 14px; top: 12px; width: {hw - 28:.0f}px; display: flex; flex-direction: column; gap: 4px; text-align: left">'
            f'<span style="{SERIF}; font-size: {num}px; line-height: 1; font-weight: 600; color: {INK}">{nn(n)}</span>'
            f'<span style="font-size: 15px; line-height: 1.3; font-weight: 700; color: {INK}">{e(title)}</span>'
            + ("" if compact else f'<span style="font-size: 12.5px; color: {MUTED}">{len(s["parts"])} parts · {s["words"]:,} words</span>') + f'{hook}</div>')
    out.append(box(x, y, w, h, f"border: none; padding: 0; border-radius: 14px; background: {HUE[n]}; {ring(here)} {FONT}", head, tag="button", label=f"Section {n}: {s['title']}"))
    if opened:
        if side:
            ax, ay, aw, ah = x + hw, y + 10, w - hw - 10, h - 20
        else:
            ax, ay, aw, ah = x + 10, y + head_h, w - 20, h - head_h - 10
        parts = [(p[0], max(p[1], 220)) for p in s["parts"]]
        rows = [parts] if len(parts) <= 3 else [parts[:3], parts[3:]]
        horizontal = aw / len(parts) >= 100 or len(rows) == 2
        if len(rows) == 1:
            cells = strip_split(parts, ax, ay, aw, ah, 6, horizontal=horizontal)
        else:
            tot = sum(p[1] for p in parts)
            r1h = (ah - 6) * sum(p[1] for p in rows[0]) / tot
            cells = strip_split(rows[0], ax, ay, aw, r1h, 6) + strip_split(rows[1], ax, ay + r1h + 6, aw, ah - r1h - 6, 6)
        for pt, px, py, pw, ph in cells:
            src = [(m[0], m[1], m[2]) for m in MED["parts"]] if pt in open_parts and pt == MED_TITLE else None
            out += part_tile(px, py, pw, ph, pt, n, here=pt in here_parts, sources=src)
    return out


def doc_regions(W, H, opened=(), open_parts=(), here_parts=(), here_secs=(), compact=False, pad=12, gap=8, tag_on=None):
    out = []
    rows = [SECTIONS[:3], SECTIONS[3:]]
    total = sum(s["words"] for s in SECTIONS)
    y = pad
    ah = H - 2 * pad - gap
    tag_xy = None
    for row in rows:
        rh = ah * sum(s["words"] for s in row) / total
        for s, x, yy, w, h in strip_split([(s, s["words"]) for s in row], pad, y, W - 2 * pad, rh, gap):
            out += section_region(s, x, yy, w, h, opened=s["n"] in opened, open_parts=open_parts,
                                  here_parts=here_parts, here=s["n"] in here_secs, compact=compact)
            if tag_on == s["n"]:
                tag_xy = (x + w - 112, yy + 6)
        y += rh + gap
    if tag_xy:
        out.append(here_tag(*tag_xy))
    return "\n".join(out)


# ---------------------------------------------------------------- page wrapper
def page(title, w, h, body):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{e(title)}</title>
<script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&amp;family=Work+Sans:wght@400;600;700&amp;display=swap" rel="stylesheet">
<style>
body{{margin:0;font-family:'Work Sans',sans-serif;background:#FBF7F2}}
a{{color:#2A2521}}a:hover{{color:#2A2521}}
</style>
</helmet>
<div style="width: {w}px; height: {h}px; box-sizing: border-box; background: #FBF7F2; display: flex; flex-direction: column; {FONT}; color: {INK}; overflow: hidden">
{body}
</div>
</x-dc>
<script type="text/x-dc" data-dc-script data-props='{{"$preview":{{"width":{w},"height":{h}}}}}'>
class Component extends DCLogic {{
renderVals() {{
return {{}};
}}
}}
</script>
</body>
</html>
"""


def map_toolbar(label, subtitle, width=None):
    return f"""<div style="display: flex; align-items: center; gap: 10px; height: 40px{'; width: %dpx' % width if width else ''}">
<span style="font-size: 12px; font-weight: 700; letter-spacing: 0.08em; color: {LABEL}">{e(label)}</span>
<span style="font-size: 13px; color: {MUTED}">{e(subtitle)}</span>
<div style="flex-grow: 1"></div>
<button type="button" style="height: 36px; padding: 0 14px; border-radius: 999px; border: 1px solid {BORDER}; background: {CHIP}; color: {INK}; {FONT}; font-size: 13px; font-weight: 600">Fit</button>
<button type="button" aria-label="Zoom map out" style="width: 36px; height: 36px; border-radius: 999px; border: 1px solid {BORDER}; background: {PANEL}; color: {INK}; font-size: 16px">−</button>
<button type="button" aria-label="Zoom map in" style="width: 36px; height: 36px; border-radius: 999px; border: 1px solid {BORDER}; background: {PANEL}; color: {INK}; font-size: 16px">+</button>
</div>"""


# ---------------------------------------------------------------- A2: the map mirrors the reader
def a2():
    s2_parts = [p[0] for p in SECTIONS[1]["parts"]]
    top = f"""<div style="height: 900px; flex-shrink: 0; display: grid; grid-template-columns: 620px minmax(0, 1fr) 340px; grid-template-rows: 72px minmax(0, 1fr)">
{header()}
{map_panel(doc_regions(580, 688, opened={2}, here_parts=set(s2_parts), tag_on=2), "Mirrors the reader · 02 is open")}
{reader()}
{rail()}
</div>"""
    panels = [
        ("1 · Reader at the gist", "Nothing open yet: four solid districts, each with its number, colour and title.",
         doc_regions(464, 440, compact=True)),
        ("2 · Reader opened 02", "02 splits into its three parts, the ones on screen in the reader outlined.",
         doc_regions(464, 440, opened={2}, here_parts=set(s2_parts), compact=True)),
        ("3 · Reader deep in 04", "04 shows its five parts; Medication windows shows the three source paragraphs you're reading.",
         doc_regions(464, 440, opened={4}, open_parts={MED_TITLE}, here_parts={MED_TITLE}, compact=True)),
    ]
    body = top + strip(panels, "The map is a live picture of the reader: whatever you open there splits here, and what's on screen is outlined.")
    return page("Map A2: mirrors the reader", 1600, 1560, body)


# ---------------------------------------------------------------- A3: map first, reader as a side panel
def a3():
    lis_blocks = []
    for title, prov, pts in S2_PARTS:
        lis = "".join(
            f'<li style="position: relative; padding-left: 22px; font-size: 15.5px; line-height: 1.5; color: {BODY}"><span aria-hidden="true" style="position: absolute; left: 2px; top: 7px; width: 9px; height: 9px; border-radius: 999px; background: {HUE[2]}; box-shadow: 0 0 0 1.5px {EDGE[2]}"></span>{e(p)}</li>'
            for p in pts)
        lis_blocks.append(f"""<div style="display: flex; flex-direction: column; gap: 8px">
<div style="display: flex; align-items: baseline; gap: 8px"><h2 style="margin: 0; font-size: 16px; font-weight: 700; color: {INK}">{e(title)}</h2><span style="font-size: 12px; color: {LABEL}; white-space: nowrap; text-decoration: underline dotted">{prov}</span></div>
<ul style="margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 6px">{lis}</ul>
</div>""")
    s2_parts = [p[0] for p in SECTIONS[1]["parts"]]
    body = f"""<div style="height: 900px; display: grid; grid-template-columns: minmax(0, 1fr) 520px; grid-template-rows: 72px minmax(0, 1fr)">
{header()}
<section aria-label="Document map" style="grid-column: 1; grid-row: 2; padding: 16px 24px 20px 32px; display: flex; flex-direction: column; gap: 12px; min-height: 0">
{map_toolbar("MAP", "Click a region to read it · the reader follows")}
<div style="position: relative; width: 1024px; height: 740px; border-radius: 20px; background: {MAPBG}; overflow: hidden">
{doc_regions(1024, 740, opened={2}, here_parts=set(s2_parts), pad=16, gap=10, tag_on=2)}
</div>
</section>
<aside aria-label="Reader" style="grid-column: 2; grid-row: 2; background: {PANEL}; border-left: 1px solid {BORDER}; padding: 28px 32px; display: flex; flex-direction: column; gap: 14px; overflow: hidden">
<div style="display: flex; align-items: center; gap: 10px">
<span style="font-size: 12px; font-weight: 700; letter-spacing: 0.08em; color: {LABEL}">READING</span>
<div style="flex-grow: 1"></div>
<button type="button" style="height: 36px; padding: 0 14px; border-radius: 999px; border: 1px solid {BORDER}; background: {CHIP}; color: {INK}; {FONT}; font-size: 13px; font-weight: 600">Open full reader</button>
</div>
<span style="font-size: 13px; font-weight: 700; letter-spacing: 0.1em; color: {LABEL}"><span style="padding: 4px 10px; border-radius: 999px; background: {HUE[2]}; color: {INK}">02</span> · SECTION</span>
<h1 style="margin: 0; {SERIF}; font-size: 30px; line-height: 1.15; font-weight: 600; color: {INK}">Which ADHD claims hold up, and which don't</h1>
<p style="margin: 0; font-size: 16px; line-height: 1.55; color: {MUTED}">{e(SEC_HOOKS[2])}</p>
<div style="display: flex; flex-direction: column; gap: 18px; margin-top: 4px">{"".join(lis_blocks)}</div>
</aside>
</div>"""
    return page("Map A3: map first", 1600, 900, body)


# ---------------------------------------------------------------- A4: the map as a band along the bottom
def nav():
    items = []
    for s in SECTIONS:
        cur = s["n"] == 2
        dot = "" if cur else f'<span aria-hidden="true" style="width: 10px; height: 10px; margin-top: 6px; flex-shrink: 0; border-radius: 999px; background: {HUE[s["n"]]}; box-shadow: inset 0 0 0 1px {BORDER}"></span>'
        items.append(f'<a href="#"{" aria-current=\"true\"" if cur else ""} style="display: flex; gap: 12px; padding: 12px; border-radius: 12px; text-decoration: none; color: {INK if cur else BODY}; {("background: " + HUE[2] + "; font-weight: 600;") if cur else ""}">{dot}<span style="font-weight: 700; color: {INK if cur else LABEL}">{nn(s["n"])}</span><span>{e(s["title"])}</span></a>')
    return f"""<nav aria-label="Sections" style="grid-column: 1; grid-row: 2; padding: 28px 20px 20px 32px; display: flex; flex-direction: column; gap: 6px; border-right: 1px solid {BORDER}; background: {PANEL}; font-size: 15px; overflow: hidden">
<span style="font-size: 12px; font-weight: 700; letter-spacing: 0.08em; color: {LABEL}; padding: 0 12px 8px">SECTIONS</span>
{"".join(items)}
</nav>"""


def band(W, H):
    out = []
    pad, gap = 8, 8
    secs = [(s, s["words"] * (3 if s["n"] == 2 else 1)) for s in SECTIONS]  # fisheye: the section you're in gets room
    for s, x, y, w, h in strip_split(secs, pad, pad, W - 2 * pad, H - 2 * pad, gap):
        n = s["n"]
        opened = n == 2
        hw = 176 if opened else w
        head = (f'<div style="position: absolute; left: 14px; top: 12px; width: {hw - 28:.0f}px; display: flex; flex-direction: column; gap: 4px; text-align: left">'
                f'<span style="{SERIF}; font-size: 30px; line-height: 1; font-weight: 600; color: {INK}">{nn(n)}</span>'
                f'<span style="font-size: 14px; line-height: 1.3; font-weight: 700; color: {INK}">{e(s["short"])}</span>'
                f'<span style="font-size: 12.5px; color: {MUTED}">{s["words"]:,} words</span></div>')
        out.append(box(x, y, w, h, f"border: none; padding: 0; border-radius: 12px; background: {HUE[n]}; {FONT}", head, tag="button", label=f"Section {n}: {s['title']}"))
        if opened:
            cells = strip_split([(p[0], p[1]) for p in s["parts"]], x + hw, y + 8, w - hw - 8, h - 16, 6)
            for pt, px, py, pw, ph in cells:
                out += part_tile(px, py, pw, ph, pt, n)
            # the reader's viewport: parts 1-2 of 02 are on screen
            vx = cells[0][1] - 4
            vw = cells[1][1] + cells[1][3] - vx + 4
            out.append(box(vx, y + 2, vw, h - 4, f"border: 3px solid {INK}; border-radius: 12px; pointer-events: none; z-index: 3", ""))
            out.append(box(vx + vw / 2 - 52, y + h - 34, 104, 26, f"border-radius: 999px; background: {INK}; color: {PANEL}; font-size: 12px; font-weight: 700; display: flex; align-items: center; justify-content: center; z-index: 4", "On screen"))
    return "\n".join(out)


def a4():
    body = f"""<div style="height: 900px; display: grid; grid-template-columns: 300px minmax(0, 1fr) 340px; grid-template-rows: 72px minmax(0, 1fr) 236px">
{header()}
{nav()}
{reader()}
{rail()}
<section aria-label="Document map" style="grid-column: 1 / 4; grid-row: 3; background: {PANEL}; border-top: 1px solid {BORDER}; padding: 10px 32px 16px; display: flex; flex-direction: column; gap: 8px">
{map_toolbar("MAP", "Reading order, left to right · the outline is what's on screen")}
<div style="position: relative; width: 1536px; height: 164px; border-radius: 16px; background: {MAPBG}; overflow: hidden">
{band(1536, 164)}
</div>
</section>
</div>"""
    return page("Map A4: map along the bottom", 1600, 900, body)


def main():
    for name, html in {"Map-A2-Mirror.dc.html": a2(), "Map-A3-MapFirst.dc.html": a3(), "Map-A4-Band.dc.html": a4()}.items():
        (ROOT / name).write_text(html, encoding="utf-8")
        print("wrote", name, len(html))


if __name__ == "__main__":
    main()
