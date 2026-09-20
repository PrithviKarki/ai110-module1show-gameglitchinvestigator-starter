# 🎮 Game Glitch Investigator: The Impossible Guesser

## 🚨 The Situation

You asked an AI to build a simple "Number Guessing Game" using Streamlit.
It wrote the code, ran away, and now the game is unplayable. 

- You can't win.
- The hints lie to you.
- The secret number seems to have commitment issues.

## 🛠️ Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Run the broken app: `python -m streamlit run app.py`

## 🕵️‍♂️ Your Mission

1. **Play the game.** Open the "Developer Debug Info" tab in the app to see the secret number. Try to win.
2. **Find the State Bug.** Why does the secret number change every time you click "Submit"? Ask ChatGPT: *"How do I keep a variable from resetting in Streamlit when I click a button?"*
3. **Fix the Logic.** The hints ("Higher/Lower") are wrong. Fix them.
4. **Refactor & Test.** - Move the logic into `logic_utils.py`.
   - Run `pytest` in your terminal.
   - Keep fixing until all tests pass!

## 📝 Document Your Experience

- [ ] Describe the game's purpose.
- [ ] Detail which bugs you found.
- [ ] Explain what fixes you applied.

## 📸 Demo Walkthrough

Describe your fixed game in numbered steps so a reader can follow along without watching a video:

1. User enters a guess of 0
2. Game returns "Out of range. Guess a number between 1 and 100.
3. User enters a guess of 101
4. Game returns "Out of range. Guess a number between 1 and 100.
5. User enters a guess of 40 → "Go HIGHER!"
6. User enters a guess of 70 → "Go LOWER!"
7. User enters a guess of 68 → "Correct!"
8. Game ends after the correct guess

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
collected 243 items

tests/test_app_feature.py ................                               [  6%]
tests/test_game_logic.py ............................................... [ 25%]
........................................................................ [ 55%]
........................................................................ [ 85%]
....................................                                     [100%]

============================= 243 passed in 1.56s ==============================
```

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
