from datatidy.schema import OP_DOCS, PARAM_MODELS, move_dedupe_last, validate_plan

COLS = ["price", "city", "date"]


def step(op, column=None, params=None, reason="evidence from profile"):
    return {"op": op, "column": column, "params": params or {}, "reason": reason}


def test_every_operation_is_documented_and_implemented():
    from datatidy.operations import OPERATIONS
    assert set(PARAM_MODELS) == set(OPERATIONS) == set(OP_DOCS)


def test_valid_plan_passes_and_normalises_params():
    r = validate_plan([step("fill_missing", "price", {"strategy": "median"}), step("drop_duplicates")], COLS)
    assert r.ok and r.steps[0]["params"] == {"strategy": "median"}


def test_collects_all_errors_not_just_first():
    plan = [
        step("make_pretty", "price"),                              # unknown op
        step("fill_missing", "nope", {"strategy": "mean"}),        # unknown column
        step("fill_missing", "price", {"strategy": "constant"}),   # constant w/o value
        step("fill_missing", "price", {"bogus": 1}),               # unknown param
        step("drop_duplicates", "price"),                          # takes no column
        {"op": "cast_type", "column": "price", "params": {"target": "float"}},   # no reason
        "not a dict",
    ]
    r = validate_plan(plan, COLS)
    assert not r.ok and len(r.errors) == 7


def test_non_list_plan_rejected():
    assert not validate_plan({"op": "x"}, COLS).ok


def test_empty_plan_is_valid_with_warning():
    r = validate_plan([], COLS)
    assert r.ok and r.warnings


def test_column_tracking_through_rename_and_drop():
    plan = [step("rename_column", "price", {"new_name": "cost"}),
            step("fill_missing", "cost", {"strategy": "median"}),    # uses new name: OK
            step("drop_column", "city"),
            step("normalise_text", "city")]                          # dropped: error
    r = validate_plan(plan, COLS)
    assert len(r.errors) == 1 and "city" in r.errors[0]
    r2 = validate_plan([step("rename_column", "price", {"new_name": "cost"}), step("fill_missing", "price")], COLS)
    assert not r2.ok                                                  # old name is gone


def test_params_range_checks():
    assert not validate_plan([step("drop_missing_rows", None, {"threshold": 1.5})], COLS).ok
    assert not validate_plan([step("cast_type", "price", {"target": "datetime"})], COLS).ok
    assert validate_plan([step("drop_missing_rows", None, {"threshold": 0.5})], COLS).ok


def test_move_dedupe_last():
    steps = [step("drop_duplicates"), step("normalise_text", "city")]
    new, changed = move_dedupe_last(steps)
    assert changed and new[-1]["op"] == "drop_duplicates"
    assert move_dedupe_last(new)[1] is False
