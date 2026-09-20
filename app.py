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


# ============================================================================
# FEATURE: Scoreboard & Guess History (built in Claude Code agent mode)
# ============================================================================
#
# These four helpers are deliberately pure - they take state in and return new
# state out, touching neither st.session_state nor random. That is what lets
# tests/test_game_logic.py cover the feature without running Streamlit.
# See ai_interactions.md for the agent transcript and my manual corrections.

OUTCOME_ICONS = {
    "Win": "🎯",
    "Too High": "📉",
    "Too Low": "📈",
    "Invalid": "🚫",
}


def record_guess(history, attempt_number, guess, outcome, message):
    """Return a NEW history list with this guess appended.

    attempt_number is None for rejected input, which does not burn a turn.
    Returning a new list instead of mutating keeps Streamlit's rerun model
    honest - the old list is never aliased into the next run.
    """
    entry = {
        "attempt": attempt_number,
        "guess": guess,
        "outcome": outcome,
        "message": message,
    }
    return list(history) + [entry]


def format_history_line(entry):
    """Render one history entry as a single readable line."""
    icon = OUTCOME_ICONS.get(entry["outcome"], "❔")
    label = "·" if entry["attempt"] is None else str(entry["attempt"])
    return f"{icon} #{label} — {entry['guess']} → {entry['outcome']}"


def blank_high_score():
    """A difficulty that has never been finished."""
    return {"best_score": None, "fewest_attempts": None, "wins": 0, "losses": 0}


def update_high_scores(high_scores, difficulty, score, attempts, won):
    """Fold one finished game into the high-score table and return a NEW table.

    Best score is the HIGHEST score; fewest attempts is the LOWEST attempt
    count - they move in opposite directions, which is the part I got wrong
    by hand before the tests caught it. A loss records a loss and nothing else:
    you cannot set a personal best by running out of turns.
    """
    table = {d: dict(row) for d, row in high_scores.items()}
    row = table.get(difficulty) or blank_high_score()

    if won:
        row["wins"] += 1
        if row["best_score"] is None or score > row["best_score"]:
            row["best_score"] = score
        if row["fewest_attempts"] is None or attempts < row["fewest_attempts"]:
            row["fewest_attempts"] = attempts
    else:
        row["losses"] += 1

    table[difficulty] = row
    return table


def new_game_state(low, high, pick=random.randint):
    """Every field a fresh game needs, as one dict.

    FIX (Bug 3): the old "New Game" button set attempts back to 0 but left
    status as "won"/"lost", so the next click hit the st.stop() guard and the
    Submit button did nothing - the bug in row 3 of my reproduction log. It
    also called randint(1, 100) regardless of difficulty, so an Easy game
    could hide a secret of 87 inside a 1-20 board. Resetting through one
    function means no field can be forgotten again.
    """
    return {
        "secret": pick(low, high),
        "attempts": 0,
        "score": 0,
        "status": "playing",
        "history": [],
    }


st.set_page_config(page_title="Glitchy Guesser", page_icon="🎮")

st.title("🎮 Game Glitch Investigator")
st.caption("An AI-generated guessing game. Now with a scoreboard that tells the truth.")

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

# --- session state ----------------------------------------------------------

if "high_scores" not in st.session_state:
    # FEATURE: survives every New Game; only a full page reload clears it.
    st.session_state.high_scores = {}

if "difficulty" not in st.session_state:
    st.session_state.difficulty = difficulty

if "secret" not in st.session_state:
    # FIX: one call site for the starting state, so "attempts" can no longer
    # start at 1 while the label claims you have all of them left.
    st.session_state.update(new_game_state(low, high))

# FEATURE: switching difficulty mid-game used to keep the old secret, so an
# Easy board could still be hiding 87. Changing the board starts a new game.
if st.session_state.difficulty != difficulty:
    st.session_state.difficulty = difficulty
    st.session_state.update(new_game_state(low, high))

# --- main panel -------------------------------------------------------------

st.subheader("Make a guess")

# FIX: these two panels are reserved here but FILLED at the bottom of the
# script, after the guess has been processed. Written inline they showed the
# attempt count from before the click - the counter was always one behind.
status_slot = st.empty()
debug_slot = st.empty()

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
    # FIX (Bug 3): this used to reset only attempts and the secret, leaving
    # status stuck on "won"/"lost" so Submit stayed dead.
    st.session_state.update(new_game_state(low, high))
    st.rerun()

# FIX: this used to be a bare st.stop(), which killed the rest of the script -
# including the sidebar panels below. A finished game now falls through to an
# else branch so the scoreboard and history stay on screen after the last turn.
if st.session_state.status != "playing":
    if st.session_state.status == "won":
        st.success("You already won. Start a new game to play again.")
    else:
        st.error("Game over. Start a new game to try again.")

elif submit:
    # FIX: pass the difficulty's real bounds in; this call used to be
    # parse_guess(raw_guess) with no range to validate against.
    ok, guess_int, err = parse_guess(raw_guess, low, high)

    if not ok:
        # FIX: the attempt counter used to increment BEFORE parsing, so typos
        # and out-of-range numbers burned a turn. Rejected input is logged
        # with no attempt number and costs nothing.
        st.session_state.history = record_guess(
            st.session_state.history, None, raw_guess, "Invalid", err
        )
        st.error(err)
    else:
        st.session_state.attempts += 1

        # FIX (Bug 4): app.py used to stringify the secret on even-numbered
        # attempts, pushing check_guess into its string-comparison fallback.
        # Guessing 9 against a secret of 73 came back "Go LOWER", because
        # "9" > "73" as text. The history log made this obvious - the sidebar
        # showed two hints pointing opposite ways for the same secret.
        outcome, message = check_guess(guess_int, st.session_state.secret)

        st.session_state.history = record_guess(
            st.session_state.history,
            st.session_state.attempts,
            guess_int,
            outcome,
            message,
        )

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
            # FEATURE: a finished game is what feeds the scoreboard.
            st.session_state.high_scores = update_high_scores(
                st.session_state.high_scores,
                difficulty,
                score=st.session_state.score,
                attempts=st.session_state.attempts,
                won=True,
            )
            st.success(
                f"You won! The secret was {st.session_state.secret}. "
                f"Final score: {st.session_state.score}"
            )
        elif st.session_state.attempts >= attempt_limit:
            st.session_state.status = "lost"
            st.session_state.high_scores = update_high_scores(
                st.session_state.high_scores,
                difficulty,
                score=st.session_state.score,
                attempts=st.session_state.attempts,
                won=False,
            )
            st.error(
                f"Out of attempts! "
                f"The secret was {st.session_state.secret}. "
                f"Score: {st.session_state.score}"
            )

# --- deferred main-panel rendering ------------------------------------------

attempts_left = attempt_limit - st.session_state.attempts

status_slot.info(
    # FIX: was hardcoded "between 1 and 100", which contradicted the new
    # validator on Easy (1-20) and Hard (1-50).
    f"Guess a number between {low} and {high}. "
    f"Attempts left: {attempts_left}"
)

with debug_slot.expander("Developer Debug Info"):
    st.write("Secret:", st.session_state.secret)
    st.write("Attempts used:", st.session_state.attempts)
    st.write("Score:", st.session_state.score)
    st.write("Difficulty:", difficulty)
    st.write("Status:", st.session_state.status)
    st.write("High scores:", st.session_state.high_scores)
    st.write("History:", st.session_state.history)


# --- sidebar panels ---------------------------------------------------------
#
# FEATURE: these render LAST on purpose. Streamlit runs the script top to
# bottom, so drawing them above the submit handler showed the state from
# before the guess - the history was always one click behind. st.sidebar
# writes into the sidebar container no matter where it is called, so moving
# them down fixes the lag without a single st.rerun().

# --- sidebar: high scores ---------------------------------------------------

st.sidebar.divider()
st.sidebar.subheader("🏆 High Scores")

if not st.session_state.high_scores:
    st.sidebar.caption("No finished games yet. Win one and it lands here.")
else:
    for name in ["Easy", "Normal", "Hard"]:
        row = st.session_state.high_scores.get(name)
        if row is None:
            continue

        best = "—" if row["best_score"] is None else row["best_score"]
        fewest = "—" if row["fewest_attempts"] is None else row["fewest_attempts"]

        st.sidebar.markdown(
            f"**{name}** — best {best} pts · "
            f"fewest {fewest} tries · "
            f"{row['wins']}W / {row['losses']}L"
        )

# --- sidebar: guess history -------------------------------------------------

st.sidebar.divider()
st.sidebar.subheader("📜 Guess History")

if not st.session_state.history:
    st.sidebar.caption("This game's guesses will show up here.")
else:
    # Newest first: the hint you are acting on right now sits at the top.
    for entry in reversed(st.session_state.history):
        st.sidebar.text(format_history_line(entry))

st.divider()
st.caption("Built by an AI that claims this code is production-ready.")
