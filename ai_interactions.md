# AI Interactions Log

> **Stretch features only.** Only fill in the sections that apply to stretch features you attempted. If you did not attempt a stretch feature, leave its section blank or delete it. This file is not required for the core project.
>
> Attempted: **SF8 (agent workflow)** and **SF7 (test generation)**. The other
> sections are left blank. Test output lives in `README.md`; the tests
> themselves are in `tests/test_game_logic.py`.

---

## Agent Workflow (SF8)

> Document your experience using an AI agent (e.g., Cursor Agent, Claude, Copilot) to make multi-step changes autonomously.

**What task did you give the agent?**

I used Claude Code in agent mode in VS Code. I gave it `app.py` plus my bug
reproduction log from `reflection.md` and asked it to trace where each glitch
actually came from rather than rewriting the game — specifically the backwards
direction hints and the fact that guessing `0` returned a hint instead of an
error.

**What did the agent do?**

- Read `app.py` and located `check_guess()`, where the outcome labels were
  correct but the messages paired with them were swapped, and found the same
  inversion duplicated in the `except TypeError` fallback branch.
- Read `parse_guess()` and found that `get_range_for_difficulty()` already
  computed `low`/`high` but those values never reached the parser, so no bounds
  check existed at all.
- Edited `app.py` to fix both, updated the `parse_guess` call site to pass the
  difficulty's real bounds, and fixed the hardcoded "between 1 and 100" caption.
- Fixed `tests/test_game_logic.py`, which imported from the `logic_utils` stubs
  and compared a `(outcome, message)` tuple to a plain string.
- Ran `pytest` after each change.

**What did you have to verify or fix manually?**

I checked every claim against the running app with the Developer Debug Info
expander open, and I ran the new tests against a copy of `app.py` with the swap
restored to prove they actually failed. The agent's edge-case pass then found
three defects in its *own* range fix — `"1_0"`, `"٥٠"` and `"50.9"` all slipped
through the `try/except int()` it wrote — which is the clearest evidence that
accepting a green test run without adversarial input would have shipped bugs.

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

**Prompt used:**

```
<!-- Paste the prompt you gave the AI -->
```

**Linting output before:**

```
<!-- Paste relevant linter warnings/errors -->
```

**Changes applied:**

<!-- Describe what you changed based on the AI's suggestions -->

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
