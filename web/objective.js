// Reader goal ("What's this for?"): the chip list and a cheap, local
// heuristic that suggests one from a document's title, format and opening
// text. No model call. Loaded before app.js; also require()able from node
// (tests/test_objective.py).
(function (root) {
  // Keys match research/ledger/objectives.json and build.OBJECTIVE_FOCUS.
  const OBJECTIVES = [
    { key: "learn", label: "Learn it" },
    { key: "execute", label: "Do it" },
    { key: "decide", label: "Decide" },
    { key: "reference", label: "Look it up" },
    { key: "plan", label: "Plan" },
    { key: "communicate", label: "Reply" },
  ];

  // [regex, weight]. Title hits count double (see suggestObjective).
  const RULES = {
    execute: [
      [/\bassignments?\b/i, 3], [/\bdue(?!\s+to\b)\b/i, 2], [/\bmarks\b|\b(?:final|total|your) mark\b|\bmarking\b/i, 2], [/\brubric\b/i, 3],
      [/\bsubmit\b|\bsubmission\b/i, 3], [/\bdeliverables?\b/i, 3], [/\bmarking criteria\b/i, 3],
      [/\bword limit\b|\bword count\b/i, 2], [/\bworth \d+\s*%|\b\d+\s*% of (?:your|the) (?:grade|mark|unit)/i, 3],
      [/\bassessment task\b|\b(?:project|assignment|task|assessment|design|creative) brief\b/i, 2], [/\bmust (?:include|submit|complete)\b/i, 1],
    ],
    communicate: [
      [/^(?:from|to|subject|cc|sent):/im, 3], [/^(?:hi|hello|hey|dear)\b[^\n]{0,40},/im, 3],
      [/\b(?:kind |best )?regards\b|\bcheers,|\bthanks,\s*$/im, 2], [/\bcould you (?:please )?(?:let me know|send|confirm)/i, 2],
      [/\bplease (?:let me know|reply|respond|confirm)\b/i, 2], [/^re:/i, 3],
    ],
    decide: [
      [/\bpros and cons\b|\btrade-?offs?\b/i, 3], [/\bcompar(?:e|ison|ing)\b/i, 2], [/\b(?:vs\.?|versus)\b/i, 2],
      [/\brecommendations?\b/i, 1], [/\boptions?\b/i, 1], [/\bshould (?:we|i)\b/i, 2], [/\balternatives?\b/i, 1],
    ],
    plan: [
      [/\broadmaps?\b/i, 3], [/\btimeline\b/i, 2], [/\bmilestones?\b/i, 2], [/\bschedule\b/i, 1],
      [/\bagenda\b/i, 2], [/\bnext steps\b/i, 2], [/\bproject plan\b/i, 3],
    ],
    reference: [
      [/\bapi (?:reference|docs?)\b|\bdocumentation\b/i, 3], [/\bmanual\b|\bhandbook\b/i, 2],
      [/\bspecification\b|\bdatasheet\b/i, 3], [/\bfaq\b|\bglossary\b|\bcheat ?sheet\b/i, 3], [/\bparameters?\b|\breturns?:/i, 1],
    ],
    learn: [
      [/\babstract\b/i, 2], [/\bintroduction\b/i, 1], [/\bet al\b|\bdoi\b|\barxiv\b|\bjournal\b/i, 3],
      [/\blecture\b|\bchapter \d+\b|\bwikipedia\b/i, 2], [/\bpaper\b|\barticle\b|\bessay\b/i, 2], [/\bhow (?:does|do|to)\b|\bwhy\b|\bexplained?\b/i, 1],
    ],
  };

  const MIN_SCORE = 3;

  // input: { title, format ("paste"|"file"|"url"), text }. Returns an
  // objective key, or null when there is no clear signal.
  function suggestObjective(input) {
    input = input || {};
    const title = String(input.title || "");
    const text = String(input.text || "").slice(0, 2000);
    const scores = {};
    for (const key of Object.keys(RULES)) {
      let s = 0;
      for (const [re, w] of RULES[key]) {
        if (re.test(title)) s += w * 2;
        if (re.test(text)) s += w;
      }
      scores[key] = s;
    }
    if (input.format === "file" && /\.pdf$/i.test(title)) scores.learn += 1;
    let best = null;
    let bestScore = 0;
    // Order breaks ties: a task beats a topic.
    for (const key of ["execute", "communicate", "decide", "plan", "reference", "learn"]) {
      if (scores[key] > bestScore) {
        best = key;
        bestScore = scores[key];
      }
    }
    return bestScore >= MIN_SCORE ? best : null;
  }

  const api = { OBJECTIVES, suggestObjective };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Objective = api;
})(typeof window !== "undefined" ? window : globalThis);
