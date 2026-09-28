from smart_repository_integrity import validate_repository


def test_repository_integrity_contract() -> None:
    evidence = validate_repository()
    assert evidence["status"] == "PASS"
    assert evidence["portable_identity"] is True
    assert evidence["epoch"]["status"] == "FROZEN"
    assert evidence["epoch"]["target_contest"] > evidence["epoch"]["cutoff_contest"]
