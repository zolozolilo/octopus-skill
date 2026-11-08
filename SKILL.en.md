---
name: octopus
description: Use at the start of every task with more than one step, in any project — fix, feature, release, research, document, agent assignment — and when the user says "octopus", "tree", "leaves", "from both ends", "meet in the middle", "in parallel", "all at once", "faster".
---

# Task tree, two ends, everything in parallel

## Splash — the octopus shakes the trees
When this skill is invoked, first thing in the reply, print the drawing (once per task, in a code block). Falling leaves are tasks the agents pick up.
```
  .  '  *                       *  '  .
   _____          _____          _____
  / * * \        /     \        / * * \
 /* * * *\      | o   o |      /* * * *\
 \_______/      |  \_/  |      \_______/
    | |          \_____/          | |
    | |~~~~~~~~~~/|||||\~~~~~~~~~~| |
 '  | |  .      ~ ~ ~ ~ ~      .  | |  '
  ' | | .                       . | | '
-----------------------------------------
```
Under the drawing, one loading line: `tentacles busy: N of 8 — <agent: leaf>, …` (N = agents working right now).

## Status as a tree
Every status on a multi-step task is a tree with marks, not a wall of text:
```
v2.0
├─ ✔ A  login form
├─ ⏳ B  export no longer hangs (agent, ~10 min)
├─ ✘ C  sync — reviewer: defect, agent fixing
└─ ·  release — waits for A–C and checks
```
✔ done and verified by me · ⏳ in progress (who, how long left) · ✘ broken/returned · · waiting (for what). Under the tree, 1–2 lines: what is needed from the user. I put ✔ only after my own check (git, test, screenshot), never on an agent's report alone.

The tree can also be kept on a page: `python -I ~/.claude/skills/octopus/doska.py --help` — a board of leaves in `doska/derevo.json` and a local page `doska/doska.html` that updates itself.

Before handing leaves to agents, check file overlaps: `python ~/.claude/skills/octopus/peresechenie.py <task1.txt> <task2.txt> …` (a file named in two tasks means stop: one file, one agent). After an agent finishes: `peresechenie.py sverka <task> --repo <repo> --ot <base>` — promised vs. done.

## Code map — octopus × Graphify
If the repo has `graphify-out/` ([Graphify](https://docs.graphify.com), a code map), the map works at both ends of the tree:
- **Handing out:** add `--graphify <repo>` to the check above. One leaf directly calls or imports a file of another → STOP-LINK (one agent, or in sequence); linked through one shared file → "tell both"; a document references code → "reconcile the text"; tests that every leaf touches go to the acceptor.
- **Bottom end:** `peresechenie.py zadeto <file> … --repo <repo>` — who a change affects: directly, through one hop, tests, documents (2–3 s). These are verification leaves; put the output into the builder's task ("what not to break") and the acceptor's task ("which tests to run") instead of letting an agent read the repo. Do not call `graphify affected` for this: 33 s per file, and it misses a function call without a file import.
- "map older than code" — run `graphify update .` in the repo folder (no AI; minutes for a big repo) or use the `--obnovit` flag. "map: UNKNOWN" — no map or a foreign format: the check was not done, which is not "clean".
- The map sees calls and imports, but not shared JSON keys, data fields and string routes — and projects break silently exactly that way. For those, grep the exact name; "no links" from the map is not a guarantee.

Agent folders (always kept in order) — `python -I ~/.claude/skills/octopus/papki.py novaya --repo <repo> --put <folder> --vetka <branch> [--ot master]`. After EVERY release — `papki.py ubrat --repo <repo>`: shows what to clean up; then with `--da` it removes only merged, clean folders untouched for 12 h (no --force, branches only if merged).

## Essence
Any task is a tree of processes. Walk the tree and pick the leaves; everything that does not depend on each other is done SIMULTANEOUSLY; each branch is led from two ends toward each other — from the start (cause, data, requirements) and from the end (how the result reaches the person: release, text, check). Quality is not cut: checks are leaves too, running next to the code, not after it.

## First minute
1. **Root** — the goal in the user's words ("the form saves all fields", "the report is with the client").
2. **Branches** — processes: facts/cause, work (code, text, data), verification, delivery (release, file, link), people (what they must click or read).
3. **Leaves** — actions of 1–10 minutes. For each, note what it waits for.
The tree lives in the head or as 5–10 lines in a scratchpad; do not show it to the user unless asked.

## Flow
1. All leaves without dependencies go in one move: several tool calls in one message, agents in the background. Agents — one per independent branch in DIFFERENT files; one file, one agent, additions go to it as a message.
2. End B starts the same minute as end A: a draft of the release, text and checks while the work is being done.
3. A leaf is done — pick it up and immediately launch what was waiting for it. Wait for notifications, do not poll.
4. The verifier (reviewer, tests) reads the work as it goes; its "no" is a new leaf for the same executor, other branches do not stop.
5. The two ends meet in a short finale: tests/verdict → delivery → "done" backed by my own check.

## Scheme (drawings — `skhema-*.png` in the skill folder)
The same at every level: tree → branch → leaf → segment.
1. **Every leaf is a pair.** The builder goes from the cause (the change), the acceptor from the result: FIRST writes what must be true at the end (red acceptance tests, a scenario, a text for the person), then checks what was delivered. They meet in the middle when his checks are green. The acceptor starts the same minute as the builder, not after.
1a. **A red run is evidence, not words** (idea from fusion-harness): the output of the failing test (2–3 lines of FAIL) is saved into the handoff note BEFORE the code is changed; the agent's report contains the path to it. Acceptance: red output exists and exactly that test fails → only then may the leaf become ✔. No red run — the test proves nothing.
2. **A leaf longer than ~15 minutes is cut into segments**, each with its own pair. Three things in one task ("input validation + migration + button") are three segments, three pairs at once.
3. **A finished segment is accepted at once** — reviewer and live run go per segment and per intermediate merge, not on the whole build at the end.
4. **A critic on every piece of agent work** — anything that goes to the shared branch (main/master), to GitHub or to production is checked by an independent critic agent before merge (ready-made: `agents/kritik.md`, copy to `~/.claude/agents/`): it gets the task, `base..branch`, the test command; do not give it the author's report. RETURN — back to the same builder as a message. A small thing I fix myself without an agent, I verify myself.
Without this, tests get written after the code, and the reviewer and sandbox run after the merge — three extra rounds of "found → fix → check again".

## Like a torrent — the more peers, the faster
| Torrent | Here |
|---|---|
| A file is cut into pieces | Work is cut into leaves — small, independent, each in its own files |
| Peers download different pieces | Agents take different leaves at once; more leaves — more agents |
| The tracker hands out pieces | Me: I hand out leaves, merge the finished, write nothing myself where an agent can |
| Hash check of each piece | A test on each leaf — at once, before assembly |
| Rare pieces first | The longest path first (cause, code core) — the rest wait for it |
| A peer finished — seeds onward | An agent delivered a leaf — the next leaf goes TO IT as a message (context exists, cheaper than a new one) |
| File assembly | An assembly branch, merge after every leaf, full test run in the background |

The speed limit is the largest indivisible leaf and the one file everyone edits: cut it first (extract a function, a separate file), otherwise the peers wait for each other. The number of agents follows the number of independent leaves, not "≤2"; in quiet times be more frugal: every agent costs tokens.

## Two ends — wherever applicable
| Task | End from the start | End from the result (prepared at once) |
|---|---|---|
| Code/rule | the change | scenarios and law-tests BEFORE the code (they go red), reviewer on the move, release script, "What's new" |
| User complaint | analysis of the complaint | a log watcher from the first minute — learn before they write again |
| Server/prod | root-cause analysis | an apply script with auto-rollback and verification — ready before the user's "yes" |
| Research | search | the question "what will I do with the answer" and the place where the result will land |
Where the second end consciously waits (instructions for people only from screenshots of the build that will actually ship), say so plainly.

## When the user is in a hurry
"Faster", "full throttle", "all resources" — read `skorost-sveta.md` next to this file (in Russian): helpers for builders, a texts-and-delivery agent from minute one, warm-up; gates are never cut.

## Red flags
| Thought | Reality |
|---|---|
| "I'll do it one by one, it's more reliable" | Independent leaves go in one move |
| "I'll prepare the release/text later" | End B starts in the first minute |
| "I'll wait until everyone finishes" | A leaf is done — launch what depends on it |
| "I'll check at the end" | Verification is a branch of the tree, it runs alongside |
| "I'll call more agents onto one place" | One file, one agent |
| "The files differ, so the leaves are independent" | `--graphify`: a call or import between them is a STOP-LINK |
| "The map said no links, so it's clean" | The map does not see JSON keys, fields and string routes — grep the name |
| "The agent writes the code, then the tests" | The acceptor writes red tests at the same time as the builder's code |
| "One task for three changes is simpler" | Three segments — three pairs in parallel |
