import json, sys
OUT = __import__('os').environ.get('RIEMANN_CANVAS_OUT', '/tmp/riemann-canvas/project')

def lum(h):
    h = h.lstrip('#'); r, g, b = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
def cr(a, b):
    la, lb = sorted([lum(a), lum(b)], reverse=True); return (la + 0.05) / (lb + 0.05)

THEMES = {
 "Studio": dict(name="Warm Studio", note="cream, terracotta, Fraunces over Work Sans, soft 20px corners",
   bg="#F7F1E8", panel="#FFFBF5", border="#E7DCCB", text="#1F1A15", body="#2E2822", muted="#5B5147", label="#6E6256",
   accent="#B4441A", onAccent="#FFFFFF", soft="#F6E3D6", softText="#5A220C", deep="#3B2417", deepText="#FFFFFF", deepSub="#F2D8C8", deepLabel="#F0B99A",
   display="Fraunces", body_font="Work Sans", ui="Work Sans", fonts="family=Fraunces:opsz,wght@9..144,600&amp;family=Work+Sans:wght@400;600;700",
   radius=20, btn=999, chip="#F1E7DA"),
 "Nordic": dict(name="Nordic Slate", note="cool grey-blue, indigo, IBM Plex Sans + Serif, crisp 6px corners",
   bg="#EEF2F6", panel="#FFFFFF", border="#D5DDE7", text="#0F172A", body="#1E293B", muted="#475569", label="#56647A",
   accent="#4338CA", onAccent="#FFFFFF", soft="#E0E7FF", softText="#1E1B6B", deep="#1E1B4B", deepText="#FFFFFF", deepSub="#C7D2FE", deepLabel="#A5B4FC",
   display="IBM Plex Serif", body_font="IBM Plex Serif", ui="IBM Plex Sans", fonts="family=IBM+Plex+Serif:wght@400;600&amp;family=IBM+Plex+Sans:wght@400;600;700",
   radius=6, btn=6, chip="#E2E8F0"),
 "Editorial": dict(name="Paper Mono", note="white and black ink, one vermilion accent, mono labels, square corners",
   bg="#FFFFFF", panel="#FFFFFF", border="#111111", text="#111111", body="#1A1A1A", muted="#3D3D3D", label="#4A4A4A",
   accent="#D13F1C", onAccent="#FFFFFF", soft="#FFE9E2", softText="#6E1C08", deep="#111111", deepText="#FFFFFF", deepSub="#E6E6E6", deepLabel="#FF9A7E",
   display="Source Serif 4", body_font="Source Serif 4", ui="IBM Plex Mono", fonts="family=Source+Serif+4:opsz,wght@8..60,400;8..60,700&amp;family=IBM+Plex+Mono:wght@400;600",
   radius=0, btn=0, chip="#F2F2F2"),
 "Lavender": dict(name="Lavender Calm", note="soft violet, DM Sans over Lora, gentle and low-contrast chrome",
   bg="#F6F4FC", panel="#FFFFFF", border="#E4DFF5", text="#1E1633", body="#2B2340", muted="#554B6E", label="#62587C",
   accent="#6D28D9", onAccent="#FFFFFF", soft="#EDE5FD", softText="#3B1285", deep="#2E1065", deepText="#FFFFFF", deepSub="#DDD0FB", deepLabel="#C4B1F7",
   display="Lora", body_font="Lora", ui="DM Sans", fonts="family=Lora:wght@400;600&amp;family=DM+Sans:wght@400;600;700",
   radius=14, btn=999, chip="#EFEBF9"),
 "Midnight": dict(name="Midnight Ink", note="dark ink-blue, sky accent, Manrope over Newsreader (dark)",
   bg="#0F141B", panel="#151C25", border="#263140", text="#EEF2F7", body="#D6DDE7", muted="#A7B2C2", label="#94A1B3",
   accent="#7DD3FC", onAccent="#062235", soft="#16324A", softText="#DDF3FF", deep="#0B2A40", deepText="#FFFFFF", deepSub="#C4E6F8", deepLabel="#7DD3FC",
   display="Newsreader", body_font="Newsreader", ui="Manrope", fonts="family=Newsreader:opsz,wght@6..72,400;6..72,600&amp;family=Manrope:wght@400;600;700",
   radius=14, btn=999, chip="#1B2430"),
 "Forest": dict(name="Forest Dusk", note="deep green, amber accent, Space Grotesk over Literata (dark)",
   bg="#0F1D17", panel="#15261E", border="#27402F", text="#EEF3EC", body="#D4DFD2", muted="#A9BBA8", label="#97AE98",
   accent="#F5B942", onAccent="#1E1504", soft="#243A2B", softText="#FCE6B5", deep="#2B2208", deepText="#FFF6E0", deepSub="#EED9A8", deepLabel="#F5B942",
   display="Space Grotesk", body_font="Literata", ui="Space Grotesk", fonts="family=Space+Grotesk:wght@500;700&amp;family=Literata:opsz,wght@7..72,400",
   radius=10, btn=10, chip="#1B3024"),
}

def check(k, t):
    pairs = [("text", "bg"), ("body", "bg"), ("muted", "bg"), ("label", "bg"), ("label", "panel"), ("text", "panel"), ("body", "panel"),
             ("onAccent", "accent"), ("softText", "soft"), ("deepText", "deep"), ("deepSub", "deep"), ("deepLabel", "deep"),
             ("text", "chip"), ("muted", "panel")]
    bad = [(a, b, round(cr(t[a], t[b]), 2)) for a, b in pairs if cr(t[a], t[b]) < 4.5]
    if t["accent"] and cr(t["accent"], t["bg"]) < 3: bad.append(("accent-as-text/UI", "bg", round(cr(t["accent"], t["bg"]), 2)))
    return bad

def board(k, t):
    R, B = t["radius"], t["btn"]
    ui, disp, bod = t["ui"], t["display"], t["body_font"]
    mono_up = "letter-spacing: 0.08em"
    sec = lambda n, title, cur=False: (
      f'<a href="#" aria-current="true" style="display: flex; gap: 12px; padding: 12px; border-radius: {min(R,12)}px; text-decoration: none; color: {t["softText"]}; background: {t["soft"]}; box-shadow: inset 3px 0 0 {t["accent"]}; font-weight: 600"><span style="font-weight: 700; color: {t["softText"]}">{n}</span><span>{title}</span></a>'
      if cur else
      f'<a href="#" style="display: flex; gap: 12px; padding: 12px; border-radius: {min(R,12)}px; text-decoration: none; color: {t["body"]}"><span style="font-weight: 700; color: {t["label"]}">{n}</span><span>{title}</span></a>')
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Command centre: {t["name"]}</title>
<script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?{t["fonts"]}&amp;display=swap" rel="stylesheet">
<style>
body{{margin:0;font-family:'{ui}',sans-serif;background:{t["bg"]}}}
a{{color:{t["accent"]}}}a:hover{{color:{t["accent"]}}}
</style>
</helmet>
<div style="width: 1600px; height: 900px; box-sizing: border-box; background: {t["bg"]}; display: grid; grid-template-columns: 300px minmax(0, 1fr) 380px; grid-template-rows: 72px minmax(0, 1fr); font-family: '{ui}', sans-serif; color: {t["text"]}">

<header style="grid-column: 1 / 4; display: flex; align-items: center; gap: 18px; padding: 0 32px; background: {t["panel"]}; border-bottom: 1px solid {t["border"]}">
<button type="button" aria-label="Back to the gist" style="width: 44px; height: 44px; border-radius: {min(B,12)}px; border: 1px solid {t["border"]}; background: {t["chip"]}; color: {t["text"]}; font-size: 18px">⌂</button>
<div style="display: flex; flex-direction: column; gap: 2px; min-width: 0">
<span style="font-size: 12px; font-weight: 700; {mono_up}; color: {t["label"]}">HOW THE INTERNET ACTUALLY MOVES YOUR DATA</span>
<span style="font-family: '{disp}', serif; font-size: 17px; color: {t["text"]}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">Turn “the internet is broken” into a specific, answerable question.</span>
</div>
<div style="flex-grow: 1"></div>
<div style="display: flex; align-items: center; gap: 6px; padding: 6px; border-radius: {B}px; background: {t["chip"]}; border: 1px solid {t["border"]}">
<button type="button" aria-label="Less detail" style="height: 36px; padding: 0 14px; border-radius: {B}px; border: 1px solid {t["border"]}; background: {t["panel"]}; color: {t["text"]}; font-family: '{ui}', sans-serif; font-size: 14px; font-weight: 600">− Less</button>
<span style="font-size: 13px; color: {t["muted"]}; padding: 0 6px">~3 min · 49% of original</span>
<button type="button" aria-label="More detail" style="height: 36px; padding: 0 14px; border-radius: {B}px; border: none; background: {t["accent"]}; color: {t["onAccent"]}; font-family: '{ui}', sans-serif; font-size: 14px; font-weight: 700">More +</button>
</div>
</header>

<nav aria-label="Sections" style="padding: 28px 20px 28px 32px; display: flex; flex-direction: column; gap: 6px; border-right: 1px solid {t["border"]}; background: {t["panel"]}; font-size: 15px">
<span style="font-size: 12px; font-weight: 700; {mono_up}; color: {t["label"]}; padding: 0 12px 8px">SECTIONS</span>
{sec("01","Not one pipe, but a mesh")}
{sec("02","Why your video call stutters")}
{sec("03","When a site won't load, suspect DNS", True)}
{sec("04","Speed vs. certainty")}
{sec("05","Diagnose it yourself")}
<div style="flex-grow: 1"></div>
<p style="margin: 0; padding: 12px; font-size: 13px; line-height: 1.5; color: {t["muted"]}">Hold <strong style="color: {t["text"]}">Z</strong> and move the mouse over any passage to open it up or fold it away.</p>
</nav>

<main style="overflow: hidden; padding: 36px 48px 0; display: flex; flex-direction: column; gap: 18px">
<span style="font-size: 13px; font-weight: 700; letter-spacing: 0.1em; color: {t["label"]}"><span style="color: {t["accent"] if lum(t["bg"])<0.2 else t["softText"]}">03</span> · NAMES &amp; RELIABILITY</span>
<h1 style="margin: 0; font-family: '{disp}', serif; font-size: 46px; line-height: 1.1; font-weight: 600; color: {t["text"]}">When a site won't load, suspect DNS</h1>
<p style="margin: 0; font-size: 19px; line-height: 1.55; color: {t["muted"]}; max-width: 780px">Names become addresses through a hierarchy, and TCP makes delivery reliable on top of an IP layer that promises nothing.</p>
<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 36px; margin-top: 8px">
<section style="display: flex; flex-direction: column; gap: 10px">
<h2 style="margin: 0; font-size: 17px; font-weight: 700; color: {t["text"]}">Names → numbers</h2>
<p style="margin: 0; font-family: '{bod}', serif; font-size: 17px; line-height: 1.65; color: {t["body"]}">Nobody wants to type a string of numbers to visit a website, so the internet layers a naming system, the Domain Name System or DNS, on top of raw IP addresses. When you type a domain name into a browser, your computer asks a DNS resolver to translate that name into an IP address before any connection can be made. This lookup is usually invisible and fast, cached at several levels, but it is also a common point of failure: <strong style="color: {t["text"]}">if DNS is broken or blocked, a website can be completely unreachable even though the server hosting it is running fine.</strong></p>
</section>
<section style="display: flex; flex-direction: column; gap: 10px">
<h2 style="margin: 0; font-size: 17px; font-weight: 700; color: {t["text"]}">A hierarchy, so no server stores everything</h2>
<p style="margin: 0; font-family: '{bod}', serif; font-size: 17px; line-height: 1.65; color: {t["body"]}">DNS is organized as a hierarchy. At the top are root servers that know which servers are authoritative for each top-level domain, such as .com or .org. Those servers in turn know which servers are authoritative for individual domains, and so on down to the specific record for a given subdomain. This structure means no single server needs to store the whole internet's worth of names, and it is part of why the naming system has scaled from a few hundred hosts in the 1980s to billions of names today.</p>
</section>
</div>
</main>

<aside style="padding: 36px 32px 0 0; display: flex; flex-direction: column; gap: 16px; overflow: hidden">
<div style="background: {t["deep"]}; color: {t["deepText"]}; border-radius: {R}px; padding: 22px 24px; display: flex; flex-direction: column; gap: 6px">
<span style="font-size: 12px; font-weight: 700; {mono_up}; color: {t["deepLabel"]}">KEY FACT</span>
<span style="font-family: '{disp}', serif; font-size: 34px; font-weight: 600; line-height: 1.1">Hundreds → billions</span>
<span style="font-size: 14px; line-height: 1.5; color: {t["deepSub"]}">DNS grew from a few hundred hosts in the 1980s to billions of names today.</span>
</div>
<div style="background: {t["panel"]}; border: 1px solid {t["border"]}; border-radius: {R}px; padding: 20px 24px; display: flex; flex-direction: column; gap: 12px">
<span style="font-size: 12px; font-weight: 700; {mono_up}; color: {t["label"]}">HOW A NAME IS FOUND</span>
<div style="display: flex; flex-direction: column; gap: 8px; font-size: 14px; color: {t["text"]}">
<span style="padding: 8px 12px; border-radius: {min(R,8)}px; background: {t["chip"]}">Root servers</span>
<span style="padding-left: 12px; color: {t["muted"]}">↓</span>
<span style="padding: 8px 12px; border-radius: {min(R,8)}px; background: {t["chip"]}">.com / .org servers</span>
<span style="padding-left: 12px; color: {t["muted"]}">↓</span>
<span style="padding: 8px 12px; border-radius: {min(R,8)}px; background: {t["soft"]}; color: {t["softText"]}; font-weight: 600">The domain's own servers → the record</span>
</div>
</div>
<div style="background: {t["panel"]}; border: 1px solid {t["border"]}; border-radius: {R}px; padding: 20px 24px; display: flex; flex-direction: column; gap: 8px">
<span style="font-size: 12px; font-weight: 700; {mono_up}; color: {t["label"]}">UP NEXT · 04</span>
<span style="font-family: '{disp}', serif; font-size: 21px; font-weight: 600; color: {t["text"]}">Speed vs. certainty</span>
<span style="font-size: 14px; line-height: 1.5; color: {t["muted"]}">UDP drops late packets instead of waiting; TLS encrypts and verifies who you're talking to.</span>
</div>
</aside>

</div>
</x-dc>
<script type="text/x-dc" data-dc-script data-props='{{"$preview":{{"width":1600,"height":900}}}}'>
class Component extends DCLogic {{
renderVals() {{
return {{}};
}}
}}
</script>
</body>
</html>
'''

failed = False
for k, t in THEMES.items():
    bad = check(k, t)
    if bad:
        failed = True; print("CONTRAST FAIL", k, bad)
if failed: sys.exit(1)
for k, t in THEMES.items():
    open(f"{OUT}/Theme-{k}.dc.html", "w").write(board(k, t))
json.dump({k: {kk: vv for kk, vv in t.items() if kk not in ("fonts",)} for k, t in THEMES.items()}, open(__import__('os').path.join(__import__('os').path.dirname(__file__), 'theme-tokens.json'), 'w'), indent=1)
print("wrote", list(THEMES))
