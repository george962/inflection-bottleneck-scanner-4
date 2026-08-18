from inflection_scanner.build_info import source_hash


def test_source_hash_is_stable_for_same_tree():
    assert source_hash()==source_hash()
    assert len(source_hash())==16
