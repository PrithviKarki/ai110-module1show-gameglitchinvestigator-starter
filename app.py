"""Streamlit UI for the Glitchy Guesser.

This module is deliberately thin: it owns widgets, session state and
layout, and nothing else. Every rule of the game lives in `logic_utils`,
where it can be tested without starting a Streamlit server.

Run it with:

    python -m streamlit run app.py
"""

import streamlit as st

from logic_utils import (
    check_guess,
    format_history_line,
    get_range_for_difficulty,
    new_game_state,
    parse_guess,
    record_guess,
    update_high_scores,
    update_score,
)

st.set_page_config(page_title="Glitchy Guesser", page_icon="🎮")

st.title("🎮 Game Glitch Investigator")
st.caption(
    "An AI-generated guessing game. "
    "Now with a scoreboard that tells the truth."
)

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
        fewest = row["fewest_attempts"]
        fewest = "—" if fewest is None else fewest

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
