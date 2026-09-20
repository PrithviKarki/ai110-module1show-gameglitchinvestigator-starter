"""Pure game logic for the Glitchy Guesser.

Every function here is deliberately free of Streamlit and of global state.
They take values in and hand new values back, which is what lets the test
suite exercise the whole game without ever starting a Streamlit server.

The module is organised in two halves:

* **Core rules** - the range for a difficulty, parsing a typed guess,
  comparing it to the secret, and scoring the result.
* **Scoreboard & Guess History** - the helpers behind the two sidebar
  panels, added as a stretch feature.

`app.py` imports from this module and is responsible only for widgets,
session state, and layout.
"""

import random
import re

#: Icon shown beside each entry in the guess-history panel. ``Invalid``
#: covers input that was rejected before it ever reached the secret.
OUTCOME_ICONS = {
    "Win": "🎯",
    "Too High": "📉",
    "Too Low": "📈",
    "Invalid": "🚫",
}

#: Matches only a plain ASCII whole number or decimal, with an optional
#: leading sign. Deliberately stricter than ``int()``, which accepts
#: underscore separators ("1_0") and non-ASCII digits ("٥٠").
NUMERIC_PATTERN = re.compile(r"[+-]?\d+(\.\d+)?", re.ASCII)


# ---------------------------------------------------------------------------
# Core rules
# ---------------------------------------------------------------------------

def get_range_for_difficulty(difficulty):
    """Return the inclusive guessing range for a difficulty.

    Args:
        difficulty (str): One of ``"Easy"``, ``"Normal"`` or ``"Hard"``.

    Returns:
        tuple[int, int]: The ``(low, high)`` bounds, both inclusive. An
        unrecognised difficulty falls back to the Normal range rather than
        returning ``None``, so a typo or a renamed menu option cannot crash
        the caller that unpacks this tuple.

    Example:
        >>> get_range_for_difficulty("Easy")
        (1, 20)
        >>> get_range_for_difficulty("Nightmare")
        (1, 100)
    """
    if difficulty == "Easy":
        return 1, 20
    if difficulty == "Normal":
        return 1, 100
    if difficulty == "Hard":
        return 1, 50
    return 1, 100


def parse_guess(raw, low, high):
    """Turn whatever the player typed into a usable guess.

    This is the game's only input gate, so it is strict on purpose. Python's
    own ``int()`` and ``float()`` are more permissive than they look: they
    accept underscore separators (``int("1_0")`` is ``10``), non-ASCII
    digits (``int("٥٠")`` is ``50``), and ``float("50.9")`` truncated to
    ``50`` would score the player on a number they never typed. The regular
    expression check exists to close all three.

    Args:
        raw (str | None): The raw text from the input box. ``None`` and
            whitespace-only strings are treated as "nothing typed yet",
            which is the normal state on every Streamlit rerun.
        low (int): Lowest legal guess, inclusive.
        high (int): Highest legal guess, inclusive.

    Returns:
        tuple[bool, int | None, str | None]: A triple of
        ``(ok, guess, error)``. On success ``ok`` is ``True``, ``guess`` is
        the parsed integer and ``error`` is ``None``. On failure ``ok`` is
        ``False``, ``guess`` is ``None`` and ``error`` is a message written
        for the player. The three failure messages are distinct so the UI
        can tell "nothing typed" from "not a number" from "out of range".

    Example:
        >>> parse_guess("42", 1, 100)
        (True, 42, None)
        >>> parse_guess("101", 1, 100)[2]
        'Out of range. Guess a number between 1 and 100.'
        >>> parse_guess("1_0", 1, 100)[0]
        False
    """
    if raw is None:
        return False, None, "Enter a guess."

    if not isinstance(raw, str):
        raw = str(raw)

    raw = raw.strip()

    if raw == "":
        return False, None, "Enter a guess."

    if not NUMERIC_PATTERN.fullmatch(raw):
        return False, None, "That is not a number."

    if "." in raw:
        as_float = float(raw)
        if as_float != int(as_float):
            return False, None, "Whole numbers only. Drop the decimal."
        value = int(as_float)
    else:
        value = int(raw)

    if value < low or value > high:
        return (
            False,
            None,
            f"Out of range. Guess a number between {low} and {high}.",
        )

    return True, value, None


def check_guess(guess, secret):
    """Compare a guess against the secret and describe the result.

    Args:
        guess (int | str): The player's guess.
        secret (int | str): The number to find. Strings are tolerated by
            the fallback branch below; see the note on that branch.

    Returns:
        tuple[str, str]: An ``(outcome, message)`` pair. ``outcome`` is one
        of ``"Win"``, ``"Too High"`` or ``"Too Low"``, and ``message`` is
        the player-facing hint. The two always agree on direction: a
        ``"Too High"`` outcome always carries a "go LOWER" message.

    Note:
        The original code paired every outcome with the *opposite* hint, so
        guessing above the secret told the player to go higher. Both the
        numeric path and the string fallback carried the same swap. The
        fallback is kept because it is covered by tests that document the
        bug, but ``app.py`` no longer reaches it: it passes the secret
        through as an integer on every turn.

    Example:
        >>> check_guess(60, 50)
        ('Too High', '📉 Go LOWER!')
        >>> check_guess(50, 50)[0]
        'Win'
    """
    if guess == secret:
        return "Win", "🎉 Correct!"

    try:
        if guess > secret:
            return "Too High", "📉 Go LOWER!"
        return "Too Low", "📈 Go HIGHER!"
    except TypeError:
        text = str(guess)
        if text == secret:
            return "Win", "🎉 Correct!"
        if text > secret:
            return "Too High", "📉 Go LOWER!"
        return "Too Low", "📈 Go HIGHER!"


def update_score(current_score, outcome, attempt_number):
    """Apply one turn's result to the running score.

    A win is worth more the sooner it arrives, floored at 10 points so a
    long game still pays something. A miss costs 5 points.

    Args:
        current_score (int): Score before this turn.
        outcome (str): The outcome from :func:`check_guess`.
        attempt_number (int): Which attempt this was, counting from 1.

    Returns:
        int: The new score. An unrecognised outcome returns the score
        unchanged rather than guessing at a penalty.

    Note:
        The ``"Too High"`` branch awards **+5** on even-numbered attempts
        instead of deducting 5, which means a patient player can farm
        points by guessing high. This is left exactly as the original AI
        wrote it: it is scoring balance rather than a correctness bug, and
        changing it would invalidate the scores already recorded by the
        high-score table.

    Example:
        >>> update_score(0, "Win", 1)
        80
        >>> update_score(100, "Too Low", 3)
        95
    """
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


# ---------------------------------------------------------------------------
# Scoreboard & Guess History
# ---------------------------------------------------------------------------

def record_guess(history, attempt_number, guess, outcome, message):
    """Append one guess to the history and return a new list.

    Args:
        history (list[dict]): The history so far. It is never modified.
        attempt_number (int | None): Which attempt this was, or ``None``
            for input that was rejected and therefore cost no turn.
        guess (int | str): The parsed guess, or the raw text if it was
            rejected.
        outcome (str): An outcome from :func:`check_guess`, or
            ``"Invalid"`` for rejected input.
        message (str): The hint or error the player was shown.

    Returns:
        list[dict]: A **new** list with the entry appended. Returning a new
        list rather than mutating matters under Streamlit, which re-runs
        the whole script on every click: a stale reference to the old list
        could otherwise append the same guess twice.

    Example:
        >>> history = record_guess([], 1, 42, "Too Low", "Go HIGHER!")
        >>> history[0]["guess"], history[0]["attempt"]
        (42, 1)
    """
    entry = {
        "attempt": attempt_number,
        "guess": guess,
        "outcome": outcome,
        "message": message,
    }
    return list(history) + [entry]


def format_history_line(entry):
    """Render one history entry as a single line for the sidebar.

    Args:
        entry (dict): An entry built by :func:`record_guess`.

    Returns:
        str: A line such as ``"📉 #3 — 80 → Too High"``. A rejected guess
        shows ``#·`` in place of an attempt number, so the player can see
        the typo without it looking like a turn was spent. An unrecognised
        outcome renders a ``❔`` fallback icon rather than raising
        ``KeyError`` and taking the sidebar down.

    Example:
        >>> format_history_line({"attempt": 3, "guess": 80,
        ...                      "outcome": "Too High", "message": "m"})
        '📉 #3 — 80 → Too High'
    """
    icon = OUTCOME_ICONS.get(entry["outcome"], "❔")
    label = "·" if entry["attempt"] is None else str(entry["attempt"])
    return f"{icon} #{label} — {entry['guess']} → {entry['outcome']}"


def blank_high_score():
    """Return the high-score row for a difficulty never yet finished.

    Returns:
        dict: ``best_score`` and ``fewest_attempts`` start as ``None``
        rather than ``0``, because zero is a real score and would read as a
        record that had already been set.
    """
    return {
        "best_score": None,
        "fewest_attempts": None,
        "wins": 0,
        "losses": 0,
    }


def update_high_scores(high_scores, difficulty, score, attempts, won):
    """Fold one finished game into the high-score table.

    Args:
        high_scores (dict[str, dict]): The table so far, keyed by
            difficulty. It is never modified.
        difficulty (str): The difficulty the game was played on. Each one
            keeps its own record, because a 20-number board and a
            100-number board are not comparable.
        score (int): Final score for the game.
        attempts (int): How many turns the game took.
        won (bool): Whether the player found the secret.

    Returns:
        dict[str, dict]: A **new** table, deep enough that the caller's
        nested per-difficulty dicts are untouched.

    Note:
        The two records move in opposite directions: ``best_score`` keeps
        the **highest** value, ``fewest_attempts`` the **lowest**. A loss
        records a loss and nothing else, so running out of turns can never
        set a personal best no matter how many points were banked.

    Example:
        >>> table = update_high_scores({}, "Normal", 70, 3, won=True)
        >>> table["Normal"]["fewest_attempts"]
        3
    """
    table = {name: dict(row) for name, row in high_scores.items()}
    row = table.get(difficulty) or blank_high_score()

    if won:
        row["wins"] += 1
        if row["best_score"] is None or score > row["best_score"]:
            row["best_score"] = score
        if (row["fewest_attempts"] is None
                or attempts < row["fewest_attempts"]):
            row["fewest_attempts"] = attempts
    else:
        row["losses"] += 1

    table[difficulty] = row
    return table


def new_game_state(low, high, pick=random.randint):
    """Build every field a fresh game needs, as one dictionary.

    Args:
        low (int): Lowest legal guess for this difficulty, inclusive.
        high (int): Highest legal guess for this difficulty, inclusive.
        pick (callable): Two-argument picker used to choose the secret.
            Injectable so tests can pin the secret instead of seeding the
            global random module.

    Returns:
        dict: Keys ``secret``, ``attempts``, ``score``, ``status`` and
        ``history``, ready to splat into ``st.session_state``.

    Note:
        This exists because the old "New Game" button reset only
        ``attempts`` and ``secret``, leaving ``status`` on ``"won"`` so the
        guard clause swallowed every later click and the Submit button
        stayed dead. It also picked from 1-100 regardless of difficulty, so
        an Easy board could hide an unreachable secret like 87. Resetting
        through one function means no field can be silently forgotten
        again.

    Example:
        >>> state = new_game_state(1, 20, pick=lambda lo, hi: 7)
        >>> state["secret"], state["status"]
        (7, 'playing')
    """
    return {
        "secret": pick(low, high),
        "attempts": 0,
        "score": 0,
        "status": "playing",
        "history": [],
    }
