# 💭 Reflection: Game Glitch Investigator

Answer each question in 3 to 5 sentences. Be specific and honest about what actually happened while you worked. This is about your process, not trying to sound perfect.

## 1. What was broken when you started?

- What did the game look like the first time you ran it?
- List at least two concrete bugs you noticed at the start  
  (for example: "the hints were backwards").

**Bug Reproduction Log**

Document at least 3 bugs you found. Add rows as needed.

| Input | Expected Behavior | Actual Behavior | Console Output / Error |
|-------|-------------------|-----------------|------------------------|
| 0|Input is lower than the lower bound error| Tells me that the correct answer is even lower| "📉 Go LOWER!" |
| 100| Input is higher than the upper bound error| Tells me that the correct answer is even higher | "📈 Go HIGHER!" |
| 80 (after starting a new game)| Correct/ Go lower/ Go higher | The counter had reset but it didnt work | "Game over. Start a new game to try again." |

---

## 2. How did you use AI as a teammate?

- Which AI tools did you use on this project (for example: ChatGPT, Gemini, Copilot)?
- Give one example of an AI suggestion that was correct (including what the AI suggested and how you verified the result).
- Give one example of an AI suggestion you did not accept as written (including what the AI suggested, why you rejected or changed it, and how you verified your version). It does not have to be a suggestion that was wrong: over-engineered, out of scope, harder to read, or a poor fit for this codebase all count.

I used Claude (through Claude Code in VS Code) as my main AI teammate. I pasted in `app.py` and my bug reproduction log and asked it to trace where each glitch actually came from, instead of just asking it to "fix the game." Treating it like a teammate meant I still had to check every claim it made against the code and the running app.

**Suggestion 1 — the backwards hints (correct)**

The AI pointed me to `check_guess()` in `app.py` and said the outcome labels were right but the hint messages attached to them were swapped: `if guess > secret` returned `"Too High"` paired with `"📈 Go HIGHER!"`, and the `else` branch returned `"Too Low"` paired with `"📉 Go LOWER!"`. It also caught that the same inversion was duplicated in the `except TypeError` fallback further down, which I had not noticed on my own. This suggestion was correct. I verified it two ways: I wrote pytest cases asserting that a guess below the secret returns the "HIGHER" message and a guess above it returns the "LOWER" message, and those tests failed before the fix and passed after. Then I opened the Developer Debug Info expander in the game, read the actual secret, and deliberately guessed above and below it — the arrows now pointed the right direction every time.

**Suggestion 2 — the missing range validation (correct)**

The AI also explained why guessing `0` gave me a hint instead of an error: `parse_guess()` only checked for empty input and non-numeric input, and never compared the value against `low` and `high` at all, so out-of-bounds numbers were accepted as valid guesses and burned an attempt. It suggested passing `low` and `high` into `parse_guess()` and returning an error tuple when the value falls outside that range, and reminded me to update the call site in `app.py` since `low, high` were already being computed from the difficulty. This suggestion was also correct. I verified it by intentionally passing numbers beyond the range — `0`, `-5`, and `9999` — and confirming the game now shows a bounds error instead of a hint, and that the attempt counter in the Developer Debug Info did not increase on those rejected inputs. I backed that up with pytest cases covering values just inside and just outside both bounds.

**Suggestion 3 — the one I did not accept as written (rejected)**

While building the Guess History sidebar, the panel was rendering the state from *before* the click — you had to guess twice before your first guess appeared. The AI correctly diagnosed why: Streamlit runs the script top to bottom, and the panel was drawn above the code that handles the guess. Its proposed fix was to call `st.rerun()` at the end of every submit branch so the script re-executes with the new state.

I did not accept it. It would have worked for the history panel and broken something else: `st.rerun()` throws away everything already written to the page that run, including the `st.warning()` hint telling the player to go higher or lower. Trading the hint for the history is not a fix, it is a swap. When I pushed back, the AI's next idea was to stash the hint in session state and re-render it after the rerun, which is more moving parts to solve a problem I had just created.

What I did instead was move the two sidebar panels to the *bottom* of `app.py`. `st.sidebar` writes into the sidebar container no matter where in the script it is called, so the panels can be defined last and still appear in the sidebar — they just read state that is now up to date. Zero reruns. I used the same trick with `st.empty()` placeholders for the "Attempts left" line and the debug expander, which had the identical lag.

I verified my version two ways. `test_a_guess_shows_up_in_the_sidebar_on_the_same_click` in `tests/test_app_feature.py` submits one guess and asserts the sidebar already shows it on that same run — it fails against the original layout. Then I played the game by hand and confirmed the hint and the new history line now appear together on one click, which was the whole point.

Two smaller ones I also turned down: the AI wanted to add a `setup.cfg` with `max-line-length = 88`, which would have silenced 16 of 21 flake8 violations without changing any code — I had it rewrap the lines properly instead, so the project passes on stock defaults. And it offered to replace the `(ok, guess, err)` return triple with a `NamedTuple`, which is genuinely nicer but would have touched about 40 tests for a readability gain the docstring already delivers. I noted it as a follow-up rather than doing it.

The pattern across all three: the AI was never *wrong* about the diagnosis. It was wrong about the cost. It reached for the fix that was fastest to write rather than the one that was cheapest to live with, and that is the part I had to supply.

---

## 3. Debugging and testing your fixes

- How did you decide whether a bug was really fixed?

I decided a bug was fixed only when it failed a test before the change and passed after, and when I could also watch the corrected behavior in the running Streamlit app. Before I fixed anything I had to repair the test file itself: `tests/test_game_logic.py` imported `check_guess` from `logic_utils`, which was still all `raise NotImplementedError` stubs, and the three starter tests compared a `(outcome, message)` tuple to a plain string. So those tests could never have caught anything. I pointed the import at `app.py`, where the real implementations lived at the time, and unpacked the tuple. (The logic has since been refactored into `logic_utils.py` where the starter file always meant it to go, so the import is back where it began — only now there is something behind it.) That was the first real lesson: a green-looking test file is not the same as a test file that is actually checking your code. I ended up with 282 passing tests: 129 covering the two bugs I found by playing, and a further round aimed at hostile input to `parse_guess`, which turned up three more defects in my own range fix (`"1_0"` parsed as 10, `"٥٠"` parsed as 50, and `"50.9"` was silently truncated to 50), and a final set covering the Scoreboard & Guess History feature — 27 unit tests for its pure helpers plus 16 that drive the real `app.py` through Streamlit's `AppTest` harness. Building that feature surfaced two more bugs I had logged but never fixed: the New Game button left `status` on `"won"` so Submit stayed dead (row 3 of my reproduction log), and the attempt counter started at 1 and incremented before parsing, which is why 6 attempts showed as 7. A third only became visible once the history panel existed — `app.py` stringified the secret on even turns, so guessing 9 against a secret of 66 said "Go LOWER" on attempt 2 and "Go HIGHER" on attempt 1. Seeing both lines in the same list is what gave it away. The last block of tests checks the documentation itself: every public function in `logic_utils.py` must keep its docstring, its `Args:` entry for each parameter and its `Returns:` section, and every `>>>` example is executed as a doctest so a docstring cannot quietly start lying about its own output.

- Describe at least one test you ran (manual or using pytest) and what it showed you about your code.

The test that convinced me the hint bug was truly gone is `test_following_the_hints_actually_finds_the_secret`. Instead of asserting on one message, it plays the game: it binary-searches for the secret by obeying whatever the hint says each turn, and fails if it never lands on the number. With the swap in place the search walks away from the secret and never converges, so this test reproduces the actual player experience rather than just the string. I paired it with `test_outcome_and_message_always_agree`, which sweeps every guess from 1 to 100 against a secret of 50 and asserts the direction word in the message matches the direction named by the outcome — that pins down the invariant the bug violated. I also added `test_string_comparison_fallback_also_pairs_correctly`, because `app.py` stringifies the secret on even-numbered attempts and sends `check_guess` into its `except TypeError` branch, where the same swap was duplicated. To prove the tests had teeth, I ran them against a copy of `app.py` with the swap put back, and they all failed as expected.

For the range bug I ran `pytest` cases feeding `0`, `-1`, `-500`, `101`, and `9999` into `parse_guess`, plus `test_range_follows_difficulty_not_a_hardcoded_1_to_100`, which checks that `21` is rejected on Easy (1–20) but accepted on Normal (1–100) — that one catches a "fix" that just hardcodes 1 and 100. I confirmed the same thing by hand in the game: I opened the Developer Debug Info expander, deliberately typed numbers beyond the range, and watched it show the bounds error instead of a hint, with the attempt counter staying put instead of burning a turn.

- Did AI help you design or understand any tests? How?

Yes. I asked Claude Code in agent mode to draft tests aimed specifically at the swapped labels, and its most useful contribution was pointing out that asserting on the outcome alone (`"Too High"` / `"Too Low"`) would never have caught this bug, since the outcomes were correct the whole time and only the message was wrong — so the assertions had to check the message text. It also suggested the binary-search test as a way to express the bug in terms of what the player experiences. I still had to verify the tests were meaningful myself, which is why I ran them against the broken version of the code before trusting the green run.

---

## 4. What did you learn about Streamlit and state?

- How would you explain Streamlit "reruns" and session state to a friend who has never used Streamlit?

Streamlit reruns are the app refreshing itself after an interaction, and session state is the place where you save the important information you want to keep between those refreshes. Without session state, a Streamlit app would feel broken because it would reset to square one on every click.
---

## 5. Looking ahead: your developer habits

- What is one habit or strategy from this project that you want to reuse in future labs or projects?
  - This could be a testing habit, a prompting strategy, or a way you used Git.
  Thinking the solution through, provide expected inputs and outputs to minimize hallucination, and also descibe the logic in plain english. I also like using what i call the "OC method" where i first list the outcome and then explain the context in a separate block.
- What is one thing you would do differently next time you work with AI on a coding task?
  Spend more time designing the solution, viusalizing it using AI, and then proceed to coding.
- In one or two sentences, describe how this project changed the way you think about AI generated code.
  AI generated code can be hit or miss depending on the prompt and context engineering but one of the most efficient way to mitigate that is by working in small increments instead of asking the ai to build the whole project end to end in a single prompt. 


## Reflections 
- Going out of bounds lower 
- Goind out of bounds higher 
- 6 attempts actual vs 7 attempts (labelled)
- Start new game resets the counter but the submit button wont