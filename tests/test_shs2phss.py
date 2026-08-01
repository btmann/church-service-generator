from shs2phss import shs2phss


def test_all_keys_are_numeric_strings():
    assert all(key.isdigit() for key in shs2phss.keys())


def test_all_values_are_ints():
    assert all(isinstance(value, int) for value in shs2phss.values())


def test_known_mapping():
    # song 1 in the Sumphonia Hymn Supplement maps to phss 74.
    assert shs2phss["1"] == 74


def test_missing_song_sentinel():
    # Entry 34 ("For You Have Promised") has no PHSS equivalent and is
    # marked with the -1 sentinel rather than being omitted.
    assert shs2phss["34"] == -1


def test_no_duplicate_targets_besides_sentinel():
    targets = [v for v in shs2phss.values() if v != -1]
    assert len(targets) == len(set(targets)), "two SHS songs map to the same PHSS number"
