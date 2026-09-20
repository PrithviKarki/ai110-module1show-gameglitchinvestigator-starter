"""End-to-end tests for the Scoreboard & Guess History feature.

tests/test_game_logic.py covers the pure helpers. This file drives the real
app.py through Streamlit's own AppTest harness - clicking the actual buttons
and reading the actual sidebar - so "the feature works" is something the suite
proves rather than something I claim in the README.
"""

import pytest
from streamlit.testing.v1 import AppTest


def fresh_app():
    app = AppTest.from_file("app.py", default_timeout=30).run()
    assert not app.exception
    return app


def submit(app, value):
    """Type a guess and click Submit Guess."""
    app.text_input[0].set_value(value)
    app.button[0].click().run()
    return app


def sidebar_text(app):
    return [element.value for element in app.sidebar.text]


def sidebar_markdown(app):
    return [element.value for element in app.sidebar.markdown]


# --- the app still loads ----------------------------------------------------

def test_app_starts_with_a_clean_board():
    app = fresh_app()

    assert app.session_state.attempts == 0
    assert app.session_state.history == []
    assert app.session_state.high_scores == {}
    assert app.session_state.status == "playing"
    assert 1 <= app.session_state.secret <= 100


def test_attempts_left_starts_at_the_full_allowance():
    # The old counter started at 1, so a Normal game claimed 7 of its 8 turns
    # were left before the player had touched anything.
    app = fresh_app()
    assert "Attempts left: 8" in app.info[0].value


# --- guess history panel ----------------------------------------------------

def test_a_guess_shows_up_in_the_sidebar_on_the_same_click():
    # The panel is rendered at the bottom of the script for exactly this
    # reason. Rendered inline it lagged a click behind the guess.
    app = fresh_app()
    secret = app.session_state.secret
    guess = 1 if secret != 1 else 2

    submit(app, str(guess))

    lines = sidebar_text(app)
    assert len(lines) == 1
    assert str(guess) in lines[0]


def test_history_lists_newest_guess_first():
    app = fresh_app()
    app.session_state.secret = 50

    for guess in ["10", "20", "30"]:
        submit(app, guess)

    lines = sidebar_text(app)
    assert "30" in lines[0]
    assert "10" in lines[-1]


def test_rejected_input_is_logged_but_costs_no_attempt():
    app = fresh_app()

    submit(app, "abc")
    assert app.session_state.attempts == 0
    assert app.error[0].value == "That is not a number."

    submit(app, "999")
    assert app.session_state.attempts == 0
    assert "Out of range" in app.error[0].value

    # Both are visible in the panel, both marked as free.
    lines = sidebar_text(app)
    assert len(lines) == 2
    assert all("#·" in line for line in lines)

    # And the allowance never moved.
    assert "Attempts left: 8" in app.info[0].value


def test_history_survives_across_several_turns():
    app = fresh_app()
    app.session_state.secret = 50

    submit(app, "abc")
    submit(app, "10")
    submit(app, "90")

    assert app.session_state.attempts == 2
    assert len(app.session_state.history) == 3
    assert "Attempts left: 6" in app.info[0].value


def test_hints_in_the_history_all_point_the_same_way():
    # FIX (Bug 4): app.py used to stringify the secret on even-numbered
    # attempts, which sent check_guess into its text-comparison fallback.
    # Guessing 9 against a secret of 66 came back "Go LOWER" on attempt 2 and
    # "Go HIGHER" on attempt 1 - the history panel is what made it obvious.
    app = fresh_app()
    app.session_state.secret = 66

    for _ in range(4):
        submit(app, "9")

    outcomes = {entry["outcome"] for entry in app.session_state.history}
    assert outcomes == {"Too Low"}

    messages = {entry["message"] for entry in app.session_state.history}
    assert len(messages) == 1
    assert "HIGHER" in messages.pop()


# --- high score panel -------------------------------------------------------

def test_scoreboard_is_empty_until_a_game_finishes():
    app = fresh_app()
    assert app.session_state.high_scores == {}

    app.session_state.secret = 50
    submit(app, "10")
    assert app.session_state.high_scores == {}


def test_a_win_lands_on_the_scoreboard():
    app = fresh_app()
    app.session_state.secret = 50

    submit(app, "10")
    submit(app, "50")

    assert app.session_state.status == "won"

    row = app.session_state.high_scores["Normal"]
    assert row["wins"] == 1
    assert row["losses"] == 0
    assert row["fewest_attempts"] == 2
    assert row["best_score"] is not None

    rendered = " ".join(sidebar_markdown(app))
    assert "Normal" in rendered
    assert "1W / 0L" in rendered


def test_running_out_of_attempts_records_a_loss_and_no_record():
    app = fresh_app()
    app.session_state.secret = 50

    for _ in range(8):
        submit(app, "10")

    assert app.session_state.status == "lost"

    row = app.session_state.high_scores["Normal"]
    assert row["losses"] == 1
    assert row["wins"] == 0
    assert row["best_score"] is None


def test_scoreboard_outlives_a_new_game():
    # The whole point of a high score: it is the one thing New Game keeps.
    app = fresh_app()
    app.session_state.secret = 50
    submit(app, "50")

    saved = dict(app.session_state.high_scores["Normal"])

    app.button[1].click().run()  # New Game

    assert app.session_state.high_scores["Normal"] == saved
    assert app.session_state.history == []
    assert app.session_state.attempts == 0


# --- New Game ---------------------------------------------------------------

def test_new_game_revives_the_submit_button_after_a_win():
    # FIX (Bug 3), row 3 of my reproduction log: New Game reset the counter
    # but left status on "won", so the st.stop() guard swallowed every later
    # click and Submit did nothing.
    app = fresh_app()
    app.session_state.secret = 50
    submit(app, "50")
    assert app.session_state.status == "won"

    app.button[1].click().run()
    assert app.session_state.status == "playing"

    submit(app, "10")
    assert app.session_state.attempts == 1
    assert not app.exception


def test_new_game_clears_the_history_panel():
    app = fresh_app()
    app.session_state.secret = 50
    submit(app, "10")
    assert sidebar_text(app)

    app.button[1].click().run()
    assert sidebar_text(app) == []


# --- difficulty -------------------------------------------------------------

@pytest.mark.parametrize(
    "difficulty,low,high,allowance",
    [("Easy", 1, 20, 6), ("Hard", 1, 50, 5)],
)
def test_switching_difficulty_deals_a_reachable_secret(
    difficulty, low, high, allowance
):
    # Switching boards used to keep the old secret, so an Easy game could
    # still be hiding 87 - unguessable, because 87 is out of range.
    app = fresh_app()
    app.selectbox[0].set_value(difficulty).run()

    assert low <= app.session_state.secret <= high
    assert app.session_state.attempts == 0
    assert app.session_state.history == []
    assert f"Attempts left: {allowance}" in app.info[0].value


def test_each_difficulty_keeps_its_own_record():
    app = fresh_app()

    app.selectbox[0].set_value("Easy").run()
    app.session_state.secret = 10
    submit(app, "10")

    app.selectbox[0].set_value("Hard").run()
    app.session_state.secret = 25
    submit(app, "25")

    assert app.session_state.high_scores["Easy"]["wins"] == 1
    assert app.session_state.high_scores["Hard"]["wins"] == 1
    assert "Normal" not in app.session_state.high_scores


# --- enhanced UI ------------------------------------------------------------
#
# The formatting layer must improve what the player sees without changing
# what the game does. These tests check both halves of that: the panels
# appear and say the right thing, and the rules underneath are untouched.


def banners(app):
    """The colour-coded hint lines currently on the page."""
    return [m.value for m in app.markdown if m.value.startswith("###")]


def test_the_metric_tiles_track_the_game():
    app = fresh_app()
    app.session_state.secret = 50

    labels = [m.label for m in app.metric]
    assert labels == ["Score", "Attempts", "Closest yet"]
    assert [m.value for m in app.metric] == ["0", "0/8", "—"]

    submit(app, "40")
    values = {m.label: m.value for m in app.metric}
    assert values["Attempts"] == "1/8"
    assert values["Closest yet"] == "10"


def test_closest_yet_only_improves():
    app = fresh_app()
    app.session_state.secret = 50

    submit(app, "45")
    submit(app, "10")

    closest = {m.label: m.value for m in app.metric}["Closest yet"]
    assert closest == "5"


def test_the_hint_is_colour_coded_and_carries_a_temperature():
    app = fresh_app()
    app.session_state.secret = 66

    submit(app, "10")
    banner = banners(app)[0]

    assert ":orange[" in banner      # a miss, in the "keep going" colour
    assert "Go HIGHER!" in banner    # the direction, unchanged
    assert "Freezing" in banner      # and how far off it was


def test_a_win_is_green_and_drops_the_temperature():
    app = fresh_app()
    app.session_state.secret = 50

    submit(app, "50")
    banner = banners(app)[0]

    assert ":green[" in banner
    assert "Correct!" in banner
    assert "Exact" not in banner


def test_rejected_input_clears_the_previous_hint():
    # Otherwise the banner from the last real guess sits there looking
    # like a response to the typo that was just submitted.
    app = fresh_app()
    app.session_state.secret = 50

    submit(app, "40")
    assert banners(app)

    submit(app, "abc")
    assert not banners(app)
    assert app.error[0].value == "That is not a number."


def test_errors_show_even_with_hints_switched_off():
    # The hint is optional; being told your input was rejected is not.
    app = fresh_app()
    app.checkbox[0].set_value(False).run()

    submit(app, "abc")
    assert not banners(app)
    assert app.error[0].value == "That is not a number."


def test_switching_hints_off_hides_the_banner_but_not_the_game():
    app = fresh_app()
    app.session_state.secret = 50

    app.checkbox[0].set_value(False).run()
    submit(app, "40")

    assert not banners(app)
    # The guess still counted, was still logged, and still scored.
    assert app.session_state.attempts == 1
    assert app.session_state.history[-1]["outcome"] == "Too Low"


def test_the_summary_table_appears_only_once_the_game_is_over():
    # Every row reveals the distance to the secret, so showing it mid-game
    # would hand the player the answer.
    app = fresh_app()
    app.session_state.secret = 50

    submit(app, "40")
    assert not app.get("table")

    submit(app, "50")
    assert len(app.get("table")) == 1


def test_the_summary_table_replays_the_whole_session():
    app = fresh_app()
    app.session_state.secret = 50

    submit(app, "abc")
    submit(app, "10")
    submit(app, "90")
    submit(app, "50")

    rows = app.get("table")[0].value
    assert list(rows["Guess"]) == ["abc", "10", "90", "50"]
    assert list(rows["Result"]) == ["Invalid", "Too Low", "Too High", "Win"]
    assert list(rows["Off by"]) == ["—", "40", "40", "0"]


def test_the_summary_caption_reports_the_secret_and_the_counts():
    app = fresh_app()
    app.session_state.secret = 50

    submit(app, "abc")
    submit(app, "50")

    caption = [c.value for c in app.caption if "Secret:" in c.value][0]
    assert "Secret: 50" in caption
    assert "1 attempts used" in caption
    assert "1 rejected" in caption


def test_the_progress_bar_tracks_attempts():
    app = fresh_app()
    app.session_state.secret = 50

    assert "8 of 8 attempts remaining" in app.get("progress")[0].proto.text

    submit(app, "40")
    assert "7 of 8 attempts remaining" in app.get("progress")[0].proto.text


def test_a_rejected_guess_does_not_move_the_progress_bar():
    app = fresh_app()
    app.session_state.secret = 50

    submit(app, "abc")
    assert "8 of 8 attempts remaining" in app.get("progress")[0].proto.text


def test_the_progress_bar_never_overflows():
    # st.progress raises if the fraction leaves 0..1, so a game played to
    # its last turn is the case that would catch an off-by-one.
    app = fresh_app()
    app.session_state.secret = 50

    for _ in range(8):
        submit(app, "10")

    assert app.session_state.status == "lost"
    assert not app.exception
    assert "0 of 8 attempts remaining" in app.get("progress")[0].proto.text


def test_the_formatting_layer_does_not_change_the_rules():
    # The guard on this whole section: play a scripted game and assert the
    # underlying state is exactly what it was before any of the UI work.
    app = fresh_app()
    app.session_state.secret = 73

    submit(app, "abc")   # rejected, costs nothing
    submit(app, "50")    # Too Low
    submit(app, "90")    # Too High
    submit(app, "73")    # Win

    assert app.session_state.attempts == 3
    assert app.session_state.status == "won"
    assert [e["outcome"] for e in app.session_state.history] == [
        "Invalid", "Too Low", "Too High", "Win"
    ]
    assert app.session_state.high_scores["Normal"]["wins"] == 1
    assert app.session_state.high_scores["Normal"]["fewest_attempts"] == 3
