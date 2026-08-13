"""Drop-in audio matching (M7).

The person using this is copying files into ``audio/`` minutes before a pitch,
so the matcher has to be forgiving about naming -- and the route that serves
what it finds has to be unforgiving about paths.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from app.catalog import audio  # noqa: E402
from app.contracts import Track  # noqa: E402


def track(track_id, title, artist):
    return Track(id=track_id, title=title, artist=artist)


@pytest.fixture()
def tracks():
    return [
        track("trk_patiala_dd", "Patiala Peg", "Diljit Dosanjh"),
        track("trk_lover_dd", "Lover", "Diljit Dosanjh"),
        track("trk_loverboy_xx", "Lover Boy", "Shubh"),
        track("trk_fall_da", "Fall", "Davido"),
    ]


def drop(directory, *names):
    for name in names:
        (directory / name).write_bytes(b"\x00\x01")
    return directory


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


def test_no_audio_directory_is_not_an_error(tracks, tmp_path):
    assert audio.discover(tracks, tmp_path / "does-not-exist") == {}
    assert audio.attach(tracks, tmp_path / "nope") == 0
    assert all(t.audio_file is None for t in tracks)


def test_empty_directory_matches_nothing(tracks, tmp_path):
    assert audio.discover(tracks, tmp_path) == {}


def test_exact_track_id_filename_wins(tracks, tmp_path):
    drop(tmp_path, "trk_patiala_dd.mp3")
    assert audio.discover(tracks, tmp_path) == {"trk_patiala_dd": "trk_patiala_dd.mp3"}


@pytest.mark.parametrize(
    "filename",
    [
        "Patiala Peg - Diljit Dosanjh.mp3",
        "Diljit Dosanjh - Patiala Peg.m4a",
        "01 - Patiala Peg (Official Video).mp3",
        "patiala_peg.wav",
        "PATIALA PEG.flac",
    ],
)
def test_forgiving_about_real_world_filenames(tracks, tmp_path, filename):
    drop(tmp_path, filename)
    assert audio.discover(tracks, tmp_path) == {"trk_patiala_dd": filename}


def test_partial_title_does_not_steal_a_longer_title(tracks, tmp_path):
    """"Lover" must not claim a file that clearly says "Lover Boy"."""
    drop(tmp_path, "Lover Boy - Shubh.mp3")
    assert audio.discover(tracks, tmp_path) == {"trk_loverboy_xx": "Lover Boy - Shubh.mp3"}


def test_artist_in_the_name_breaks_a_title_tie(tracks, tmp_path):
    drop(tmp_path, "Lover - Diljit Dosanjh.mp3")
    mapping = audio.discover(tracks, tmp_path)
    assert mapping.get("trk_lover_dd") == "Lover - Diljit Dosanjh.mp3"


def test_each_file_claims_at_most_one_track(tracks, tmp_path):
    drop(tmp_path, "Fall - Davido.mp3", "trk_patiala_dd.mp3")
    mapping = audio.discover(tracks, tmp_path)
    assert sorted(mapping) == ["trk_fall_da", "trk_patiala_dd"]
    assert len(set(mapping.values())) == 2


def test_unrelated_and_hidden_files_are_ignored(tracks, tmp_path):
    drop(tmp_path, "something-nobody-requested.mp3", ".DS_Store.mp3", "notes.txt")
    assert audio.discover(tracks, tmp_path) == {}


def test_attach_populates_audio_file_in_place(tracks, tmp_path):
    drop(tmp_path, "trk_fall_da.mp3")
    assert audio.attach(tracks, tmp_path) == 1
    by_id = {t.id: t for t in tracks}
    assert by_id["trk_fall_da"].audio_file == "trk_fall_da.mp3"
    assert by_id["trk_lover_dd"].audio_file is None


def test_matching_is_stable_across_runs(tracks, tmp_path):
    drop(tmp_path, "Lover - Diljit Dosanjh.mp3", "Lover Boy - Shubh.mp3", "Fall.mp3")
    first = audio.discover(tracks, tmp_path)
    assert first == audio.discover(tracks, tmp_path)


# ---------------------------------------------------------------------------
# Serving -- the route hands user input straight to resolve()
# ---------------------------------------------------------------------------


def test_resolve_finds_a_real_file(tmp_path):
    drop(tmp_path, "trk_fall_da.mp3")
    resolved = audio.resolve("trk_fall_da.mp3", tmp_path)
    assert resolved is not None and resolved.name == "trk_fall_da.mp3"


@pytest.mark.parametrize(
    "hostile",
    [
        "../../../../etc/passwd",
        "../secret.mp3",
        "/etc/passwd",
        "..%2F..%2Fsecret.mp3",
        "",
        "   ",
        ".hidden.mp3",
        "notes.txt",
        "missing.mp3",
    ],
)
def test_resolve_refuses_anything_outside_the_audio_dir(tmp_path, hostile):
    drop(tmp_path, "trk_fall_da.mp3")
    (tmp_path.parent / "secret.mp3").write_bytes(b"\x00")
    assert audio.resolve(hostile, tmp_path) is None


def test_resolve_ignores_directory_components_in_a_valid_name(tmp_path):
    """A basename that exists is served; the directory part is discarded."""
    drop(tmp_path, "trk_fall_da.mp3")
    resolved = audio.resolve("anything/you/like/trk_fall_da.mp3", tmp_path)
    assert resolved is not None and resolved.name == "trk_fall_da.mp3"
