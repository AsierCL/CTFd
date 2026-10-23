#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Removing a solve must also remove the hint costs charged against it."""

from CTFd.models import Awards, Solves, Users
from tests.helpers import (
    create_ctfd,
    destroy_ctfd,
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
        assert Awards.query.filter_by(category="hints").count() == 1

        solve_id = Solves.query.filter_by(challenge_id=chal_id, user_id=2).first().id

        with login_as_user(app, "admin") as admin:
            probe = admin.get("/api/v1/submissions")
            assert probe.status_code == 200, ("admin probe", probe.status_code)
            r = admin.delete("/api/v1/submissions/{}".format(solve_id), json="")
            assert r.status_code == 200, r.get_json()

        # The challenge value is gone, and so is the hint cost charged against it
        assert Users.query.filter_by(id=2).first().score == 0
        assert Awards.query.filter_by(category="hints").count() == 0
    destroy_ctfd(app)
