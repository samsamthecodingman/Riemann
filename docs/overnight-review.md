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
