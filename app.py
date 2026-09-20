import random
import re
import streamlit as st

def get_range_for_difficulty(difficulty: str):
    if difficulty == "Easy":
        return 1, 20
    if difficulty == "Normal":
        return 1, 100
    if difficulty == "Hard":
        return 1, 50
    return 1, 100

# FIX (Bug 2): I pointed Claude Code at app.py in agent mode saying there was
# no range validation at all; it found that get_range_for_difficulty already
# computed low/high but they never reached this function, and added the bounds
# check below. I reviewed the fix and asked for pytest cases covering it.
#
# EDGE CASES: the original `int(raw)` / `int(float(raw))` path was far more
# permissive than it looks. Python accepts underscore separators ("1_0" -> 10)
# and non-ASCII digits (Arabic-Indic "٥٠" -> 50), and the float branch silently
# truncated "50.9" to 50 - scoring the player on a number they never typed.
# This strict ASCII pattern is what closes all three.
_NUMERIC_PATTERN = re.compile(r"[+-]?\d+(\.\d+)?", re.ASCII)


def parse_guess(raw: str, low: int, high: int):
    if raw is None:
        return False, None, "Enter a guess."

    if not isinstance(raw, str):
        raw = str(raw)

    raw = raw.strip()

    if raw == "":
        return False, None, "Enter a guess."

    # FIX: added - replaces a bare try/except int() that accepted "1_0",
    # full-width "１２" and other shapes no player ever means to type.
    if not _NUMERIC_PATTERN.fullmatch(raw):
        return False, None, "That is not a number."

    if "." in raw:
        as_float = float(raw)
        # FIX: added - "50.9" used to truncate to 50 and get scored silently.
        if as_float != int(as_float):
            return False, None, "Whole numbers only. Drop the decimal."
        value = int(as_float)
    else:
        value = int(raw)

    # FIX: added - previously any int was accepted, so -500 and 9999 were
    # treated as valid guesses, burned an attempt, and got scored.
    if value < low or value > high:
        return False, None, f"Out of range. Guess a number between {low} and {high}."

    return True, value, None


# FIX (Bug 1): I asked Claude Code in agent mode to analyze app.py for the
# swapped direction hints; it traced the swap to all four return statements
# below (both the int path and the TypeError fallback) and I reviewed the fix.
def check_guess(guess, secret):
    if guess == secret:
        return "Win", "🎉 Correct!"

    try:
        if guess > secret:
            return "Too High", "📉 Go LOWER!"   # FIX: was "Go HIGHER!"
        else:
            return "Too Low", "📈 Go HIGHER!"   # FIX: was "Go LOWER!"
    except TypeError:
        g = str(guess)
        if g == secret:
            return "Win", "🎉 Correct!"
        # FIX: same swap lived in this fallback branch, which app.py reaches on
        # even-numbered attempts; the AI caught it after I pointed out the first one.
        if g > secret:
            return "Too High", "📉 Go LOWER!"   # FIX: was "Go HIGHER!"
        return "Too Low", "📈 Go HIGHER!"       # FIX: was "Go LOWER!"


def update_score(current_score: int, outcome: str, attempt_number: int):
    if outcome == "Win":
        points = 100 - 10 * (attempt_number + 1)
        if points < 10:
            points = 10
        return current_score + points

    if outcome == "Too High":
        if attempt_number % 2 == 0:
            return current_score + 5
        return current_score - 5

    if outcome == "Too Low":
        return current_score - 5

    return current_score

st.set_page_config(page_title="Glitchy Guesser", page_icon="🎮")

st.title("🎮 Game Glitch Investigator")
st.caption("An AI-generated guessing game. Something is off.")

st.sidebar.header("Settings")

difficulty = st.sidebar.selectbox(
    "Difficulty",
    ["Easy", "Normal", "Hard"],
    index=1,
)

attempt_limit_map = {
    "Easy": 6,
    "Normal": 8,
    "Hard": 5,
}
attempt_limit = attempt_limit_map[difficulty]

low, high = get_range_for_difficulty(difficulty)

st.sidebar.caption(f"Range: {low} to {high}")
st.sidebar.caption(f"Attempts allowed: {attempt_limit}")

if "secret" not in st.session_state:
    st.session_state.secret = random.randint(low, high)

if "attempts" not in st.session_state:
    st.session_state.attempts = 1

if "score" not in st.session_state:
    st.session_state.score = 0

if "status" not in st.session_state:
    st.session_state.status = "playing"

if "history" not in st.session_state:
    st.session_state.history = []

st.subheader("Make a guess")

st.info(
    # FIX: was hardcoded "between 1 and 100", which contradicted the new
    # validator on Easy (1-20) and Hard (1-50).
    f"Guess a number between {low} and {high}. "
    f"Attempts left: {attempt_limit - st.session_state.attempts}"
)

with st.expander("Developer Debug Info"):
    st.write("Secret:", st.session_state.secret)
    st.write("Attempts:", st.session_state.attempts)
    st.write("Score:", st.session_state.score)
    st.write("Difficulty:", difficulty)
    st.write("History:", st.session_state.history)

raw_guess = st.text_input(
    "Enter your guess:",
    key=f"guess_input_{difficulty}"
)

col1, col2, col3 = st.columns(3)
with col1:
    submit = st.button("Submit Guess 🚀")
with col2:
    new_game = st.button("New Game 🔁")
with col3:
    show_hint = st.checkbox("Show hint", value=True)

if new_game:
    st.session_state.attempts = 0
    st.session_state.secret = random.randint(1, 100)
    st.success("New game started.")
    st.rerun()

if st.session_state.status != "playing":
    if st.session_state.status == "won":
        st.success("You already won. Start a new game to play again.")
    else:
        st.error("Game over. Start a new game to try again.")
    st.stop()

if submit:
    st.session_state.attempts += 1

    # FIX: pass the difficulty's real bounds in; this call used to be
    # parse_guess(raw_guess) with no range to validate against.
    ok, guess_int, err = parse_guess(raw_guess, low, high)

    if not ok:
        st.session_state.history.append(raw_guess)
        st.error(err)
    else:
        st.session_state.history.append(guess_int)

        if st.session_state.attempts % 2 == 0:
            secret = str(st.session_state.secret)
        else:
            secret = st.session_state.secret

        outcome, message = check_guess(guess_int, secret)

        if show_hint:
            st.warning(message)

        st.session_state.score = update_score(
            current_score=st.session_state.score,
            outcome=outcome,
            attempt_number=st.session_state.attempts,
        )

        if outcome == "Win":
            st.balloons()
            st.session_state.status = "won"
            st.success(
                f"You won! The secret was {st.session_state.secret}. "
                f"Final score: {st.session_state.score}"
            )
        else:
            if st.session_state.attempts >= attempt_limit:
                st.session_state.status = "lost"
                st.error(
                    f"Out of attempts! "
                    f"The secret was {st.session_state.secret}. "
                    f"Score: {st.session_state.score}"
                )

st.divider()
st.caption("Built by an AI that claims this code is production-ready.")
