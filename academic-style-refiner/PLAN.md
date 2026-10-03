# Academic Style Refiner: next-version plan

Status: **paused**. Agreed in discussion; nothing below is built yet.
The first version (Python/FastAPI backend + React frontend, Claude-only) is in this folder.

## Target setup

- **Online website**, used in the browser on an Android phone (Tecno Spark 40) and a
  low-memory laptop (HP ProBook 430). Installable with "Add to Home screen".
- **Hosting:** GitHub Pages in a **new public repository** (not the private `WORK`
  repository). All processing runs in the browser; no server stores documents.
- **AI engine, chosen in Settings** (key saved only on the user's device):
  - Claude Opus 5.5: best quality, paid (default model ID `claude-opus-5-5`)
  - Gemini 3.8 Flash: free tier, very good quality; Gemini 3.5 Flash-Lite as backup
    when the free daily limit runs out. Group paragraphs per request and wait
    automatically for free-tier rate limits.
- **Decision still open:** which engine is the default.

Offline/on-device models were ruled out: the target devices cannot run a model good
enough for this task (see discussion notes below).

## Features to build

1. **Full-document context.** Rewrite one paragraph at a time, but include the whole
   document as background (prompt caching on Claude, 1-hour TTL) for consistent
   terminology and flow.
2. **Diagnose -> target -> verify.**
   - Diagnose each paragraph in the browser (no AI cost): stock phrases, repetitive
     sentence openings, uniform sentence lengths, overused connectives, nearby
     repeated words (excluding technical terms), overlong sentences, wordy
     constructions, vague statements.
   - Give each paragraph a "needs work" level; skip or lightly touch good paragraphs.
   - Send targeted instructions naming the specific problems.
   - Re-score after rewriting; retry once with feedback if the problems remain.
   - Show a per-paragraph summary such as "Fixed: 2 stock phrases, repetitive openings".
3. **Change report** (for the user's own records): original vs refined per paragraph,
   exportable as .docx/.pdf.
4. **"Fix this paragraph"**: a single flow (replaces the separate Rework mode and
   "Help me write it"):
   1. key points, citations and numbers shown as notes;
   2. optional quick question ("Add a detail from your work?"), answered by tap,
      typing or voice, or skipped; one set of questions per document is also possible;
   3. rewritten draft in an editable box (uses the supervisor's comment if any);
   4. user accepts or edits the draft;
   5. live check: all key points kept, citations and numbers exact, tips for any
      remaining stiff phrasing;
   6. "Use this paragraph" replaces only that paragraph.
   Supports one paragraph, several selected paragraphs, or a whole colour group.
5. **"Use a source properly" helper**: paste a source passage + reference -> plain-
   language summary -> paraphrase draft with the citation added -> closeness check
   against the source (warn and suggest quoting if too similar) -> insert.
6. **Supervisor PDF upload.**
   - Read highlight annotations (text under each highlight, its colour) and comments.
     Comments are optional; with no comment, the diagnosis decides what to fix.
   - Also read highlights from a supervisor's .docx (Word text highlight colour).
   - Colour actions, set once and remembered: Rewrite / Grammar and wording only /
     Check citation / Ignore. Default: all colours = Rewrite. Group similar shades.
   - Flagged list grouped by colour, showing location, highlighted text and comment.
   - Option to fix only the highlighted sentences (default) or the whole paragraph.
   - Input options: paste paragraphs only, supervisor's PDF only, or (recommended)
     PDF + the user's original .docx, which returns the .docx with only the fixed
     paragraphs changed and formatting kept.
   - Fallback: tap paragraphs manually when highlights can't be detected
     (pen marks, drawn shapes, scanned PDFs).

Keep from version 1: citation/number/quote/URL/maths locking, fidelity checks with
retry and fallback, Light/Moderate/Strong intensity, side-by-side and inline diffs,
regenerate / keep original, metrics panel, .docx/.pdf/.txt export, no server-side
storage. Also make the layout phone-friendly and save progress on the device.

## Removed by the user's choice

- Voice matching
- Self-edit mode
- Disclosure statement (the general Responsible Use note in the app and in
  `docs/RESPONSIBLE_USE.md` stays; it is never added to documents)

## Out of scope

- AI-authorship detection scores, or rewriting text until a detector is satisfied.
- Rewording other writers' work to present it as the user's own.

## Estimated costs (Claude Opus 5.5; not yet measured)

| Task | Approximate cost |
|---|---|
| Refine one paragraph | ~4 cents |
| "Fix this paragraph" | ~5-10 cents |
| Highlighted paragraphs with the full 10,000-word work as background | ~15-20 cents for the first, ~4-8 cents each after |
| Whole 10,000-word work with full-document context | ~$2.50-3.50 |

Claude Sonnet 5.5 is roughly half these prices. Gemini 3.8 Flash on the free tier is $0
(Google may use free-tier text to improve its products).

## Discussion notes

- Offline on the target devices is not practical: the HP 430 has ~3.7 GB usable RAM
  and the Tecno Spark 40 has a Helio G81 with a weak GPU. Even quantized,
  Qwen3-8B needs ~5-6 GB. A 10,000-word offline run needs at least 16 GB RAM
  (overnight, fair-good quality) or a GPU with 8-12 GB+ (good quality, under 30 min).
- Copy-paste mode (prepare prompts for any chat website) was discussed as a no-key
  fallback; not on the build list.
- Free GitHub Pages requires a public repository; keep school work out of it.
