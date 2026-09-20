# 🎮 Game Glitch Investigator: The Impossible Guesser

## 🚨 The Situation

You asked an AI to build a simple "Number Guessing Game" using Streamlit.
It wrote the code, ran away, and now the game is unplayable. 

- You can't win.
- The hints lie to you.
- The secret number seems to have commitment issues.

## 🛠️ Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Run the app: `python -m streamlit run app.py`
3. Run the tests: `python -m pytest tests/`
4. Check style: `python -m flake8 app.py logic_utils.py tests/`

## 📂 Project Structure

| File | Role |
|------|------|
| `logic_utils.py` | All 14 game-logic and formatting functions, each with a Google-style docstring and a runnable `>>>` example. No Streamlit, no global state — which is why the whole game is testable without a server. |
| `app.py` | Streamlit only: widgets, session state, layout. Imports every rule from `logic_utils`. |
| `tests/test_game_logic.py` | Unit tests for the logic, the edge cases, the feature helpers, and the docstrings themselves. |
| `tests/test_app_feature.py` | End-to-end tests that drive the real `app.py` through Streamlit's `AppTest` harness. |
| `lint_report.txt` | Committed flake8 before/after. |

## 🕵️‍♂️ Your Mission

1. **Play the game.** Open the "Developer Debug Info" tab in the app to see the secret number. Try to win.
2. **Find the State Bug.** Why does the secret number change every time you click "Submit"? Ask ChatGPT: *"How do I keep a variable from resetting in Streamlit when I click a button?"*
3. **Fix the Logic.** The hints ("Higher/Lower") are wrong. Fix them.
4. **Refactor & Test.** ✅ Done — all nine functions now live in
   `logic_utils.py` with full docstrings, `app.py` is pure UI, and the suite
   is green at 456 tests.

## 📝 Document Your Experience

- [ ] Describe the game's purpose.
- [ ] Detail which bugs you found.
- [ ] Explain what fixes you applied.

## 📸 Demo Walkthrough

Describe your fixed game in numbered steps so a reader can follow along without watching a video:

1. User enters a guess of 0
2. Game returns "Out of range. Guess a number between 1 and 100." — the attempt
   counter does not move and the progress bar stays put
3. User enters a guess of 101
4. Game returns the same bounds error
5. User enters a guess of 40 → :orange[**📈 Go HIGHER!** · 🌤️ Lukewarm], and the
   "Closest yet" tile reads 28
6. User enters a guess of 70 → :orange[**📉 Go LOWER!** · 🔥 Scorching]
7. User enters a guess of 68 → :green[**🎉 Correct!**], balloons
8. Game ends, the 📊 Session Summary table replays every guess with its distance
   and temperature, and the win lands on the 🏆 High Scores panel

**Screenshot** *(optional)*: <!-- Insert a screenshot of your fixed, winning game here -->

## 🧪 Test Results

Run with the project venv active:

```
$ source venv/bin/activate
$ python -m pytest tests/
============================= test session starts ==============================
platform darwin -- Python 3.13.0, pytest-9.1.1, pluggy-1.6.0
rootdir: /Users/prithvikarki/Documents/CS Projects/CP Game Glitch/ai110-module1show-gameglitchinvestigator-starter
plugins: anyio-4.14.2
collected 456 items

tests/test_app_feature.py ..............................                 [  6%]
tests/test_game_logic.py ............................................... [ 16%]
........................................................................ [ 32%]
........................................................................ [ 48%]
........................................................................ [ 64%]
........................................................................ [ 80%]
........................................................................ [ 95%]
...................                                                      [100%]

============================= 456 passed in 2.64s ==============================
```

### Style checks

```
$ python -m flake8 app.py logic_utils.py tests/
$ echo $?
0
```

Zero violations on flake8's stock defaults — no `setup.cfg`, no raised
`max-line-length`, no per-file ignores. flake8 prints nothing on a clean run,
so the empty block above is the result. The full before/after (21 violations →
0) with tool versions and reproduction steps is committed as `lint_report.txt`.

`tests/test_game_logic.py` covers the pure logic. `tests/test_app_feature.py`
drives the real `app.py` through Streamlit's own `AppTest` harness — clicking
the actual buttons and reading the actual sidebar — so the Scoreboard & Guess
History feature is proven working, not just asserted.

### Advanced edge-case coverage

The last section of `tests/test_game_logic.py` targets the inputs the happy
path never thinks about. The six groups are:

| Edge case | What it feeds `parse_guess` | Why it matters |
|-----------|-----------------------------|----------------|
| Non-numeric strings | `abc`, `🎮`, `0x32`, `5e1`, `1_0`, `٥٠`, `nan`, `inf` | Python's `int()`/`float()` silently **accept** the last five, so a naive `try/except` parser scores them |
| Negative numbers | `-1`, `-500`, `-0`, `+0` | A negative is a valid `int`, so only the bounds check can reject it — and it must say "out of range", not "not a number" |
| Empty / whitespace input | `""`, `" "`, `"\t"`, `None` | Streamlit hands back `""` on every rerun before the player types; `None` would crash `.strip()` |
| Decimals | `50.9`, `50.0`, `.5`, `5.` | `int(float("50.9"))` is 50 — the player got scored on a number they never typed |
| Size & boundary extremes | a 300-digit number, `low-1`/`low`/`high`/`high+1` on all three difficulties | Off-by-one sweep plus proof that unbounded ints don't crash the parser |
| Never-raises contract | the whole hostile corpus | `parse_guess` always returns `(ok, value, error)` and never lets an exception reach Streamlit |

Three of these found real defects in my own Bug 2 fix — `"1_0"` parsed as `10`,
`"٥٠"` parsed as `50`, and `"50.9"` was truncated to `50`. To confirm the tests
had teeth I re-ran them against the old permissive parser: **9 failed**, and all
200 pass against the fixed one. Prompts and per-case reasoning are in
`ai_interactions.md`.

## 🚀 Stretch Features

### 🎨 Enhanced Game UI

The original game gave the player one uniformly-yellow `st.warning` per turn
and hid everything else behind the debug expander. Five additions, all built on
pure functions in `logic_utils.py` so the formatting is testable and the rules
underneath are untouched.

**1. Hot/Cold temperature readings — `proximity()`**

The direction hint tells you *which way* to move. It never told you *how far*,
so every guess after the first was still a blind step. `proximity()` reports a
band from 🔥 Scorching down to 🧊 Freezing:

```
📈 Go HIGHER! · 🧊 Freezing      guessed 10, secret 66
📉 Go LOWER!  · 🌤️ Lukewarm      guessed 90, secret 66
📈 Go HIGHER! · 🔥 Scorching     guessed 64, secret 66
```

The bands scale with the board, because being 3 away means something different
on Easy (1–20) than on Normal (1–100). That scaling needed one non-obvious
correction, which a test caught: taken as a plain share of the board, Easy's 2%
band is **0.38 wide**, so 🔥 Scorching was mathematically unreachable and a
guess one step from winning read "Warm". Each band is now rounded up to at
least 1, so being one away is the hottest reading on every difficulty —
`test_one_away_is_always_the_hottest_reading`.

**2. Colour-coded hints — `hint_color()` and `format_hint_banner()`**

Green for a win, orange for a miss, red for rejected input, rendered through
Streamlit's `:color[text]` markdown. Both directions share orange on purpose:
"Too High" and "Too Low" are the same kind of event — *keep going* — and the
direction lives in the words, not the colour.

Rejected input stays on `st.error` rather than joining the banner, because an
error has to be visible even with **Show hint** switched off
(`test_errors_show_even_with_hints_switched_off`).

**3. Session summary table — `build_session_summary()` and `session_stats()`**

At game over, the whole session replayed:

```
 #  Guess   Result    Off by  Temp
 ·  abc     Invalid   —       —
 1  10      Too Low   56      🧊 Freezing
 2  90      Too High  24      🌤️ Lukewarm
 3  64      Too Low   2       🔥 Scorching
 4  66      Win       0       🎯 Exact

Secret: 66 · 4 attempts used · 1 rejected · closest miss: 0
```

It appears **only once the game is over** — every row reveals the distance to
the secret, so showing it mid-game would hand over the answer
(`test_the_summary_table_appears_only_once_the_game_is_over`).

**4. Metric tiles**

`st.metric` row across the top for Score, Attempts (`3/8`) and Closest yet —
three numbers previously buried in the debug expander.

**5. Attempts progress bar**

`st.progress` instead of a bare number, so a nearly-spent game looks like one.
A rejected guess does not move it, matching the rule that typos cost nothing.

#### Functions added or modified

| Function | File | Role |
|---|---|---|
| `proximity()` | `logic_utils.py` | **New.** Distance → Hot/Cold band, scaled to the board |
| `hint_color()` | `logic_utils.py` | **New.** Outcome → Streamlit colour name |
| `format_hint_banner()` | `logic_utils.py` | **New.** Builds the colour-coded hint line |
| `build_session_summary()` | `logic_utils.py` | **New.** History → table rows |
| `session_stats()` | `logic_utils.py` | **New.** Turns used, rejects, closest miss |
| `PROXIMITY_TIERS`, `OUTCOME_COLORS` | `logic_utils.py` | **New.** The bands and the palette |
| submit handler | `app.py` | Replaces `st.warning(message)` with the banner; stores it in `st.session_state.last_hint` so it survives to the bottom of the script |
| deferred render block | `app.py` | **New.** Metric tiles, progress bar, hint banner, summary table |

#### Core logic is untouched

`check_guess`, `parse_guess`, `update_score`, `new_game_state` and
`update_high_scores` are unchanged — the enhancements read game state and
render it, and never decide anything. `test_the_formatting_layer_does_not_change_the_rules`
plays a scripted game and asserts attempts, history, status and high scores are
exactly what they were before any of this was added.

---

### 🏆 Scoreboard & Guess History (built in Claude Code agent mode)

Two new sidebar panels. Built by giving an agent the feature spec and a rule:
put the real work in pure functions and flag anything it had to fix rather than
fixing it silently. The agent transcript, the blockers it surfaced, and my four
manual corrections are in `ai_interactions.md` under **Agent Workflow → Run 2**.

**📜 Guess History** — every guess this game, newest first:

```
🎯 #3 — 66 → Win
📈 #2 — 9 → Too Low
📈 #1 — 9 → Too Low
🚫 #· — 999 → Invalid
🚫 #· — abc → Invalid
```

The `#·` marker means the input was rejected and cost no attempt, so a typo is
visible in the log without silently burning a turn.

**🏆 High Scores** — one row per difficulty, kept across every New Game:

```
Easy   — best 80 pts · fewest 2 tries · 3W / 1L
Normal — best 50 pts · fewest 3 tries · 1W / 0L
```

Easy, Normal and Hard keep separate records, because a 20-number board and a
100-number board are not comparable. A loss records a loss and sets no record —
you cannot earn a personal best by running out of turns.

**Four bugs the feature exposed**, all fixed:

| Bug | Symptom | Fix |
|-----|---------|-----|
| Partial reset | `New Game` reset `attempts` and `secret` but left `status` on `"won"`, so the `st.stop()` guard killed Submit forever | One `new_game_state()` returns every field a fresh game needs |
| Wrong range on reset | `New Game` called `randint(1, 100)` on every difficulty, so an Easy board could hide an unreachable 87 | `new_game_state(low, high)` takes the difficulty's real bounds |
| Even-attempt hints | `app.py` stringified the secret on even turns, so guessing `9` against `66` said "Go LOWER" — `"9" > "66"` as text | Pass the secret through unchanged; `check_guess` keeps its fallback for the tests |
| Counter off by one | `attempts` started at `1` and incremented *before* parsing, so a Normal game claimed 7 of 8 turns left before you touched it, and typos burned turns | Starts at `0`, increments only on a valid guess |

The third one is the clearest argument for the feature: the history panel made
it visible by showing two entries for the same guess pointing opposite ways.

**Implementation note.** The panels render at the *bottom* of `app.py` on
purpose. Streamlit runs the script top to bottom, so drawing them inline showed
the state from before the click and the history lagged a turn behind.
`st.sidebar` writes into the sidebar container wherever it is called, so moving
the panels down fixes the lag with zero `st.rerun()` calls — and `st.empty()`
placeholders do the same job for the "Attempts left" line and the debug panel.

**Screenshot** *(optional)*: <!-- Insert a screenshot of the sidebar here -->
