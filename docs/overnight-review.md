# Overnight review

Dated sections, newest last. Each finding gives: the claim, sources, what Riemann does now, a recommended change, and an effort/risk estimate. Nothing here has been built unless it says so; these are proposals for Sam.

## 2026-10-01: genre-aware summarisation, and where Riemann is wrong rather than buggy

The question: people who summarise for a living (editors, teachers, clinicians, minute-takers) do not summarise every document the same way. They pick a shape by genre, and the shape is what makes the summary usable. Riemann currently shapes summaries by **the reader's goal** (`OBJECTIVE_FOCUS`, six values chosen on the home page) and by a per-goal essentials hint (`OVERVIEW_ESSENTIALS`), but not by **what kind of document it is**. The kind is only worked out after the tree is built (`doc_kind` in the overview call), and it steers nothing.

### F1. Genre decides which aspects a summary must cover (aspect-based summarisation)

- **Claim:** For each genre the aspects a good summary must touch are different, so summarisers work from a per-genre aspect list rather than a generic "shorter version". Aspect-based summarisation research shows the benefit is readers get the part they need without reading the rest.
- **Sources:** WikiAsp, multi-domain aspect-based summarisation dataset (https://arxiv.org/pdf/2011.07832); Inducing Document Structure for Aspect-based Summarization, ACL 2019 (https://aclanthology.org/P19-1630/); genre-specific summarisation patent overview noting that "for each genre the aspects will differ greatly" (https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/6766287).
- **Riemann now:** One generic node prompt plus a goal block. The overview prompt lists example labels by kind (assignment, paper, decision, plan, email, reference), but the model has to guess the kind itself and the tree underneath (titles, key points, key fact, steps) does not know it.
- **Recommendation:** A small genre table (`GENRE_ASPECTS`) keyed by `doc_kind`, injected into the same prompts the way the goal block is. Genres and their aspects are in F2 to F7. Detect the genre with a cheap pre-classification (regex first, as `objective.js` does, then a one-call fallback on the first 300 words) so the tree build is shaped by it.
- **Effort/risk:** Medium-large, medium risk. It changes output shape for every build, so it needs a golden-set comparison on the cached trees before it ships. Do not build without Sam's sign-off.

### F2. Assignment briefs: front-load the constraints, then unpack the task

- **Claim:** Good assignment instructions put word count, due date and the specific task up front. Students who fail briefs mostly fail to unpack them (command words, hidden constraints, criteria), so the useful summary is an unpacking, not a shortening.
- **Sources:** Boston College CTE, Communicating Assignment Instructions (https://cteresources.bc.edu/documentation/designing-major-assignments/communicating-assignment-instructions/); University of Michigan Sweetland Center, How do I make sure I understand an assignment (https://lsa.umich.edu/sweetland/undergraduates/writing-guides/how-do-i-make-sure-i-understand-an-assignment-.html; fetch was blocked, search snippet used); Assignment analysis guidance about command words and the marking rubric (https://assignmentcart.com/blog/what-to-do-if-you-dont-understand-your-assignment-brief).
- **Riemann now:** Good. `execute` puts deliverables, due, weight, submit-how, what to do and assessed-on in the overview and asks for `steps` and a deadline `key_fact`. A real build tonight of a small brief produced seven short essentials (Deliverable, Due, Weight, Submit how, Must include, Assessed on, Rules and penalties), all under 20 words and each with a `¶` cite.
- **Gaps:** (a) no explicit "command word" (analyse / evaluate / compare / discuss) essential, which is the thing that most changes what a good answer looks like; (b) limits and prohibitions (word count, AI rules, collaboration) are folded into one essential, so they are easy to miss; (c) order is model-chosen: put "what to hand in, and when" first.
- **Recommendation:** Add to `OVERVIEW_ESSENTIALS["execute"]`: "Task verb (the command word and what it asks for)", "Limits" and "Not allowed". Tell the model to order essentials as: deliverable, due, then the rest. Prompt-only.
- **Effort/risk:** Small, low risk, but it is a prompt change, so it needs one real build to check it. Left as a proposal because the brief said prompt changes are Sam's call.

### F3. Research papers: IMRaD-shaped, with evidence limits kept

- **Claim:** A structured abstract covers Introduction, Methods, Results, Discussion. LLM summaries aligned to IMRaD track a paper's rhetorical structure better, but IMRaD summaries often lack explicit evidence constraints, so faithfulness and verifiability suffer, and non-IMRaD articles do worse.
- **Sources:** Structured abstract generator, IMRaD analysis (https://link.springer.com/article/10.1007/s00799-024-00402-8); Enhancing abstractive summarisation of scientific papers using structure information (https://arxiv.org/pdf/2505.14179); Discourse-aware paper summarisation via QA-style summaries (https://arxiv.org/pdf/2511.03330); GMU Writing Center on IMRaD abstracts (https://writingcenter.gmu.edu/writing-resources/imrad/abstracts-in-scientific-research-papers-imrad).
- **Riemann now:** `learn` essentials are "Main idea, Key concepts, Why it matters, Prerequisites", which suit a lecture note or explainer better than a paper. The prompt's kind list has "Main claim, Evidence, Limits" for papers, but only in the overview, and `Limits` depends on the model volunteering it. The cite-and-verify validator (every number must be in a cited leaf) is exactly the evidence constraint the literature says is missing elsewhere, so that is a strength.
- **Recommendation:** For `doc_kind` = research paper: essentials "Question", "Method and sample", "Main result (with the number)", "Limits". Tell the model that if the paper states no limitation, the value is "not stated" (the existing pattern). Keep the number validator. Section titles for papers: name the claim, not the heading ("Methods" becomes what was done).
- **Effort/risk:** Small if done only in the essentials hint, medium if section titles follow. Low risk.

### F4. News: the source is already an inverted pyramid, so use its shape

- **Claim:** A news story leads with a summary lede answering who, what, when, where, why and how, in one sentence of about 30 words or fewer, with detail in descending importance. That makes position a strong prior for importance.
- **Sources:** Inverted pyramid (https://en.wikipedia.org/wiki/Inverted_pyramid_(journalism)); Evaluating the Inverted Pyramid Structure through Automatic 5W1H Extraction and Summarization (https://faculty.washington.edu/tmitra/public/papers/5W1H-C_J_2020.pdf); Trint on the 5 Ws (https://trint.com/creator-hub/the-5-ws-of-journalism-and-the-inverted-pyramid).
- **Riemann now:** Importance per child comes only from the model's 0..1 score. The root prompt asks for "the single most important conclusion", which for a news story is normally the lede itself.
- **Recommendation:** For news, use 5W1H as the essentials (Who, What, When, Where, Why/How), and let the frontier expansion prefer earlier leaves when scores tie (a positional prior, applied only to `doc_kind` = news). Attribution ("said", "according to") must survive summarising: add it to the hedge rule.
- **Effort/risk:** Small for the essentials, medium for the positional prior (touches `frontier.py` and `frontier.js`, which must stay in parity). Only do the essentials first.

### F5. Emails and threads: state first, history second, and decisions separate from discussion

- **Claim:** The practical structure people converge on for a thread is: a two to three sentence overview, decisions made (not the discussion that led to them), action items with owner and due date, and open questions. Summarising "what is settled" separately from "what is unresolved" is the highest-value split. A concrete length target ("3 bullets, each under 20 words") is the single most reliable instruction.
- **Sources:** Mailbird, How to summarise long email threads (https://www.getmailbird.com/summarize-long-email-threads/); Missive, Summarise an email thread with AI (https://missiveapp.com/blog/summarize-email-thread-ai); Prompting for summarisation (https://pristren.com/blog/prompting-for-summarization-guide/).
- **Riemann now:** `communicate` foregrounds the ask, who, by when and what is needed from the reader. That is right for the "reply" goal. It does not separate decided from open, and threads paste in with quoted replies (`> ...`), signatures and legal footers, which `normalise.py` leaves in, so the same paragraph is summarised several times.
- **Recommendation:** (1) Ingest: strip quoted-reply lines and repeated signature or disclaimer blocks from pasted email before hashing (deterministic, testable, small). (2) Essentials for threads: "The ask", "Decided", "Still open", "Reply by". (3) Keep the sender and date of each message as part of the leaf so "who said it" survives.
- **Effort/risk:** (1) small, low risk, worth doing next; (2) and (3) prompt and chunking changes, medium.

### F6. Meeting notes: actions are first-class (owner plus date), notes are not actions

- **Claim:** Strong meeting summaries carry the goal, three to five key points, decisions with their rationale and any dissent, and action items in the form "[owner] will [specific deliverable] by [date]". The main failure is conflating what was said with what will be done.
- **Sources:** Wudpecker, Meeting minutes example with action items (https://www.wudpecker.io/blog/meeting-minutes-example-with-action-items-a-template); Umbrex, Capturing action items and decisions (https://umbrex.com/resources/how-to-run-effective-meetings/capturing-action-items-and-decisions/); Wrike, Meeting minutes template (https://www.wrike.com/blog/action-items-with-meeting-notes-template/).
- **Riemann now:** `plan` is the closest goal (milestones, next action, dates, owners) and `steps` are generic labels with no owner or date. There is no per-node structure for "who does what by when".
- **Recommendation:** Add an optional `actions` list to key facts or steps: `{who, what, by, cites}`, validated the same way `key_fact` is (any date or name must appear in a cited leaf). Show it in the rail in place of "How it works" when present.
- **Effort/risk:** Medium (model schema, validator, rail UI, and old trees stay valid because it is optional). It is a new feature, so not built.

### F7. Legal and policy documents: never lose the modal verb, the exception or the deadline

- **Claim:** In policy and legal text "must" and "shall" mark obligations, "may" grants discretion, and "should" recommends; plain-language guidance says to preserve who does what and to include specific time frames and deadlines. A summary that flattens these changes the meaning.
- **Sources:** ISO 24495-2:2025, Plain language, Legal communication (https://www.iso.org/standard/85774.html); Plain Language guidelines, Digital.gov (https://www.plainlanguage.gov/media/FederalPLGuidelines.pdf); Cornell Policy Writing 101 (https://compliance.weill.cornell.edu/compliance/policy-office/policy-writing-101).
- **Riemann now:** The base prompt keeps hedges ("may", "likely") and never adds causation, which helps. The deterministic validator only checks numbers and dates. Exceptions ("unless", "except") and negations are not checked, and the model can drop them silently while every number still validates.
- **Recommendation:** Extend the deterministic check: if a leaf under a summary contains "must not", "shall not", "unless" or "except" and the summary text contains none of the negation or exception words, flag it (log only at first, then drop or downgrade the key point). Essentials for policy: "Applies to", "Must", "May", "Exceptions", "Deadline", "If not followed".
- **Effort/risk:** Medium; false positives are likely, so log-only first. A validator is safer than a prompt rewrite.

### F8. Technical documentation: the four Diataxis types want four different shapes

- **Claim:** Documentation serves four distinct needs that should not be blended: tutorials (learning by doing), how-to guides (a competent user reaching a goal), reference (facts to look up), explanation (background and why). Each is summarised differently: a how-to keeps its ordered steps, reference keeps values and is navigated not read, explanation keeps the causal chain.
- **Sources:** Diataxis, start here (https://diataxis.fr/start-here/); What is Diataxis (https://idratherbewriting.com/blog/what-is-diataxis-documentation-framework).
- **Riemann now:** The goals `reference`, `execute` and `learn` already map roughly onto reference, how-to and explanation, and `steps` exists. The mapping is by the reader's goal, chosen by hand, so a how-to pasted with goal `learn` gets explanatory summaries and loses its step order.
- **Recommendation:** When `doc_kind` reads as a how-to or tutorial, force `steps` to be filled in order and keep numbered items and commands verbatim (leaves already are). When it reads as reference, prefer the map and the section list over prose zooming: the reader will use "Look it up", not read.
- **Effort/risk:** Small if limited to prompt wording, but it depends on F1's genre detection.

### F9. Clinician-style handoff (SBAR) as a check on the overview card

- **Claim:** SBAR (Situation, Background, Assessment, Recommendation) is recognised by the Joint Commission, AHRQ, IHI and WHO for handoffs because it puts the problem and the requested action in a fixed order, so the receiver knows what to do with the information. Evidence in the reviews is that structure reduces communication breakdown.
- **Sources:** IHI SBAR tool (https://www.ihi.org/library/tools/sbar-tool-situation-background-assessment-recommendation); SBAR narrative review, Safety in Health (https://link.springer.com/article/10.1186/s40886-018-0073-1).
- **Riemann now:** The overview card is "kind, title, one sentence, essentials". It says what the document is, but the order of essentials is left to the model, and the action the reader must take (the "R" of SBAR) may come last or be missing.
- **Recommendation:** Give the essentials a fixed skeleton: (1) what it is (already there), (2) what you have to do or decide, by when, (3) the constraints that matter, (4) where to look. In prompt terms: "order essentials by what the reader must act on first". For documents with no action (an article), the essential is "What to take from it".
- **Effort/risk:** Small, prompt-only, low risk.

### F10. ADHD reading: chunking, organisers and colour are supported; timing advice is soft

- **Claim:** Practitioner and small-study sources for readers with ADHD recommend chunking text into meaningful segments, graphic organisers, colour-coding key points and short timed reading blocks. Riemann's own evidence review (`research/`, doc 03) already records that much of the ADHD design folklore is weakly supported, so these should be presented as defaults the reader can change, not as clinical fact.
- **Sources:** Reading comprehension strategies for students with ADHD, UNI ScholarWorks (https://scholarworks.uni.edu/grp/1375/); Chunking, Accommodation Central (https://acentral.education/accommodations/chunking); ADHD reading strategies, Verdant Psychology (https://www.verdantpsychology.com/blog-resources/adhd-and-reading-comprehension).
- **Riemann now:** Chunking (leaves at most 120 words), organisers (overview card, section map), colour (macaron palette) and a reading-time readout are all present. The time-block advice is not surfaced anywhere, and correctly so: there are no progress bars or read marks by design.
- **Recommendation:** No change. Do not add progress or completion cues. If anything, treat "~N min" as the only time cue.
- **Effort/risk:** None.

### F11. Old trees still show long essentials; a one-time refresh would fix the first-level glance

- **Claim (measured tonight, not from a source):** Trees built before the 30-word cap have essentials of 30 to 45 words. With the two-line clamp removed (commit `b518355`) the overview card of `ENG2207` is 770 px tall at 1366x768 and pushes section 01 below the fold; a tree built tonight with short values is 500 px and fits.
- **Riemann now:** The card shows whatever the tree stores.
- **Recommendation:** Add a "Shorten essentials" backfill: one model call per old tree that rewrites each value to under 15 words using the already-stored cited leaves, run lazily on open like the overview backfill, only when any value exceeds 30 words. Alternatively, do nothing and let Sam rebuild the few trees he still reads.
- **Effort/risk:** Small-medium; one real call per old tree, so it should be opt-in.

### F12. Phone layout spends a third of the screen on chrome

- **Claim (measured):** At 390x844 the header, zoom pill and section-pill row occupy about 265 px, 31% of the height, before the first line of the overview card. The `¶` provenance links are 17 px tall, under the 24 px minimum target size in WCAG 2.2 (2.5.8), and the zoom hint used to tell phone users to hold the Z key (fixed tonight, commit `4e5d290`).
- **Sources:** WCAG 2.2, Success Criterion 2.5.8 Target Size (Minimum) (https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html).
- **Recommendation:** On phone, put Map and Palette behind one overflow button, and let the pill row hide on scroll down and return on scroll up (a scroll-linked show/hide, no progress meaning). Give `.provenance` a 24 px hit area with padding or a pseudo-element.
- **Effort/risk:** Medium (layout) for the header, small for the hit area.

### F13. The goal is a build-time choice, and a wrong choice costs a full rebuild

- **Claim (from code):** The tree id hashes text, model and objective, so choosing a different goal means a new tree and new model spend. The goal suggestion is a regex heuristic on the title and the first 2,000 characters. Tonight I fixed three false positives ("due to", the name Mark, "brief history"), which shows how thin that signal is.
- **Recommendation:** Two cheaper options, either of which is a design decision: (a) make the overview card and rail goal-dependent but the tree goal-independent (goal shapes only the overview and titles at read time via one small call), or (b) keep the build-time goal but show a one-line suggestion from a cheap model call on the first 300 words ("This looks like an assignment brief. Do it?"). (b) is smaller and matches F1's genre detection.
- **Effort/risk:** (b) small-medium; (a) large.

### Suggested order, if Sam wants to act on these

1. F9 and F2 (essentials order and the task-verb, limits, not-allowed labels): prompt-only, one real build to check each.
2. F5 part 1 (strip quoted replies and signatures at ingest): deterministic and testable.
3. F13(b) and F1 (genre detection, then genre aspect tables), since F3, F4, F6, F7 and F8 all need it.
4. F7's validator in log-only mode.
5. F6 (actions with owner and date) and F12 (phone header): features, so only after the above.

## 2026-10-01: QA findings from testing (measured, for the record)

These were found by driving the app in headless Chromium against a scratch data directory (`RIEMANN_DATA_DIR`) and copied cached trees. Fixed ones have their own commits (see the final report); this list is what was checked and passed, so the next reviewer does not redo it.

- Zoom: with `=` from the gist to the deepest level on seven cached trees, every step added visible words, and `-` retraced them; no step failed to grow. Zoom hold, tap-Z sticky mode with wheel, Ctrl+wheel and the dial's Home/End all worked; the pinned block's top moved by at most 0.4 px across a full gesture (limit 2 px). Home and End only act while the dial has focus, which matches the spec.
- Palette closes on an outside click; highlights persist across reload, hide while zoomed out and return when zoomed back in, and adding one changed the block height by 0 px.
- Map: opens with the button and `g`; compact below 520 px, full above; wheel zoom keeps the tile under the pointer to within 0.001 of its width; Fit resets; click-to-jump lands the target on screen.
- Columns: drag and keyboard resize persist, re-clamp on window resize without writing to storage.
- Check-in: low energy shortens the start depth and shows "Adjusted for: low energy" with a working undo; a check-in older than 4 hours is ignored and the panel shows "optional".
- Not fixed, by design: the buttons Less and More are not disabled at the ends of the range (no harm), and the key `m` toggles minimal chrome.

## 2026-10-01 (round 2): faithfulness checking, progressive disclosure, and how to tell if Riemann helps

### R1. The number validator was defeatable, and it is the only deterministic grounding check (one part fixed)

- **Claim:** Factual-consistency research treats "does every claim have support in the source" as its own task and finds no single cheap check sufficient. Sentence-level NLI (SummaC) works better than whole-document NLI, which wrongly predicted entailment with 0.91 probability when the whole document was the premise; QA-based checks (QAGS, QuestEval) add complexity for a small gain over NLI; decomposing into atomic facts (FActScore) is the fine-grained direction. Reported balanced accuracy for inconsistency detection sits around 60 to 75 percent on common benchmarks, so every method needs a cheap deterministic layer beside it. Errors in summaries are often only a few spans, which suits span-level checks on short values like essentials and key facts.
- **Sources:** SummaC (https://www.researchgate.net/publication/358553684_SummaC_Re-Visiting_NLI-based_Models_for_Inconsistency_Detection_in_Summarization); QAGS (https://www.researchgate.net/publication/343298797_Asking_and_Answering_Questions_to_Evaluate_the_Factual_Consistency_of_Summaries); TRUE benchmark (https://arxiv.org/pdf/2204.04991); AlignScore (https://github.com/yuh-zha/AlignScore); long-document stress test (https://arxiv.org/html/2511.07689v1); practitioner survey of NLI, QA and sampling methods (https://eugeneyan.com/writing/abstractive/); span-level faithfulness (https://arxiv.org/html/2510.09915); Maynez et al., On faithfulness and factuality in abstractive summarisation (https://aclanthology.org/2020.acl-main.173.pdf).
- **Riemann now:** `key_fact`, essentials and the overview sentence are checked by "every number-like token must appear in a cited leaf". The check used a substring test, so "5%" passed against a leaf that said "25%", and "20" against "2025". **Fixed** in commit `fd48fac` (whole-number match, thousands commas ignored); I re-ran it over the 164 numbers in the cached trees and none newly fail.
- **Still not checked (measured, not just argued):** In the 12 essentials that carry cites in the cached trees, about 4 percent of longer words have no trace in the cited leaves, almost all harmless (a paraphrase such as "order" or "statement"). So a lexical grounding check has a low false-positive rate on this data, but the sample is small.
  1. Weekday, month and other proper names: "due Monday" cited to a leaf that says "Friday" passes, because only digits are compared.
  2. Negation and modality: "late work is accepted" against "is not accepted" passes; likewise "must" swapped for "may".
  3. Number words: "twelve" is invisible to a digit check, so "12 pages" cited to "twelve pages" would be dropped while "13 pages" against "twelve pages" would also be dropped for the wrong reason.
  4. Cites are only required to exist; a cite to a leaf that merely contains the digits satisfies the check. A leaf that shares a number is not evidence for the claim.
  5. Titles, hooks, key points and every summary paragraph have no grounding check at all, only the prompt.
- **Recommendation, in order of cost:**
  1. (Small, safe) Add weekday and month names to the checked tokens, matching by 3-letter prefix and case, so "Fri" and "Friday" both satisfy "Friday". Log-only first, because "may" is both a month and a modal verb.
  2. (Small) Check that each cited leaf actually shares content words with the essential (a lexical overlap floor). Drop the cite, not the item, when it fails.
  3. (Medium) For essentials only (7 short strings per document), run one batched NLI or judge call per document: premise is the cited leaves, hypothesis is "label: value". Sentence-level premises, as the literature says, not whole documents. About 1 call per document, and it turns the "not stated" rule into a verified status.
  4. (Larger) Surface it: show a subtle "source check" state on essentials that failed verification instead of silently dropping them, and let the `¶` link open the leaf. Sam's own log shows `hover_source` (144) and `jump_source` (5), so he does check sources sometimes.
- **Effort/risk:** 1 and 2 small and low risk; 3 medium and needs a golden set to tune; 4 is a design change.

### R2. Shneiderman's mantra maps onto Riemann almost one to one, and the gap is "filter"

- **Claim:** The visual information-seeking mantra is overview first, zoom and filter, then details on demand. The full taxonomy has seven tasks: overview, zoom, filter, details-on-demand, relate, history and extract. The 2008 survey of interface strategies distinguishes overview plus detail (spatial separation), zooming (temporal separation) and focus plus context, and notes the tradeoffs: zooming loses the overview while you are zoomed, overview plus detail costs screen space and attention shifts.
- **Sources:** Shneiderman, The Eyes Have It, 1996 (https://www.cs.umd.edu/~ben/papers/Shneiderman1996eyes.pdf); Cockburn, Karlson and Bederson, A Review of Overview+Detail, Zooming, and Focus+Context Interfaces, ACM Computing Surveys 2008 (https://dl.acm.org/doi/10.1145/1456650.1456652).
- **Riemann against the seven tasks:**
  - Overview: the overview card and gist. Present, and better than the plain data-visualisation case because it is written for the document kind.
  - Zoom: the dial, Z-hold, Ctrl+wheel. Present. The map adds overview plus detail, so Riemann already combines the two strategies the survey compares.
  - Details on demand: `¶` provenance links and the source text at the deepest level. Present.
  - **Filter: absent.** There is no in-document search. Browser find (Ctrl+F) only sees what is currently expanded, so a word that lives in an unexpanded passage cannot be found. This is the largest gap in the mantra, and it matters for the "reference" goal ("look it up").
  - Relate: partial. Cites link a summary to its leaves; nothing links two passages that mention the same thing.
  - History: none for zoom. Back and Forward move between documents, not between depths. A "return to where I was before that zoom" is not there, and after a long Z drag it is the thing a reader wants.
  - Extract: highlights exist but cannot be exported or copied out as a set.
- **Recommendation:** (1) In-document search that looks through every leaf, ranks by node, and on selection calls `jumpToNode` (which already reveals the passage). Estimated one focused change. (2) A one-step "back to previous depth" (Alt+Left or a small button) that restores `z` and the anchor. (3) Copy highlights as markdown.
- **Effort/risk:** (1) medium, new feature; (2) small-medium (state exists in `setZ`); (3) small. All three are features, so proposals only.

### R3. Riemann is zoom-only where the literature says overview plus detail can be cheaper

- **Claim:** Empirical work reviewed in the survey finds zooming carries a cost: when zoomed in, the overview is gone, so readers lose orientation and take longer on tasks needing both levels. Overview plus detail costs more screen space but keeps orientation.
- **Riemann now:** Both exist: the section nav and the map are the overview, the reading column is the detail. The map is closed by default at the gist and by check-in on low energy. That default is a reasonable choice for an ADHD reader (fewer things on screen) but it means the orientation aid is one keypress (`g`) away that a new reader may never find.
- **Recommendation:** Keep the default, but show the section nav's current-section highlight and "you are here" more strongly on a long jump, and mention `g` in the first-time hint once a reader has zoomed past level 3. No structural change.
- **Effort/risk:** Small, low risk.

### R4. How Sam could measure whether Riemann helps (methods, not a build)

- **Claim:** For a single user, the standard method is a single-case experimental design: each participant is their own control, alternating baseline (A) and intervention (B) phases, and ABAB is the simplest design that shows an effect at least three times. Within-subject reading-tool studies typically pair objective measures (task time, comprehension accuracy) with a subjective load score (NASA-TLX, six 0 to 100 ratings).
- **Sources:** N-of-1 trial (https://en.wikipedia.org/wiki/N-of-1_trial); single-case designs, practical guide (https://www.sciencedirect.com/science/article/pii/S1877065717304542); single-case designs for technology-based interventions (https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3636286/); NASA Task Load Index (https://www.nasa.gov/human-systems-integration-division/nasa-task-load-index-tlx/); example within-subject reading-tool study with time, accuracy and NASA-TLX (https://arxiv.org/pdf/2512.06408).
- **What the existing log already gives:** Counts in `events.jsonl` today: 1,575 `dial`, 185 `dwell`, 144 `hover_source`, 66 `close`, 63 `open`, 37 `map`, 5 `jump_source`. That is enough for behaviour proxies (session length from open to close, deepest zoom per document, source checks per session) but not for outcomes: nothing measures whether Sam understood or acted on the document.
- **Proposal (a two-week ABAB, about 30 minutes of setup):**
  1. Pick one recurring task with a checkable outcome: a weekly assignment brief or reading. For each document, before reading, Sam writes down the three things he thinks he must do; after reading, a fixed 5-question checklist (what is due, what is worth what, what to submit, what is allowed, what is unclear) is scored against the source by hand (0 to 5).
  2. Alternate by document, not by day: A = read the original as he normally would, B = read in Riemann. Four phases (A B A B) of about 3 documents each, order fixed in advance.
  3. Record per document: minutes to first "I know what to do" (self-timed), checklist score, NASA-TLX raw score (six sliders, under a minute), and whether he later found he had missed something (a yes or no tick a week later). Riemann already logs the B-phase timing; the A phase is the one to add (a stopwatch is enough).
  4. Judge it by the plotted phase data, not a p-value: did B beat A in both B phases, with the effect appearing again after the reversal.
  5. Guard against the obvious confound: novelty. Run at least one B document late in the fortnight, after the novelty has faded.
- **Cheap, automatic additions to the log, if Sam wants them** (all local, no progress or read marks): `first_zoom_ms` (time from open to first dial input), `max_z` per session (deepest level reached), and a `did_it_help` yes or no ask on close, which the existing "not helpful" link half-does.
- **Effort/risk:** The protocol is paper and a spreadsheet; the three log fields are small. None of this adds progress or read state.

### R5. Re-test with these lenses: what the two lenses changed in the QA list

- Faithfulness lens found the substring bug (fixed, `fd48fac`), and pointed at the four gaps above, none built.
- Shneiderman lens found no filter, no zoom history and no extract, and confirmed overview, zoom and details are present and work (word growth per step and pointer-pinned anchor measured in round 1; round 2 measured 41 ms median per zoom step on a 40,000-word tree).

### Round 2 measurements (for the record)

- **Large document (40,165 words, FakeSummariser, Chromium headless, 1366x768):** build 0.45 s; 650 nodes, 437 leaves; tree JSON 0.93 MB, served in 6 ms; reader opens in 147 to 156 ms; zoom step from first `=` to fully expanded (309 steps): median 41 ms, p90 72 ms, none over 150 ms; 20 full-screen scrolls in 331 ms. Map: opens in 29 to 39 ms with 16 to 40 tiles; at 649 tiles a wheel-zoom frame costs 37 ms median and 419 ms worst. That worst case is the frame that first draws all tiles and is acceptable; a virtualised draw would only matter above roughly 1,500 tiles.
- **Leaks:** 50 map open/close cycles plus 100 `g` toggles, then 400 zoom steps, then 20 open/close-document cycles: JS heap 3.7 MB to 4.5 MB (flat after the first cycle), DOM nodes 1,278 to 1,402, native listener count 125 to 115 (no growth).
- **Concurrency and restart:** two builds started together finish together (10.8 s each with a 1.2 s fake latency, 4 concurrent calls per build); closing the event stream mid-build and reopening replays the history and reaches "done"; the tree can also be fetched mid-build (`status: building`). A server restart mid-build loses the build: the loading screen shows "Lost the connection to the Riemann server", and reopening that link says "Could not find that document. It may have been built by an older version", which is misleading (it was in progress, not old). Proposal: persist a "building" marker or the source text so the reader can offer "Build it again".
- **Contrast:** every text and background pair on the home page, reader, palette and map passes WCAG AA (lowest 4.66:1, muted text on the pastel tiles). With the palette set to Rose quartz slots (the lowest-contrast pastel, 3.98:1 for the label colour on the full pastel, 4.7:1 on the 60 percent tile mix) nothing fails in any surface the app draws; a custom palette that puts `--label` text on a full-strength Rose quartz block would fail.
- **Keyboard:** Tab reaches every control on the home page, reader, palette and map in a sensible order with a visible focus indicator on each; every interactive element has an accessible name. Keyboard users cannot create a highlight (creation needs a mouse selection); that is a proposal, not a fix.
- **Firefox:** Playwright's own Firefox was not installed and installing it downloads a large file, which I did not do without asking. The system Firefox 156 was driven over WebDriver BiDi instead: overview card (7 tiles), rail cards, zoom-word growth (503, 558, 617, 813, 977, 1045, 1249, 1289, 1336, the same sequence as Chromium), zoom out, map open (compact) and keyboard column resize with persistence all matched. WebKit was not tested.

### Round 2 addendum: ingestion notes (measured with a generated 5-page PDF and seven real URLs)

- **PDF (Chromium-printed, two-column body, running header and footer, bullets, tables):** running headers, "Page N of M" footers and bare page numbers are now removed (commit `39c3cdf`). Numbered headings such as "2. Methods" no longer become a one-item list that swallows the next paragraph, and now become markdown headings so leaves carry a `heading_path` (commits `de720c7`, `b5b950e`); on the test PDF the chunker went from zero headings to all five, giving 21 leaves in five named sections.
- **Known limits, not fixed:** (1) pypdf gives no blank line between paragraphs, so a paragraph that ends near the right margin is glued to the next one; the rule "a sentence ended a short line" only fires when the last line is under 60 percent of the wide-line width. Loosening it risks splitting real paragraphs at chance short lines. (2) Bullet glyphs drawn as shapes (Chromium and many Word exports) leave no character, so bullets arrive as plain lines. (3) Table cells arrive as space-separated text. All three need layout-aware extraction (pdfminer or pdfplumber with coordinates), which is a new dependency and so a decision for Sam.
- **URLs:** extracted cleanly from a personal essay site (after unwrapping its one-cell layout table, commit `c6db1a2`), Sphinx docs (pilcrow permalinks removed), arXiv abstract pages and a plain HTML page. A paywalled Nature news page returns only the teaser plus "Access options" boilerplate (134 words) and would build a summary of the paywall; the fix (detect very short extractions from long pages and warn) is a small proposal.
- **Server memory:** `BUILDS` keeps every finished builder (tree plus source text) for the life of the process. For one user that is a few MB per document, so it is fine, but it should evict `done` builders once they are saved to the cache if the server is ever left running for weeks.

## 2026-10-01 (round 3): security review, awkward content, randomised and monkey tests, chunking and typography research

### S1. Server security review (all fixed or noted; every fix has a test and its own commit)

Threat model: a personal app on localhost that spends Sam's model quota through a local proxy (:8317) and reads and writes his disk cache and activity log. The realistic attackers are a web page open in another browser tab, a hostile document or link Sam is asked to summarise, and a malformed file. There is no login and there should not be one; the defence is to make the server refuse anything that is not Sam's own browser talking to it.

| Area | Finding | Fix |
|---|---|---|
| Path traversal via tree id | Not exploitable: the router does not let `%2F` or `..` reach the handlers (404 for every variant, all four tree routes). But `path_for` built a path from the id with no check, so one careless new caller would have been. | `cache.is_safe_id` (`[A-Za-z0-9_-]{1,64}`); `path_for` raises, `load_tree` and `exists` refuse, in the current and the fallback dirs (`964a4e6`). |
| SSRF on link ingest | Exploitable: any link, including `http://127.0.0.1:8317` (the model proxy), `localhost`, `169.254.169.254`, `10.x`, `file://` and redirects to them, was fetched by the server. | `check_public_url`: http(s) only; the host must resolve only to global addresses (loopback, private, link-local, CGNAT, reserved and IPv4-mapped IPv6 all refused); redirects are followed by hand and every hop is checked; body capped at 15 MB. `RIEMANN_ALLOW_PRIVATE_URLS=1` opts in. Tested against a dummy server on an ephemeral port (never :8317 or :8787) that records hits: zero hits for a loopback link and for a redirect hop (`27331a8`). |
| Cross-site requests and DNS rebinding | Exploitable: `POST /api/abstract` accepted any content type and any origin, so a web page in another tab could `fetch("http://localhost:8765/api/abstract", {method:"POST", mode:"no-cors", body: ...})` and start builds on Sam's quota, or fill the events log; a rebinding domain could read `/api/recent`. | Middleware: the `Host` header must be `localhost`, `127.0.0.1` or `::1` (403 otherwise); a state-changing request with a foreign `Origin` (or `Sec-Fetch-Site: cross-site`) is refused; the JSON endpoints require `Content-Type: application/json`, which forces a CORS preflight that a foreign page fails (`bc4ee4b`). |
| Request sizes | No limit: a multi-GB body was read into memory. | JSON 5 MB, upload 30 MB (411 without a length), events 1 MB, pastes 50,000 words (earlier) (`bc4ee4b`). |
| Zip bomb in .docx | Exploitable: `z.read()` inflated `word/document.xml` unbounded. | Declared size checked before reading, and a hard read limit if the header lies; cap 40 MB inflated (a 300-page report is about 2 MB) (`1131fe8`). |
| XSS | The server-built strings (titles, `doc_title`, essentials, key facts, map labels, recent cards, file names) are all escaped: a tree with an `<img onerror>` payload in every text field ran nothing. **Not safe:** the palette read back from `localStorage` was written into `style="background:${c}"`, and a poisoned value executed script; a bad saved position blanked the reader. | Palette, highlights and saved position are validated on read (hex colours only, known preset names, finite numbers). Checked with a six-scenario poison test before and after; there is no browser test harness in the repo, so it is not in pytest (`b32baad`). |
| Bind address | `uvicorn ... --port 8765` binds `127.0.0.1` by default (confirmed with `ss -ltn`). | README and the dev-server config now say `--host 127.0.0.1` explicitly. |

Residual risks, not fixed:
1. DNS rebinding between the address check and the connection for link ingest (a hostname that resolves public for the check and private for the connect). Closing it means connecting to the checked IP directly, which needs a custom transport that keeps TLS server-name checking; low value for one user.
2. A hostile document can carry instructions aimed at the summariser ("say the deadline is Monday"). The number validator, `¶` cites and `not stated` rule limit the damage, but text and titles are not checked (see R1).
3. Any other program running as Sam on the machine can call the API; that is inherent to a localhost service.
4. `events.jsonl` and `~/.cache/riemann` grow without bound, and PDF page count and pypdf inflate limits are pypdf's own.

### A1. Awkward content (FakeSummariser for everything except one real build)

Documents: Chinese and Japanese, Arabic, Hebrew, emoji, LaTeX, code plus markdown tables, a 29-word note, a 12,000-word single paragraph with no punctuation, an outline of 60 headings with no body, six sections all titled "Results", a 600-character URL and a 14-column table.

| Case | Result |
|---|---|
| CJK (Chinese, Japanese) | **Not supported.** Word counting splits on spaces, so a 1,600-character document counts as 1 word, becomes a single leaf, shows "~1 min" and is never summarised (it builds instantly and costs nothing, so it fails safe). Proposal below. Korean uses spaces and is fine. |
| Arabic, Hebrew | Rendered left-to-right and left-aligned. **Fixed:** text blocks now carry `dir="auto"` (measured `ltr` to `rtl`; `75e64b0`). |
| Emoji | Chunks, titles and map labels fine. |
| LaTeX | Chunked correctly (display math is its own atomic leaf) but **shown as raw source** (`$x_{t+1} = x_t - \eta \nabla f(x_t)$`). Confirmed in the one real build. Not fixed: rendering with KaTeX changes each node's plain text and the highlights store character offsets into that text, so it needs the highlight anchoring reworked first. A proposal. |
| Code fences | Atomic, scroll inside the block, no overflow. |
| Markdown tables | **Fixed twice:** a table over 120 words was cut mid-row and merged into prose (now one atomic leaf, `0d650ff`); a wide table pushed the page sideways by up to 6,000 px (now scrolls inside its block, `58dcf83`). |
| Long URL or 400-character token | **Fixed:** wrapped instead of overflowing (`58dcf83`; a follow-up stopped the rule splitting "01" in the nav, `9787726`). |
| 29-word note | One leaf, shown verbatim, no summary, no error. Fine. |
| 12,000-word single paragraph | 100 hard-cut 120-word leaves, no crash; mid-sentence cuts are expected. |
| 60 headings, no body | Collapses to one leaf holding the outline. Acceptable. |
| Duplicate section titles | Sections stay separate (a heading flushes the pack); the nav and map show the same title six times, distinguished only by number. |
| Ligatures in PDFs | Sam's cached PDF has "classiﬁed", "Deﬁne" (fi ligature). **Fixed** (`f950061`). |

The one real build (a 330-word note with LaTeX, a code block and a table, goal "learn"): the model turned the LaTeX into readable Unicode in the overview ("x_{t+1} = x_t - η∇f(x_t)", "κ = L/μ"), and every number in the essentials was found in its cited leaf (including "1,380 steps versus 21"). Titles were faithful. The one visible defect is the raw `$...$` in the reading area.

Proposals (not built): (1) count CJK characters as words (about two characters per word) in both `chunk.word_count` and the JS counters, split long CJK paragraphs at "。！？", and bump the cache schema; medium effort because it touches the parity code. (2) KaTeX math with highlight offsets computed on the source text rather than the rendered text. (3) Show the section number with the title when two sections share a title.

### T1. Randomised frontier tests

`tests/test_frontier_random.py`: 20 fixed seeds by 7 tree shapes (single leaf, wide fan, deep single-child chain, balanced, lopsided, ragged, ragged with pass-through levels). For sampled anchors of every tree it checks that tokens name real internal nodes and never repeat, that the last step shows every leaf, that `keep_expanded` leaves the current page unchanged, that visible words strictly increase, and (under node) that `frontier.js` produces the same sequence, the same page and prose set at every k, and that `kToReveal` returns the smallest k at which the node is on the page (or, for a skipped pass-through level, its content is).

What it found:
- **Strict growth holds for trees shaped like real ones** (summary about a third of what it summarises, no pass-through levels): 0 violations in the seeded runs, and 0 in 12,703 steps over all anchors of the 15 real cached trees.
- **It fails for other shapes**, which is worth knowing: if a node's prose is more than about a third of its children, or a level has a single child, a step can *reduce* the visible words. The cause is the fallback in `expansion_sequence`: when no later step can be merged into a tentative one, the tentative step is emitted alone without a growth check. With real prompts (`RATIO = 3`, `collapse_single_child_chains`) it does not occur, so nothing was changed. If the ratio or the collapse step ever changes, this test is the alarm; the generator's realistic mode keeps the summary at 28 to 40 percent of the children.
- `kToReveal` for a pass-through level returns the k at which its ancestors are open even though the level itself is never drawn; the app's jump falls back to the nearest drawn node, so this is consistent, and the test encodes it.

### M1. Monkey test (seeded, Playwright, about 500 actions per seed)

Harness (kept in the scratchpad, not the repo): weighted random actions over zoom keys and bursts, dial keys, Less/More, Z hold and tap, Ctrl+wheel, scrolling, map (button, `g`, tile click, wheel, drag, Fit), column drag and keyboard, palette (open, preset, slot, swatch, Esc or outside click), highlights, section jumps, source links, Home to a recent card, Back and Forward, minimal chrome, viewport resizes across 390 to 1920, reload. After every action it asserts no page or console errors, no horizontal overflow, the header visible (except in minimal chrome), the dial text well formed, and the dial percentage consistent with the words in the DOM (within a wide tolerance).

Found and fixed: minimal chrome (`m`) only faded the header, nav, rail and column handles, so they stayed in the Tab order and widened the page by 32 px (`97b76ca`); a no-sections document used a bare `1fr` track, so a header wider than a phone screen pushed the page 174 px sideways (`d526734`); and three regressions I had introduced earlier in the round and then caught myself: the wrap-anywhere rule split "01" in the nav (`9787726`), the reader container query collapsed a single-column document to 0 px (`d3d8cab`), and a no-wrap pill overflowed a narrow area (`1ebc691`). The Home-during-rail-fade TypeError (seed 7) is `eedc209`. Several harness false alarms (the poisoned XSS tree in the scratch cache, a stale dial reading after Back) were fixed in the harness, not the app.

### R6. Text segmentation and chunking: what the literature says, and where `chunk.py` stands

- **Claim:** Segmenting a document into topic-coherent passages has two long lines of work. TextTiling (Hearst, 1997) scores lexical cohesion between adjacent blocks of text and puts boundaries at valleys in that signal; its output matched human judgements of subtopic boundaries on the texts she tested. Embedding-based "semantic chunking" does the same with sentence-embedding similarity. For retrieval, recent evaluations are mixed: semantic chunking gives small or no gain over fixed-size or recursive splitting on realistic documents and costs embeddings per sentence, while structure-aware and hierarchical methods (headings, then size) do well. Boundary quality matters most when the passage will be read or retrieved alone.
- **Sources:** Hearst, TextTiling (https://dl.acm.org/doi/10.5555/972684.972687); Is Semantic Chunking Worth the Computational Cost?, Findings of NAACL 2025 (https://aclanthology.org/2025.findings-naacl.114.pdf); Chroma, Evaluating Chunking Strategies for Retrieval (https://www.trychroma.com/research/evaluating-chunking); HiChunk, hierarchical chunking for RAG (https://arxiv.org/pdf/2509.11552); Evaluating chunking strategies on academic texts (https://arxiv.org/html/2607.01852v1).
- **What `chunk.py` does:** structure first, then size. It splits at headings, keeps code fences, `$$` math, numbered procedures (and, since tonight, markdown tables) as atomic leaves, then packs consecutive paragraphs of the same heading path into leaves of at most 120 words, cutting an over-long paragraph near a sentence end (60 to 100 percent of the cap) and otherwise by word count. That is the hierarchical, structure-aware family, which the retrieval studies rate as a strong baseline, and it never needs an embedding call.
- **Measured on Sam's 15 cached documents (354 leaves):** median leaf 96 words (p10 44, p90 120); 3 percent under 30 words; 45 percent at 100 words or more; 20 percent of leaves join more than one paragraph; 81 of 351 non-atomic leaves end without sentence punctuation. Of those 81, 12 carry a page footer ("Page 2") from before the header stripping and a number end on footnote markers such as `<sup>[5]</sup>`; the rest are genuine mid-sentence cuts from the word-count fallback ("... during training,", "... the per-class").
- **Where it can split an argument:** (1) the greedy packer joins paragraphs until 120 words with no regard for topic, so a leaf can straddle a topic shift inside one section (the case TextTiling exists for); (2) the fallback cut breaks mid-sentence in run-on paragraphs and PDF text with no sentence punctuation; (3) only `heading_path[0]` (the top-level heading) is used to group leaves into the first tree level, so deeper headings shape leaves but not sections; (4) a heading level is never a boundary the model sees, only the path string.
- **Leaf size:** RAG guides usually prefer 200 to 500 tokens because a retriever needs enough context; Riemann's leaves are read one after another as the smallest zoom step, so about 120 words (roughly 160 tokens) is defensible, and matches the ADHD chunking advice in R7. The real cost of small leaves is that the top of the tree has to compress more, which the `RATIO = 3` summaries already absorb.
- **Recommendations:**
  1. (Small, low risk) Prefer to cut a long paragraph at the *latest* sentence boundary in the window, and if there is none at a clause boundary (`;` `:` `,` followed by a lowercase word) before falling back to a raw word cut. Would remove most of the 81.
  2. (Small) Do not pack across a heading of any level (today a `###` change inside one `##` section keeps packing), so subsections stay whole.
  3. (Medium, optional) A TextTiling-style boundary preference *within* a heading section: when a paragraph pack would exceed 120 words, choose the split point with the lowest word-overlap between the neighbouring 3-paragraph windows instead of "as full as possible". Pure Python, no embeddings, deterministic and testable; evaluate against the cached trees by counting leaves whose first and last sentences share no content words.
  4. (Not recommended) Embedding-based semantic chunking: the retrieval studies do not show a reliable gain, it adds a dependency and a per-document cost, and Riemann's structure-first approach already gets most of what it gives.
- **Effort/risk:** 1 and 2 small (a few lines and tests, and they change chunking, so the cache schema should be bumped when they ship, which would make all existing trees rebuild-only); 3 medium.

### R7. Typography and layout for ADHD and dyslexic readers, and the Macaron reader as measured

- **Claim (what is supported):**
  - *Letter spacing* is the best-supported single lever for dyslexic readers: extra-large inter-letter spacing improved reading accuracy and speed in a PNAS study, and later work agrees for people with dyslexia, low vision and unfamiliar content.
  - *Special fonts do not help.* The Dyslexie font did not benefit children with or without dyslexia; Rello and Baeza-Yates' results favour plain, common sans-serif fonts at a comfortable size, with the effect coming from size and spacing rather than a "dyslexia font".
  - *Line length:* the classic comfortable range is about 45 to 75 characters (66 is often quoted); Dyson's experiments found around 55 characters read comfortably at normal and fast speeds, and shorter lines (about 45 to 50) are often recommended for dyslexic readers. Very short lines (under about 35) break reading into fragments.
  - *ADHD:* evidence is thinner. In adolescents, spaced text on a computer screen gave the best comprehension for readers with poor sustained attention, and practitioner guidance recommends chunking, ample white space and 1.5x line height. Treat these as reasonable defaults, not proven effects (this matches Riemann's own evidence review, which rates most ADHD design claims as weak).
  - *Bionic reading (bolding the first half of each word) does not work:* a 2,074-reader timing study found no speed gain (2.6 words per minute slower on average); a 2024 paper is titled "No, Bionic Reading does not work"; a registered eye-tracking study of 90 skilled readers found the bolding moved the first fixation but produced no gain in reading speed, word skipping or comprehension, and comprehension of easy text was lower with it.
- **Sources:** Zorzi et al., extra-large letter spacing improves reading in dyslexia, PNAS 2012 (summarised in https://link.springer.com/chapter/10.1007/978-3-030-78095-1_17); Rello and Baeza-Yates, Good Fonts for Dyslexia (https://dyslexiahelp.umich.edu/wp-content/uploads/2014/02/good_fonts_for_dyslexia_study.pdf); Dyslexie font does not benefit reading in children with or without dyslexia (https://pmc.ncbi.nlm.nih.gov/articles/PMC5934461/); Optimal line length, a literature review (https://www.researchgate.net/publication/234578707_Optimal_Line_Length_in_Reading--A_Literature_Review) and Baymard (https://baymard.com/blog/line-length-readability); Effects of sustained attention, spacing and presentation type on reading comprehension in adolescents with and without ADHD, JOV (https://jov.arvojournals.org/article.aspx?articleid=2141319); Reading with diversity in mind: pupillometry and typography for ADHD readers, CHI 2026 extended abstracts (https://dl.acm.org/doi/full/10.1145/3772363.3799383); Bionic Reading does not work (https://www.sciencedirect.com/science/article/pii/S0001691824001811); Readwise timing study (https://blog.readwise.io/bionic-reading-results/); Guiding the gaze, eye-tracking (https://pmc.ncbi.nlm.nih.gov/articles/PMC12565662/).
- **Riemann as measured (Chromium, a 16 px browser default, Work Sans 17 px, line height 1.65, letter spacing normal, word spacing 0, paragraph margin 0.7 em):**

| Viewport and state | Reading area | Characters per line (median) |
|---|---|---|
| 1366x768 default (nav 300, rail 380, two columns) | 590 px, two 277 px columns | **24** (leaf text is 239 px wide) |
| 1366x768 with the map open | two 453 px columns | 43 |
| 1366x768 minimal chrome | two 534 px columns | 51 |
| 1920x1080 default | two 554 px columns | 55 |
| 1100x700 (desktop layout, nav and rail open) | 324 px | 9 before, 28 after tonight's fix (`392ca9b`) |
| 768x1024 tablet | one 736 px column | 70 |
| 390x844 phone | one 358 px column | 31 |

  Body size (17 px) and line height (1.65) are in the recommended range and the font is a plain sans. **The defect is the line length at the most common laptop size:** 24 characters per line at 1366x768 is under the range where reading is comfortable, and the skim bullets are the same width. That is a design choice (the 2-column grid is in the spec), so only the pathological case at 1100 px was fixed.
- **Recommendations (all proposals):**
  1. At reading areas under about 720 px (which includes the default 1366 laptop), use one column of about 590 px (about 62 characters) and keep the two-column flow for wide screens (about 1500 px and up). This trades the macaron grid look for a measured comfortable line; a 1366 laptop is the size Sam named. An intermediate option is to keep two columns but let the reading area take the space of the rail when the rail has nothing selected.
  2. Offer letter spacing (about +0.04 em) and word spacing as a reader setting beside the palette, off by default. It is the one typographic lever with dyslexia evidence, and it fits the existing localStorage preference pattern. Do not add a "dyslexia font".
  3. Do not add bionic-style bolding or any per-word emphasis: the evidence says no effect on speed and possibly worse comprehension.
  4. Keep the line height at 1.5 or more and the paragraph gaps; do not shrink them to fit more on screen.
  5. Show a reading-width control (narrow, medium, wide) instead of a fixed measure, so a reader who prefers shorter lines can have them; store it with the palette.
- **Effort/risk:** 1 is a CSS change with a design decision; 2 and 5 are small settings with a stored value; 3 and 4 are "do not".

### Round 3 re-test with those lenses

- Chunking lens found the table splitter (fixed), the ligature gap (fixed) and the mid-sentence cuts (measured, proposed).
- Typography lens found the 9 and 24 characters-per-line cases (the first fixed) and confirmed there is no per-word emphasis, no decorative font and no motion that the evidence argues against; the reduced-motion rule from round 1 stands.

Monkey tally at the end of round 3: 16 seeds of 500 actions (about 8,000 actions) over five cached documents, including one single-column document and the poisoned XSS tree; every seed passes on the final code (seeds 1, 3, 4, 5, 6, 8, 9, 10, 11 to 16 clean; seeds 2, 4 and 7 each found something that is now fixed and were re-run clean).

## 2026-10-01 (round 4): browser tests, docs accuracy, code health, genre spot-check, and reading to start a task

### E1. Opt-in browser test suite (`tests/e2e/`, commit `1f3a04d`)

Runs Playwright (Node) against its own server on a free port with a scratch `RIEMANN_DATA_DIR` and a FakeSummariser (`tests/e2e/fake_app.py`), so it never touches Sam's cache or events log and never calls a model. Skipped unless `RIEMANN_E2E=1` is set, and skipped with a message if Node, the `playwright` npm package or a Chromium build is missing, so `uv run pytest` stays at about 7 seconds. Eleven tests (about 105 seconds together): word growth over 12 zoom steps; the pinned block drifts under 2 px through a Z-hold gesture; map open, tile jump and close; a column drag that survives a reload; a palette preset and a highlight that survive a reload; a poisoned `localStorage` (palette, highlights, position, columns, check-in) that runs nothing and still renders; an HTML payload in every text field of a built tree that stays escaped; the overview card with its essentials and no clamped value; a 390x844 layout with no horizontal overflow across eight zoom steps; and two seeded random-action runs (60 actions each) that assert no page or console errors, no horizontal overflow and a visible header. Negative control: with `app.js` swapped back to the version before the localStorage fix, the poisoned-storage test fails (`pwn: 1, imgs: 1, nodes: 0`) and passes on the current code.

### D1. Docs accuracy

Re-ran the README setup from a fresh local clone in the scratchpad: `uv sync` (offline from the cache), starting the server with the README's `--host 127.0.0.1 --port` command and `RIEMANN_PROVIDER=agent-sdk`, `/`, `/?fixture=1` and `/api/models` all answer, and `uv run pytest -q` passes there (475 with the browser tests enabled, 464 without). Not re-run: `git clone https://github.com/...` (used a local clone instead) and `npm install --no-save playwright && npx playwright install chromium` (both are downloads; the second is documented as a one-time step).

Wrong or missing in the docs and now fixed (`5bb9627`): the README said trees and the log both live under `~/.local/share/riemann/` (trees are in `~/.cache/riemann`); it said Home and End jump the zoom from anywhere (only with the dial focused); it did not mention .docx, the paste and upload limits, `RIEMANN_ALLOW_PRIVATE_URLS`, `RIEMANN_ALLOWED_HOSTS`, the localhost-only guard, the overview card or minimal chrome. The v1 spec's API table now has the new status codes, the two backfill routes and `/api/models`; the v2 spec's minimal-chrome and reading-width notes match the code; `overview-spec.md` records the ingest repairs (docx, PDF headers, numbered headings, ligatures, link handling, atomic tables).

### C1. Code health (each its own commit; full suite plus browser suite green each time)

Removed: `hop_distance` and `_ancestor_depths` in `frontier.py` (never called, no JS twin), `firstNSentences` in `app.js` (never called), a redundant `overflow-wrap` declaration, and a stale test-file name in an `objective.js` comment. A scan for unused imports and never-referenced functions in `riemann/` and `web/` found nothing else; the CSS classes not found in JS or HTML (`map-leaf`, `map-solid` and two more) are built dynamically as `map-${kind}`.

**Refactor plan for `web/app.js` (about 2,700 lines in one IIFE; proposal only, not started):**
1. *Why:* everything shares one closure and one `state` object, so any change needs the whole file in your head, and the anchor maths (`offsetAtY`, `yOfOffset`, `setZ` pinning) sits next to unrelated code, which is what makes it risky to touch.
2. *Safety net first:* the new e2e suite (pin drift, zoom growth, map, columns, palette and highlight persistence, the monkey runs) plus `test_frontier_parity` and `test_frontier_random`. Add two e2e checks before starting: highlight offsets after a re-render, and Back and Forward across documents.
3. *Order, smallest and least entangled first, one commit each, e2e green after each:* (a) `events.js` (log batching, `sendBeacon`, about 60 lines, no DOM); (b) `store.js` (localStorage reads and their validation: palette, highlights, position, check-in, model choice); (c) `palette.js` (panel, presets, CSS variables); (d) `highlights.js` (selection, toolbar, rendering marks; depends on `store` and on node plain text); (e) `checkin.js`; (f) `home.js` (composer, model picker, recent cards, loading screen and SSE); (g) `overview.js` and `rail.js` (pure HTML builders from a tree); (h) `zoom.js` (dial, gestures, pin) last and least: it owns `state.z`, `state.frontier`, the anchor and `render`, and must keep `offsetAtY`, `yOfOffset` and `setZ` byte for byte.
4. *Mechanics:* plain `<script>` files exposing `window.Riemann.<module>` like `frontier.js` and `map.js` already do (no bundler); modules receive a small `api` object of `getTree`, `getFrontier` and `keepReadingPosition`, the pattern `map.js` uses today. Do not change any function body while moving it.
5. *Risk and effort:* (a) to (e) are low risk, roughly an hour each; (f) to (g) medium; (h) high and only worth it if a feature needs it. Stop after (g) if the file is manageable.

### G1. Summary-quality spot check on two new genres (the last 2 real builds)

Two synthetic documents written for this: a 529-word meeting-notes document (agenda items, a decision, open questions, five actions with owners and dates), built with goal Plan; and a 409-word email thread (a new message, two levels of quoted history, a legal disclaimer, an appended reply from a second person), built with goal Reply. Scores are 1 to 5 by hand, with every essential's cited leaves read against its value.

| | Meeting notes (Plan) | Email thread (Reply) |
|---|---|---|
| Overview says what the reader must know or do | **4**: the data-reload dependency with owner and date, draft target and its fallback, correction note and date, charter and deposit date, budget left, open questions, next meeting. | **4**: the ask (signed agreement, orientation answer), the deadline with its consequence (24 October, next slot 1 December), who must sign, what is already settled (Thursday finish, laptop), the parking form. |
| Essentials supported by the source | **7 of 7** (all cites checked; "Priya called tight" paraphrases "Priya noted ... tight"). | **7 of 7**, including the two that come from quoted or appended text (the countersignature from the 13 October message, the Thursday and laptop answer from Marcus's appended reply). |
| Unsupported or over-reaching framing | The root line says the reload "gates everything"; the source only makes the dashboard, the correction note and the results section depend on it, not the field trip booking. | None found. |
| Important content missing at the gist | Aisha's action, the earliest deadline (Wednesday 15 October: chase Dr Malik, ethics check); the decision that the dashboard is republished; what went wrong (a UTC timestamp change, about 0.4 degrees overstated), which appears only in section 1. | The first-day facts a reader needs in order to act: Monday 3 November, 9 am, level 2 reception, bring photo ID. "Reply by: Monday" has no date (the source gives none). |
| Structure | Two sections for five headed agenda items, with the decisions, open questions and actions all inside "Charter booked, draft date depends on reload". A bug, now fixed (below). | Four sections with sensible titles; the signature and confidentiality notice share a leaf with Marcus's reply. |

Bugs the build exposed, both fixed with tests:
1. **Section boundaries ignored every heading except the first** (`2652113`): `build.py` grouped leaves at "the top-level heading", but a document with a single `# Title` over `## Sections` has the same first heading on every leaf, so nothing separated the sections. Five of Sam's fifteen cached documents have that shape (boundary groups 1 to between 4 and 17). Existing cached trees keep their old structure until rebuilt; new builds split at the `##` headings.
2. **Quoted replies and email headers were flattened** (`6519070`): the normaliser joined every line of the thread into paragraphs, leaving `> Hi Dana, > > Thanks for the details. ... > > Thanks, > Sam` inside one line and running the From, To, Cc, Subject and Date headers together. Quote blocks and each header now keep their own lines.

Prompt-level observations (proposals only): (a) for meetings, `actions` with owner and date deserve their own structure (F6) and a "who is this reader" choice, because "my actions" is what a meeting reader wants; (b) an essential for the *earliest* dated action would have caught Aisha's; (c) for emails, order the essentials as ask, deadline and consequence, what is already settled, then logistics, and add "First-day facts" for onboarding mail; (d) strip signature and disclaimer blocks at ingest (F5 part 1) so a reply is not chunked together with boilerplate.

### R8. Reading a brief in order to start it: task initiation, time perception, and what the "Do it" output should do

- **Claim:**
  - *Reading to do is not reading to remember.* Research on reading purpose separates read-to-recall from read-to-do; a read-to-do purpose puts the effort into building a model of the actions and the state after each one, and procedural text is hard because it describes a changing situation. So a useful "do it" summary is a *procedure with a first step*, not a shorter description.
  - *Time perception is impaired in ADHD in ways that matter for deadlines.* In Barkley's model poor behavioural inhibition and working memory degrade temporal processing; in studies adults with ADHD make more errors reproducing intervals, and the practical recommendations converge on external time cues (visible timers, dates made concrete, structured routines) rather than relying on an internal sense of time.
  - *Everyone underestimates and starts late.* Students who know they finished past work at the deadline still predict finishing the next early (the planning fallacy), and effort is applied when urgency is felt (student syndrome), so the distance to the deadline has to be made visible.
  - *If-then plans work on starting.* Implementation intentions ("when X happens, I will do Y") improved goal attainment with a medium-to-large effect (d about 0.65) across 94 studies, the mechanism targets the moment of initiation, and there is supporting but thinner evidence in ADHD samples and clinical analogue samples.
- **Sources:** Read-to-do and procedural text comprehension (https://www.academia.edu/48588753/Processing_text_and_pictures_in_procedural_instructions; https://arxiv.org/pdf/1805.06975); ADHD time perception and Barkley's model (https://www.simplypsychology.com/articles/adhd-time-blindness-guide; https://super-productivity.com/blog/adhd-time-blindness-strategies/); planning fallacy in students (https://www.researchgate.net/publication/288481604_Procrastination_and_the_Planning_Fallacy_An_Examination_of_the_Study_Habits_of_University_Students) and student syndrome (https://en.wikipedia.org/wiki/Student_syndrome); implementation intentions: Gollwitzer and Sheeran 2006 (https://howtostopprocrastinating.org/research/gollwitzer-2006-implementation-intentions/), Gollwitzer 1999 (https://www.prospectivepsych.org/sites/default/files/pictures/Gollwitzer_Implementation-intentions-1999.pdf), and a meta-analysis in clinical and analogue samples (https://bpspsychub.onlinelibrary.wiley.com/doi/10.1111/bjc.12086). Much of the ADHD-specific timing advice online is practitioner opinion; the strongest evidence here is the general planning-fallacy and implementation-intention work.
- **What "Do it" produces now (read from real builds: the BIO1101 brief built in round 1, Sam's ENG2207 and MMA3001 briefs, and tonight's two builds):** an overview with Deliverables, Due, Weight, Submit how, What you need to do (an imperative list), Assessed on and rules; section titles phrased as requirements; a "How it works" chip list of the process steps; a key fact for the deadline or weighting. All grounded in the source, with `¶` links.
- **Critique against the research:**
  1. *There is no first step.* The chips list the procedure, but nothing says "start here", and nothing separates a five-minute opening move from the whole job. The reader still has to decide where to begin, which is the initiation problem.
  2. *The deadline is an absolute date only.* "5 pm Friday 14 November 2025" asks the reader to compute how far away it is, which is exactly what time blindness and the planning fallacy make unreliable. The app knows today's date.
  3. *No sense of size.* The source often gives it (pages, words, number of datasets, weeks) but the overview does not gather it, so nothing counters the underestimate.
  4. *The essentials are a reference card, not a sequence.* Seven tiles of equal weight leave the reader choosing what to read next; the order is the model's.
  5. *Nothing supports "when".* No way to say, once, "I will start on Tuesday at 9", which is the if-then plan the strongest evidence supports. (Any such feature must stay free of progress bars, streaks and read marks.)
- **Proposals (none built; each needs Sam's call):**
  1. **"Start here" tile** for goal Do it: the first concrete action, taken from the earliest step or instruction in the source, worded as a short imperative, cited, and "not stated" when the brief gives no order. Prompt plus validator (it must be a substring-level paraphrase of a cited leaf). Small to medium.
  2. **Deadline in days, computed in the browser:** when an essential's value contains a parseable date, show "in 9 days" beside it (a plain time cue, no colours for urgency and no countdown that ticks). No model call. Small, low risk; needs a tolerant date parser and a rule to hide it when the date is in the past or ambiguous.
  3. **"Size of the job" tile** built only from numbers the source states (pages, words, datasets, weeks, sessions), each validated by the whole-number check. Prompt plus validator. Small.
  4. **Order the essentials** for goal Do it as: first step, due, size, deliverables, weighting, how to submit, everything else. Prompt only.
  5. **An optional "when will you start?" chooser** (today, tomorrow, pick a time) that stores a plain local note next to the document and shows it on reopening ("You planned to start Tuesday 9:00"). No notifications, no streaks, no marks. Evidence: d of about 0.65 for if-then plans in general, thinner in ADHD; worth testing in the ABAB protocol (R4) as a B-phase variant. Small to medium.
  6. **Fewer tiles at the top** for goal Do it (five instead of seven, the rest one zoom step deeper). This conflicts with Sam's wish that the key information be readable at the first level, so it is a trade-off to decide, not a recommendation.
- **How to tell if it worked (extends R4):** add "started within 24 hours" (yes or no, self-reported) and "time from first opening to first real action" to the ABAB record; the app can log the first opening, and the reader supplies the rest.
