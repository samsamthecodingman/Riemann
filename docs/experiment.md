# Does Riemann help? A two-week check you can run yourself

This is a small experiment on your own reading, not a study. It takes about 30 minutes to set up and a few
minutes per document. At the end you will have your own numbers on whether reading in Riemann got you to "I know
what to do" faster, with fewer misses and less effort, than reading the original.

It uses an **ABAB** design: you alternate between reading the original (A) and reading in Riemann (B), and you
look for the same difference showing up again after the switch back. One person is both the experiment and the
control, so the pattern across the phases is the evidence. There is no p-value to compute.

## What you need

- About 12 documents from your real life, all the same kind: a weekly assignment brief or a weekly reading is ideal.
  Mix is fine, but "something with a checkable outcome" matters.
- A stopwatch (your phone), and a way to write a number down (a notes file or a spreadsheet).
- Riemann running as usual. Its event log already records opening, zooming, source checks and closing; the
  experiment adds a few optional fields (listed below).

## The plan

1. **Fix the order before you start.** Four phases of about three documents each, in this order:
   `A1` (original), `B1` (Riemann), `A2` (original), `B2` (Riemann). Decide which document goes in which phase
   now, so you do not choose easy ones for Riemann. Put at least one B document late in the two weeks, once the
   novelty has worn off.
2. **Before you read each document**, write down the three things you think you must do. Takes a minute.
3. **Read it.** In an A phase, read the original the way you normally would. In a B phase, read it in Riemann.
   Start the stopwatch when you begin.
4. **Stop the stopwatch** at the moment you can say "I know what to do". That is the first number.
5. **Score yourself** against the source with the same five questions every time (0 to 5, one point each):
   1. What is due, and when?
   2. What is it worth?
   3. What do I have to submit?
   4. What is allowed and not allowed?
   5. What is unclear or missing?
6. **Rate the effort** (NASA-TLX, six sliders from 0 to 100, under a minute): mental demand, physical demand,
   hurry, how well it went, effort, frustration.
7. **A week later**, answer one yes/no: did I find I had missed something? And, if you want to test getting started:
   did I start within 24 hours, and how many minutes passed between first opening it and doing the first real
   thing? (These last two are the "Do it" questions: Riemann's new first-step and deadline lines are meant to
   help exactly there.)

## What Riemann records

All of it stays on your machine, in the event log (`~/.local/share/riemann/events.jsonl`, or under
`RIEMANN_DATA_DIR`). Nothing records progress, "read" marks or the text of a document.

| Event | Fields | When |
|---|---|---|
| `experiment` | `action` (`set` or `end`), `condition` (`A` or `B`), `phase` (`A1`, `B1`, `A2`, `B2`), `doc_label` | When you start a phase or move to the next document. Everything after it belongs to that phase and document, until the next `experiment` event |
| `close` | `tree_id`, `session_ms`, `first_zoom_ms`, `max_z`, `source_checks` | When you close a document in Riemann (the extra fields are new and optional) |
| `did_it_help` | `tree_id`, `value` (yes or no) | When you close, if asked |
| `outcome` | `doc_label`, `minutes_to_know`, `checklist_score`, `tlx_mental`, `tlx_physical`, `tlx_temporal`, `tlx_performance`, `tlx_effort`, `tlx_frustration`, `missed_later`, `started_within_24h`, `minutes_to_first_action` | One per document, or several partial ones for the same document (they are merged by `doc_label`) |

Any event can also carry `condition`, `phase` and `doc_label` itself. Values outside the allowed ranges are
dropped when the event is saved, and the rest of the event is kept.

## In the app

On the home page, a collapsed **Experiment** section (it says "off" until you use it) sets the condition (A the
original, B Riemann), the phase (A1, B1, A2, B2; choosing a phase sets the condition) and an optional document label
(no document text). **Start** (or **Update**) sends an `experiment {action: "set"}` event and remembers the choice on this
device; **End experiment** sends `{action: "end"}` and turns it off. While it is on, `open`, `close`, `did_it_help` and
`outcome` events also carry the condition, phase and label.

Whether or not the experiment is on, every `close` event carries the session numbers: `session_ms`, `first_zoom_ms`
(open to the first zoom; left out if you never zoomed), `max_z` and `source_checks`. When the experiment is on, closing a
document shows a small dismissible card on the home page: "Did it help?" (Yes or No, B phases only; sends `did_it_help`)
and "Add the numbers", a form for `outcome` (minutes until you knew what to do, the 0 to 5 checklist score, the six effort
sliders, and the "a week later" answers). Every field is optional and only what you fill in is sent; reopen the form from
the Experiment section later with the same label to add the rest. Nothing is shown in the reader, and nothing at all
when the experiment is off.

You can also write an event by hand while Riemann is running, for example when you start phase B1:

    curl -s -X POST http://127.0.0.1:8765/api/events -H 'Content-Type: application/json' \
      -d '[{"type":"experiment","action":"set","condition":"B","phase":"B1","doc_label":"week1-brief"}]'

and after reading, the numbers for that document:

    curl -s -X POST http://127.0.0.1:8765/api/events -H 'Content-Type: application/json' \
      -d '[{"type":"outcome","doc_label":"week1-brief","minutes_to_know":6,"checklist_score":4,"tlx_mental":40,"tlx_physical":10,"tlx_temporal":35,"tlx_performance":30,"tlx_effort":40,"tlx_frustration":25}]'

(Or keep the numbers in a spreadsheet; the report below can also produce a CSV to compare with.)

## Reading the result

    uv run python scripts/experiment_report.py             # a readable summary by phase
    uv run python scripts/experiment_report.py --csv       # one row per document, for a spreadsheet
    uv run python scripts/experiment_report.py --json      # everything, for your own chart

The summary shows, for each phase, the median minutes to know what to do, the mean checklist score and effort,
the yes/no answers, and in the B phases how long you stayed, how soon you first zoomed, how deep you went and how
often you checked the source. Under it is the pattern across the phases, for example
`A1 15 > B1 7 > A2 14 > B2 6 (better) (worse) (better)`: B beat A, it reverted when you went back to A, and it
improved again in B2. **That shape, repeated, is the result.** One good B phase alone could be novelty or an easy
batch of documents.

Things that should make you doubt a result: only one B phase beat A; the B documents were easier; the numbers
moved in the first B phase and not the second (novelty); or you started to time yourself differently. If so, run
another round with the documents re-ordered.

## Limits

This shows what happened for you, with your documents, over two weeks. It cannot tell you why, and it does not
generalise to anyone else. It also cannot rule out that you read more carefully because you were being measured.
That is fine for deciding whether to keep using the tool.
