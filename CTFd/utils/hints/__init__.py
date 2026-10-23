"""Helpers for the hint penalty rules.

The penalty mode decides when the cost of a hint is charged to an account:

``at_solve``
    Unlocking the hint is free. When a challenge is solved, the cost of the hints the
    account unlocked for it is deducted from the points the challenge awards, clamped
    at zero. A hint asked for on a challenge that is never solved costs nothing.

``at_unlock``
    Stock CTFd behaviour. The cost is deducted from the account score the moment the
    hint is unlocked, and solving the challenge pays its full value.

Each hint can carry its own ``penalty_mode``. A hint with no explicit mode inherits
the instance wide ``hint_penalty_mode`` setting, so both modes can coexist inside one
challenge and existing hints keep behaving as they did.
"""

from CTFd.models import Awards, Hints, HintUnlocks, db
from CTFd.utils import get_config

HINT_PENALTY_AT_SOLVE = "at_solve"
HINT_PENALTY_AT_UNLOCK = "at_unlock"
HINT_PENALTY_MODES = (HINT_PENALTY_AT_SOLVE, HINT_PENALTY_AT_UNLOCK)


def get_hint_penalty_mode():
    """Return the instance wide mode, falling back to at_solve."""
    mode = get_config("hint_penalty_mode", default=HINT_PENALTY_AT_SOLVE)
    if mode not in HINT_PENALTY_MODES:
        return HINT_PENALTY_AT_SOLVE
    return mode


def hint_penalty_mode(hint):
    """Effective mode for one hint: its own value, else the instance setting."""
    mode = getattr(hint, "penalty_mode", None)
    if mode in HINT_PENALTY_MODES:
        return mode
    return get_hint_penalty_mode()


def hint_charges_at_unlock(hint):
    """True when unlocking this hint has to be charged right away."""
    return hint_penalty_mode(hint) == HINT_PENALTY_AT_UNLOCK


def get_hint_cost(account_id, challenge_id, mode=None):
    """Total cost of the hints this account unlocked for a challenge.

    Passing ``mode`` limits the sum to the hints whose effective mode matches, which is
    how a challenge with hints of both modes is charged correctly on each side.
    """
    rows = (
        db.session.query(Hints)
        .join(HintUnlocks, HintUnlocks.target == Hints.id)
        .filter(
            HintUnlocks.account_id == account_id,
            Hints.challenge_id == challenge_id,
        )
        .all()
    )

    total = 0
    for hint in rows:
        if mode is not None and hint_penalty_mode(hint) != mode:
            continue
        total += int(hint.cost or 0)
    return total


def apply_hint_deduction(user, team, challenge):
    """Charge the at_solve hints unlocked for a challenge against the points it awards.

    The deduction is clamped to the challenge value so solving a challenge can never
    lower an account score. Returns the Award that was created, or None.
    """
    cost = get_hint_cost(
        account_id=user.account_id,
        challenge_id=challenge.id,
        mode=HINT_PENALTY_AT_SOLVE,
    )
    if cost <= 0:
        return None

    value = int(challenge.value or 0)
    deduction = min(cost, value)
    if deduction <= 0:
        return None

    award = Awards(
        user_id=user.id,
        team_id=team.id if team else None,
        name="Hint deduction: {}".format(challenge.name),
        description="Cost of the hints unlocked for {}".format(challenge.name),
        value=-deduction,
        category="hints",
        # Keeps the deduction tied to its challenge so removing the solve can
        # remove the deduction with it.
        requirements={"challenge_id": challenge.id, "hint_cost": cost},
    )
    db.session.add(award)
    db.session.commit()
    return award


def remove_hint_deduction(account_id, challenge_id):
    """Delete the deduction created for a solved challenge.

    Called when a solve is removed so the account does not keep a permanent penalty
    without the challenge value that paid for it.
    """
    awards = Awards.query.filter(Awards.category == "hints").all()
    removed = 0
    for award in awards:
        requirements = award.requirements or {}
        if requirements.get("challenge_id") != challenge_id:
            continue
        if account_id is not None and award.account_id != account_id:
            continue
        db.session.delete(award)
        removed += 1
    if removed:
        db.session.commit()
    return removed
