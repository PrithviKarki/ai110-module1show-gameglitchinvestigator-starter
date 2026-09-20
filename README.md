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
collected 200 items

tests/test_game_logic.py ............................................... [ 23%]
........................................................................ [ 59%]
........................................................................ [ 95%]
.........                                                                [100%]

============================= 200 passed in 0.40s ==============================
```

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

- [ ] [If you choose to complete Challenge 4, describe the Enhanced UI changes here — a screenshot is optional]
