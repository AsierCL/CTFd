"""Helpers for the ``hint_penalty_mode`` setting.

``hint_penalty_mode`` controls when the cost of a hint is charged to an account:

``at_solve`` (default)
    Unlocking a hint is free. When a challenge is solved, the cost of the hints the
    account unlocked for that challenge is deducted from the points the challenge
    awards, clamped at zero. A hint asked for on a challenge that is never solved
    costs nothing.

``at_unlock``
    Stock CTFd behaviour. The cost is deducted from the account score the moment the
    hint is unlocked, and solving the challenge pays its full value.
"""

from CTFd.models import Awards, Hints, HintUnlocks, db
from CTFd.utils import get_config

HINT_PENALTY_AT_SOLVE = "at_solve"
HINT_PENALTY_AT_UNLOCK = "at_unlock"
HINT_PENALTY_MODES = (HINT_PENALTY_AT_SOLVE, HINT_PENALTY_AT_UNLOCK)


def get_hint_penalty_mode():
    """Return the configured hint penalty mode, falling back to at_solve."""
    mode = get_config("hint_penalty_mode", default=HINT_PENALTY_AT_SOLVE)
    if mode not in HINT_PENALTY_MODES:
        return HINT_PENALTY_AT_SOLVE
    return mode


def deducts_at_solve():
    """True when the hint cost is charged when the challenge is solved."""
    return get_hint_penalty_mode() == HINT_PENALTY_AT_SOLVE


def get_hint_cost(account_id, challenge_id):
    """Total cost of the hints this account unlocked for a challenge."""
    total = (
        db.session.query(db.func.sum(Hints.cost))
        .join(HintUnlocks, HintUnlocks.target == Hints.id)
        .filter(
            HintUnlocks.account_id == account_id,
            Hints.challenge_id == challenge_id,
        )
        .scalar()
    )
    return int(total or 0)


def apply_hint_deduction(user, team, challenge):
    """Charge the hints unlocked for a challenge against the points it awards.

    Only active in at_solve mode. The deduction is clamped to the challenge value so
    solving a challenge can never lower an account score. Returns the Award that was
    created, or None when nothing was charged.
    """
    if not deducts_at_solve():
        return None

    cost = get_hint_cost(account_id=user.account_id, challenge_id=challenge.id)
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
    if not deducts_at_solve():
        return 0

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
