"""Helpers for the hint cost behaviour.

The cost behaviour decides when the cost of a hint is charged to an account:

``at_unlock`` (default)
    Stock CTFd behaviour. The cost is deducted from the account score the moment the
    hint is unlocked, and solving the challenge pays its full value.

``at_solve``
    Unlocking the hint is free. When a challenge is solved, the cost of the hints the
    account unlocked for it is deducted from the points the challenge awards, clamped
    at zero. A hint asked for on a challenge that is never solved costs nothing.

Each hint can carry its own ``cost_behavior``. A hint with no explicit behaviour
inherits the instance wide ``hint_cost_behavior`` setting, so both behaviours can
coexist inside one challenge and existing hints keep behaving as they did.
"""

from CTFd.models import Awards, Hints, HintUnlocks, db
from CTFd.utils import get_config

HINT_COST_AT_UNLOCK = "at_unlock"
HINT_COST_AT_SOLVE = "at_solve"
HINT_COST_BEHAVIORS = (HINT_COST_AT_UNLOCK, HINT_COST_AT_SOLVE)

# Category used by the charge created at solve time. It is deliberately distinct from
# the "hints" category used by the charge created at unlock time, so that removing a
# solve can drop the former without touching what the player paid to unlock a hint.
HINT_DEDUCTION_CATEGORY = "hint_deduction"


def get_hint_cost_behavior():
    """Return the instance wide behaviour, falling back to at_unlock."""
    behavior = get_config("hint_cost_behavior", default=HINT_COST_AT_UNLOCK)
    if behavior not in HINT_COST_BEHAVIORS:
        return HINT_COST_AT_UNLOCK
    return behavior


def hint_cost_behavior(hint):
    """Effective behaviour for one hint: its own value, else the instance setting."""
    behavior = getattr(hint, "cost_behavior", None)
    if behavior in HINT_COST_BEHAVIORS:
        return behavior
    return get_hint_cost_behavior()


def hint_charges_at_unlock(hint):
    """True when unlocking this hint has to be charged right away."""
    return hint_cost_behavior(hint) == HINT_COST_AT_UNLOCK


def get_hint_cost(account_id, challenge_id, behavior=None):
    """Total cost of the hints this account unlocked for a challenge.

    Passing ``behavior`` limits the sum to the hints whose effective behaviour
    matches, which is how a challenge with hints of both behaviours is charged
    correctly on each side.
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
        if behavior is not None and hint_cost_behavior(hint) != behavior:
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
        behavior=HINT_COST_AT_SOLVE,
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
        challenge_id=challenge.id,
        name="Hint deduction: {}".format(challenge.name),
        description="Cost of the hints unlocked for {}".format(challenge.name),
        value=-deduction,
        category=HINT_DEDUCTION_CATEGORY,
    )
    db.session.add(award)
    db.session.commit()
    return award


def remove_hint_deduction(account_id, challenge_id):
    """Delete the charge created at solve time for a challenge.

    Called when a solve is removed so the account does not keep a permanent penalty
    without the challenge value that paid for it. Awards created at unlock time are
    left alone: the player paid for those when they asked for the hint.
    """
    query = Awards.query.filter(
        Awards.category == HINT_DEDUCTION_CATEGORY,
        Awards.challenge_id == challenge_id,
    )
    if account_id is not None:
        query = query.filter(Awards.account_id == account_id)

    removed = 0
    for award in query.all():
        db.session.delete(award)
        removed += 1
    if removed:
        db.session.commit()
    return removed


def remove_challenge_hint_awards(challenge_id):
    """Drop every hint charge tied to a challenge that is being deleted.

    Without this, deleting a challenge removes its solves (and therefore the points
    that paid for the hints) but leaves the charges behind as a permanent penalty.
    """
    removed = 0
    for award in Awards.query.filter_by(challenge_id=challenge_id).all():
        db.session.delete(award)
        removed += 1
    if removed:
        db.session.commit()
    return removed
