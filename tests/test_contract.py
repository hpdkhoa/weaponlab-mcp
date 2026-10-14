from weaponlab import contract as C

JOB = {"contract": C.CONTRACT, "out": "rows.json",
       "weapons": [{"id": "A", "actions": [{"name": "idle", "seconds": 1.6, "at": [1.2]}]},
                   {"id": "A", "tag": "fix", "actions": [{"name": "idle"}], "tune": {"x": 1}, "support_l": [0, 25, 1]}]}


def test_a_good_job_passes():
    assert C.check_job(JOB) == []


def test_a_job_without_contract_field_is_version_1():
    job = dict(JOB)
    job.pop("contract")
    assert C.check_job(job) == []


def test_bad_jobs_are_named():
    assert any("out" in b for b in C.check_job({"weapons": []}))
    assert any("actions" in b for b in C.check_job({"out": "o", "weapons": [{"id": "A", "actions": []}]}))
    assert any("support_l" in b for b in C.check_job({"out": "o", "weapons": [{"id": "A", "actions": [{"name": "idle"}], "support_l": [1, 2]}]}))
    assert any("slomo" in b for b in C.check_job({"out": "o", "weapons": [], "slomo": 2}))
    assert any("contract" in b for b in C.check_job({"contract": "other/9", "out": "o", "weapons": []}))


def test_rows_follow_the_job():
    rows = {"rows": [{"weapon": "A", "action": "idle", "metric": "hands.l_gap_cm", "value": 0.2},
                     {"weapon": "A@fix", "action": "idle", "metric": "hands.l_gap_cm", "value": None},
                     {"weapon": "_probe", "action": "-", "metric": "note", "value": None, "note": "hi"}], "notes": ["ok"]}
    assert C.check_rows(rows, JOB) == []


def test_a_tagged_row_under_the_plain_id_is_caught():
    # the ToangTown probe wrote a tagged entry's view rows under the plain id (found by this check, 2026-10-14)
    job = {"out": "o", "weapons": [{"id": "A", "tag": "t", "actions": [{"name": "idle"}]}]}
    bad = C.check_rows({"rows": [{"weapon": "A", "action": "idle", "metric": "view.cover_total", "value": 0.1}]}, job)
    assert bad and "not in the job" in bad[0]


def test_bad_rows_are_named():
    bad = C.check_rows({"rows": [{"weapon": "A", "action": "idle", "metric": "gap", "value": float("nan")},
                                 {"weapon": "A", "action": "idle", "metric": "x.y", "value": 1},
                                 {"weapon": "A", "action": "idle", "metric": "x.y", "value": 2}]})
    text = " ".join(bad)
    assert "finite" in text and "<group>.<name>" in text and "twice" in text


def test_parts(tmp_path):
    p = tmp_path / "d.obj"
    p.write_text("# eye 1 2 3\n# hold rig X\ng gun|G|/a|-\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\ng arms|A|/b|hand_r\nv 0 0 1\nv 1 0 1\nv 0 1 1\nf 4 5 6\n")
    assert C.check_parts(p) == []
    d = C.read_parts(p)
    assert d["eye"] == [1.0, 2.0, 3.0] and d["header"]["hold"] == ["rig", "X"]
    assert d["groups"][("arms", "A", "/b", "hand_r")]["tris"] == [[0, 1, 2]]
    q = tmp_path / "e.obj"
    q.write_text("g arms|A|/b|hand_r\nv 0 0 1\nv 1 0 1\nv 0 1 1\nf 1 2 3\n")
    assert any("'gun'" in b for b in C.check_parts(q))
