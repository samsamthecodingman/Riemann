# Riemann Research: The Contrarian View (Failure Modes & Skepticism)

## 1. TL;DR
- **Friction is often necessary:** The "zoom dial" abstractions risk creating *fluency illusions* where users feel they understand a text just because it's easily readable, bypassing actual encoding and retention.
- **Expertise reversal:** Heavily structured, low-load interfaces (L0/L1 summaries) help novices but actively degrade comprehension for domain experts.
- **Spatial UI is often a trap:** 3D/depth-based spatial interfaces typically underperform 2D equivalents due to navigation overhead, occlusion, and "desert fog" (losing orientation during zooms).
- **Error cascading in LLM abstractions:** Summarizing a summary exponentially increases the risk of nuance-loss and hallucination.
- **ADHD "Streaks" are harmful:** Gamification mechanics relying on consistency cause shame-spirals for ADHD populations when broken.
- **Debunking baseline assumptions:** The premise that "minimizing cognitive load is always good" ignores *germane load* (the effort required to actually learn). Furthermore, several pop-science learning models (goldfish attention, strict learning styles) are debunked myths.

## 2. Findings

### Illusion of Explanatory Depth & Fluency Illusions
- **Claim:** Easily readable summaries (L0, L1) cause an illusion of competence. Users confuse perceptual fluency (ease of reading) with cognitive retention (actual understanding). When the LLM does the summarization, it bypasses the *Generation Effect* (users learn by creating summaries themselves).
- **Evidence Strength:** STRONG.
- **Sources:**
  - Bjork, R. A. (1994). *Memory and metamemory considerations in the training of human beings* (Desirable Difficulties).
  - Slamecka, N. J., & Graf, P. (1978). *The generation effect*.
  - Roediger, H. L., & Karpicke, J. D. (2006). *Test-enhanced learning* (Highlights testing/generation over restudying summaries).

### The Expertise Reversal Effect
- **Claim:** What helps a novice (highly structured, simplified L0/L1 summaries to reduce intrinsic load) actively hurts an expert. Experts already possess complex mental schemas; forcing them through over-simplified abstractions causes redundant processing and cognitive interference.
- **Evidence Strength:** STRONG.
- **Sources:**
  - Kalyuga, S., Ayres, P., Chandler, P., & Sweller, J. (2003). *The expertise reversal effect*. Educational Psychologist.

### ZUI Disorientation and the Failure of 3D Spatial Memory
- **Claim:** Depth-encoded spatial memory interfaces often fail in practice. Zoomable User Interfaces (ZUIs) suffer from "Desert Fog" (zooming into an area with no scale cues or landmarks). Furthermore, 3D spatial interfaces generally underperform 2D equivalents because navigation mechanics distract from the task, and objects occlude one another.
- **Evidence Strength:** STRONG.
- **Sources:**
  - Jul, S., & Furnas, G. W. (1998). *Critical zones in desert fog: Aids to multiscale navigation*. UIST.
  - Cockburn, A., & McKenzie, B. (2002). *Evaluating the effectiveness of spatial memory in 2D and 3D physical and virtual environments*. CHI. (Proves 3D offers no spatial memory benefit over 2D and often hinders retrieval).

### Compound Hallucination and Nuance Stripping
- **Claim:** Automatically generating hierarchical abstraction trees (L3 -> L2 -> L1 -> L0) creates cascading errors. If L2 hallucinates or flattens a nuanced hedging from L3, L1 magnifies that error, making L0 a confident, authoritative falsehood.
- **Evidence Strength:** MODERATE (Mechanistically certain in NLP, though formal user-harm studies in hierarchical UI are still emerging).
- **Sources:**
  - Bender, E. M., et al. (2021). *On the Dangers of Stochastic Parrots*. FAccT. (Focus on LLM detachment from meaning).
  - Practitioner knowledge: Data provenance research in NLP (e.g., attribution UI design).

### ADHD Gamification Harms
- **Claim:** Imposing streaks, "daily goals," or high-pressure adaptive nudges on ADHD users causes the "What the Hell" effect. Missing one day induces a shame spiral, causing complete system abandonment.
- **Evidence Strength:** MODERATE.
- **Sources:**
  - Marlatt, G. A., & Gordon, J. R. (1985). *Relapse prevention*. (Abstinence Violation Effect applied to behavioral design).
  - Practitioner ADHD Coaches (e.g., Russell Barkley's work on executive functioning and motivation deficits).

### Baseline Myths to Discard
- **Claim:** "Goldfish attention span" (humans have 8-second attention), strict "Learning Styles" (Visual/Auditory/Kinesthetic), and "Bionic Reading" guarantees.
- **Evidence Strength:** MYTH / DEBUNKED.
- **Sources:**
  - Pashler, H. et al. (2008). *Learning styles: Concepts and evidence*. Psychological Science.
  - BBC News reality check on the "Goldfish attention span" Microsoft study.

## 3. Design Implications for Riemann

1. **The "Prove It" Dial (Mitigating Fluency Illusions):** Don't just make the zoom dial passive consumption. At L1 or L0, Riemann should occasionally prompt the user to guess or expand the node *before* revealing the LLM's summary, utilizing the Generation Effect.
2. **2.5D over True 3D (Spatial View):** Do not use Z-axis depth to encode importance if it requires virtual camera movement. Use pseudo-depth (layered 2D planes, opacity, or shadow) to preserve fixed spatial coordinates without the occlusion/navigation tax of 3D.
3. **Minimap & Persistent Landmarks (ZUI Mitigation):** To prevent "Desert Fog" during zoom dial operations, a high-level structural minimap must *always* remain on screen.
4. **Provenance Highlighting (Mitigating AI hallucinations):** Hovering over a sentence in L1 should visually highlight the exact anchoring text in L3. If the LLM cannot confidently map the L1 claim to a specific L3 quote, the UI must visually degrade its certainty (e.g., rendering it with a dashed underline).
5. **Amnestic Recovery (ADHD design):** The system must welcome the user back gracefully after a 3-week absence without showing "overdue" counts, red badges, or lost streaks.

## 4. Signals Riemann Could Measure
- **Zoom-Velocity vs. Dwell Time:** If a user dials straight to L0 and immediately leaves, tag as *skimmed (low retention likely)*. If they dial between L1 and L2 iteratively, tag as *high engagement*.
- **Domain Familiarity (Implicit):** If the user frequently adjusts the dial to L3 for topics clustered in a specific spatial region (e.g., "Python programming"), Riemann should learn they are an expert here and default to higher complexity, avoiding the Expertise Reversal Effect.
- **Scroll Reversals:** Rapid scrolling up and down at L3 indicates high intrinsic cognitive load or confusion, signaling Riemann should gently suggest dialing back out to L2.

## 5. Contradictions and Caveats
- **Ease vs. Learning:** Riemann's brief states the goal is reaching "any chosen level of understanding in the shortest possible time." The literature fundamentally contradicts this: understanding requires *time and friction* (germane load). If Sam just wants to *retrieve facts*, low friction is good. If Sam wants to *understand/learn*, low friction is harmful. Riemann must decide if it is a reference tool or a learning tool.
- **ADHD novelty vs. stability:** The brief demands a "stable home anchor," which helps build reliable spatial memory. However, ADHD brains crave novelty for dopamine. Too much stability risks the UI becoming "wallpaper" (invisible/under-stimulating).

## 6. Gaps
- **Sensory Overload in Voice Channels:** The brief mentions "voice as a background channel." We have no research on how asynchronous voice processing interferes with visual reading tasks, especially for neurodivergent individuals (Auditory Processing Disorder is highly comorbid with ADHD). *The fleet needs a worker to investigate dual-channel sensory processing.*
- **LLM Summary Verifiability UIs:** How do users actually react to uncertainty markers in AI summaries? Do they ignore them (automation bias)? *The fleet should look into HCI studies on "Trust calibration in AI systems."*