from datetime import datetime
from pathlib import Path

import pytest
from libtc import TorrentData, TorrentFile, TorrentState

from .fixtures import *
from .fixtures import client as client2
from .fixtures import client as client3


def test_scan_ls_client(tmp_path, indexer, matcher, client):
    infohash = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
    name = "test torrent 1"
    download_path = tmp_path / "test torrent 1"
    files = []
    size = 0
    seeded_files = [("file1", 400, True), ("file2", 600, True), ("file3", 100, False)]
    for fn, fsize, add_to_files in seeded_files:
        fp = download_path / Path(fn)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_bytes(b"a" * fsize)
        if add_to_files:
            size += fsize
            files.append(TorrentFile(fn, fsize, 100))

    client._inject_torrent(
        TorrentData(
            infohash,
            name,
            size,
            TorrentState.ACTIVE,
            100,
            1000,
            datetime(2020, 1, 1, 1, 1),
            "example.com",
            0,
            0,
            None,
        ),
        files,
        download_path,
    )
    indexer.scan_clients({"test_client": client}, full_scan=False, fast_scan=False)

    not_seeded_file = tmp_path / "not_seeded.bin"
    not_seeded_file.write_bytes(b"a" * 60)

    map_result = matcher.map_path_to_clients(download_path)
    assert map_result.total_size == 1100
    assert map_result.seeded_size == 1000
    assert len(map_result.files) == 3

    expected_files = {sf[0]: sf[1:] for sf in seeded_files}
    for f, mf in map_result.files.items():
        expected_file = expected_files.pop(f.name)
        assert expected_file[0] == mf.size
        if expected_file[1]:
            assert len(mf.clients) == 1
            assert mf.clients[0][0] == "test_client"
            assert mf.clients[0][1] == infohash
        else:
            assert not mf.clients


def test_new_download_path_fast_scan(tmp_path, indexer, matcher, client):
    infohash = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
    name = "test torrent 1"
    download_path = tmp_path / "test torrent 1"
    files = []
    size = 0
    seeded_files = [("file1", 400, True), ("file2", 600, True)]
    for fn, fsize, add_to_files in seeded_files:
        fp = download_path / Path(fn)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_bytes(b"a" * fsize)
        if add_to_files:
            size += fsize
            files.append(TorrentFile(fn, fsize, 100))

    client._inject_torrent(
        TorrentData(
            infohash,
            name,
            size,
            TorrentState.ACTIVE,
            100,
            1000,
            datetime(2020, 1, 1, 1, 1),
            "example.com",
            0,
            0,
            None,
        ),
        files,
        download_path,
    )
    indexer.scan_clients({"test_client": client}, full_scan=False, fast_scan=True)

    map_result = matcher.map_path_to_clients(download_path)
    assert map_result.seeded_size == 1000

    new_download_path = tmp_path / "test torrent 2"
    download_path.rename(new_download_path)
    download_path.mkdir()

    map_result = matcher.map_path_to_clients(download_path)
    assert map_result.seeded_size == 0

    map_result = matcher.map_path_to_clients(new_download_path)
    assert map_result.seeded_size == 0
    assert map_result.total_size == 1000

    map_result = matcher.map_path_to_clients(new_download_path)
    assert map_result.seeded_size == 0
    assert map_result.total_size == 1000

    client._inject_torrent(
        TorrentData(
            infohash,
            name,
            size,
            TorrentState.ACTIVE,
            100,
            1000,
            datetime(2020, 1, 1, 1, 1),
            "example.com",
            0,
            0,
            None,
        ),
        files,
        new_download_path,
    )

    indexer.scan_clients({"test_client": client}, full_scan=False, fast_scan=True)

    map_result = matcher.map_path_to_clients(new_download_path)
    assert map_result.seeded_size == 0
    assert map_result.total_size == 1000

    indexer.scan_clients({"test_client": client}, full_scan=False, fast_scan=False)

    map_result = matcher.map_path_to_clients(new_download_path)
    assert map_result.seeded_size == 1000
    assert map_result.total_size == 1000


def test_multiple_clients(tmp_path, indexer, matcher, client, client2):
    infohash_1 = "1a39a3ee5e6b4b0d3255bfef95601890afd80709"
    infohash_2 = "2a39a3ee5e6b4b0d3255bfef95601890afd80709"
    infohash_3_1 = "3a39a3ee5e6b4b0d3255bfef95601890afd80709"
    infohash_3_2 = "3b39a3ee5e6b4b0d3255bfef95601890afd80709"
    files_1, files_2, files_3 = [], [], []
    name_1 = "test torrent 1"
    name_2 = "test torrent 2"
    name_3 = "test torrent 3"
    download_path_1 = tmp_path / "torrent 1"
    download_path_2 = tmp_path / "torrent 2"
    download_path_3 = tmp_path / "torrent 3"

    download_path_1.mkdir()
    file_1 = download_path_1 / "file 1.bin"
    file_1.write_bytes(b"a" * 100)
    client._inject_torrent(
        TorrentData(
            infohash_1,
            name_2,
            100,
            TorrentState.ACTIVE,
            100,
            1000,
            datetime(2020, 1, 1, 1, 1),
            "example.com",
            0,
            0,
            None,
        ),
        [TorrentFile("file 1.bin", 100, 100)],
        download_path_1,
    )

    download_path_2.mkdir()
    file_2 = download_path_2 / "file 1.bin"
    file_2.write_bytes(b"a" * 200)
    client2._inject_torrent(
        TorrentData(
            infohash_2,
            name_2,
            200,
            TorrentState.ACTIVE,
            100,
            1000,
            datetime(2020, 1, 1, 1, 1),
            "example.com",
            0,
            0,
            None,
        ),
        [TorrentFile("file 1.bin", 200, 100)],
        download_path_2,
    )

    download_path_3.mkdir()
    file_3 = download_path_3 / "file 1.bin"
    file_3.write_bytes(b"a" * 300)
    client._inject_torrent(
        TorrentData(
            infohash_3_1,
            name_3,
            300,
            TorrentState.ACTIVE,
            100,
            1000,
            datetime(2020, 1, 1, 1, 1),
            "example.com",
            0,
            0,
            None,
        ),
        [TorrentFile("file 1.bin", 300, 100)],
        download_path_3,
    )
    client2._inject_torrent(
        TorrentData(
            infohash_3_2,
            name_3,
            300,
            TorrentState.ACTIVE,
            100,
            1000,
            datetime(2020, 1, 1, 1, 1),
            "example.com",
            0,
            0,
            None,
        ),
        [TorrentFile("file 1.bin", 300, 100)],
        download_path_3,
    )

    clients = {
        "client1": client,
        "client2": client2,
    }
    indexer.scan_clients(clients)
    indexer.scan_clients({"client1": client}, full_scan=True)

    map_result = matcher.map_path_to_clients(download_path_1)
    assert map_result.seeded_size == 100
    assert len(map_result.files) == 1
    assert list(map_result.files.keys())[0].name == "file 1.bin"
    assert len(list(map_result.files.values())[0].clients) == 1
    assert list(map_result.files.values())[0].clients[0] == ("client1", infohash_1)

    map_result = matcher.map_path_to_clients(download_path_2)
    assert map_result.seeded_size == 200
    assert len(map_result.files) == 1
    assert list(map_result.files.keys())[0].name == "file 1.bin"
    assert len(list(map_result.files.values())[0].clients) == 1
    assert list(map_result.files.values())[0].clients[0] == ("client2", infohash_2)

    map_result = matcher.map_path_to_clients(download_path_3)
    assert map_result.seeded_size == 300
    assert len(map_result.files) == 1
    assert list(map_result.files.keys())[0].name == "file 1.bin"
    assert len(list(map_result.files.values())[0].clients) == 2
    assert sorted(list(map_result.files.values())[0].clients) == sorted(
        [("client1", infohash_3_1), ("client2", infohash_3_2)]
    )


def test_symlink(tmp_path, indexer, matcher, client, client2, client3):
    infohash = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
    name = "test torrent 1"
    download_path = tmp_path / "test torrent 1"
    files = []
    size = 0
    seeded_files = [("file1", 400, True), ("file2", 600, True)]
    for fn, fsize, add_to_files in seeded_files:
        fp = download_path / Path(fn)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_bytes(b"a" * fsize)
        if add_to_files:
            size += fsize
            files.append(TorrentFile(fn, fsize, 100))

    client._inject_torrent(
        TorrentData(
            infohash,
            name,
            size,
            TorrentState.ACTIVE,
            100,
            1000,
            datetime(2020, 1, 1, 1, 1),
            "example.com",
            0,
            0,
            None,
        ),
        files,
        download_path,
    )

    download_path_symlink = tmp_path / "test torrent 2"
    download_path_symlink.symlink_to(download_path)

    download_path_symlink_files = tmp_path / "test torrent 3"
    download_path_symlink_files.mkdir()
    (download_path_symlink_files / "file1").symlink_to(download_path_symlink / "file1")
    (download_path_symlink_files / "file2").symlink_to(download_path_symlink / "file2")
    indexer.scan_clients({"test_client": client}, full_scan=False, fast_scan=False)

    map_result = matcher.map_path_to_clients(download_path)
    assert map_result.seeded_size == 1000
    assert len(map_result.files) == 2
    for mf in map_result.files.values():
        assert len(mf.clients) == 1

    map_result = matcher.map_path_to_clients(download_path_symlink)
    assert map_result.seeded_size == 0
    assert map_result.total_size == 1000
    assert len(map_result.files) == 2
    for f, mf in map_result.files.items():
        assert len(mf.clients) == 0

    map_result = matcher.map_path_to_clients(download_path_symlink_files)
    assert map_result.seeded_size == 0
    assert map_result.total_size == 1000
    assert len(map_result.files) == 2
    for f, mf in map_result.files.items():
        assert len(mf.clients) == 0

    client2._inject_torrent(
        TorrentData(
            infohash,
            name,
            size,
            TorrentState.ACTIVE,
            100,
            1000,
            datetime(2020, 1, 1, 1, 1),
            "example.com",
            0,
            0,
            None,
        ),
        files,
        download_path_symlink,
    )

    client3._inject_torrent(
        TorrentData(
            infohash,
            name,
            size,
            TorrentState.ACTIVE,
            100,
            1000,
            datetime(2020, 1, 1, 1, 1),
            "example.com",
            0,
            0,
            None,
        ),
        files,
        download_path_symlink_files,
    )

    indexer.scan_clients({"test_client2": client2, "test_client3": client3}, full_scan=False, fast_scan=False)

    map_result = matcher.map_path_to_clients(download_path)
    assert map_result.seeded_size == 1000
    assert len(map_result.files) == 2
    for mf in map_result.files.values():
        assert sorted(mf.clients) == sorted(
            [
                ("test_client", "da39a3ee5e6b4b0d3255bfef95601890afd80709"),
                ("test_client2", "da39a3ee5e6b4b0d3255bfef95601890afd80709"),
                ("test_client3", "da39a3ee5e6b4b0d3255bfef95601890afd80709"),
            ]
        )
        assert len(mf.clients) == 3

    map_result = matcher.map_path_to_clients(download_path_symlink)
    assert map_result.seeded_size == 1000
    assert map_result.total_size == 1000
    assert len(map_result.files) == 2
    for f, mf in map_result.files.items():
        assert len(mf.clients) == 1

    map_result = matcher.map_path_to_clients(download_path_symlink_files)
    assert map_result.seeded_size == 1000
    assert map_result.total_size == 1000
    assert len(map_result.files) == 2
    for f, mf in map_result.files.items():
        assert len(mf.clients) == 1


def test_rewrite(tmp_path, rewriter, indexer, matcher, client):
    infohash_1 = "1a39a3ee5e6b4b0d3255bfef95601890afd80709"
    infohash_2 = "2a39a3ee5e6b4b0d3255bfef95601890afd80709"
    name = "test torrent"

    download_path_1 = tmp_path / "test torrent 1"
    download_path_1.mkdir()
    (download_path_1 / "file1").write_bytes(b"a" * 100)

    download_path_2 = tmp_path / "test torrent 2"
    download_path_2.mkdir()
    (download_path_2 / "file1").write_bytes(b"a" * 100)

    download_path_3 = tmp_path / "test torrent 3"
    download_path_3_subpath = download_path_3 / "deeppath"
    download_path_3_subpath.mkdir(parents=True)
    (download_path_3_subpath / "file1").write_bytes(b"a" * 100)

    download_path_4 = tmp_path / "test torrent 4"
    download_path_4_subpath = download_path_4 / "deeppath"
    download_path_4_subpath.mkdir(parents=True)
    (download_path_4_subpath / "file1").write_bytes(b"a" * 100)

    client._inject_torrent(
        TorrentData(
            infohash_1,
            name,
            100,
            TorrentState.ACTIVE,
            100,
            1000,
            datetime(2020, 1, 1, 1, 1),
            "example.com",
            0,
            0,
            None,
        ),
        [TorrentFile("file1", 100, 100)],
        download_path_1,
    )

    indexer.scan_clients({"test_client": client}, full_scan=False, fast_scan=False)

    map_result = matcher.map_path_to_clients(download_path_1)
    assert map_result.seeded_size == 100
    assert len(map_result.files) == 1
    for mf in map_result.files.values():
        assert len(mf.clients) == 1

    map_result = matcher.map_path_to_clients(download_path_2)
    assert map_result.seeded_size == 0
    assert len(map_result.files) == 1
    for mf in map_result.files.values():
        assert len(mf.clients) == 0

    rewriter.handle_path_mappings(
        [
            [str(download_path_1), str(download_path_2)],
            [str(download_path_3), str(download_path_4)],
        ]
    )

    map_result = matcher.map_path_to_clients(download_path_2)
    assert map_result.seeded_size == 100
    assert len(map_result.files) == 2
    found_zero, found_one = False, False
    for mf in map_result.files.values():
        if len(mf.clients) == 1:
            found_one = True
        if len(mf.clients) == 0:
            found_zero = True
    assert found_one
    assert found_zero

    map_result = matcher.map_path_to_clients(download_path_3)
    assert map_result.seeded_size == 0
    assert len(map_result.files) == 2
    for mf in map_result.files.values():
        assert len(mf.clients) == 0
