"""Pure validation tests for project readiness policy normalization."""
from services.commissioning_readiness_policy import DEFAULT_READINESS_POLICY, normalize_readiness_policy


def test_mc_task_types_default_to_no_task_gating():
    policy, errors = normalize_readiness_policy(None)
    assert errors == []
    assert policy["mc_required_task_types"] == []
    assert DEFAULT_READINESS_POLICY["mc_required_task_types"] == []


def test_valid_mc_task_types_are_deduplicated_and_sorted():
    policy, errors = normalize_readiness_policy({"mc_required_task_types": ["STS", "CCK", "CCK"]})
    assert errors == []
    assert policy["mc_required_task_types"] == ["CCK", "STS"]


def test_unknown_mc_task_type_is_reported_and_fails_validation():
    _, errors = normalize_readiness_policy({"mc_required_task_types": ["NOT_A_TASK"]})
    assert errors == ["Invalid MC task types"]


def test_mc_task_types_must_be_a_list_of_strings():
    _, errors = normalize_readiness_policy({"mc_required_task_types": "CCK"})
    assert errors == ["Invalid MC task types"]
    _, errors = normalize_readiness_policy({"mc_required_task_types": [1]})
    assert errors == ["Invalid MC task types"]


def test_mechanical_check_sheet_types_are_accepted_for_gates():
    policy, errors = normalize_readiness_policy({
        "required_check_sheet_types": {"MC": ["PRE_COMM_A", "HYDROTEST", "LEAK_TEST"]},
    })
    assert errors == []
    assert policy["required_check_sheet_types"]["MC"] == ["HYDROTEST", "LEAK_TEST", "PRE_COMM_A"]


def test_mc_blocking_equipment_statuses_default_and_normalization():
    policy, errors = normalize_readiness_policy(None)
    assert errors == []
    assert policy["mc_blocking_equipment_statuses"] == ["NOT_INSTALLED", "PLANNED"]

    policy, errors = normalize_readiness_policy({"mc_blocking_equipment_statuses": ["PLANNED", " PLANNED "]})
    assert errors == []
    assert policy["mc_blocking_equipment_statuses"] == ["PLANNED"]


def test_invalid_mc_blocking_equipment_statuses_are_reported():
    _, errors = normalize_readiness_policy({"mc_blocking_equipment_statuses": [""]})
    assert errors == ["Invalid MC blocking equipment statuses"]
    _, errors = normalize_readiness_policy({"mc_blocking_equipment_statuses": ["X" * 31]})
    assert errors == ["Invalid MC blocking equipment statuses"]


def test_presence_required_gates_must_be_known_gates():
    _, errors = normalize_readiness_policy({"presence_required_gates": ["MC", "NOPE"]})
    assert errors == ["Invalid presence-required gates"]
