#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Hint charges must disappear together with what paid for them.

Deleting a solve or a challenge removes the points that paid for the hints, so the
charges tied to them have to go with it or the account keeps a permanent penalty.
"""

from CTFd.models import Awards, Solves, Users
from CTFd.utils import set_config
from tests.helpers import (
    create_ctfd,
    destroy_ctfd,
    gen_award,
    gen_challenge,
    gen_flag,
    gen_hint,
    login_as_user,
    register_user,
)


def solve(client, challenge_id, submission="flag"):
    return client.post(
        "/api/v1/challenges/attempt",
        json={"challenge_id": challenge_id, "submission": submission},
    )


def test_deleting_a_solve_removes_the_hint_deduction():
    """A removed solve must not leave a permanent hint penalty behind"""
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
        assert Users.query.filter_by(id=2).first().score == 8
        assert Awards.query.filter_by(category="hint_deduction").count() == 1

        solve_id = Solves.query.filter_by(challenge_id=chal_id, user_id=2).first().id

        with login_as_user(app, "admin") as admin:
            probe = admin.get("/api/v1/submissions")
            assert probe.status_code == 200, ("admin probe", probe.status_code)
            r = admin.delete("/api/v1/submissions/{}".format(solve_id), json="")
            assert r.status_code == 200, r.get_json()

        # The challenge value is gone, and so is the hint cost charged against it
        assert Users.query.filter_by(id=2).first().score == 0
        assert Awards.query.filter_by(category="hint_deduction").count() == 0
    destroy_ctfd(app)


def test_deleting_a_challenge_removes_its_solve_time_charges():
    """Deleting a challenge must not leave the deduction behind"""
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
        solve(client, chal_id)
        assert Users.query.filter_by(id=2).first().score == 8
        assert Awards.query.filter_by(challenge_id=chal_id).count() == 1

        with login_as_user(app, "admin") as admin:
            r = admin.delete("/api/v1/challenges/{}".format(chal_id), json="")
            assert r.status_code == 200, r.get_json()

        assert Awards.query.filter_by(challenge_id=chal_id).count() == 0
        assert Users.query.filter_by(id=2).first().score == 0
    destroy_ctfd(app)


def test_deleting_a_challenge_removes_its_unlock_time_charges():
    """The charge paid at unlock time is tied to the challenge as well"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        chal = gen_challenge(app.db, value=10)
        chal_id = chal.id
        gen_hint(app.db, chal_id, cost=4)
        gen_award(app.db, user_id=2, value=10)

        client = login_as_user(app)
        r = client.post("/api/v1/unlocks", json={"target": 1, "type": "hints"})
        assert r.status_code == 200
        assert Users.query.filter_by(id=2).first().score == 6
        assert Awards.query.filter_by(challenge_id=chal_id).count() == 1

        with login_as_user(app, "admin") as admin:
            r = admin.delete("/api/v1/challenges/{}".format(chal_id), json="")
            assert r.status_code == 200, r.get_json()

        assert Awards.query.filter_by(challenge_id=chal_id).count() == 0
        # Only the fixture award is left
        assert Users.query.filter_by(id=2).first().score == 10
    destroy_ctfd(app)
