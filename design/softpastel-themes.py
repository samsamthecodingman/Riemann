from importlib import import_module
main = import_module("command-centre-themes").main  # sibling module
F = "family=Fraunces:opsz,wght@9..144,600&amp;family=Work+Sans:wght@400;600;700"
base = dict(display="Fraunces", body_font="Work Sans", ui="Work Sans", fonts=F, radius=20, btn=999)
SOFT = {
 "Macaron": dict(base, name="Macaron", note="cream ground, five macaron pastels (blush, butter, sage, sky, lilac), ink buttons",
   bg="#FBF7F2", panel="#FFFDFA", border="#ECE4D8", text="#2A2521", body="#38312B", muted="#5E554C", label="#6B6157",
   accent="#2A2521", onAccent="#FFFDFA", soft="#F7E8B5", softText="#2A2521",
   deep="#F7E8B5", deepText="#2A2521", deepSub="#3E362E", deepLabel="#5A4E3F",
   chip="#F3EEE6", flow="#D3E4F2", mark="#F7E8B5",
   sections=["#F6D5D1", "#D5E6CF", "#F7E8B5", "#D3E4F2", "#E2D8F0"]),
 "Seaside": dict(base, name="Seaside", note="off-white, seafoam / sand / shell / powder blue / pistachio, slate-blue buttons",
   bg="#F6F8F7", panel="#FFFFFF", border="#DDE5E2", text="#1F2A2E", body="#2A363B", muted="#51606A", label="#5A6973",
   accent="#3F5A73", onAccent="#FFFFFF", soft="#CFE8E1", softText="#1F2A2E",
   deep="#D6E3F3", deepText="#1F2A2E", deepSub="#2F3E4E", deepLabel="#44576B",
   chip="#EDF2F1", flow="#F1E4CC", mark="#CFE8E1",
   sections=["#CFE8E1", "#F1E4CC", "#F4D3CB", "#D6E3F3", "#E1ECCB"]),
 "Watercolour": dict(base, name="Watercolour", note="warm white, peach / mint / periwinkle / rose / lemon chiffon, pastel buttons",
   bg="#FAF8F5", panel="#FFFFFF", border="#E9E2D9", text="#26232A", body="#332F37", muted="#5A5560", label="#65606B",
   accent="#D9DDF4", onAccent="#26232A", accentEdge="#7B82AB", soft="#F1D6E0", softText="#26232A",
   deep="#D2EBDD", deepText="#1F2C25", deepSub="#2E3E35", deepLabel="#41554A",
   chip="#F2EEE9", flow="#F5EEC2", mark="#F5EEC2",
   sections=["#F3D9C6", "#D2EBDD", "#D9DDF4", "#F1D6E0", "#F5EEC2"]),
}
main(SOFT, "softpastel-tokens.json")
