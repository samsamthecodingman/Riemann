"""Generate the three spatial-view mockup boards (Map-A region map, Map-B mind
map, Map-C card canvas) for the Riemann Design canvas. Static mockups in the
Macaron system, real content from the ADHD research tree (f0ccd10ec67bf72e)."""
from html import escape as e
from pathlib import Path

ROOT = Path(__file__).parent / "project"  # run from a local copy of the canvas (boards are written to <canvas>/project/)

INK, PANEL, BORDER, CHIP = "#2A2521", "#FFFDFA", "#ECE4D8", "#F3EEE6"
BODY, MUTED, LABEL, MAPBG = "#38312B", "#5E554C", "#6B6157", "#F5EFE6"
HUE = {1: "#F6D5D1", 2: "#D5E6CF", 3: "#F7E8B5", 4: "#D3E4F2"}
EDGE = {1: "#C9A29C", 2: "#9FB896", 3: "#C4B27A", 4: "#95AFC6"}  # same-hue edges for outlines/lines

DOC_TITLE = "03 — ABSORBING AND DISPLAYING INFORMATION FOR ADULTS WITH ADHD"
ROOT_TITLE = "Adapt per user; ADHD evidence is uneven"
ROOT_HOOK = "Only some ADHD claims are well supported, so Riemann should adapt to each user rather than assume group traits."

SECTIONS = [
    {"n": 1, "title": "Unpredictable attention and delay aversion shape design", "short": "Unpredictable attention", "words": 718,
     "parts": [("Design for unpredictable attention, not constant", 231), ("Fidgeting, chunking, emotion and medication confounds", 199), ("Three cognitive findings behind adult ADHD", 288)]},
    {"n": 2, "title": "Which ADHD claims hold up, and which don't", "short": "Which claims hold up", "words": 836,
     "parts": [("Interest-based, DMN and time-blindness frameworks rated", 345), ("Text plus audio helps weaker readers", 167), ("Bionic reading debunked; noise helps unevenly", 324)]},
    {"n": 3, "title": "Fidgeting, COGA guidance and thin HCI evidence", "short": "Fidgeting & COGA", "words": 744,
     "parts": [("Fidgeting helps ADHD focus; COGA offers patterns", 235), ("Strong guidance, weak bullet-point claims, one RCT", 260), ("ADHD HCI overlooks text summarization; apps show patterns", 249)]},
    {"n": 4, "title": "Weak constructs, medication windows and Riemann's design rules", "short": "Weak constructs & medication", "words": 2048,
     "parts": [("RSD is practitioner shorthand, not diagnosis", 157), ("Wall of Awful and body doubling lack evidence", 238), ("Passive behavioral signals and research caveats", 341), ("Medication windows and resulting design guidance", 699), ("Evidence limits for Riemann's target user", 613)]},
]
S4_HOOKS = {
    "RSD is practitioner shorthand, not diagnosis": "Explains avoidance in clinical practice, but not a formal diagnosis.",
    "Wall of Awful and body doubling lack evidence": "Popular ideas resting on practitioner knowledge and thin evidence.",
    "Passive behavioral signals and research caveats": "Riemann could infer capacity and avoidance from behaviour.",
    "Medication windows and resulting design guidance": "Timing is large and unobservable, so favour manual capacity input and flexible re-entry.",
    "Evidence limits for Riemann's target user": "Much of the evidence is child-derived or group-level.",
}
MED = {
    "title": "Medication windows and resulting design guidance",
    "points": ["Stimulant effects last roughly 3–14 hours depending on formulation.",
               "Stimulants may aid attention without reliably improving academic learning.",
               "Allow re-entry at any level; make the gist near-instant and low-stakes.",
               "Use a manual capacity input rather than inferring medication state."],
    "parts": [("Stimulants create time-bounded cognitive windows", 97, "¶ 31", "Short-acting stimulants: onset 30–45 min, wear off in 3–6 hours."),
              ("Strong pharmacokinetics, weaker learning-outcome evidence", 51, "¶ 32", "Moderate-strong for onset and duration; moderate for learning outcomes."),
              ("Eleven design recommendations for adaptive reading", 551, "¶ 33", "1. Never assume a flat attention budget across a session.")],
}
S2_PARTS = [
    ("Interest-based, DMN and time-blindness frameworks rated", "¶ 10–12",
     ["Dodson's interest-based nervous system lacks peer-reviewed testing; useful only as a heuristic.",
      "DMN connectivity differs in ADHD, but its link to mind-wandering is contested."]),
    ("Text plus audio helps weaker readers", "¶ 13–14",
     ["Less-skilled readers' bimodal comprehension matched average readers' visual-only comprehension.",
      "Bimodal presentation aids vocabulary acquisition."]),
    ("Bionic reading debunked; noise helps unevenly", "¶ 15–17",
     ["Bionic reading showed no measurable benefit for ADHD readers or general readers.",
      "Noise improves ADHD performance on average, with moderate evidence."]),
]
S2_POINTS = ["Dodson's interest-based nervous system is practitioner theory: useful as a design heuristic.",
             "Bimodal reading helps weaker readers, but redundancy may add load.",
             "Bionic reading has no supporting evidence for ADHD readers.",
             "Noise benefit is moderate overall; subtype reversal is contested."]

FONT = "font-family: 'Work Sans', sans-serif"
SERIF = "font-family: 'Fraunces', serif"


def nn(n):
    return f"{n:02d}"


# ---------------------------------------------------------------- shared chrome
def header():
    return f"""<header style="grid-column: 1 / 4; display: flex; align-items: center; gap: 18px; padding: 0 32px; background: {PANEL}; border-bottom: 1px solid {BORDER}">
<button type="button" aria-label="Home page" style="width: 44px; height: 44px; border-radius: 12px; border: 1px solid {BORDER}; background: {CHIP}; color: {INK}; font-size: 18px">⌂</button>
<div style="display: flex; flex-direction: column; gap: 2px; min-width: 0; max-width: 620px">
<span style="font-size: 12px; font-weight: 700; letter-spacing: 0.08em; color: {LABEL}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{e(DOC_TITLE)}</span>
<span style="{SERIF}; font-size: 17px; color: {INK}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{e(ROOT_HOOK)}</span>
</div>
<div style="flex-grow: 1"></div>
<button type="button" aria-pressed="true" style="height: 44px; padding: 0 18px; border-radius: 999px; border: none; background: {INK}; color: {PANEL}; {FONT}; font-size: 15px; font-weight: 700; display: flex; align-items: center; gap: 8px"><svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="{PANEL}" stroke-width="1.6" aria-hidden="true"><rect x="1.5" y="2.5" width="5" height="11" rx="1.5"></rect><rect x="9.5" y="2.5" width="5" height="5" rx="1.5"></rect><rect x="9.5" y="9.5" width="5" height="4" rx="1.5"></rect></svg>Map</button>
<button type="button" style="height: 44px; padding: 0 16px; border-radius: 999px; border: 1px solid {BORDER}; background: {PANEL}; color: {INK}; {FONT}; font-size: 15px; font-weight: 600; display: flex; align-items: center; gap: 8px"><span aria-hidden="true" style="display: inline-flex; gap: 3px"><span style="width: 10px; height: 10px; border-radius: 999px; background: #F9D3E3"></span><span style="width: 10px; height: 10px; border-radius: 999px; background: #F7E8B5"></span><span style="width: 10px; height: 10px; border-radius: 999px; background: #E2D8F0"></span></span>Palette</button>
<div style="display: flex; align-items: center; gap: 6px; padding: 6px; border-radius: 999px; background: {CHIP}; border: 1px solid {BORDER}">
<button type="button" aria-label="Less detail" style="height: 36px; padding: 0 14px; border-radius: 999px; border: 1px solid {BORDER}; background: {PANEL}; color: {INK}; {FONT}; font-size: 14px; font-weight: 600">− Less</button>
<span style="font-size: 13px; color: {MUTED}; padding: 0 6px">~2 min · 9% of original</span>
<button type="button" aria-label="More detail" style="height: 36px; padding: 0 14px; border-radius: 999px; border: none; background: {INK}; color: {PANEL}; {FONT}; font-size: 14px; font-weight: 700">More +</button>
</div>
</header>"""


def map_panel(inner, subtitle):
    return f"""<section aria-label="Document map" style="grid-column: 1; grid-row: 2; display: flex; flex-direction: column; gap: 12px; padding: 16px 20px 16px 20px; background: {PANEL}; border-right: 1px solid {BORDER}; min-height: 0">
<div style="display: flex; align-items: center; gap: 10px; height: 40px">
<span style="font-size: 12px; font-weight: 700; letter-spacing: 0.08em; color: {LABEL}">MAP</span>
<span style="font-size: 13px; color: {MUTED}">{e(subtitle)}</span>
<div style="flex-grow: 1"></div>
<button type="button" style="height: 36px; padding: 0 14px; border-radius: 999px; border: 1px solid {BORDER}; background: {CHIP}; color: {INK}; {FONT}; font-size: 13px; font-weight: 600">Fit</button>
<button type="button" aria-label="Zoom map out" style="width: 36px; height: 36px; border-radius: 999px; border: 1px solid {BORDER}; background: {PANEL}; color: {INK}; font-size: 16px">−</button>
<button type="button" aria-label="Zoom map in" style="width: 36px; height: 36px; border-radius: 999px; border: 1px solid {BORDER}; background: {PANEL}; color: {INK}; font-size: 16px">+</button>
<button type="button" aria-label="Close map" style="width: 36px; height: 36px; border-radius: 999px; border: none; background: transparent; color: {INK}; font-size: 15px">✕</button>
</div>
<div style="position: relative; width: 580px; height: 688px; border-radius: 18px; background: {MAPBG}; overflow: hidden">
{inner}
</div>
<p style="margin: 0; font-size: 13px; color: {MUTED}">Scroll to zoom · drag to move · click a region to read it</p>
</section>"""


def reader():
    blocks = []
    for title, prov, pts in S2_PARTS:
        lis = "".join(
            f'<li style="position: relative; padding-left: 22px; font-size: 16px; line-height: 1.5; color: {BODY}"><span aria-hidden="true" style="position: absolute; left: 2px; top: 7px; width: 9px; height: 9px; border-radius: 999px; background: {HUE[2]}; box-shadow: 0 0 0 1.5px {EDGE[2]}"></span>{e(p)}</li>'
            for p in pts)
        blocks.append(f"""<div style="display: flex; flex-direction: column; gap: 10px">
<div style="display: flex; align-items: baseline; gap: 8px"><h2 style="margin: 0; font-size: 17px; font-weight: 700; color: {INK}">{e(title)}</h2><span style="font-size: 12px; color: {LABEL}; white-space: nowrap; text-decoration: underline dotted">{prov}</span></div>
<ul style="margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 8px">{lis}</ul>
</div>""")
    return f"""<main style="grid-column: 2; grid-row: 2; overflow: hidden; padding: 36px 40px 0; display: flex; flex-direction: column; gap: 16px">
<span style="font-size: 13px; font-weight: 700; letter-spacing: 0.1em; color: {LABEL}"><span style="padding: 4px 10px; border-radius: 999px; background: {HUE[2]}; color: {INK}">02</span> · WHICH ADHD CLAIMS HOLD UP, AND WHICH DON'T</span>
<h1 style="margin: 0; {SERIF}; font-size: 40px; line-height: 1.1; font-weight: 600; color: {INK}">Which ADHD claims hold up, and which don't</h1>
<p style="margin: 0; font-size: 18px; line-height: 1.55; color: {MUTED}">Popular ADHD frameworks and interventions differ sharply in how well the evidence supports them.</p>
<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 32px; row-gap: 26px; margin-top: 6px">
{"".join(blocks)}
</div>
</main>"""


def rail():
    lis = "".join(f'<li style="font-size: 14px; line-height: 1.5; color: {BODY}">{e(p)}</li>' for p in S2_POINTS)
    return f"""<aside style="grid-column: 3; grid-row: 2; padding: 36px 32px 0 0; display: flex; flex-direction: column; gap: 16px; overflow: hidden">
<div style="background: {PANEL}; border: 1px solid {BORDER}; border-radius: 20px; padding: 20px 24px; display: flex; flex-direction: column; gap: 10px">
<span style="font-size: 12px; font-weight: 700; letter-spacing: 0.08em; color: {LABEL}">KEY POINTS</span>
<ul style="margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 8px">{lis}</ul>
</div>
<button type="button" style="text-align: left; background: {PANEL}; border: 1px solid {BORDER}; border-radius: 20px; padding: 20px 24px; display: flex; flex-direction: column; gap: 8px; {FONT}">
<span style="font-size: 12px; font-weight: 700; letter-spacing: 0.08em; color: {LABEL}">UP NEXT · 03</span>
<span style="{SERIF}; font-size: 21px; font-weight: 600; color: {INK}">Fidgeting, COGA guidance and thin HCI evidence</span>
<span style="font-size: 14px; line-height: 1.5; color: {MUTED}">Which design choices have solid support, and which rest on blogs, reviews or one trial.</span>
</button>
</aside>"""


def strip(panels, blurb):
    cells = []
    for label, caption, inner in panels:
        cells.append(f"""<div style="display: flex; flex-direction: column; gap: 12px; width: 464px">
<span style="align-self: flex-start; padding: 6px 14px; border-radius: 999px; background: {INK}; color: {PANEL}; font-size: 13px; font-weight: 700">{e(label)}</span>
<div style="position: relative; width: 464px; height: 440px; border-radius: 18px; background: {MAPBG}; overflow: hidden; border: 1px solid {BORDER}">
{inner}
</div>
<p style="margin: 0; font-size: 14px; line-height: 1.5; color: {MUTED}">{e(caption)}</p>
</div>""")
    return f"""<section style="height: 660px; box-sizing: border-box; padding: 36px 48px 0; border-top: 1px solid {BORDER}; display: flex; flex-direction: column; gap: 18px">
<div style="display: flex; align-items: baseline; gap: 18px">
<h2 style="margin: 0; {SERIF}; font-size: 30px; font-weight: 600; color: {INK}">Zooming the map</h2>
<span style="font-size: 15px; color: {MUTED}">{e(blurb)}</span>
</div>
<div style="display: flex; gap: 40px">{"".join(cells)}</div>
</section>"""


def board(title, map_inner, map_subtitle, panels, blurb):
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
<div style="width: 1600px; height: 1560px; box-sizing: border-box; background: #FBF7F2; display: flex; flex-direction: column; {FONT}; color: {INK}">
<div style="height: 900px; display: grid; grid-template-columns: 620px minmax(0, 1fr) 340px; grid-template-rows: 72px minmax(0, 1fr)">
{header()}
{map_panel(map_inner, map_subtitle)}
{reader()}
{rail()}
</div>
{strip(panels, blurb)}
</div>
</x-dc>
<script type="text/x-dc" data-dc-script data-props='{{"$preview":{{"width":1600,"height":1560}}}}'>
class Component extends DCLogic {{
renderVals() {{
return {{}};
}}
}}
</script>
</body>
</html>
"""


# ---------------------------------------------------------------- helpers
def box(x, y, w, h, style, inner="", tag="div", label=None):
    aria = f' aria-label="{e(label)}"' if label else ""
    typ = ' type="button"' if tag == "button" else ""
    return (f'<{tag}{typ}{aria} style="position: absolute; left: {x:.0f}px; top: {y:.0f}px; width: {w:.0f}px; height: {h:.0f}px; '
            f'box-sizing: border-box; {style}">{inner}</{tag}>')


def here_tag(x, y):
    return box(x, y, 104, 28, f"border-radius: 999px; background: {INK}; color: {PANEL}; font-size: 12px; font-weight: 700; display: flex; align-items: center; justify-content: center; z-index: 3", "You are here")


def crumb(text, x=14, y=14):
    return (f'<span style="position: absolute; left: {x}px; top: {y}px; padding: 5px 12px; border-radius: 999px; background: {PANEL}; '
            f'border: 1px solid {BORDER}; font-size: 12.5px; font-weight: 600; color: {INK}; z-index: 3">{e(text)}</span>')


def strip_split(items, x, y, w, h, gap, horizontal=True):
    """Split a rect proportionally to item weights, in order, along one axis."""
    total = sum(wt for _, wt in items)
    out = []
    span = (w if horizontal else h) - gap * (len(items) - 1)
    pos = x if horizontal else y
    for key, wt in items:
        size = span * wt / total
        out.append((key, pos, y, size, h) if horizontal else (key, x, pos, w, size))
        pos += size + gap
    return out


# ---------------------------------------------------------------- A: region map
def a_district_header(s, big=True):
    return (f'<div style="display: flex; flex-direction: column; gap: 4px; text-align: left">'
            f'<span style="{SERIF}; font-size: {40 if big else 30}px; line-height: 1; font-weight: 600; color: {INK}">{nn(s["n"])}</span>'
            f'<span style="font-size: 15px; line-height: 1.3; font-weight: 700; color: {INK}">{e(s["title"] if big else s["short"])}</span>'
            f'<span style="font-size: 12.5px; color: {MUTED}">{len(s["parts"])} parts · {s["words"]:,} words</span></div>')


def a_whole(W, H, here=True, compact=False):
    pad, gap = 12, 8
    rows = [SECTIONS[:3], SECTIONS[3:]]
    total = sum(s["words"] for s in SECTIONS)
    avail_h = H - 2 * pad - gap
    out = []
    y = pad
    for row in rows:
        rh = avail_h * sum(s["words"] for s in row) / total
        for s, x, yy, w, h in strip_split([(s, s["words"]) for s in row], pad, y, W - 2 * pad, rh, gap):
            parts_html = ""
            if s["n"] < 4:
                import math
                title = s["title"] if not compact else s["short"]
                lines = math.ceil(len(title) / ((w - 28) / (15 * 0.6)))
                head_h = 14 + (40 if not compact else 30) + 8 + lines * 19.5 + 8 + 17 + 14
                ph = h - head_h - 16
                for pt, px, py, pw, phh in strip_split(s["parts"], 10, head_h, w - 20, ph, 6, horizontal=False):
                    txt = ""  # whole-document zoom: parts are shapes only; titles appear one zoom in
                    parts_html += box(px, py, pw, phh, f"border-radius: 10px; background: rgba(255,253,250,0.6); padding: 6px 8px; font-size: 13px; line-height: 1.3; color: {BODY}; overflow: hidden; text-align: left", txt)
                inner = f'<div style="position: absolute; left: 14px; top: 14px; right: 12px">{a_district_header(s, big=not compact)}</div>{parts_html}'
            else:
                hw = 210 if not compact else 170
                inner_parts = []
                rx, rw = hw, w - hw - 10
                r1 = s["parts"][:3]
                r2 = s["parts"][3:]
                rr1 = (h - 26) * sum(p[1] for p in r1) / s["words"]
                for pt, px, py, pw, phh in strip_split(r1, rx, 10, rw, rr1, 6):
                    inner_parts.append(box(px, py, pw, phh, f"border-radius: 10px; background: rgba(255,253,250,0.6); padding: 6px 8px; font-size: 13px; line-height: 1.3; color: {BODY}; overflow: hidden; text-align: left", ""))
                for pt, px, py, pw, phh in strip_split(r2, rx, 10 + rr1 + 6, rw, h - 26 - rr1, 6):
                    inner_parts.append(box(px, py, pw, phh, f"border-radius: 10px; background: rgba(255,253,250,0.6); padding: 6px 8px; font-size: 13px; line-height: 1.3; color: {BODY}; overflow: hidden; text-align: left", ""))
                inner = f'<div style="position: absolute; left: 14px; top: 14px; width: {hw - 28}px">{a_district_header(s, big=not compact)}</div>{"".join(inner_parts)}'
            outline = f"outline: 3px solid {INK}; outline-offset: 3px;" if (here and s["n"] == 2) else ""
            out.append(box(x, yy, w, h, f"border: none; padding: 0; border-radius: 14px; background: {HUE[s['n']]}; {outline} {FONT}; cursor: pointer", inner, tag="button", label=f"Section {s['n']}: {s['title']}"))
            if here and s["n"] == 2:
                out.append(here_tag(x + w - 110, yy - 14))
        y += rh + gap
    return "\n".join(out)


def a_section(W, H):
    s = SECTIONS[3]
    out = [crumb("Whole document  ›  04")]
    pad, top = 12, 52
    head = (f'<div style="position: absolute; left: {pad + 14}px; top: {top + 12}px; right: 20px; display: flex; align-items: baseline; gap: 12px">'
            f'<span style="{SERIF}; font-size: 30px; font-weight: 600; color: {INK}">04</span>'
            f'<span style="{SERIF}; font-size: 19px; line-height: 1.25; font-weight: 600; color: {INK}">{e(s["title"])}</span></div>')
    out.append(box(pad, top, W - 2 * pad, H - top - pad, f"border-radius: 16px; background: {HUE[4]}", ""))
    out.append(head)
    gx, gy, gw, gh = pad + 10, top + 92, W - 2 * pad - 20, H - top - pad - 102
    floor = lambda ps: [(p[0], max(p[1], 260)) for p in ps]
    r1, r2 = floor(s["parts"][:3]), floor(s["parts"][3:])
    h1 = gh * 0.42
    for pt, x, y, w, h in strip_split(r1, gx, gy, gw, h1, 8) + strip_split(r2, gx, gy + h1 + 8, gw, gh - h1 - 8, 8):
        inner = (f'<span style="font-size: 14px; line-height: 1.3; font-weight: 700; color: {INK}">{e(pt)}</span>'
                 + (f'<span style="font-size: 13px; line-height: 1.4; color: {MUTED}">{e(S4_HOOKS[pt])}</span>' if (h > 120 and w > 170) else ""))
        out.append(box(x, y, w, h, f"border: none; border-radius: 12px; background: {PANEL}; padding: 10px 12px; display: flex; flex-direction: column; gap: 6px; text-align: left; overflow: hidden; {FONT}", inner, tag="button", label=pt))
    return "\n".join(out)


def a_close(W, H):
    out = [crumb("…  ›  04  ›  Medication windows")]
    pad, top = 12, 52
    out.append(box(pad, top, W - 2 * pad, H - top - pad, f"border-radius: 16px; background: {HUE[4]}", ""))
    lis = "".join(f'<li style="font-size: 13.5px; line-height: 1.45; color: {BODY}">{e(p)}</li>' for p in MED["points"][:3])
    out.append(box(pad + 12, top + 12, W - 2 * pad - 24, 178, f"border-radius: 12px; background: {PANEL}; padding: 12px 14px; display: flex; flex-direction: column; gap: 8px",
                   f'<span style="{SERIF}; font-size: 18px; font-weight: 600; line-height: 1.25; color: {INK}">{e(MED["title"])}</span><ul style="margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 4px">{lis}</ul>'))
    y0 = top + 12 + 178 + 10
    for pt, x, y, w, h in strip_split([(p[0], 1) for p in MED["parts"]], pad + 12, y0, W - 2 * pad - 24, H - y0 - pad - 12, 8):
        part = next(p for p in MED["parts"] if p[0] == pt)
        inner = (f'<span style="font-size: 12px; color: {LABEL}">{part[2]} · source</span>'
                 f'<span style="font-size: 13px; line-height: 1.3; font-weight: 700; color: {INK}">{e(pt)}</span>'
                 f'<span style="font-size: 13px; line-height: 1.45; color: {BODY}; border-left: 2px solid {EDGE[4]}; padding-left: 8px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden">{e(part[3])}</span>')
        out.append(box(x, y, w, h, f"border: none; border-radius: 12px; background: rgba(255,253,250,0.75); padding: 10px 12px; display: flex; flex-direction: column; gap: 6px; text-align: left; overflow: hidden; {FONT}", inner, tag="button", label=pt))
    return "\n".join(out)


# ---------------------------------------------------------------- B: mind map
def b_node(x, y, w, h, s, here=False, small=False):
    outline = f"outline: 3px dashed {INK}; outline-offset: 5px;" if here else ""
    inner = (f'<span style="{SERIF}; font-size: {22 if not small else 18}px; font-weight: 600; color: {INK}">{nn(s["n"])}</span>'
             f'<span style="font-size: {14 if not small else 13}px; line-height: 1.3; font-weight: 700; color: {INK}; text-align: left">{e(s["title"] if not small else s["short"])}</span>')
    return box(x, y, w, h, f"border: none; border-radius: 16px; background: {HUE[s['n']]}; padding: 10px 14px; display: flex; gap: 10px; align-items: flex-start; {outline} {FONT}; z-index: 2", inner, tag="button", label=f"Section {s['n']}: {s['title']}")


def b_whole(W, H, here=True, compact=False):
    cx, cy = W / 2, H / 2
    rw, rh = (220, 96) if not compact else (180, 84)
    nw, nh = (230, 92) if not compact else (190, 64)
    pos = {1: (18, 30), 2: (W - nw - 18, 30), 3: (18, H - nh - 30), 4: (W - nw - 18, H - nh - 30)}
    lines, dots, nodes = [], [], []
    for s in SECTIONS:
        x, y = pos[s["n"]]
        ncx, ncy = x + nw / 2, y + nh / 2
        lines.append(f'<path d="M {cx:.0f} {cy:.0f} C {cx:.0f} {(cy + ncy) / 2:.0f}, {ncx:.0f} {(cy + ncy) / 2:.0f}, {ncx:.0f} {ncy:.0f}" stroke="{EDGE[s["n"]]}" stroke-width="3" fill="none"></path>')
        k = len(s["parts"])
        for i in range(k):
            dx = (i - (k - 1) / 2) * 34
            dy = (nh / 2 + 34) * (1 if s["n"] <= 2 else -1)
            px, py = ncx + dx, ncy + dy
            lines.append(f'<line x1="{ncx:.0f}" y1="{ncy:.0f}" x2="{px:.0f}" y2="{py:.0f}" stroke="{EDGE[s["n"]]}" stroke-width="1.5"></line>')
            dots.append(box(px - 9, py - 9, 18, 18, f"border-radius: 999px; background: {HUE[s['n']]}; box-shadow: 0 0 0 2px {EDGE[s['n']]}"))
        nodes.append(b_node(x, y, nw, nh, s, here=(here and s["n"] == 2), small=compact))
        if here and s["n"] == 2:
            nodes.append(here_tag(x + nw - 104, y + nh + 12 if s["n"] <= 2 else y - 40))
    root = box(cx - rw / 2, cy - rh / 2, rw, rh, f"border-radius: 999px; background: {INK}; color: {PANEL}; padding: 12px 20px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px; text-align: center; z-index: 2",
               f'<span style="font-size: 11.5px; font-weight: 700; letter-spacing: 0.08em; color: #E9DFD2">GIST</span><span style="{SERIF}; font-size: {17 if not compact else 15}px; line-height: 1.2; font-weight: 600">{e(ROOT_TITLE)}</span>')
    svg = f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" style="position: absolute; left: 0; top: 0" aria-hidden="true">{"".join(lines)}</svg>'
    return svg + "".join(dots) + root + "".join(nodes)


def b_section(W, H):
    s = SECTIONS[3]
    out = [crumb("Gist  ›  04")]
    hx, hy, hw, hh = 16, H / 2 - 70, 150, 140
    kids = s["parts"]
    lines = [f'<path d="M -20 60 C 20 60, 30 {hy + 20:.0f}, {hx + 40:.0f} {hy + 10:.0f}" stroke="{EDGE[4]}" stroke-width="3" fill="none" stroke-dasharray="6 6"></path>']
    cards = []
    ky = 54
    kh = (H - ky - 12 - 4 * 8) / 5
    for i, (pt, _) in enumerate(kids):
        x, y, w = 200, ky + i * (kh + 8), W - 200 - 12
        lines.append(f'<path d="M {hx + hw:.0f} {hy + hh / 2:.0f} C {hx + hw + 30:.0f} {hy + hh / 2:.0f}, {x - 30:.0f} {y + kh / 2:.0f}, {x:.0f} {y + kh / 2:.0f}" stroke="{EDGE[4]}" stroke-width="2" fill="none"></path>')
        inner = (f'<span style="font-size: 13.5px; line-height: 1.25; font-weight: 700; color: {INK}">{e(pt)}</span>'
                 f'<span style="font-size: 13px; line-height: 1.35; color: {MUTED}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{e(S4_HOOKS[pt])}</span>')
        cards.append(box(x, y, w, kh, f"border: 1.5px solid {EDGE[4]}; border-radius: 14px; background: {PANEL}; padding: 8px 12px; display: flex; flex-direction: column; gap: 3px; text-align: left; overflow: hidden; {FONT}; z-index: 2", inner, tag="button", label=pt))
    node = box(hx, hy, hw, hh, f"border-radius: 18px; background: {HUE[4]}; padding: 12px 14px; display: flex; flex-direction: column; gap: 6px; z-index: 2",
               f'<span style="{SERIF}; font-size: 28px; font-weight: 600; line-height: 1; color: {INK}">04</span><span style="font-size: 13px; line-height: 1.3; font-weight: 700; color: {INK}">Weak constructs, medication windows and design rules</span>')
    svg = f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" style="position: absolute; left: 0; top: 0" aria-hidden="true">{"".join(lines)}</svg>'
    return svg + node + "".join(cards) + "".join(out)


def b_close(W, H):
    out = [crumb("Gist  ›  04  ›  Medication windows")]
    lis = "".join(f'<li style="font-size: 13.5px; line-height: 1.45; color: {BODY}">{e(p)}</li>' for p in MED["points"][:3])
    cx, cy, cw, ch = 60, 56, W - 120, 190
    lines = []
    kids = MED["parts"]
    kw = (W - 24 - 2 * 10) / 3
    for i, (pt, _, prov, text) in enumerate(kids):
        x, y = 12 + i * (kw + 10), 300
        lines.append(f'<path d="M {cx + cw / 2:.0f} {cy + ch:.0f} C {cx + cw / 2:.0f} {cy + ch + 30:.0f}, {x + kw / 2:.0f} {y - 30:.0f}, {x + kw / 2:.0f} {y:.0f}" stroke="{EDGE[4]}" stroke-width="2" fill="none"></path>')
        out.append(box(x, y, kw, H - y - 12, f"border: 1.5px solid {EDGE[4]}; border-radius: 14px; background: {PANEL}; padding: 10px 12px; display: flex; flex-direction: column; gap: 5px; text-align: left; overflow: hidden; {FONT}; z-index: 2",
                       f'<span style="font-size: 12px; color: {LABEL}">{prov} · source</span><span style="font-size: 13px; line-height: 1.3; font-weight: 700; color: {INK}">{e(pt)}</span>', tag="button", label=pt))
    node = box(cx, cy, cw, ch, f"border-radius: 18px; background: {HUE[4]}; padding: 12px 16px; display: flex; flex-direction: column; gap: 8px; z-index: 2",
               f'<span style="{SERIF}; font-size: 17px; font-weight: 600; line-height: 1.25; color: {INK}">{e(MED["title"])}</span><ul style="margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 4px">{lis}</ul>')
    svg = f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" style="position: absolute; left: 0; top: 0" aria-hidden="true">{"".join(lines)}</svg>'
    return svg + node + "".join(out)


# ---------------------------------------------------------------- C: card canvas
def lines_for(text, width, px=13):
    import math
    cpl = max(8, (width - 24) / (px * 0.6))
    return math.ceil(len(text) / cpl)


def c_whole(W, H, here=True, compact=False):
    pad, gap = 12, 10
    cw = (W - 2 * pad - 3 * gap) / 4
    out = []
    for i, s in enumerate(SECTIONS):
        x = pad + i * (cw + gap)
        hh = 112 if not compact else 92
        outline = f"outline: 3px solid {INK}; outline-offset: 4px;" if (here and s["n"] == 2) else ""
        out.append(box(x, pad, cw, hh, f"border: none; border-radius: 14px; background: {HUE[s['n']]}; padding: 10px 12px; display: flex; flex-direction: column; gap: 4px; text-align: left; {outline} {FONT}",
                       f'<span style="{SERIF}; font-size: 26px; line-height: 1; font-weight: 600; color: {INK}">{nn(s["n"])}</span><span style="font-size: 13px; line-height: 1.25; font-weight: 700; color: {INK}">{e(s["short"])}</span>', tag="button", label=f"Section {s['n']}: {s['title']}"))
        y = pad + hh + 10
        for pt, words in s["parts"]:
            h = (22 + lines_for(pt, cw) * 17 + words * 0.03) if not compact else (24 + words * 0.07)
            txt = f'<span style="font-size: 13px; line-height: 1.3; color: {BODY}">{e(pt)}</span>' if not compact else ""
            ring = f"box-shadow: 0 0 0 2.5px {INK};" if (here and s["n"] == 2) else f"box-shadow: inset 0 0 0 1px {BORDER};"
            out.append(box(x, y, cw, h, f"border: none; border-radius: 12px; background: {PANEL}; padding: 8px 10px; border-top: 5px solid {HUE[s['n']]}; {ring} text-align: left; overflow: hidden; {FONT}", txt, tag="button", label=pt))
            y += h + 8
        if here and s["n"] == 2:
            out.append(here_tag(x + cw / 2 - 52, y + 4))
    return "\n".join(out)


def c_section(W, H):
    s = SECTIONS[3]
    out = [crumb("Canvas  ›  04")]
    peek = box(-60, 60, 90, 300, f"border-radius: 12px; background: {PANEL}; border-top: 5px solid {HUE[3]}; opacity: 0.55", "")
    out.append(peek)
    x0, cw = 44, W - 44 - 12
    out.append(box(x0, 52, cw, 62, f"border-radius: 14px; background: {HUE[4]}; padding: 10px 14px; display: flex; gap: 10px; align-items: center",
                   f'<span style="{SERIF}; font-size: 26px; font-weight: 600; color: {INK}">04</span><span style="font-size: 14px; line-height: 1.3; font-weight: 700; color: {INK}">{e(s["title"])}</span>'))
    colw = (cw - 10) / 2
    ys = [124, 124]
    for i, (pt, words) in enumerate(s["parts"]):
        c = 0 if ys[0] <= ys[1] else 1
        h = 24 + lines_for(pt, colw, 13.5) * 18 + lines_for(S4_HOOKS[pt], colw) * 18
        inner = (f'<span style="font-size: 13.5px; line-height: 1.25; font-weight: 700; color: {INK}">{e(pt)}</span>'
                 f'<span style="font-size: 13px; line-height: 1.35; color: {MUTED}">{e(S4_HOOKS[pt])}</span>')
        out.append(box(x0 + c * (colw + 10), ys[c], colw, h, f"border: none; border-radius: 12px; background: {PANEL}; border-top: 5px solid {HUE[4]}; box-shadow: inset 0 0 0 1px {BORDER}; padding: 8px 12px; display: flex; flex-direction: column; gap: 4px; text-align: left; overflow: hidden; {FONT}", inner, tag="button", label=pt))
        ys[c] += h + 10
    return "\n".join(out)


def c_close(W, H):
    out = [crumb("Canvas  ›  04  ›  Medication windows")]
    lis = "".join(f'<li style="font-size: 13.5px; line-height: 1.45; color: {BODY}">{e(p)}</li>' for p in MED["points"][:3])
    out.append(box(24, 52, W - 48, 176, f"border-radius: 14px; background: {PANEL}; border-top: 6px solid {HUE[4]}; box-shadow: 0 0 0 2.5px {INK}, 0 14px 30px rgba(42,37,33,0.12); padding: 12px 16px; display: flex; flex-direction: column; gap: 8px",
                   f'<span style="{SERIF}; font-size: 17px; font-weight: 600; line-height: 1.25; color: {INK}">{e(MED["title"])}</span><ul style="margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 3px">{lis}</ul>'))
    kw = (W - 48 - 16) / 3
    for i, (pt, _, prov, text) in enumerate(MED["parts"]):
        out.append(box(24 + i * (kw + 8), 242, kw, H - 242 - 14, f"border: none; border-radius: 12px; background: {PANEL}; box-shadow: inset 0 0 0 1px {BORDER}; padding: 10px 12px; display: flex; flex-direction: column; gap: 5px; text-align: left; overflow: hidden; {FONT}",
                       f'<span style="font-size: 12px; color: {LABEL}">{prov} · source</span><span style="font-size: 13px; line-height: 1.3; font-weight: 700; color: {INK}">{e(pt)}</span><span style="font-size: 13px; line-height: 1.45; color: {BODY}; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden">{e(text)}</span>', tag="button", label=pt))
    return "\n".join(out)


def main():
    SW, SH = 464, 440
    boards = {
        "Map-A-Regions.dc.html": board(
            "Map A: region map", a_whole(580, 688), "Whole document · 4 sections",
            [("1 · Whole document", "Four districts, sized by length and in reading order. The number and colour are the landmark.", a_whole(SW, SH, here=False, compact=True)),
             ("2 · One section", "Zoomed into 04: its five parts become districts with a one-line summary each.", a_section(SW, SH)),
             ("3 · Close up", "Into one part: its bullets, then the original paragraphs it came from.", a_close(SW, SH))],
            "Text never shrinks below reading size; each region swaps title → summary → bullets → source as you zoom."),
        "Map-B-MindMap.dc.html": board(
            "Map B: mind map", b_whole(580, 688), "Whole document · 4 sections",
            [("1 · Whole document", "The gist in the middle, sections branching out, with a dot for each part.", b_whole(SW, SH, here=False, compact=True)),
             ("2 · One section", "Zoomed into 04: its parts fan out to the right with their one-line summaries.", b_section(SW, SH)),
             ("3 · Close up", "One part in the middle with its bullets; its source paragraphs hang below.", b_close(SW, SH))],
            "The branches show how ideas connect; the dashed line leads back to the gist."),
        "Map-C-Cards.dc.html": board(
            "Map C: card canvas", c_whole(580, 688), "Whole document · 4 sections",
            [("1 · Whole document", "One column per section; cards are taller for longer parts.", c_whole(SW, SH, here=False, compact=True)),
             ("2 · One section", "Zoomed into 04: its cards show their one-line summaries.", c_section(SW, SH)),
             ("3 · Close up", "One card opened: its bullets, with its source cards underneath.", c_close(SW, SH))],
            "Cards could later be dragged around; this version keeps them in reading order."),
    }
    for name, html in boards.items():
        (ROOT / name).write_text(html, encoding="utf-8")
        print("wrote", name, len(html))


if __name__ == "__main__":
    main()
