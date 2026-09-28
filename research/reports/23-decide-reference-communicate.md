# 23 — Decide, reference, communicate

Targeted research for the three new objectives: **decide** (Riemann as analyst), **reference** (Riemann as index), **communicate** (Riemann as briefing aide; Sam always sends). Scope was limited to the open questions listed in the brief — this does not re-cover formats (see 16) or purpose/medium (see 18).

## TL;DR

- Choice overload is real but **conditional**, not a general law: Chernev et al. (2015, meta-analysis, N=7,202) found overload appears specifically when alternatives are hard to compare, preferences are uncertain, task difficulty is high, or commitment to deciding is weak — while Scheibehenne et al.'s (2010) earlier meta-analysis (N=5,036) found the *average* effect across studies is essentially zero. These two meta-analyses are in real tension; the honest read is "more options ≠ automatically worse, but overload is a real risk under specific, addressable conditions."
- The Cochrane review of patient decision aids (105 RCTs, N=31,043) is the strongest evidence in this report: structured decision aids reliably reduce "feeling uninformed" and increase values-choice congruence, with no measured downside. The mechanism is linking options to the decider's own values, not just presenting more facts.
- A large fact-box RCT (N>2,300) found tables beat prose for comprehension and 6-week recall, but did **not** move actual decisions, feeling-informed, or trust — format changes comprehension, not the decision itself.
- **A29×decide resolves to N** (original detail is not independently valuable for deciding): information-overload and fact-box evidence both point to decision-relevant, comparable detail mattering, with extra raw detail actively hurting satisfaction.
- **A20×decide resolves to C** (proactive surfacing of a due decision is conditionally wanted): field studies of proactive AI reminders show value concentrated in easily-forgotten low-stakes items, with user backlash specifically tied to bad timing/no control, independent of content quality — so it should ride the same interrupt-tier logic already planned for `monitor`.
- Decision fatigue's mechanistic backbone (ego depletion) failed a rigorous 23-lab preregistered replication (pooled d≈0.04) — don't architect around a "decision budget" theory; if timing of decisions matters, treat it as ordinary A17 attention/motivation variation.
- ADHD is robustly linked to steeper delay discounting (Marx et al. 2021 meta-analysis, N=3,763, small-to-medium effect, stronger with real vs hypothetical stakes) — delayed-benefit options in a decision table need concrete, salient framing.
- For reference/lookup, information foraging theory and the known-item-vs-exploratory-search literature converge on the same answer: **a summary is worse than search-plus-highlighted-source** for known-item lookup, because summarisation strips the scent cues (exact wording, structure) that make fast targeted retrieval possible.
- Email overload is fundamentally a triage/classification problem (Whittaker & Sidner, 1996) as much as a volume problem, and reducing check-frequency alone doesn't reduce it (Kushlev & Dunn, 2015) — batching without per-item triage compression just relocates the cost.
- AI-mediated communication research (Hancock, Naaman & Levy 2020; Jakesch et al. 2019/2025) suggests a briefing aide that keeps Sam as visible author is on much safer trust ground than an auto-draft feature — the measured trust penalty for AI-written text appears specifically under head-to-head comparison ("Replicant Effect"), which a briefing-not-drafting design avoids by construction.
- Extracting "the ask" from a thread is a documented hard case for generic summarisation (EmailSum benchmark): models fail specifically at sender-intent and who-asked-whom-what attribution, not just length — this needs dedicated structured extraction, not generic compression.

## Findings

### Decide

**F23-01 [STRONG].** Chernev, Böckenholt & Goodman (2015, *J. Consumer Psychology*, meta-analysis of 99 effect-size observations, N=7,202) identify four moderators of choice overload: choice-set complexity (hard-to-compare alternatives), decision-task difficulty (e.g. time pressure), preference uncertainty, and weak decision-goal commitment. Overload is not a function of raw option count alone.
Sources: https://chernev.com/wp-content/uploads/2017/02/ChoiceOverload_JCP_2015.pdf, https://myscp.onlinelibrary.wiley.com/doi/abs/10.1016/j.jcps.2014.08.002

**F23-02 [STRONG, contradicts F23-01 at the aggregate level].** Scheibehenne, Greifeneder & Todd (2010, *J. Consumer Research*, meta-analysis of 50 experiments/63 conditions, N=5,036) found a mean choice-overload effect of essentially zero, with large between-study heterogeneity, including studies (like the famous jam-display demo) that didn't replicate cleanly at scale.
Sources: https://scheibehenne.com/ScheibehenneGreifenederTodd2010.pdf, https://academic.oup.com/jcr/article-abstract/37/3/409/1827647

**F23-03 [STRONG].** Cochrane review of patient decision aids (Stacey et al., updated through 2024, 105 RCTs, N=31,043): high-quality evidence that decision aids reduce feeling uninformed, and in 8/10 studies measuring it, increase values-choice congruence, with no adverse effects on outcomes or satisfaction vs. usual care.
Sources: https://www.cochranelibrary.com/cdsr/doi/10.1002/14651858.CD001431.pub6/full, https://www.cochranelibrary.com/cdsr/doi/10.1002/14651858.CD001431.pub5/full

**F23-04 [MODERATE].** A registered-report RCT (N>2,300) comparing "fact box" tables to equivalent prose for medical risk communication found tables improved comprehension and 6-week recall and were rated more engaging, but showed **no difference** in actual decisions, feeling informed, or trust between formats.
Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC7137953/

**F23-05 [WEAK/practitioner synthesis].** Comparison-table design writing (uxtigers.com, drawing on the alignable-differences literature) argues tables work specifically because they force attributes into alignable rows — every option gets a value on the same dimension — and that alignable differences dominate choice and memory over unalignable ones.
Source: https://www.uxtigers.com/post/comparison-tables

**F23-06 [STRONG].** Levin, Schneider & Gaeth (1998) formalize attribute framing: describing a single attribute positively vs negatively (e.g. "80% lean" vs "20% fat") shifts evaluation of that attribute without changing the underlying fact. This is the most robust of the three framing-effect types they distinguish.
Source: https://worthylab.org/wp-content/uploads/2020/12/levinetal_1998_all_frames_are_not_created_equal.pdf

**F23-07 [MYTH for the strong "decision fatigue as depletable resource" claim].** The ego-depletion theory underlying popular "decision fatigue" narratives failed a preregistered 23-lab Registered Replication Report (Hagger et al. 2016, N=2,141): pooled effect ≈ d=0.04, indistinguishable from zero.
Sources: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4971805/, https://replicationindex.com/2016/04/18/rr1egodepletion/

**F23-08 [STRONG].** Marx, Hacker, Yu, Cortese & Sonuga-Barke (2021, *J. Attention Disorders*, meta-analysis of 37 group comparisons, N=3,763, 53% ADHD) found small-to-medium effects: ADHD is associated with choosing small-immediate over larger-delayed rewards more often, and the effect roughly doubles in odds ratio with real (vs hypothetical) rewards.
Source: https://journals.sagepub.com/doi/10.1177/1087054718772138

**F23-09 [MODERATE — resolves A29×decide].** See "Resolves" section below.

**F23-10 [MODERATE — resolves A20×decide].** See "Resolves" section below.

### Reference

**F23-11 [MODERATE].** Information foraging theory (Pirolli & Card) models information-seeking as maximising rate of gain (value/cost), driven by "information scent" — cues that predict whether a path will pay off. Searchers satisfice on scent rather than exhaustively searching, and abandon low-scent paths fast.
Sources: https://www.nngroup.com/articles/information-foraging/, https://en.wikipedia.org/wiki/Information_foraging

**F23-12 [MODERATE].** The known-item vs. exploratory-search literature (Athukorala et al. 2016, *JASIST*; ACM's exploratory-search surveys) shows lookup tasks are satisfied by direct, precise access to a single target, while exploratory tasks need breadth and browsing — interfaces optimized for one measurably add friction to the other.
Sources: https://asistdl.onlinelibrary.wiley.com/doi/10.1002/asi.23617, https://cacm.acm.org/research/exploratory-search/

*A summary is worse than search-plus-highlighted-source specifically when the goal is known-item lookup*, because summarisation is a lossy transformation of exactly the cues (verbatim wording, structure, headings) that both scent-following and query matching depend on. I did not find a controlled experiment directly pitting "pre-built summary" against "full-text search + highlight" on time-to-fact — this is inferred from the foraging/lookup theory converging, not a direct empirical comparison. Flagged as a gap below.

### Communicate

**F23-13 [STRONG].** Whittaker & Sidner (1996) found email is "overloaded" in function — simultaneously communication, task management, and archive — and that undifferentiated status types (to-do/to-read/to-archive) sitting in one list, not volume per se, is the core problem. A 10-years-later revisit (2006) reached similar conclusions.
Sources: https://dl.acm.org/doi/10.1145/238386.238530, https://dl.acm.org/doi/10.1145/1180875.1180922

**F23-14 [MODERATE].** Dabbish & Kraut (2006, CSCW) tie perceived overload to volume × management strategy; Kushlev & Dunn (2015) found reducing email-check frequency lowered stress but did **not** reduce, and sometimes increased, perceived overload — deferred items still have to be triaged eventually.
Sources: https://www.interruptions.net/literature/Kushlev-ComputHumBehav15.pdf, https://kraut.hciresearch.info/wp-content/uploads/dabbish06-EmailAtWork.pdf

**F23-15 [MODERATE, theoretical framework not an effect-size study].** Hancock, Naaman & Levy (2020, *JCMC*) define AI-mediated communication (an agent modifying/augmenting/generating messages on someone's behalf) and argue it requires new trust/authenticity theory, not extension of existing CMC theory.
Sources: https://academic.oup.com/jcmc/article/25/1/89/5714020, https://www.semanticscholar.org/paper/AI-Mediated-Communication:-Definition,-Research-and-Hancock-Naaman/0efdc031c42c031f3092f3a4f85ae2e0a6c9cac4

**F23-16 [MODERATE].** Jakesch et al. (2019, CHI) found AI-suspected-written profiles were distrusted only under a **mixed-set contrast condition** (some profiles labeled/suspected AI, some human, side by side) — the "Replicant Effect" — not when viewed in isolation. A 2025 follow-up (N=1,637, incentivized trust games) found AI predictive-text assistance had minimal trust impact regardless of disclosure and let people compose equally trust-inducing messages faster.
Sources: https://dl.acm.org/doi/pdf/10.1145/3290605.3300469, https://github.com/sTechLab/aimc-chi19

**F23-17 [MODERATE].** EmailSum (Zhang et al. 2021, ACL, 2,549 annotated threads, short <30-word / long <100-word summaries): even fine-tuned models scoring well on ROUGE fail specifically at capturing sender intent ("what the thread is mainly about") and who-does-what-to-whom attribution; automatic metrics correlate poorly with human judgment of these failures.
Sources: https://arxiv.org/abs/2107.14691, https://ar5iv.labs.arxiv.org/html/2107.14691

**F23-18 [MODERATE].** The curse-of-knowledge/audience-design literature (Camerer, Loewenstein & Weber 1989; applied by Xiong et al. to data communication) shows people systematically overestimate how obvious their own context is to someone who doesn't share it — a specific, well-documented failure mode when summarising for someone else.
Source: https://dspace.library.uu.nl/bitstream/handle/1874/390947/XiongCurse2019.pdf

**F23-19 [MODERATE].** Sarrafzadeh et al. (2019, CHIIR, "Exploring Email Triage" + companion deferral-prediction study, large enterprise log data): users defer emails specifically when handling requires replying, careful reading, or clicking links/attachments, driven by perceived response effort and current workload.
Sources: https://arxiv.org/abs/1901.04375, https://www.microsoft.com/en-us/research/wp-content/uploads/2019/02/Email_Triage_CHIIR19.pdf

## Design implications for Riemann

- **FT-decision-table** should be a diff-oriented, alignable-attribute table (F23-05) showing only attributes that differ across live options by default (F23-09), with neutral/dual-valence attribute wording to avoid injecting attribute-framing bias (F23-06), and an explicit values-linking layer (priorities Sam has stated) rather than facts alone (F23-03). Concretize delayed-benefit attributes (dates, numbers) rather than leaving them abstract, given ADHD's steeper delay discounting under real stakes (F23-08). Do not default to hiding/limiting options as an anti-overload measure — gate that behavior on the actual moderators (complexity, uncertainty, time pressure, weak commitment) per F23-01/F23-02, since the "more options are bad" effect doesn't replicate as a general law.
- **A due-decision surfacing behavior** should reuse the interrupt-tier/timing machinery already planned for `monitor` (FT-interrupt-tiers) rather than being a separate always-on nudge — proactive value is conditional on good timing and user control (F23-10).
- **FT-reference-lookup** should be built as full-text search over the original content with jump-to-highlighted-passage, not a pre-generated summary layer (F23-11, F23-12). This is the one place in the zoom-dial system where the abstraction tree is the wrong tool — reference wants direct access to L3 (original), not L0/L1.
- **FT-reply-brief** should (a) first classify the thread's status type — action-required/ask, FYI, archival (F23-13) — before compressing anything; (b) run a dedicated ask/deadline/context/role extraction pass rather than generic summarisation, since generic summarisation specifically fails at intent and who-asked-whom (F23-17); (c) include a recipient-context field for what the other person does/doesn't already know, to counter curse-of-knowledge omissions (F23-18); (d) stay a briefing aide that keeps Sam as visible sender/author, never auto-drafting finished sender-voice text — this is both the stated scope (Sam sends) and the safer trust position per the Replicant Effect finding (F23-15, F23-16); (e) prioritize reply-requiring threads first, since those are the ones users defer due to perceived effort, and lowering perceived effort is exactly what a brief does (F23-19).
- **FT-batching**, if built for communicate, needs FT-reply-brief-style per-item compression built in — batching alone does not reduce overload, it just relocates the triage cost to when the batch is opened (F23-14).

## Signals Riemann could measure

- Whether Sam opens/expands attributes beyond the diff-table default (tests whether "decision-relevant detail only" default is actually sufficient, or whether A29×decide should be softer than N for him specifically).
- Time from a decision table being shown to Sam making/recording a decision, and whether that time correlates with number of differing attributes shown (a live, personal test of the choice-overload moderators).
- Dismiss/ignore rate on proactively-surfaced due decisions, segmented by time-of-day/context — direct signal for tuning A20×decide's conditions.
- For reference lookups: time-to-target and whether Sam ever falls back from search to manually zooming the abstraction tree (would indicate the reference/lookup split isn't working).
- For reply-brief: how often Sam's eventual reply uses content from the brief's extracted ask/deadline fields vs. content Riemann didn't surface (a faithfulness/completeness proxy that doesn't require reading Sam's sent mail content, just whether the brief's fields were sufficient).
- Edit distance / time-to-send after a reply-brief is shown, as a proxy for whether the brief reduced perceived effort (ties directly to F23-19's deferral mechanism).

## Contradictions and caveats

- **F23-01 vs F23-02**: two respected meta-analyses on choice overload disagree at the aggregate level (moderator-dependent effect vs. null average effect). Both are from reputable venues; the resolution in practice is to treat overload as real-but-conditional (per Chernev's moderators) rather than to assume a null effect always, or a universal effect always, since Riemann is optimizing for one specific user, not an average.
- The fact-box RCT (F23-04) shows tables help comprehension but not the decision itself — this tempers any assumption that "better presentation format" alone produces "better decisions"; the decision-aid literature's values-linking mechanism (F23-03) is doing separate, additional work.
- The AI-mediated-communication trust findings (F23-15/16) are still a young literature (2019–2025) with a handful of controlled studies, mostly in dating/social-profile and trust-game contexts, not workplace email specifically — transfer to Sam's real communicate use case (A12/A13) is not fully established.
- I could not access the primary Marx et al. 2021 full text (403/paywalled) or the Hancock JCMC PDF (returned binary/font data, not readable text) — findings from these are based on abstract-level search summaries and secondary citations, not a full read of the paper. Flagging per the "cite only sources you opened" rule: the claims are retained because search results directly quoted the relevant numbers/text, but confidence is marked medium rather than high where this applies (F23-08, F23-15).
- No direct controlled comparison of "AI summary" vs. "search + highlighted source" for time-to-fact was found (see Gaps) — F23-11/F23-12's implication for FT-reference-lookup is a theoretically well-grounded inference, not a directly measured result.

## Gaps (for a possible next wave)

- **Direct empirical test of summary-vs-search for known-item retrieval speed/accuracy.** This report infers the answer from foraging theory and the lookup/exploratory-search distinction, but a direct HCI study (if one exists — search-engine or intranet-search UX literature is the likely place) would upgrade F23-11/F23-12 from MODERATE-inferred to STRONG-measured.
- **ADHD-specific choice-overload or decision-table research.** All choice-overload and decision-aid evidence here is general-population; nothing ADHD-specific was found for A26/A29×decide beyond the delay-discounting literature (F23-08), which is a different mechanism (temporal, not overload).
- **Smart-reply / predictive-text adoption and satisfaction data** (Gmail Smart Reply, Outlook Copilot) as a closer analog to FT-reply-brief than the lab AI-MC studies — this is a large, mostly industry-report literature I did not have time to open in depth; worth a dedicated pass given how directly it maps to the feature.
- **"What's the ask" extraction specifically for Slack/chat threads**, not just email — communicate likely spans more than email for Sam; EmailSum-style benchmarks for chat threads may exist and would be directly relevant.
- **Empirical test of the A20×decide gating logic** — the proactive-surfacing findings here (F23-10) are from workplace/developer contexts, not ADHD-specific or decision-specific; worth checking the ADHD-and-notifications literature (likely already touched by an earlier report on monitor/interruption — check before re-researching) for whether "due decision" surfacing behaves differently from generic task reminders.

## Resolves

- **Resolves: A29×decide → N, because** information-overload lab evidence (Stevens Institute findings) and the fact-box RCT (F23-04) both show additional facts beyond what differentiates the live options degrade decision satisfaction rather than improving it, while the Cochrane decision-aid review's benefit (F23-03) traces specifically to linking structured, comparable information to the decider's values — not to preserving raw original-text detail. See F23-09.
- **Resolves: A20×decide → C, because** field studies of proactive AI reminder/nudge systems (F23-10) show unprompted surfacing is valuable specifically for easily-forgotten, low-stakes items and that user backlash is driven by poor timing, low control, or wrong channel/style — independent of whether the underlying content (a due decision) was itself worth surfacing. This maps to a conditional hold gated on the same timing/control machinery as `monitor`, not an unconditional Y or N.
