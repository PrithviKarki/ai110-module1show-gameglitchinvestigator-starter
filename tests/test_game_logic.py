import pytest

# FIX: check_guess was imported from the logic_utils stub, so the first three
# tests failed with NotImplementedError. The AI noticed this while adding the
# Bug 1 tests and I had it point the import at app.py, where the real
# implementations still live.
from app import (
    check_guess,
    parse_guess,
    get_range_for_difficulty,
    record_guess,
    format_history_line,
    blank_high_score,
    update_high_scores,
    new_game_state,
)

def test_winning_guess():
    # If the secret is 50 and guess is 50, it should be a win
    # FIX: these three compared a (outcome, message) tuple to a plain string,
    # so they could never pass. The AI spotted the mismatch and unpacked them.
    outcome, _ = check_guess(50, 50)
    assert outcome == "Win"

def test_guess_too_high():
    # If secret is 50 and guess is 60, hint should be "Too High"
    outcome, _ = check_guess(60, 50)
    assert outcome == "Too High"

def test_guess_too_low():
    # If secret is 50 and guess is 40, hint should be "Too Low"
    outcome, _ = check_guess(40, 50)
    assert outcome == "Too Low"


# --- Bug 1: check_guess returned the direction hint for the opposite outcome ---
#
# FIX: I asked Claude Code in agent mode to write tests targeting the swapped
# labels. It drafted this section, then verified it by running the suite against
# a copy of app.py with the swap restored - all of these failed, as they should.
#
# The outcome labels ("Too High" / "Too Low") were always correct; the message
# paired with them was backwards, so a guess above the secret told the player
# to "Go HIGHER!". These tests assert on the message, not just the outcome,
# because the outcome alone never caught the bug.


@pytest.mark.parametrize(
    "guess,secret",
    [(60, 50), (51, 50), (100, 1), (100, 99), (2, 1)],
)
def test_too_high_tells_the_player_to_go_lower(guess, secret):
    outcome, message = check_guess(guess, secret)
    assert outcome == "Too High"
    assert "LOWER" in message
    assert "HIGHER" not in message


@pytest.mark.parametrize(
    "guess,secret",
    [(40, 50), (49, 50), (1, 100), (1, 2), (99, 100)],
)
def test_too_low_tells_the_player_to_go_higher(guess, secret):
    outcome, message = check_guess(guess, secret)
    assert outcome == "Too Low"
    assert "HIGHER" in message
    assert "LOWER" not in message


@pytest.mark.parametrize("guess", [g for g in range(1, 101) if g != 50])
def test_outcome_and_message_always_agree(guess):
    # The invariant the bug violated: whichever direction the outcome names,
    # the message must name the same one. A swap flips both labels at once,
    # so this pairing check is what pins the fix in place across the whole
    # 1-100 range.
    outcome, message = check_guess(guess, 50)
    expected_word = "LOWER" if outcome == "Too High" else "HIGHER"
    assert expected_word in message


def test_winning_message_gives_no_direction_at_all():
    # A correct guess must not tell the player to keep moving.
    _, message = check_guess(50, 50)
    assert "HIGHER" not in message
    assert "LOWER" not in message


def test_following_the_hints_actually_finds_the_secret():
    # The player-facing consequence of the bug: play the game by obeying the
    # hint each turn. With the directions swapped, the search walks away from
    # the secret and never converges.
    secret = 73
    low, high = 1, 100

    for _ in range(10):
        guess = (low + high) // 2
        outcome, message = check_guess(guess, secret)

        if outcome == "Win":
            break

        if "HIGHER" in message:
            low = guess + 1
        else:
            high = guess - 1
    else:
        pytest.fail("Following the hints never reached the secret")

    assert guess == secret


@pytest.mark.parametrize(
    "guess,secret,expected_outcome,expected_word",
    [(60, "50", "Too High", "LOWER"), (40, "50", "Too Low", "HIGHER")],
)
def test_string_comparison_fallback_also_pairs_correctly(
    guess, secret, expected_outcome, expected_word
):
    # app.py stringifies the secret on even-numbered attempts, which sends
    # check_guess into its TypeError fallback. That branch had the same swap,
    # so it needs its own coverage. These two pairs are chosen so digit-order
    # and number-order agree, keeping this test about the labels only.
    outcome, message = check_guess(guess, secret)
    assert outcome == expected_outcome
    assert expected_word in message


# --- Bug 2: parse_guess accepted any integer, with no range validation ---

@pytest.mark.parametrize("raw", ["0", "-1", "-500", "101", "9999"])
def test_guess_outside_range_is_rejected(raw):
    # These all parse as valid ints, so the only thing that can reject them
    # is a range check. Before the fix, every one of these returned ok=True.
    ok, guess, err = parse_guess(raw, 1, 100)
    assert ok is False
    assert guess is None
    assert err is not None


@pytest.mark.parametrize("raw", ["0", "101"])
def test_out_of_range_guess_is_not_scoreable(raw):
    # A rejected guess must not leak a usable number back to the caller,
    # otherwise app.py would compare it to the secret and score it.
    _, guess, _ = parse_guess(raw, 1, 100)
    assert guess is None


@pytest.mark.parametrize("raw,expected", [("1", 1), ("100", 100), ("50", 50)])
def test_guesses_inside_range_still_pass(raw, expected):
    # The bounds are inclusive: 1 and 100 are legal guesses, not off-by-one
    # casualties of the new check.
    ok, guess, err = parse_guess(raw, 1, 100)
    assert ok is True
    assert guess == expected
    assert err is None


def test_range_follows_difficulty_not_a_hardcoded_1_to_100():
    # On Easy the range is 1-20, so 21 must be rejected even though it is a
    # perfectly legal guess on Normal. This is what catches a fix that
    # hardcodes 1 and 100 instead of using the difficulty's real bounds.
    low, high = get_range_for_difficulty("Easy")
    assert (low, high) == (1, 20)

    ok_easy, _, _ = parse_guess("21", low, high)
    assert ok_easy is False

    ok_normal, _, _ = parse_guess("21", 1, 100)
    assert ok_normal is True


def test_out_of_range_error_message_reports_the_bounds():
    # The player needs to be told what the legal range actually is.
    _, _, err = parse_guess("21", 1, 20)
    assert "1" in err and "20" in err


def test_out_of_range_is_distinct_from_not_a_number():
    # "101" is a number that is out of range; "abc" is not a number at all.
    # Collapsing the two would tell the player the wrong thing.
    _, _, range_err = parse_guess("101", 1, 100)
    _, _, nan_err = parse_guess("abc", 1, 100)
    assert range_err is not None
    assert nan_err is not None
    assert range_err != nan_err


# ============================================================================
# Advanced edge-case testing
# ============================================================================
#
# The tests above cover the two bugs I actually found by playing the game.
# This section covers the inputs a player can type that the happy path never
# thinks about. I asked Claude Code to brainstorm hostile inputs for
# parse_guess, then kept the ones that were really different from each other
# rather than ten spellings of "abc" (see ai_interactions.md for the prompts
# and my reasoning on each case).
#
# Three of these found real defects in my own fix, which is why they are here:
#   * "1_0" parsed as 10, because Python allows underscore digit separators.
#   * "٥٠" parsed as 50, because int() accepts non-ASCII decimal digits.
#   * "50.9" was silently truncated to 50 and scored as a guess of 50.


# --- Edge case 1: non-numeric strings ---------------------------------------

@pytest.mark.parametrize(
    "raw",
    [
        "abc",            # plain letters
        "fifty",          # the number spelled out
        "!!!",            # punctuation only
        "🎮",             # emoji
        "12abc",          # digits with a tail
        "abc12",          # digits with a head
        "1 2",            # internal whitespace
        "0x32",           # hex literal for 50
        "5e1",            # scientific notation for 50
        "--5",            # doubled sign
        "1,000",          # thousands separator
        "1_0",            # Python underscore separator -> used to parse as 10
        "٥٠",             # Arabic-Indic digits -> used to parse as 50
        "１２",            # full-width digits -> used to parse as 12
        "nan",            # float() understands these; a guessing game must not
        "inf",
        "-inf",
    ],
)
def test_non_numeric_strings_are_rejected(raw):
    # None of these are a whole number a player meant to type, so every one
    # must come back ok=False with no value. The last five matter most: they
    # are the inputs that Python's int()/float() quietly ACCEPT, so a naive
    # try/except parser lets them through and scores them.
    ok, guess, err = parse_guess(raw, 1, 100)
    assert ok is False
    assert guess is None
    assert err == "That is not a number."


# --- Edge case 2: negative numbers ------------------------------------------

@pytest.mark.parametrize("raw", ["-1", "-5", "-50", "-100", "-9999"])
def test_negative_numbers_are_rejected_as_out_of_range(raw):
    # A negative is a perfectly valid int, so the type check can never catch
    # it - only the bounds check can. It must be reported as out of range and
    # not as "not a number", because the player typed a real number.
    ok, guess, err = parse_guess(raw, 1, 100)
    assert ok is False
    assert guess is None
    assert "Out of range" in err


@pytest.mark.parametrize("raw", ["-0", "0", "+0"])
def test_zero_in_all_its_spellings_is_below_the_range(raw):
    # Zero is the off-by-one boundary: low is 1, so 0 is the first illegal
    # value underneath it. "-0" and "+0" both parse to 0 and must be treated
    # identically - no sign-handling shortcut may let one of them slip in.
    ok, guess, _ = parse_guess(raw, 1, 100)
    assert ok is False
    assert guess is None


def test_negative_range_would_still_work():
    # The bounds check must compare against the low/high it is given, not
    # against a hardcoded assumption that guesses are positive. If the game
    # ever offered a -50..50 board, -10 is a legal guess on it.
    ok, guess, err = parse_guess("-10", -50, 50)
    assert ok is True
    assert guess == -10
    assert err is None


# --- Edge case 3: empty and whitespace-only input ---------------------------

@pytest.mark.parametrize(
    "raw",
    ["", " ", "   ", "\t", "\n", "  \t\n  "],
)
def test_empty_and_whitespace_only_input_asks_for_a_guess(raw):
    # Streamlit's text_input hands back "" on every rerun before the player
    # types anything, so this is the single most common input the function
    # sees. It must say "Enter a guess." - not "That is not a number." -
    # because scolding someone for typing nothing yet is wrong.
    ok, guess, err = parse_guess(raw, 1, 100)
    assert ok is False
    assert guess is None
    assert err == "Enter a guess."


def test_none_input_is_handled_without_crashing():
    # A missing session-state key gives None rather than "". Calling .strip()
    # on None would raise AttributeError and take the whole app down, so the
    # None check has to come before any string handling.
    ok, guess, err = parse_guess(None, 1, 100)
    assert ok is False
    assert guess is None
    assert err == "Enter a guess."


@pytest.mark.parametrize("raw", [" 50", "50 ", "  50  ", "\t50\n"])
def test_padding_whitespace_is_forgiven_around_a_real_guess(raw):
    # The flip side of the rule above: whitespace AROUND a number is a typo,
    # not an error. A trailing space from a paste must not cost an attempt.
    ok, guess, err = parse_guess(raw, 1, 100)
    assert ok is True
    assert guess == 50
    assert err is None


# --- Edge case 4: decimals --------------------------------------------------

@pytest.mark.parametrize("raw", ["50.9", "49.5", "1.1", "99.99"])
def test_non_whole_decimals_are_rejected_instead_of_truncated(raw):
    # This is the defect this section found. int(float("50.9")) is 50, so the
    # old parser accepted the guess, hid the truncation, and scored the player
    # on a number they did not type. Rejecting is the honest behavior.
    ok, guess, err = parse_guess(raw, 1, 100)
    assert ok is False
    assert guess is None
    assert "Whole numbers" in err


@pytest.mark.parametrize("raw,expected", [("50.0", 50), ("1.00", 1), ("100.0", 100)])
def test_decimals_that_are_whole_numbers_still_count(raw, expected):
    # "50.0" IS fifty. Rejecting it would punish formatting, not the guess.
    ok, guess, err = parse_guess(raw, 1, 100)
    assert ok is True
    assert guess == expected
    assert err is None


@pytest.mark.parametrize("raw", [".", ".5", "5.", "1.2.3"])
def test_malformed_decimals_are_not_numbers(raw):
    # A lone or trailing dot is a half-typed guess, not a value. float() would
    # happily turn ".5" into 0.5 and "5." into 5.0, so this needs its own rule.
    ok, guess, err = parse_guess(raw, 1, 100)
    assert ok is False
    assert guess is None
    assert err == "That is not a number."


# --- Edge case 5: size and boundary extremes --------------------------------

def test_absurdly_large_number_is_rejected_not_crashed():
    # Python ints are unbounded, so a 300-digit guess parses fine and only the
    # range check stops it. This confirms the ordering never overflows or
    # hangs on input a bored player can produce by holding down a key.
    ok, guess, err = parse_guess("9" * 300, 1, 100)
    assert ok is False
    assert guess is None
    assert "Out of range" in err


@pytest.mark.parametrize(
    "difficulty,low,high",
    [("Easy", 1, 20), ("Normal", 1, 100), ("Hard", 1, 50)],
)
def test_bounds_are_inclusive_and_one_past_them_is_not(difficulty, low, high):
    # Walk the four values that straddle each difficulty's edges. This is the
    # off-by-one sweep: low-1 and high+1 out, low and high in, on every board.
    assert get_range_for_difficulty(difficulty) == (low, high)

    assert parse_guess(str(low - 1), low, high)[0] is False
    assert parse_guess(str(low), low, high)[0] is True
    assert parse_guess(str(high), low, high)[0] is True
    assert parse_guess(str(high + 1), low, high)[0] is False


def test_unknown_difficulty_falls_back_to_a_usable_range():
    # A typo or a renamed option must not return None and blow up the caller.
    assert get_range_for_difficulty("Nightmare") == (1, 100)
    assert get_range_for_difficulty("") == (1, 100)


# --- Edge case 6: parse_guess never raises ----------------------------------

@pytest.mark.parametrize(
    "raw",
    [
        None, "", "   ", "abc", "🎮", "-1", "0", "101", "50.9", ".",
        "1_0", "٥٠", "nan", "inf", "0x32", "9" * 300, "1,000", "--5",
    ],
)
def test_parse_guess_always_returns_a_three_part_answer(raw):
    # The contract app.py relies on: whatever goes in, a (ok, value, error)
    # tuple comes out and nothing propagates an exception up into Streamlit.
    # It also pins the invariant that ok and the error message can never both
    # be true at once - a rejected guess always explains itself.
    result = parse_guess(raw, 1, 100)

    assert isinstance(result, tuple)
    assert len(result) == 3

    ok, guess, err = result
    assert isinstance(ok, bool)

    if ok:
        assert isinstance(guess, int)
        assert err is None
    else:
        assert guess is None
        assert isinstance(err, str) and err != ""


# ============================================================================
# Feature: Scoreboard & Guess History
# ============================================================================
#
# Built in Claude Code agent mode (see ai_interactions.md). The four helpers
# below are pure on purpose - they take state in and hand new state back - so
# the feature can be tested without launching Streamlit. Everything that
# touches st.session_state is a one-line call to one of these.


# --- record_guess -----------------------------------------------------------

def test_record_guess_appends_a_structured_entry():
    history = record_guess([], 1, 42, "Too Low", "📈 Go HIGHER!")

    assert len(history) == 1
    assert history[0] == {
        "attempt": 1,
        "guess": 42,
        "outcome": "Too Low",
        "message": "📈 Go HIGHER!",
    }


def test_record_guess_does_not_mutate_the_list_it_was_given():
    # Streamlit re-runs the whole script on every click. If record_guess
    # mutated in place, a stale reference from the previous run could append
    # the same guess twice. Returning a new list makes that impossible.
    original = [{"attempt": 1, "guess": 10, "outcome": "Too Low", "message": "x"}]
    updated = record_guess(original, 2, 20, "Too High", "y")

    assert len(original) == 1
    assert len(updated) == 2
    assert updated[0] is not original[0] or original[0]["guess"] == 10


def test_record_guess_keeps_guesses_in_the_order_they_were_made():
    history = []
    for n, guess in enumerate([10, 20, 30], start=1):
        history = record_guess(history, n, guess, "Too Low", "📈 Go HIGHER!")

    assert [entry["guess"] for entry in history] == [10, 20, 30]
    assert [entry["attempt"] for entry in history] == [1, 2, 3]


def test_rejected_input_is_logged_with_no_attempt_number():
    # A typo is worth showing in the history, but it must not claim a turn.
    # attempt=None is what the sidebar renders as "·" instead of a number.
    history = record_guess([], None, "abc", "Invalid", "That is not a number.")

    assert history[0]["attempt"] is None
    assert history[0]["guess"] == "abc"
    assert history[0]["outcome"] == "Invalid"


# --- format_history_line ----------------------------------------------------

@pytest.mark.parametrize(
    "outcome,icon",
    [("Win", "🎯"), ("Too High", "📉"), ("Too Low", "📈"), ("Invalid", "🚫")],
)
def test_each_outcome_gets_its_own_icon(outcome, icon):
    # The icons are how you read the history at a glance, so a missing or
    # duplicated one would make the panel useless.
    line = format_history_line(
        {"attempt": 1, "guess": 50, "outcome": outcome, "message": "m"}
    )
    assert line.startswith(icon)


def test_history_line_shows_the_attempt_number_and_the_guess():
    line = format_history_line(
        {"attempt": 3, "guess": 42, "outcome": "Too High", "message": "m"}
    )
    assert "#3" in line
    assert "42" in line
    assert "Too High" in line


def test_history_line_marks_a_free_attempt_with_a_dot():
    line = format_history_line(
        {"attempt": None, "guess": "abc", "outcome": "Invalid", "message": "m"}
    )
    assert "#·" in line
    assert "None" not in line  # never leak the Python value into the UI


def test_history_line_survives_an_unknown_outcome():
    # A future outcome type must render a fallback icon, not raise KeyError
    # and take the sidebar down with it.
    line = format_history_line(
        {"attempt": 1, "guess": 5, "outcome": "Bamboozled", "message": "m"}
    )
    assert line.startswith("❔")


# --- update_high_scores -----------------------------------------------------

def test_first_win_creates_the_row_for_that_difficulty():
    table = update_high_scores({}, "Normal", score=70, attempts=3, won=True)

    assert table["Normal"] == {
        "best_score": 70,
        "fewest_attempts": 3,
        "wins": 1,
        "losses": 0,
    }


def test_a_better_score_replaces_the_old_best():
    table = update_high_scores({}, "Normal", score=70, attempts=3, won=True)
    table = update_high_scores(table, "Normal", score=90, attempts=2, won=True)

    assert table["Normal"]["best_score"] == 90
    assert table["Normal"]["fewest_attempts"] == 2
    assert table["Normal"]["wins"] == 2


def test_a_worse_score_does_not_replace_the_old_best():
    # "Best" moves one way only. This is the test that caught my first draft,
    # where I copy-pasted the comparison and wrote `<` for both fields.
    table = update_high_scores({}, "Normal", score=90, attempts=2, won=True)
    table = update_high_scores(table, "Normal", score=40, attempts=7, won=True)

    assert table["Normal"]["best_score"] == 90
    assert table["Normal"]["fewest_attempts"] == 2


def test_best_score_and_fewest_attempts_move_in_opposite_directions():
    # A win worth more points that took MORE guesses should update the score
    # and leave the attempt record alone. These two fields are independent.
    table = update_high_scores({}, "Hard", score=50, attempts=2, won=True)
    table = update_high_scores(table, "Hard", score=80, attempts=5, won=True)

    assert table["Hard"]["best_score"] == 80
    assert table["Hard"]["fewest_attempts"] == 2


def test_a_loss_records_a_loss_and_sets_no_records():
    # You cannot earn a personal best by running out of turns, even if the
    # score you accumulated happens to be high.
    table = update_high_scores({}, "Easy", score=999, attempts=1, won=False)

    assert table["Easy"]["losses"] == 1
    assert table["Easy"]["wins"] == 0
    assert table["Easy"]["best_score"] is None
    assert table["Easy"]["fewest_attempts"] is None


def test_difficulties_keep_separate_records():
    # A 20-number board and a 100-number board are not comparable, so one
    # scoreboard shared across them would be meaningless.
    table = update_high_scores({}, "Easy", score=80, attempts=2, won=True)
    table = update_high_scores(table, "Hard", score=30, attempts=5, won=True)

    assert table["Easy"]["best_score"] == 80
    assert table["Hard"]["best_score"] == 30
    assert "Normal" not in table


def test_update_high_scores_does_not_mutate_the_table_it_was_given():
    # Same rerun-safety rule as record_guess: the old table must survive
    # untouched, including the nested per-difficulty dict.
    original = update_high_scores({}, "Normal", score=70, attempts=3, won=True)
    updated = update_high_scores(original, "Normal", score=95, attempts=1, won=True)

    assert original["Normal"]["best_score"] == 70
    assert updated["Normal"]["best_score"] == 95


def test_blank_high_score_starts_empty():
    assert blank_high_score() == {
        "best_score": None,
        "fewest_attempts": None,
        "wins": 0,
        "losses": 0,
    }


# --- new_game_state ---------------------------------------------------------

def test_new_game_state_resets_every_field():
    # Bug 3 was a partial reset: attempts went back to 0 but status stayed
    # "won", so the st.stop() guard killed the Submit button forever. Listing
    # the keys here means a future field cannot be quietly forgotten.
    state = new_game_state(1, 100)

    assert set(state) == {"secret", "attempts", "score", "status", "history"}
    assert state["attempts"] == 0
    assert state["score"] == 0
    assert state["status"] == "playing"
    assert state["history"] == []


@pytest.mark.parametrize("low,high", [(1, 20), (1, 50), (1, 100)])
def test_new_secret_respects_the_difficulty_bounds(low, high):
    # The old New Game button called randint(1, 100) no matter the
    # difficulty, so an Easy board (1-20) could hide an unreachable 87.
    for _ in range(50):
        secret = new_game_state(low, high)["secret"]
        assert low <= secret <= high


def test_new_game_state_uses_the_picker_it_is_given():
    # Injecting the picker is what makes the secret testable at all.
    state = new_game_state(1, 100, pick=lambda lo, hi: 42)
    assert state["secret"] == 42


def test_a_fresh_secret_is_always_reachable_by_a_valid_guess():
    # The two halves of the fix have to agree: whatever new_game_state picks
    # must be a value parse_guess will actually accept on that board.
    for low, high in [(1, 20), (1, 50), (1, 100)]:
        secret = new_game_state(low, high)["secret"]
        ok, guess, err = parse_guess(str(secret), low, high)
        assert ok is True
        assert guess == secret


# --- the feature end to end -------------------------------------------------

def test_a_full_winning_game_lands_on_the_scoreboard():
    # Play a real game against the pure helpers: binary-search by obeying the
    # hints, log every guess, then fold the result into the high scores.
    state = new_game_state(1, 100, pick=lambda lo, hi: 73)
    high_scores = {}
    low, high = 1, 100

    while state["attempts"] < 8:
        guess = (low + high) // 2
        state["attempts"] += 1

        outcome, message = check_guess(guess, state["secret"])
        state["history"] = record_guess(
            state["history"], state["attempts"], guess, outcome, message
        )

        if outcome == "Win":
            state["status"] = "won"
            break
        if "HIGHER" in message:
            low = guess + 1
        else:
            high = guess - 1

    assert state["status"] == "won"
    assert state["history"][-1]["outcome"] == "Win"
    assert state["history"][-1]["guess"] == 73

    # Every logged attempt number is consecutive, so the history and the
    # counter can never disagree about how many turns were used.
    assert [e["attempt"] for e in state["history"]] == list(
        range(1, len(state["history"]) + 1)
    )

    high_scores = update_high_scores(
        high_scores, "Normal", score=60, attempts=state["attempts"], won=True
    )
    assert high_scores["Normal"]["wins"] == 1
    assert high_scores["Normal"]["fewest_attempts"] == state["attempts"]


def test_rejected_guesses_appear_in_history_without_costing_a_turn():
    # The player-facing promise of the free-attempt rule: three typos in a
    # row leave the attempt counter untouched but all show up in the panel.
    state = new_game_state(1, 100, pick=lambda lo, hi: 50)

    for junk in ["abc", "0", "999"]:
        ok, _, err = parse_guess(junk, 1, 100)
        assert ok is False
        state["history"] = record_guess(state["history"], None, junk, "Invalid", err)

    assert state["attempts"] == 0
    assert len(state["history"]) == 3
    assert all("#·" in format_history_line(e) for e in state["history"])
