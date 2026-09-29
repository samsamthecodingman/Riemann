from importlib import import_module
main = import_module("command-centre-themes").main  # sibling module
F = "family=Fraunces:opsz,wght@9..144,600&amp;family=Work+Sans:wght@400;600;700"
base = dict(display="Fraunces", body_font="Work Sans", ui="Work Sans", fonts=F, radius=20, btn=999)
PASTEL = {
 "Sorbet": dict(base, name="Peach Sorbet", note="peach ground, coral buttons, mint key-fact pop",
   bg="#FFF1E8", panel="#FFFAF6", border="#F6D9C8", text="#2A1510", body="#3A221A", muted="#6B4636", label="#7A4E3C",
   accent="#FF6B4A", onAccent="#2A0A02", accentEdge="#B3321A", soft="#FFD6C7", softText="#5C1A08",
   deep="#5EE0B5", deepText="#06281D", deepSub="#0B3A2B", deepLabel="#0A4A35",
   chip="#FFE6DA", flow="#D6F7EA", mark="#FFC8B5"),
 "Mango": dict(base, name="Mint & Mango", note="mint ground, mango buttons, teal key-fact pop",
   bg="#EDFAF4", panel="#F8FFFB", border="#CDEFE0", text="#0E2A21", body="#16362B", muted="#3B5E52", label="#3F6557",
   accent="#FFB21E", onAccent="#2B1A00", accentEdge="#9A5B00", soft="#FFE7B3", softText="#5A3A00",
   deep="#18C1A8", deepText="#032B25", deepSub="#053A32", deepLabel="#053A32",
   chip="#DDF5EA", flow="#FFF0CC", mark="#FFE08A"),
 "Bubblegum": dict(base, name="Bubblegum Lilac", note="lilac ground, hot-pink buttons, sky-blue key-fact pop",
   bg="#F6F0FF", panel="#FCFAFF", border="#E5D9FA", text="#231433", body="#2F1F42", muted="#584A6E", label="#5F5178",
   accent="#FF4FA3", onAccent="#3A0322", accentEdge="#B8196B", soft="#FFD3E9", softText="#6A0B3E",
   deep="#6CC4FF", deepText="#04243D", deepSub="#06324F", deepLabel="#0A3F63",
   chip="#EFE6FD", flow="#DDF0FF", mark="#FFC2E0"),
 "Citrus": dict(base, name="Citrus Sky", note="sky ground, electric-blue buttons, lemon key-fact pop",
   bg="#EEF5FF", panel="#FAFCFF", border="#D3E3FA", text="#0D1B33", body="#15243F", muted="#3C4E6E", label="#415478",
   accent="#2F5BFF", onAccent="#FFFFFF", soft="#D9E3FF", softText="#0B2378",
   deep="#FFE14D", deepText="#2B2300", deepSub="#3D3200", deepLabel="#4A3C00",
   chip="#E3EDFD", flow="#FFF6C2", mark="#FFEA7A"),
}
main(PASTEL, "pastel-tokens.json")
