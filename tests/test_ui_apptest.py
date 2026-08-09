"""Full-script interaction regression tests for ui.py's Custom Template
Builder, using streamlit.testing.v1.AppTest to drive the real app instead of
extracted functions.

These bugs are not reachable via unit tests of individual functions: the
defect was in *how the whole script reruns* when a button handler calls
st.rerun() before later widgets in the script have been instantiated for
that pass. Streamlit prunes session_state for any keyed widget not seen
during a script pass, so an early st.rerun() wiped out every already-entered
Service Flow field (song numbers, leaders, verses/chorus selections) on
every Add/Remove/Move click in the Custom Template Builder.
"""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
UI_PY = ROOT / "ui.py"


def start_custom_template_with_songs(count):
    at = AppTest.from_file(str(UI_PY))
    at.run(timeout=30)
    at.selectbox(key="template_select").set_value("Custom Template (Build Order)").run()
    for _ in range(count):
        at.selectbox(key="custom_item_type_select").set_value("song").run()
        at.button(key="custom_add_item").click().run()
    return at


class TestCustomTemplateDistinctLeaders:
    """Regression for: adding several songs with different leaders collapsed
    every leader field down to whichever name was typed last."""

    def test_each_song_gets_its_own_leader_field(self):
        at = start_custom_template_with_songs(3)
        assert list(at.exception) == []

        leader_inputs = [ti for ti in at.text_input if ti.key and ti.key.startswith("leader_Song Leader")]
        assert len(leader_inputs) == 3
        assert len({ti.key for ti in leader_inputs}) == 3

        for ti, name in zip(leader_inputs, ["Alice", "Bob", "Carol"]):
            at.text_input(key=ti.key).set_value(name).run()

        final = {ti.key: at.text_input(key=ti.key).value for ti in leader_inputs}
        assert final == {
            "leader_Song Leader 1": "Alice",
            "leader_Song Leader 2": "Bob",
            "leader_Song Leader 3": "Carol",
        }


class TestCustomTemplateReorderPreservesData:
    """Regression for: moving an item up/down in the Custom Template Builder
    reset every already-entered Service Flow field back to its default."""

    def test_move_down_preserves_song_numbers(self):
        at = start_custom_template_with_songs(3)
        num_inputs = [ni for ni in at.number_input if ni.key and ni.key.startswith("song_song-")]
        for ni, val in zip(num_inputs, [12, 67, 275]):
            at.number_input(key=ni.key).set_value(val).run()

        before = {ni.key: at.number_input(key=ni.key).value for ni in num_inputs}

        at.button(key="custom_down_0").click().run()
        assert list(at.exception) == []

        after = {ni.key: at.number_input(key=ni.key).value for ni in num_inputs}
        assert after == before

        order = [item.get("id") for item in at.session_state["custom_template_items"]]
        assert order == ["song-2", "song-1", "song-3"]

    def test_add_item_preserves_existing_song_and_leader_data(self):
        at = start_custom_template_with_songs(2)
        num_inputs = [ni for ni in at.number_input if ni.key and ni.key.startswith("song_song-")]
        for ni, val in zip(num_inputs, [12, 67]):
            at.number_input(key=ni.key).set_value(val).run()
        leader_inputs = [ti for ti in at.text_input if ti.key and ti.key.startswith("leader_Song Leader")]
        for ti, name in zip(leader_inputs, ["Alice", "Bob"]):
            at.text_input(key=ti.key).set_value(name).run()

        before_nums = {ni.key: at.number_input(key=ni.key).value for ni in num_inputs}
        before_leaders = {ti.key: at.text_input(key=ti.key).value for ti in leader_inputs}

        at.selectbox(key="custom_item_type_select").set_value("song").run()
        at.button(key="custom_add_item").click().run()

        after_nums = {ni.key: at.number_input(key=ni.key).value for ni in num_inputs}
        after_leaders = {ti.key: at.text_input(key=ti.key).value for ti in leader_inputs}
        assert after_nums == before_nums
        assert after_leaders == before_leaders

    def test_remove_item_preserves_surviving_items_data(self):
        at = start_custom_template_with_songs(3)
        num_inputs = {ni.key: ni for ni in at.number_input if ni.key and ni.key.startswith("song_song-")}
        for key, val in zip(["song_song-1", "song_song-2", "song_song-3"], [12, 67, 275]):
            at.number_input(key=key).set_value(val).run()

        at.button(key="custom_remove_1").click().run()
        assert list(at.exception) == []

        order = [item.get("id") for item in at.session_state["custom_template_items"]]
        assert order == ["song-1", "song-3"]
        assert at.number_input(key="song_song-1").value == 12
        assert at.number_input(key="song_song-3").value == 275


class TestCustomTemplateVerseChorusPersistence:
    """Regression for: deselecting a verse/chorus entry, then triggering an
    unrelated rerun, silently re-selected everything again.

    Uses pftl-738, the one song sample kept tracked in git specifically for
    fixture use (see .gitignore's ehsf/ allowlist) -- it has verses 1-4.
    """

    def test_verse_deselection_survives_unrelated_rerun(self):
        at = start_custom_template_with_songs(1)
        at.number_input(key="song_song-1").set_value(738).run()
        assert list(at.exception) == []

        verses = at.multiselect(key="verses_song-1")
        assert verses.value == [1, 2, 3, 4]

        at.multiselect(key="verses_song-1").set_value([1, 2, 3]).run()
        assert at.multiselect(key="verses_song-1").value == [1, 2, 3]

        at.selectbox(key="custom_item_type_select").set_value("reading").run()
        at.button(key="custom_add_item").click().run()
        assert list(at.exception) == []

        assert at.multiselect(key="verses_song-1").value == [1, 2, 3]
