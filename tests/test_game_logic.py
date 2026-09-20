import pytest

# FIX: check_guess was imported from the logic_utils stub, so the first three
# tests failed with NotImplementedError. The AI noticed this while adding the
# Bug 1 tests and I had it point the import at app.py, where the real
# implementations still live.
from app import check_guess, parse_guess, get_range_for_difficulty

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
