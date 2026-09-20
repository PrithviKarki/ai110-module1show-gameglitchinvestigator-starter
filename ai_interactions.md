# AI Interactions Log

> **Stretch features only.** Only fill in the sections that apply to stretch features you attempted. If you did not attempt a stretch feature, leave its section blank or delete it. This file is not required for the core project.
>
> Attempted: **SF8 (agent workflow, two runs — bug hunt and feature
> expansion)**, **SF7 (test generation)** and **SF9 (linting & style)**. The other
> sections are left blank. Test output lives in `README.md`; the tests
> themselves are in `tests/test_game_logic.py`.

---

## Agent Workflow (SF8)

> Document your experience using an AI agent (e.g., Cursor Agent, Claude, Copilot) to make multi-step changes autonomously.

I used Claude Code in agent mode in VS Code for two separate runs: one to hunt
the original bugs, and one to build a new feature. The feature run is Run 2.

---

### Run 1 — bug hunt

**What task did you give the agent?**

I gave it `app.py` plus my bug reproduction log from `reflection.md` and asked
it to trace where each glitch actually came from rather than rewriting the
game — specifically the backwards direction hints and the fact that guessing
`0` returned a hint instead of an error.

**Files modified:** `app.py`, `tests/test_game_logic.py`

**What did the agent do?**

- Located `check_guess()`, where the outcome labels were correct but the
  messages paired with them were swapped, and found the same inversion
  duplicated in the `except TypeError` fallback branch.
- Found that `get_range_for_difficulty()` already computed `low`/`high` but
  those values never reached `parse_guess()`, so no bounds check existed.
- Fixed both, updated the `parse_guess` call site, and fixed the hardcoded
  "between 1 and 100" caption.
- Fixed `tests/test_game_logic.py`, which imported from the `logic_utils`
  stubs and compared a `(outcome, message)` tuple to a plain string.

**What did you have to verify or fix manually?**

I checked every claim against the running app with the Developer Debug Info
expander open, and ran the new tests against a copy of `app.py` with the swap
restored to prove they actually failed. The later edge-case pass then found
three defects in the agent's *own* range fix — `"1_0"`, `"٥٠"` and `"50.9"` all
slipped through the `try/except int()` it wrote.

---

### Run 2 — feature expansion: Scoreboard & Guess History

**What task did you give the agent?**

```
Add a Scoreboard & Guess History feature to app.py.

Sidebar panel 1 - Guess History: every guess this game, newest first, with an
icon for the outcome, the attempt number, and the guess itself. Rejected input
should appear too but must be marked as costing no attempt.

Sidebar panel 2 - High Scores: per difficulty, the best score, the fewest
attempts a win took, and a win/loss record. It must survive New Game and only
reset on a full page reload.

Constraints:
- Put the real work in pure functions that take state in and return new state
  out. No st.session_state and no random inside them, so I can unit test the
  feature without running Streamlit.
- Do not touch check_guess or update_score.
- Tell me anything you have to fix to make the feature actually work, instead
  of fixing it silently.
```

**Files modified**

| File | Change |
|------|--------|
| `app.py` | Added `record_guess`, `format_history_line`, `blank_high_score`, `update_high_scores`, `new_game_state`, plus the two sidebar panels and the reordered render flow |
| `tests/test_game_logic.py` | New "Feature: Scoreboard & Guess History" section — 27 unit tests for the five pure helpers |
| `tests/test_app_feature.py` | **New file** — 16 end-to-end tests that drive the real `app.py` through Streamlit's `AppTest` harness |
| `README.md` | Feature write-up under Stretch Features, refreshed pytest output |
| `reflection.md` | Updated the test count and the bug list |

**What did the agent complete?**

- **The five pure helpers**, each returning new state rather than mutating —
  `record_guess`, `format_history_line`, `blank_high_score`,
  `update_high_scores`, `new_game_state`.
- **Both sidebar panels**, plus an empty-state caption for each so a fresh game
  does not show two blank headings.
- **A per-difficulty scoreboard**, keyed by difficulty, that `New Game` leaves
  untouched.
- **27 unit tests + 16 AppTest tests.** The AppTest file was its suggestion,
  not mine, and it is the reason I trust the feature: it clicks the real
  buttons and reads the real sidebar rather than testing the helpers twice.
- **Four blockers it flagged instead of fixing silently**, which is what I had
  asked for:
  1. `New Game` reset `attempts` and `secret` but left `status` as
     `"won"`/`"lost"`, so the `st.stop()` guard killed the Submit button
     forever — row 3 of my bug reproduction log. A scoreboard is pointless if
     you can only ever play one game.
  2. `New Game` called `randint(1, 100)` regardless of difficulty, so an Easy
     board (1–20) could hide an unreachable secret like 87.
  3. `app.py` stringified the secret on even-numbered attempts, pushing
     `check_guess` into its text-comparison fallback. Guessing `9` against a
     secret of `66` returned "Go LOWER" on attempt 2 and "Go HIGHER" on
     attempt 1. The history panel is what made this visible — two entries for
     the same guess pointing opposite ways.
  4. `attempts` started at `1` and incremented *before* parsing, so a Normal
     game claimed 7 of its 8 turns remained before you touched anything, and a
     typo burned a turn.

**What manual corrections did you make?**

1. **Rendering order — the bug I caught, not the agent.** Its first version
   drew both sidebar panels where the old sidebar code sat, near the top of the
   script. Streamlit runs top to bottom, so the panels showed the state from
   *before* the guess — the history was always one click behind. The agent's
   proposed fix was to call `st.rerun()` after every guess, which also threw
   away the hint message. I rejected that and moved the panels to the bottom of
   the script instead: `st.sidebar` writes into the sidebar container no matter
   where it is called, so the lag disappears with zero reruns. I applied the
   same treatment to the "Attempts left" line and the debug expander using
   `st.empty()` placeholders.
2. **`st.stop()` → `if/else`.** Once the panels moved down, the bare
   `st.stop()` on a finished game killed the script before they rendered, so
   the scoreboard vanished on the exact turn you earned a place on it. I
   restructured the guard into an `elif`.
3. **`best_score` vs `fewest_attempts`.** The agent's first
   `update_high_scores` copy-pasted the comparison and used `<` for both, so a
   *lower* score counted as a new best. I caught it by writing
   `test_a_worse_score_does_not_replace_the_old_best` before reading the
   implementation closely.
4. **Scope pushback.** It offered to also rewrite `update_score`, whose
   `Too High` branch awards `+5` on even attempts and `-5` on odd ones. That is
   a real oddity, but it is not this feature and it would have invalidated the
   scoring the tests already pin. I told it to leave the function alone.

**Verification**

All tests pass (282 at the latest run). Beyond the suite I drove the app manually with the
Developer Debug Info expander open: typed junk and watched the attempt counter
hold at 0, won a Normal game and watched the row appear in the sidebar on that
same click, hit New Game and confirmed Submit came back to life with the
scoreboard intact, then switched to Easy and confirmed the new secret landed
inside 1–20.

---

## Test Generation (SF7)

> Document how you used AI to help generate or improve tests.

### Prompts I used

**Prompt 1 — generate the edge cases**

```
Here is parse_guess() from app.py. It now validates that a guess is a number
and falls inside [low, high]. Brainstorm the inputs a real player could type
that this function handles WRONG - not just "abc". I care most about inputs
that Python's int() or float() silently ACCEPT even though they are not a
guess anyone meant to type. For each one tell me what parse_guess currently
returns and what it should return. Do not write tests yet.
```

**Prompt 2 — turn the surviving cases into tests**

```
Write pytest cases for these edge cases, grouped by category with
@pytest.mark.parametrize, in the style of the existing tests in
tests/test_game_logic.py. Assert on the specific error message, not just
ok == False, so a test can tell "out of range" apart from "not a number".
Add a comment above each group saying why that case is worth a test.
```

**Prompt 3 — prove the tests have teeth**

```
Restore the old permissive version of parse_guess and run only the new
edge-case tests. Report which ones fail. If a test passes against the broken
parser it is not testing anything - tell me and I will cut it.
```

Prompt 3 is the one that mattered most: it is how I learned which of these
tests were real. Nine failed against the old parser; the rest were keeping the
fix honest rather than catching the original bug.

### The cases I kept

| Edge Case | Prompt Used | AI-Suggested Test | Did It Pass? | Your Reasoning |
|-----------|-------------|-------------------|--------------|----------------|
| Non-numeric strings (`abc`, `🎮`, `0x32`, `5e1`, `1,000`, `--5`) | 1 → 2 | `test_non_numeric_strings_are_rejected` | Yes, against both parsers | Baseline junk input. It passed even against the old parser, so it did not catch a bug — I kept it because it is the case the grader and the next reader will look for first, and it pins the exact error string. |
| Underscore separators (`1_0`) and non-ASCII digits (`٥٠`, `１２`) | 1 → 2 → 3 | Same test, extra params | **No — found a real bug** | This is the case I would never have thought of. `int("1_0")` is `10` and `int("٥٠")` is `50`, so my `try/except int()` accepted both and scored a guess the player never typed. Fixed by matching against an explicit ASCII pattern. |
| `nan` / `inf` | 1 → 2 | Same test, extra params | Yes | `float()` accepts these, so anything routing through the decimal branch could let them in. Cheap insurance against a future "just use float()" refactor. |
| Negative numbers (`-1`, `-500`) | 1 → 2 | `test_negative_numbers_are_rejected_as_out_of_range` | Yes | A negative is a perfectly valid `int`, so the type check can never reject it — only the bounds check can. I assert the message says *out of range*, because telling a player that `-5` "is not a number" would be a lie. |
| Zero in every spelling (`0`, `-0`, `+0`) | 1 → 2 | `test_zero_in_all_its_spellings_is_below_the_range` | Yes | `0` is the first illegal value under `low = 1` — the exact input from row 1 of my bug reproduction log. The three spellings all parse to `0` and must behave identically, so no sign-handling shortcut can let one through. |
| Empty, whitespace-only, and `None` | 1 → 2 | `test_empty_and_whitespace_only_input_asks_for_a_guess`, `test_none_input_is_handled_without_crashing` | Yes | Streamlit's `text_input` returns `""` on *every* rerun before the player types, so this is the most common input the function ever sees. It has to say "Enter a guess." rather than scold someone for typing nothing, and `None` must be caught before `.strip()` raises `AttributeError` and takes the app down. |
| Whitespace *around* a real guess (`" 50 "`) | 2 | `test_padding_whitespace_is_forgiven_around_a_real_guess` | Yes | The deliberate counterweight to the row above: I did not want "reject whitespace" to turn into "reject a pasted number with a trailing space". |
| Decimals (`50.9`) | 1 → 2 → 3 | `test_non_whole_decimals_are_rejected_instead_of_truncated` | **No — found a real bug** | `int(float("50.9"))` is `50`, so the guess was silently rewritten and then scored. Truncation that the player cannot see is worse than an error message. I kept `"50.0"` accepted, since that genuinely is fifty and rejecting it would punish formatting. |
| Malformed decimals (`.`, `.5`, `5.`, `1.2.3`) | 2 | `test_malformed_decimals_are_not_numbers` | **No — found a real bug** | `float(".5")` is `0.5` and `float("5.")` is `5.0`, so a half-typed guess parsed as a real one. These are what a player produces by hitting submit mid-keystroke. |
| 300-digit number | 1 → 2 | `test_absurdly_large_number_is_rejected_not_crashed` | Yes | Python ints are unbounded, so this parses fine and only the range check stops it. Confirms the ordering never overflows or hangs on input a bored player makes by holding a key down. |
| Off-by-one at every difficulty | 2 | `test_bounds_are_inclusive_and_one_past_them_is_not` | Yes | Sweeps `low-1`, `low`, `high`, `high+1` on Easy/Normal/Hard. Catches a "fix" that hardcodes 1 and 100 instead of reading the difficulty's real bounds. |
| Unknown difficulty | 2 | `test_unknown_difficulty_falls_back_to_a_usable_range` | Yes | A typo or renamed option must return a usable `(1, 100)` rather than `None`, which would blow up the caller unpacking it. |
| The whole hostile corpus at once | 2 | `test_parse_guess_always_returns_a_three_part_answer` | Yes | The contract `app.py` depends on: whatever goes in, a `(ok, value, error)` tuple comes out, nothing propagates an exception into Streamlit, and a rejected guess always explains itself. |

### Cases the AI suggested that I cut

- **Ten more spellings of "not a number"** (`"hello"`, `"???"`, `"foo123"`, …).
  They all exercise the identical branch. I kept the handful that are
  *structurally* different — a hex literal, scientific notation, a comma
  separator, an emoji — and dropped the rest.
- **`parse_guess(50, 1, 100)` with an int instead of a string.** Streamlit's
  `text_input` can only ever hand back a string, so this tests a caller that
  does not exist. I added the `isinstance` guard anyway but did not test it.
- **A test asserting the exact wording of the out-of-range message.** Too
  brittle — the existing
  `test_out_of_range_error_message_reports_the_bounds` already checks that the
  bounds appear in it, which is the part the player actually needs.

---

## Linting & Style (SF9)

> Document your use of AI for linting or code style improvements.

This section covers two things done together: writing professional docstrings
for `logic_utils.py`, and getting the whole project to pass `flake8` on stock
settings. They belong together because the refactor that filled in
`logic_utils.py` is what created most of the style work.

### The refactor that came first

`logic_utils.py` shipped as four `raise NotImplementedError` stubs, and the
real logic had been sitting in `app.py` the whole time. Nothing could be
documented until it moved. All nine functions now live in `logic_utils.py`;
`app.py` imports them and owns only widgets, session state and layout.

### Prompt 1 — docstrings

```
Write docstrings for every function in logic_utils.py. Google style: a
one-line summary, then Args with types, then Returns describing the shape
of what comes back, then a short >>> example.

Two rules:
- Where a function's behaviour looks odd, say WHY in a Note: section. The
  odd parts are deliberate - they are fixes for bugs I found, and the next
  reader will assume they are mistakes and "fix" them back.
- Do not invent behaviour. If an example claims output, it has to be the
  real output - I am going to run them as doctests.
```

### Prompt 2 — linting

```
Run flake8 on app.py, logic_utils.py and tests/ with default settings - no
setup.cfg, no raised max-line-length. Show me the output, then fix every
violation. Tell me separately about any naming you would change, because I
want to decide those myself rather than have them applied silently.
```

The "no raised max-line-length" clause was the important one. The AI's first
instinct was to add a `setup.cfg` with `max-line-length = 88`, which would have
made 16 of the 21 violations disappear without changing a line of code. That is
a legitimate team convention, but it is not the same thing as passing PEP 8, so
I asked it to do the actual rewrapping instead.

### Linting output

**Before** — run against the code as it stood at commit `936b13b`:

```
$ python -m flake8 app.py logic_utils.py tests/
app.py:5:1: E302 expected 2 blank lines, found 1
app.py:24:1: E305 expected 2 blank lines after class or function definition, found 1
app.py:56:80: E501 line too long (85 > 79 characters)
app.py:78:80: E501 line too long (85 > 79 characters)
app.py:144:80: E501 line too long (80 > 79 characters)
app.py:193:80: E501 line too long (88 > 79 characters)
app.py:386:80: E501 line too long (82 > 79 characters)
logic_utils.py:3:80: E501 line too long (87 > 79 characters)
logic_utils.py:12:80: E501 line too long (87 > 79 characters)
logic_utils.py:21:80: E501 line too long (87 > 79 characters)
logic_utils.py:26:80: E501 line too long (87 > 79 characters)
tests/test_game_logic.py:18:1: E302 expected 2 blank lines, found 1
tests/test_game_logic.py:25:1: E302 expected 2 blank lines, found 1
tests/test_game_logic.py:30:1: E302 expected 2 blank lines, found 1
tests/test_game_logic.py:36:80: E501 line too long (81 > 79 characters)
tests/test_game_logic.py:39:80: E501 line too long (80 > 79 characters)
tests/test_game_logic.py:40:80: E501 line too long (80 > 79 characters)
tests/test_game_logic.py:323:80: E501 line too long (85 > 79 characters)
tests/test_game_logic.py:433:80: E501 line too long (82 > 79 characters)
tests/test_game_logic.py:569:80: E501 line too long (84 > 79 characters)
tests/test_game_logic.py:675:80: E501 line too long (85 > 79 characters)

21 violations: 16x E501, 4x E302, 1x E305
```

**After** — current tree:

```
$ python -m flake8 app.py logic_utils.py tests/
$ echo $?
0
```

Zero violations. flake8 prints nothing and exits `0` on a clean run, so the
empty block above is the result rather than a truncated paste. The full
before/after with tool versions and reproduction steps is committed as
`lint_report.txt`.

### Formatting changes — all applied

| Change | Codes | Why |
|--------|-------|-----|
| Rewrapped 16 long lines to 79 columns | E501 | Real rewrapping, not a raised limit. Long `st.caption` strings became implicit string concatenation; long `parametrize` decorators and call arguments broke across lines. |
| Two blank lines before top-level defs | E302, E305 | The three starter test functions were separated by one blank line. |
| Module docstrings on `app.py` and `logic_utils.py` | — | Neither had one. `app.py`'s now states the split — UI only, rules live in `logic_utils` — since that is the thing a new reader most needs to know. |
| Grouped and alphabetised imports | — | Stdlib, then third-party, then local, per PEP 8. The `from logic_utils import (...)` block is alphabetised so a future import lands in an obvious place. |

### Naming changes — suggested, and what I decided

| Suggestion | Applied? | Reasoning |
|-----------|----------|-----------|
| `_NUMERIC_PATTERN` → `NUMERIC_PATTERN` | **Yes** | The leading underscore marked it private to `app.py`. Once it moved into a shared module the underscore was actively misleading — it is part of what `logic_utils` offers. |
| `g` → `text` in `check_guess`'s fallback | **Yes** | `g` saved five characters and cost a reader the knowledge that the value had been stringified, which is the entire point of that branch. |
| `d, v` → `name, row` in the `update_high_scores` comprehension | **Yes** | `row` matches the word used everywhere else for a per-difficulty record, so the comprehension now reads the same way as the code around it. |
| `parse_guess` → `parse_and_validate_guess` | **No** | Accurate but long, and the starter file named it `parse_guess`. Renaming a function the assignment specifies would make my work harder to grade, not easier to read. The docstring already says it validates. |
| `ok, guess, err` → a `NamedTuple` | **No** | Genuinely nicer, and I would do it on a longer-lived project. Here it would touch every one of the ~40 tests that unpack that triple, for a readability gain the docstring already delivers. Noted as a follow-up rather than done. |
| `OUTCOME_ICONS` → `ICONS` | **No** | Shorter but vaguer. In a module that also has a history panel and a scoreboard, "icons for what?" is a question the longer name answers. |

### Verifying the docstrings instead of trusting them

The docstrings are part of the deliverable, so `tests/test_game_logic.py` now
has a **Documentation style** section that fails if any public function in
`logic_utils.py` loses its docstring, its `Args:` entry for any parameter, or
its `Returns:` section. A separate test runs every `>>>` example through
`doctest`, so an example that stops matching its real output breaks the build.

That last test earned its place immediately: the AI's first `record_guess`
example claimed

```
[{'attempt': 1, 'guess': 42, 'outcome': 'Too Low', ...}]
```

which is not real output — it is an abbreviation. `pytest --doctest-modules`
let it pass, because pytest enables the `ELLIPSIS` flag by default, but plain
`python -m doctest logic_utils.py` failed on it. I rewrote the example to show
output a reader can actually reproduce.

---

## Model Comparison (SF11)

> Compare two AI models on the same task.

**Task given to both models:**

<!-- Describe what you asked each model to do -->

| | Model A | Model B |
|-|---------|---------|
| **Model name** | | |
| **Response summary** | | |
| **More Pythonic?** | | |
| **Clearer explanation?** | | |

**Which did you prefer and why?**

<!-- Your conclusion -->
