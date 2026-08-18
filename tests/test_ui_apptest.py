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


def start_normal_template(template_name="wednesday", song_number=738):
    """wednesday is the smallest normal template (3 songs), keeping this fast."""
    at = AppTest.from_file(str(UI_PY))
    at.run(timeout=30)
    at.selectbox(key="template_select").set_value(template_name).run()
    song_inputs = [ni for ni in at.number_input if ni.key and ni.key.startswith("song_song-")]
    for ni in song_inputs:
        at.number_input(key=ni.key).set_value(song_number).run()
    return at


def _generate_button(at):
    return [b for b in at.button if "Generate" in (b.label or "")][0]


def _cleanup_generated_files(pptx_path):
    """Remove exactly what create_worship_files/generate_presentation wrote
    for one test run, without touching any sibling date folders."""
    pptx_path = Path(pptx_path)
    json_path = pptx_path.with_suffix(".json")
    for f in (pptx_path, json_path):
        if f.exists():
            f.unlink()

    date_str, time_str = pptx_path.stem.split("-")
    specs_leaf = ROOT / "worship" / "specs" / date_str[0:4] / date_str[4:6] / date_str[6:8] / time_str
    if specs_leaf.is_dir():
        for f in specs_leaf.iterdir():
            f.unlink()
        specs_leaf.rmdir()


class TestSongLeaderRequiredField:
    """Regression: on normal (non-custom) templates, the Song Leader field
    could be left blank and the presentation would still generate with no
    leader name anywhere -- it's now required before Generate is enabled.
    Custom templates give every song its own distinct leader field instead
    (see TestCustomTemplateDistinctLeaders), so this requirement is specific
    to the single shared "Song Leader" position on normal templates.
    """

    def test_generate_disabled_until_leader_is_filled(self):
        at = start_normal_template()
        assert _generate_button(at).disabled is True

        at.text_input(key="leader_Song Leader").set_value("Alice").run()
        assert _generate_button(at).disabled is False

    def test_whitespace_only_leader_still_counts_as_missing(self):
        at = start_normal_template()
        at.text_input(key="leader_Song Leader").set_value("   ").run()
        assert _generate_button(at).disabled is True

    def test_custom_template_does_not_require_a_leader(self):
        at = start_custom_template_with_songs(1)
        at.number_input(key="song_song-1").set_value(738).run()
        assert _generate_button(at).disabled is False


class TestWelcomeSlideLeaderNotes:
    """Regression: slides.py's add_welcome() has always written the Song
    Leader's name into the welcome slide's speaker notes when the worship
    spec has a top-level 'leader' key -- but ui.py's own from-scratch spec
    builder (a duplicate of worship.py's generate_json) never set that key,
    so the notes were silently never populated when generating through the
    app, even though the underlying slides.py feature worked.
    """

    def test_generated_welcome_slide_notes_include_leader_name(self):
        at = start_normal_template()
        at.text_input(key="leader_Song Leader").set_value("Alice Test Leader").run()
        assert _generate_button(at).disabled is False

        at.button(key=_generate_button(at).key).click().run(timeout=60)
        assert list(at.exception) == []

        pptx_path = at.session_state["generated_files"]["pptx_path"]
        try:
            from pptx import Presentation
            prs = Presentation(pptx_path)
            notes = prs.slides[0].notes_slide.notes_text_frame.text
            assert notes == "Song Leader: Alice Test Leader"
        finally:
            _cleanup_generated_files(pptx_path)
