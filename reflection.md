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

I used Claude (through Claude Code in VS Code) as my main AI teammate. I pasted in `app.py` and my bug reproduction log and asked it to trace where each glitch actually came from, instead of just asking it to "fix the game." Treating it like a teammate meant I still had to check every claim it made against the code and the running app.

**Suggestion 1 — the backwards hints (correct)**

The AI pointed me to `check_guess()` in `app.py` and said the outcome labels were right but the hint messages attached to them were swapped: `if guess > secret` returned `"Too High"` paired with `"📈 Go HIGHER!"`, and the `else` branch returned `"Too Low"` paired with `"📉 Go LOWER!"`. It also caught that the same inversion was duplicated in the `except TypeError` fallback further down, which I had not noticed on my own. This suggestion was correct. I verified it two ways: I wrote pytest cases asserting that a guess below the secret returns the "HIGHER" message and a guess above it returns the "LOWER" message, and those tests failed before the fix and passed after. Then I opened the Developer Debug Info expander in the game, read the actual secret, and deliberately guessed above and below it — the arrows now pointed the right direction every time.

**Suggestion 2 — the missing range validation (correct)**

The AI also explained why guessing `0` gave me a hint instead of an error: `parse_guess()` only checked for empty input and non-numeric input, and never compared the value against `low` and `high` at all, so out-of-bounds numbers were accepted as valid guesses and burned an attempt. It suggested passing `low` and `high` into `parse_guess()` and returning an error tuple when the value falls outside that range, and reminded me to update the call site in `app.py` since `low, high` were already being computed from the difficulty. This suggestion was also correct. I verified it by intentionally passing numbers beyond the range — `0`, `-5`, and `9999` — and confirming the game now shows a bounds error instead of a hint, and that the attempt counter in the Developer Debug Info did not increase on those rejected inputs. I backed that up with pytest cases covering values just inside and just outside both bounds.

Everything the AI suggested on this project turned out to be correct, and both fixes worked once I applied them — I did not run into a suggestion that was incorrect or misleading. What made that work was that the AI always named the specific function and line range, so its claims were cheap for me to check rather than something I had to take on faith.

---

## 3. Debugging and testing your fixes

- How did you decide whether a bug was really fixed?

I decided a bug was fixed only when it failed a test before the change and passed after, and when I could also watch the corrected behavior in the running Streamlit app. Before I fixed anything I had to repair the test file itself: `tests/test_game_logic.py` imported `check_guess` from `logic_utils`, which is still all `raise NotImplementedError` stubs, and the three starter tests compared a `(outcome, message)` tuple to a plain string. So those tests could never have caught anything. I pointed the import at `app.py`, where the real implementations live, and unpacked the tuple. That was the first real lesson: a green-looking test file is not the same as a test file that is actually checking your code. I ended up with 129 passing tests across the two bugs.

- Describe at least one test you ran (manual or using pytest) and what it showed you about your code.

The test that convinced me the hint bug was truly gone is `test_following_the_hints_actually_finds_the_secret`. Instead of asserting on one message, it plays the game: it binary-searches for the secret by obeying whatever the hint says each turn, and fails if it never lands on the number. With the swap in place the search walks away from the secret and never converges, so this test reproduces the actual player experience rather than just the string. I paired it with `test_outcome_and_message_always_agree`, which sweeps every guess from 1 to 100 against a secret of 50 and asserts the direction word in the message matches the direction named by the outcome — that pins down the invariant the bug violated. I also added `test_string_comparison_fallback_also_pairs_correctly`, because `app.py` stringifies the secret on even-numbered attempts and sends `check_guess` into its `except TypeError` branch, where the same swap was duplicated. To prove the tests had teeth, I ran them against a copy of `app.py` with the swap put back, and they all failed as expected.

For the range bug I ran `pytest` cases feeding `0`, `-1`, `-500`, `101`, and `9999` into `parse_guess`, plus `test_range_follows_difficulty_not_a_hardcoded_1_to_100`, which checks that `21` is rejected on Easy (1–20) but accepted on Normal (1–100) — that one catches a "fix" that just hardcodes 1 and 100. I confirmed the same thing by hand in the game: I opened the Developer Debug Info expander, deliberately typed numbers beyond the range, and watched it show the bounds error instead of a hint, with the attempt counter staying put instead of burning a turn.

- Did AI help you design or understand any tests? How?

Yes. I asked Claude Code in agent mode to draft tests aimed specifically at the swapped labels, and its most useful contribution was pointing out that asserting on the outcome alone (`"Too High"` / `"Too Low"`) would never have caught this bug, since the outcomes were correct the whole time and only the message was wrong — so the assertions had to check the message text. It also suggested the binary-search test as a way to express the bug in terms of what the player experiences. I still had to verify the tests were meaningful myself, which is why I ran them against the broken version of the code before trusting the green run.

---

## 4. What did you learn about Streamlit and state?

- How would you explain Streamlit "reruns" and session state to a friend who has never used Streamlit?

---

## 5. Looking ahead: your developer habits

- What is one habit or strategy from this project that you want to reuse in future labs or projects?
  - This could be a testing habit, a prompting strategy, or a way you used Git.
- What is one thing you would do differently next time you work with AI on a coding task?
- In one or two sentences, describe how this project changed the way you think about AI generated code.


## Reflections 
- Going out of bounds lower 
- Goind out of bounds higher 
- 6 attempts actual vs 7 attempts (labelled)
- Start new game resets the counter but the submit button wont