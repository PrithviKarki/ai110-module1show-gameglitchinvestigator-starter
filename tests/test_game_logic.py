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
