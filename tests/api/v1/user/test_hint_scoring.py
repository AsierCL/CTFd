#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for the hint_cost_behavior setting.

at_unlock (default): upstream CTFd behaviour. The cost is deducted from the account
at the moment the hint is unlocked, and solving pays the full challenge value.

at_solve: unlocking a hint costs nothing. When the challenge is solved, the cost of
the hints unlocked for that challenge is deducted from the points the challenge
awards, clamped at zero.
"""

from CTFd.models import Awards, Challenges, Users
from CTFd.plugins.dynamic_challenges import DynamicChallenge
from CTFd.utils import get_config, set_config
from CTFd.utils.scores import get_standings
from tests.helpers import (
    create_ctfd,
    destroy_ctfd,
    gen_award,
    gen_challenge,
    gen_flag,
    gen_hint,
    gen_team,
    gen_user,
    login_as_user,
    register_user,
)


def solve(client, challenge_id, submission="flag"):
    return client.post(
        "/api/v1/challenges/attempt",
        json={"challenge_id": challenge_id, "submission": submission},
    )


def test_hint_cost_behavior_defaults_to_at_unlock():
    """Upgrading an instance must not change how hint costs are charged"""
    app = create_ctfd()
    with app.app_context():
        assert get_config("hint_cost_behavior") == "at_unlock"
    destroy_ctfd(app)


def test_unlocking_a_hint_does_not_change_the_score():
    """S1: in at_solve mode the unlock itself never moves the account score"""
    app = create_ctfd()
    with app.app_context():
        set_config("hint_cost_behavior", "at_solve")
        register_user(app)
        chal = gen_challenge(app.db, value=100)
        chal_id = chal.id
        gen_hint(app.db, chal_id, cost=10)
        gen_award(app.db, user_id=2, value=15)

        client = login_as_user(app)
        assert Users.query.filter_by(id=2).first().score == 15

        r = client.post("/api/v1/unlocks", json={"target": 1, "type": "hints"})
        assert r.status_code == 200

        r = client.get("/api/v1/hints/1")
        assert r.get_json()["data"]["content"] == "This is a hint"

        assert Users.query.filter_by(id=2).first().score == 15
        # Only the award created by the fixture; the unlock created none
        assert Awards.query.count() == 1
    destroy_ctfd(app)


def test_hint_can_be_unlocked_without_points():
    """S1/S3: with the charge deferred to the solve there is no points gate"""
    app = create_ctfd()
    with app.app_context():
        set_config("hint_cost_behavior", "at_solve")
        register_user(app)
        chal = gen_challenge(app.db, value=100)
        chal_id = chal.id
        gen_hint(app.db, chal_id, cost=10)

        client = login_as_user(app)
        assert Users.query.filter_by(id=2).first().score == 0

        r = client.post("/api/v1/unlocks", json={"target": 1, "type": "hints"})
        assert r.status_code == 200

        r = client.get("/api/v1/hints/1")
        assert r.get_json()["data"]["content"] == "This is a hint"
        assert Users.query.filter_by(id=2).first().score == 0
    destroy_ctfd(app)


def test_solving_deducts_the_hint_cost_from_the_challenge():
    """S2: challenge worth 10 with a 2 point hint pays 8"""
    app = create_ctfd()
    with app.app_context():
        set_config("hint_cost_behavior", "at_solve")
        register_user(app)
        chal = gen_challenge(app.db, value=10)
        chal_id = chal.id
        gen_flag(app.db, challenge_id=chal_id, content="flag")
        gen_hint(app.db, chal_id, cost=2)

        client = login_as_user(app)
        r = client.post("/api/v1/unlocks", json={"target": 1, "type": "hints"})
        assert r.status_code == 200
        assert Users.query.filter_by(id=2).first().score == 0

        r = solve(client, chal_id)
        assert r.get_json()["data"]["status"] == "correct"

        assert Users.query.filter_by(id=2).first().score == 8
    destroy_ctfd(app)


def test_solving_without_hints_awards_the_full_value():
    """S2: no hints unlocked, the challenge pays its full value"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        chal = gen_challenge(app.db, value=10)
        chal_id = chal.id
        gen_flag(app.db, challenge_id=chal_id, content="flag")

        client = login_as_user(app)
        r = solve(client, chal_id)
        assert r.get_json()["data"]["status"] == "correct"

        assert Users.query.filter_by(id=2).first().score == 10
    destroy_ctfd(app)


def test_deduction_is_clamped_at_zero():
    """S5: hints worth more than the challenge never make the score negative"""
    app = create_ctfd()
    with app.app_context():
        set_config("hint_cost_behavior", "at_solve")
        register_user(app)
        chal = gen_challenge(app.db, value=10)
        chal_id = chal.id
        gen_flag(app.db, challenge_id=chal_id, content="flag")
        for _ in range(3):
            gen_hint(app.db, chal_id, cost=5)

        client = login_as_user(app)
        for hint_id in (1, 2, 3):
            r = client.post(
                "/api/v1/unlocks", json={"target": hint_id, "type": "hints"}
            )
            assert r.status_code == 200

        r = solve(client, chal_id)
        assert r.get_json()["data"]["status"] == "correct"

        assert Users.query.filter_by(id=2).first().score == 0
    destroy_ctfd(app)


def test_unlocking_after_solving_deducts_nothing():
    """S6: the challenge is already paid, unlocking later costs nothing"""
    app = create_ctfd()
    with app.app_context():
        set_config("hint_cost_behavior", "at_solve")
        register_user(app)
        chal = gen_challenge(app.db, value=10)
        chal_id = chal.id
        gen_flag(app.db, challenge_id=chal_id, content="flag")
        gen_hint(app.db, chal_id, cost=2)

        client = login_as_user(app)
        r = solve(client, chal_id)
        assert r.get_json()["data"]["status"] == "correct"
        assert Users.query.filter_by(id=2).first().score == 10

        r = client.post("/api/v1/unlocks", json={"target": 1, "type": "hints"})
        assert r.status_code == 200
        r = client.get("/api/v1/hints/1")
        assert r.get_json()["data"]["content"] == "This is a hint"

        assert Users.query.filter_by(id=2).first().score == 10
    destroy_ctfd(app)


def test_at_unlock_mode_keeps_deducting_on_unlock():
    """S7: the upstream behaviour is the default and is unchanged"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        chal = gen_challenge(app.db, value=10)
        chal_id = chal.id
        gen_flag(app.db, challenge_id=chal_id, content="flag")
        gen_hint(app.db, chal_id, cost=10)
        gen_award(app.db, user_id=2, value=15)

        client = login_as_user(app)
        assert Users.query.filter_by(id=2).first().score == 15

        r = client.post("/api/v1/unlocks", json={"target": 1, "type": "hints"})
        assert r.status_code == 200
        # Deducted at unlock time, as in stock CTFd
        assert Users.query.filter_by(id=2).first().score == 5

        r = solve(client, chal_id)
        assert r.get_json()["data"]["status"] == "correct"
        # Solving pays the full challenge value
        assert Users.query.filter_by(id=2).first().score == 15
    destroy_ctfd(app)


def test_at_unlock_mode_still_refuses_unlocks_without_points():
    """The points gate belongs to at_unlock and must not be removed from it"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        chal = gen_challenge(app.db, value=10)
        gen_hint(app.db, chal.id, cost=10)

        client = login_as_user(app)
        r = client.post("/api/v1/unlocks", json={"target": 1, "type": "hints"})
        assert r.status_code == 400
        assert (
            r.get_json()["errors"]["score"]
            == "You do not have enough points to unlock this hint"
        )
    destroy_ctfd(app)


def test_dynamic_challenge_is_deducted_from_its_solved_value():
    """S2: the deduction applies to dynamic challenges too"""
    # enable_plugins so the dynamic challenge class is registered (SAFE_MODE off)
    app = create_ctfd(enable_plugins=True)
    with app.app_context():
        set_config("hint_cost_behavior", "at_solve")
        register_user(app)
        chal = DynamicChallenge(
            name="chal_name",
            description="chal_description",
            value=1000,
            category="chal_category",
            type="dynamic",
            state="visible",
            initial=1000,
            minimum=100,
            decay=10,
            function="linear",
        )
        app.db.session.add(chal)
        app.db.session.commit()
        chal_id = chal.id
        gen_flag(app.db, challenge_id=chal_id, content="flag")
        gen_hint(app.db, chal_id, cost=2)

        client = login_as_user(app)
        r = client.post("/api/v1/unlocks", json={"target": 1, "type": "hints"})
        assert r.status_code == 200

        r = solve(client, chal_id)
        assert r.get_json()["data"]["status"] == "correct"

        solved_value = Challenges.query.filter_by(id=chal_id).first().value
        assert Users.query.filter_by(id=2).first().score == solved_value - 2
    destroy_ctfd(app)


def test_team_deduction_uses_the_team_account():
    """S2: in teams mode a hint unlocked by one member discounts another's solve"""
    app = create_ctfd(user_mode="teams")
    with app.app_context():
        set_config("hint_cost_behavior", "at_solve")
        user = gen_user(app.db)
        second_user = gen_user(app.db, name="user", email="second@examplectf.com")
        team = gen_team(app.db)
        user.team_id = team.id
        second_user.team_id = team.id
        team.members.append(user)
        team.members.append(second_user)
        chal = gen_challenge(app.db, value=10)
        chal_id = chal.id
        gen_flag(app.db, challenge_id=chal_id, content="flag")
        gen_hint(app.db, chal_id, content="hint", cost=2, type="standard")
        app.db.session.commit()

        with login_as_user(app, name="user_name") as client:
            r = client.post("/api/v1/unlocks", json={"target": 1, "type": "hints"})
            assert r.status_code == 200

        with login_as_user(app, name="user") as second_client:
            r = solve(second_client, chal_id)
            assert r.get_json()["data"]["status"] == "correct"

        standings = get_standings()
        assert standings[0].name == "team_name"
        assert standings[0].score == 8
    destroy_ctfd(app)


def test_solving_twice_does_not_duplicate_the_deduction():
    """The already_solved path must not charge the hints a second time"""
    app = create_ctfd()
    with app.app_context():
        set_config("hint_cost_behavior", "at_solve")
        register_user(app)
        chal = gen_challenge(app.db, value=10)
        chal_id = chal.id
        gen_flag(app.db, challenge_id=chal_id, content="flag")
        gen_hint(app.db, chal_id, cost=2)

        client = login_as_user(app)
        client.post("/api/v1/unlocks", json={"target": 1, "type": "hints"})

        r = solve(client, chal_id)
        assert r.get_json()["data"]["status"] == "correct"
        r = solve(client, chal_id)
        assert r.get_json()["data"]["status"] == "already_solved"

        assert Awards.query.filter_by(category="hint_deduction").count() == 1
        assert Users.query.filter_by(id=2).first().score == 8
    destroy_ctfd(app)


def test_hint_override_charges_at_unlock_while_instance_is_at_solve():
    """S8: a single hint can opt out of the instance default"""
    app = create_ctfd()
    with app.app_context():
        set_config("hint_cost_behavior", "at_solve")
        register_user(app)
        chal = gen_challenge(app.db, value=10)
        chal_id = chal.id
        gen_flag(app.db, challenge_id=chal_id, content="flag")
        gen_hint(app.db, chal_id, cost=10, cost_behavior="at_unlock")
        gen_award(app.db, user_id=2, value=15)

        client = login_as_user(app)
        assert Users.query.filter_by(id=2).first().score == 15

        r = client.post("/api/v1/unlocks", json={"target": 1, "type": "hints"})
        assert r.status_code == 200
        assert Users.query.filter_by(id=2).first().score == 5

        r = solve(client, chal_id)
        assert r.get_json()["data"]["status"] == "correct"
        # Nothing else is deducted at solve time
        assert Users.query.filter_by(id=2).first().score == 15
    destroy_ctfd(app)


def test_hint_override_charges_at_solve_while_instance_is_at_unlock():
    """S8: a hint can opt into the solve-time charge on an at_unlock instance"""
    app = create_ctfd()
    with app.app_context():
        set_config("hint_cost_behavior", "at_unlock")
        register_user(app)
        chal = gen_challenge(app.db, value=10)
        chal_id = chal.id
        gen_flag(app.db, challenge_id=chal_id, content="flag")
        gen_hint(app.db, chal_id, cost=2, cost_behavior="at_solve")

        client = login_as_user(app)
        # The points gate only applies to hints charged at unlock
        assert Users.query.filter_by(id=2).first().score == 0
        r = client.post("/api/v1/unlocks", json={"target": 1, "type": "hints"})
        assert r.status_code == 200
        assert Users.query.filter_by(id=2).first().score == 0

        r = solve(client, chal_id)
        assert r.get_json()["data"]["status"] == "correct"
        assert Users.query.filter_by(id=2).first().score == 8
    destroy_ctfd(app)


def test_hint_without_behavior_inherits_the_instance_setting():
    """S8: no explicit behaviour means the instance setting decides"""
    app = create_ctfd()
    with app.app_context():
        set_config("hint_cost_behavior", "at_unlock")
        register_user(app)
        chal = gen_challenge(app.db, value=10)
        chal_id = chal.id
        gen_flag(app.db, challenge_id=chal_id, content="flag")
        gen_hint(app.db, chal_id, cost=4)
        gen_award(app.db, user_id=2, value=10)

        client = login_as_user(app)
        r = client.post("/api/v1/unlocks", json={"target": 1, "type": "hints"})
        assert r.status_code == 200
        # Inherited at_unlock: charged immediately
        assert Users.query.filter_by(id=2).first().score == 6

        r = solve(client, chal_id)
        assert r.get_json()["data"]["status"] == "correct"
        assert Users.query.filter_by(id=2).first().score == 16
    destroy_ctfd(app)


def test_challenge_with_mixed_behaviors_deducts_only_the_at_solve_hints():
    """S9: both behaviours on one challenge coexist without double charging"""
    app = create_ctfd()
    with app.app_context():
        set_config("hint_cost_behavior", "at_solve")
        register_user(app)
        chal = gen_challenge(app.db, value=10)
        chal_id = chal.id
        gen_flag(app.db, challenge_id=chal_id, content="flag")
        gen_hint(app.db, chal_id, cost=4, cost_behavior="at_unlock")
        gen_hint(app.db, chal_id, cost=2, cost_behavior="at_solve")
        gen_award(app.db, user_id=2, value=10)

        client = login_as_user(app)
        assert Users.query.filter_by(id=2).first().score == 10

        # The at_unlock hint is charged now, the at_solve one is not
        assert (
            client.post(
                "/api/v1/unlocks", json={"target": 1, "type": "hints"}
            ).status_code
            == 200
        )
        assert Users.query.filter_by(id=2).first().score == 6
        assert (
            client.post(
                "/api/v1/unlocks", json={"target": 2, "type": "hints"}
            ).status_code
            == 200
        )
        assert Users.query.filter_by(id=2).first().score == 6

        r = solve(client, chal_id)
        assert r.get_json()["data"]["status"] == "correct"
        # Only the at_solve hint is deducted from the challenge value
        assert Users.query.filter_by(id=2).first().score == 14
    destroy_ctfd(app)
