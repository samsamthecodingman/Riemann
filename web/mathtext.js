// mathtext.js
// -----------------------------------------------------------------------
// Finds LaTeX maths in plain text so the reader can render it (KaTeX, when it
// loaded) without markdown touching it. Pure: no DOM, runs under Node for tests.
//
//   MathText.split("The area is $\\pi r^2$ but $5 and $10 are prices.")
//     -> { text: "The area is 0 but $5 and $10 are prices.",
//          maths: [{ src: "$\\pi r^2$", tex: "\\pi r^2", display: false }] }
//
// Each maths is replaced by a private-use token ( index ) that
// survives markdown and escaping; restore() swaps the tokens back for markup.
//
// What counts as maths:
//   $$...$$   display maths, may span lines
//   $...$     inline maths on one line, only when ALL of these hold:
//     - the opening $ is not directly after a letter or digit (so US$5 is not),
//       and is followed by a character that is not a space or another $
//     - the closing $ is not directly after a space (so "$5 and $10" is not) and is
//       not directly followed by a digit (so "$5-$10" is not)
//     - the inside has a letter, a backslash, ^, _ or = (a bare "$5$" is not)
// Escaped \$ and anything inside code (`...` or a fenced block) is left alone.
// -----------------------------------------------------------------------
(function () {
  "use strict";

  const OPEN = "";
  const CLOSE = "";
  const MAX_INLINE = 500;
  const MAX_DISPLAY = 4000;

  function protectedRanges(src) {
    const out = [];
    const fence = /(^|\n)[ \t]*(```|~~~)[^\n]*\n[\s\S]*?(?:\n[ \t]*\2[^\n]*(?=\n|$)|$)/g;
    let m;
    while ((m = fence.exec(src))) out.push([m.index + (m[1] ? 1 : 0), fence.lastIndex]);
    const inline = /(`+)(?!`)[\s\S]*?[^`]\1(?!`)|(`+)(?!`)\2(?!`)/g;
    while ((m = inline.exec(src))) {
      const a = m.index;
      if (!out.some(([s, e]) => a >= s && a < e)) out.push([a, inline.lastIndex]);
    }
    return out.sort((x, y) => x[0] - y[0]);
  }

  const isAlnum = (c) => !!c && /[A-Za-z0-9]/.test(c);
  const isSpace = (c) => !c || /\s/.test(c);

  function split(source) {
    const src = String(source == null ? "" : source).replace(/[]/g, "");
    if (src.indexOf("$") === -1) return { text: src, maths: [] };
    const prot = protectedRanges(src);
    const protectedAt = (i) => prot.find(([s, e]) => i >= s && i < e);
    const maths = [];
    let out = "";
    let i = 0;
    while (i < src.length) {
      const pr = protectedAt(i);
      if (pr) {
        out += src.slice(i, pr[1]);
        i = pr[1];
        continue;
      }
      const c = src[i];
      if (c === "\\") {
        out += src.slice(i, i + 2);
        i += 2;
        continue;
      }
      if (c !== "$") {
        out += c;
        i += 1;
        continue;
      }
      let end = -1;
      let display = false;
      if (src[i + 1] === "$") {
        // display: $$ ... $$
        let j = i + 2;
        while (j < src.length && j - i < MAX_DISPLAY) {
          if (src[j] === "\\") {
            j += 2;
            continue;
          }
          if (protectedAt(j)) break;
          if (src[j] === "$" && src[j + 1] === "$") {
            if (src.slice(i + 2, j).trim()) {
              end = j + 2;
              display = true;
            }
            break;
          }
          j += 1;
        }
      } else if (!isAlnum(src[i - 1]) && !isSpace(src[i + 1])) {
        let j = i + 1;
        while (j < src.length && j - i <= MAX_INLINE) {
          const d = src[j];
          if (d === "\n" || protectedAt(j)) break;
          if (d === "\\") {
            j += 2;
            continue;
          }
          if (d === "$") {
            const inner = src.slice(i + 1, j);
            if (!isSpace(src[j - 1]) && !/[0-9]/.test(src[j + 1] || "") && /[A-Za-z\\^_=]/.test(inner)) end = j + 1;
            break;
          }
          j += 1;
        }
      }
      if (end < 0) {
        out += "$";
        i += 1;
        if (src[i] === "$" && src[i - 1] === "$") {
          // a failed "$$": keep both characters literal so the second is not tried as an opener
          out += "$";
          i += 1;
        }
        continue;
      }
      const whole = src.slice(i, end);
      maths.push({ src: whole, tex: display ? whole.slice(2, -2).trim() : whole.slice(1, -1), display });
      out += OPEN + (maths.length - 1) + CLOSE;
      i = end;
    }
    return { text: out, maths };
  }

  // Swap tokens back for markup: html is the text after markdown; make(item) returns the markup.
  function restore(html, maths, make) {
    if (!maths || !maths.length) return html;
    return String(html).replace(/(\d+)/g, (all, n) => (maths[+n] ? make(maths[+n]) : all));
  }

  window.MathText = { split, restore };
})();
