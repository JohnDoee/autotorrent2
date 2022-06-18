import shutil
from datetime import datetime
from pathlib import Path, PurePosixPath

import pytest
from libtc import TorrentData, TorrentFile, TorrentState, bdecode

from .fixtures import *


def test_scan_match_exact_client(testfiles, indexer, matcher, client):
    indexer.scan_paths([testfiles])
    assert (
        matcher.match_files_exact(bdecode((testfiles / "test.torrent").read_bytes()))
        == testfiles.parent
    )
    assert (
        matcher.match_files_exact(
            bdecode((testfiles / "test_single.torrent").read_bytes())
        )
        == testfiles
    )
    assert (
        matcher.match_files_exact(
            bdecode((testfiles / "My-Bluray.torrent").read_bytes())
        )
        == testfiles
    )
    assert (
        matcher.match_files_exact(bdecode((testfiles / "My-DVD.torrent").read_bytes()))
        == testfiles
    )
    assert (
        matcher.match_files_exact(
            bdecode((testfiles / "Some-CD-Release.torrent").read_bytes())
        )
        == testfiles
    )
    assert (
        matcher.match_files_exact(
            bdecode((testfiles / "Some-Release.torrent").read_bytes())
        )
        == testfiles
    )

    (testfiles / "file_a.txt").write_bytes(b"not a good match")

    indexer.scan_paths([testfiles])

    assert (
        matcher.match_files_exact(bdecode((testfiles / "test.torrent").read_bytes()))
        == None
    )
    assert (
        matcher.match_files_exact(
            bdecode((testfiles / "test_single.torrent").read_bytes())
        )
        == None
    )
    assert (
        matcher.match_files_exact(
            bdecode((testfiles / "My-Bluray.torrent").read_bytes())
        )
        == testfiles
    )
    assert (
        matcher.match_files_exact(bdecode((testfiles / "My-DVD.torrent").read_bytes()))
        == testfiles
    )
    assert (
        matcher.match_files_exact(
            bdecode((testfiles / "Some-CD-Release.torrent").read_bytes())
        )
        == testfiles
    )
    assert (
        matcher.match_files_exact(
            bdecode((testfiles / "Some-Release.torrent").read_bytes())
        )
        == testfiles
    )

    (testfiles / "file_a.txt").unlink()

    indexer.scan_paths([testfiles])

    assert (
        matcher.match_files_exact(bdecode((testfiles / "test.torrent").read_bytes()))
        == None
    )
    assert (
        matcher.match_files_exact(
            bdecode((testfiles / "test_single.torrent").read_bytes())
        )
        == None
    )
    assert (
        matcher.match_files_exact(
            bdecode((testfiles / "My-Bluray.torrent").read_bytes())
        )
        == testfiles
    )
    assert (
        matcher.match_files_exact(bdecode((testfiles / "My-DVD.torrent").read_bytes()))
        == testfiles
    )
    assert (
        matcher.match_files_exact(
            bdecode((testfiles / "Some-CD-Release.torrent").read_bytes())
        )
        == testfiles
    )
    assert (
        matcher.match_files_exact(
            bdecode((testfiles / "Some-Release.torrent").read_bytes())
        )
        == testfiles
    )


def test_scan_match_dynamic_basic_as_exact(testfiles, indexer, matcher, client):
    indexer.scan_paths([testfiles])

    result = matcher.match_files_dynamic(
        bdecode((testfiles / "test.torrent").read_bytes())
    )
    assert result.touched_files == []
    assert result.matched_files == {
        PurePosixPath("testfiles/file_a.txt"): testfiles / "file_a.txt",
        PurePosixPath("testfiles/file_b.txt"): testfiles / "file_b.txt",
        PurePosixPath("testfiles/file_c.txt"): testfiles / "file_c.txt",
    }

    result = matcher.match_files_dynamic(
        bdecode((testfiles / "test_single.torrent").read_bytes())
    )
    assert result.touched_files == []
    assert result.matched_files == {
        PurePosixPath("file_a.txt"): testfiles / "file_a.txt",
    }

    result = matcher.match_files_dynamic(
        bdecode((testfiles / "My-Bluray.torrent").read_bytes())
    )
    assert result.touched_files == []
    assert result.matched_files == {
        PurePosixPath("My-Bluray/BDMV/BACKUP/MovieObject.bdmv"): testfiles
        / "My-Bluray/BDMV/BACKUP/MovieObject.bdmv",
        PurePosixPath("My-Bluray/BDMV/BACKUP/PLAYLIST/00000.mpls"): testfiles
        / "My-Bluray/BDMV/BACKUP/PLAYLIST/00000.mpls",
        PurePosixPath("My-Bluray/BDMV/BACKUP/index.bdmv"): testfiles
        / "My-Bluray/BDMV/BACKUP/index.bdmv",
        PurePosixPath("My-Bluray/BDMV/MovieObject.bdmv"): testfiles
        / "My-Bluray/BDMV/MovieObject.bdmv",
        PurePosixPath("My-Bluray/BDMV/PLAYLIST/00000.mpls"): testfiles
        / "My-Bluray/BDMV/PLAYLIST/00000.mpls",
        PurePosixPath("My-Bluray/BDMV/STREAM/00000.m2ts"): testfiles
        / "My-Bluray/BDMV/STREAM/00000.m2ts",
        PurePosixPath("My-Bluray/BDMV/index.bdmv"): testfiles
        / "My-Bluray/BDMV/index.bdmv",
    }

    result = matcher.match_files_dynamic(
        bdecode((testfiles / "My-DVD.torrent").read_bytes())
    )
    assert result.touched_files == []
    assert result.matched_files == {
        PurePosixPath("My-DVD/VIDEO_TS/VIDEO_TS.BUP"): testfiles
        / "My-DVD/VIDEO_TS/VIDEO_TS.BUP",
        PurePosixPath("My-DVD/VIDEO_TS/VIDEO_TS.IFO"): testfiles
        / "My-DVD/VIDEO_TS/VIDEO_TS.IFO",
        PurePosixPath("My-DVD/VIDEO_TS/VTS_01_0.BUP"): testfiles
        / "My-DVD/VIDEO_TS/VTS_01_0.BUP",
        PurePosixPath("My-DVD/VIDEO_TS/VTS_01_0.IFO"): testfiles
        / "My-DVD/VIDEO_TS/VTS_01_0.IFO",
        PurePosixPath("My-DVD/VIDEO_TS/VTS_01_0.VOB"): testfiles
        / "My-DVD/VIDEO_TS/VTS_01_0.VOB",
        PurePosixPath("My-DVD/VIDEO_TS/VTS_01_1.VOB"): testfiles
        / "My-DVD/VIDEO_TS/VTS_01_1.VOB",
    }

    result = matcher.match_files_dynamic(
        bdecode((testfiles / "Some-CD-Release.torrent").read_bytes())
    )
    assert result.touched_files == []
    assert result.matched_files == {
        PurePosixPath("Some-CD-Release/CD1/somestuff-1.r00"): testfiles
        / "Some-CD-Release/CD1/somestuff-1.r00",
        PurePosixPath("Some-CD-Release/CD1/somestuff-1.r01"): testfiles
        / "Some-CD-Release/CD1/somestuff-1.r01",
        PurePosixPath("Some-CD-Release/CD1/somestuff-1.r02"): testfiles
        / "Some-CD-Release/CD1/somestuff-1.r02",
        PurePosixPath("Some-CD-Release/CD1/somestuff-1.r03"): testfiles
        / "Some-CD-Release/CD1/somestuff-1.r03",
        PurePosixPath("Some-CD-Release/CD1/somestuff-1.r04"): testfiles
        / "Some-CD-Release/CD1/somestuff-1.r04",
        PurePosixPath("Some-CD-Release/CD1/somestuff-1.r05"): testfiles
        / "Some-CD-Release/CD1/somestuff-1.r05",
        PurePosixPath("Some-CD-Release/CD1/somestuff-1.r06"): testfiles
        / "Some-CD-Release/CD1/somestuff-1.r06",
        PurePosixPath("Some-CD-Release/CD1/somestuff-1.rar"): testfiles
        / "Some-CD-Release/CD1/somestuff-1.rar",
        PurePosixPath("Some-CD-Release/CD1/somestuff-1.sfv"): testfiles
        / "Some-CD-Release/CD1/somestuff-1.sfv",
        PurePosixPath("Some-CD-Release/CD2/somestuff-2.r00"): testfiles
        / "Some-CD-Release/CD2/somestuff-2.r00",
        PurePosixPath("Some-CD-Release/CD2/somestuff-2.r01"): testfiles
        / "Some-CD-Release/CD2/somestuff-2.r01",
        PurePosixPath("Some-CD-Release/CD2/somestuff-2.r02"): testfiles
        / "Some-CD-Release/CD2/somestuff-2.r02",
        PurePosixPath("Some-CD-Release/CD2/somestuff-2.r03"): testfiles
        / "Some-CD-Release/CD2/somestuff-2.r03",
        PurePosixPath("Some-CD-Release/CD2/somestuff-2.r04"): testfiles
        / "Some-CD-Release/CD2/somestuff-2.r04",
        PurePosixPath("Some-CD-Release/CD2/somestuff-2.r05"): testfiles
        / "Some-CD-Release/CD2/somestuff-2.r05",
        PurePosixPath("Some-CD-Release/CD2/somestuff-2.r06"): testfiles
        / "Some-CD-Release/CD2/somestuff-2.r06",
        PurePosixPath("Some-CD-Release/CD2/somestuff-2.r07"): testfiles
        / "Some-CD-Release/CD2/somestuff-2.r07",
        PurePosixPath("Some-CD-Release/CD2/somestuff-2.rar"): testfiles
        / "Some-CD-Release/CD2/somestuff-2.rar",
        PurePosixPath("Some-CD-Release/CD2/somestuff-2.sfv"): testfiles
        / "Some-CD-Release/CD2/somestuff-2.sfv",
        PurePosixPath("Some-CD-Release/Sample/some-rls.mkv"): testfiles
        / "Some-CD-Release/Sample/some-rls.mkv",
        PurePosixPath("Some-CD-Release/Subs/somestuff-subs.r00"): testfiles
        / "Some-CD-Release/Subs/somestuff-subs.r00",
        PurePosixPath("Some-CD-Release/Subs/somestuff-subs.rar"): testfiles
        / "Some-CD-Release/Subs/somestuff-subs.rar",
        PurePosixPath("Some-CD-Release/Subs/somestuff-subs.sfv"): testfiles
        / "Some-CD-Release/Subs/somestuff-subs.sfv",
        PurePosixPath("Some-CD-Release/crap.nfo"): testfiles
        / "Some-CD-Release/crap.nfo",
    }

    result = matcher.match_files_dynamic(
        bdecode((testfiles / "Some-Release.torrent").read_bytes())
    )
    assert result.touched_files == []
    assert result.matched_files == {
        PurePosixPath("Some-Release/Sample/some-rls.mkv"): testfiles
        / "Some-Release/Sample/some-rls.mkv",
        PurePosixPath("Some-Release/Subs/some-subs.rar"): testfiles
        / "Some-Release/Subs/some-subs.rar",
        PurePosixPath("Some-Release/Subs/some-subs.sfv"): testfiles
        / "Some-Release/Subs/some-subs.sfv",
        PurePosixPath("Some-Release/some-rls.sfv"): testfiles
        / "Some-Release/some-rls.sfv",
        PurePosixPath("Some-Release/some-rls.nfo"): testfiles
        / "Some-Release/some-rls.nfo",
        PurePosixPath("Some-Release/some-rls.rar"): testfiles
        / "Some-Release/some-rls.rar",
        PurePosixPath("Some-Release/some-rls.r00"): testfiles
        / "Some-Release/some-rls.r00",
        PurePosixPath("Some-Release/some-rls.r01"): testfiles
        / "Some-Release/some-rls.r01",
        PurePosixPath("Some-Release/some-rls.r02"): testfiles
        / "Some-Release/some-rls.r02",
        PurePosixPath("Some-Release/some-rls.r03"): testfiles
        / "Some-Release/some-rls.r03",
        PurePosixPath("Some-Release/some-rls.r04"): testfiles
        / "Some-Release/some-rls.r04",
        PurePosixPath("Some-Release/some-rls.r05"): testfiles
        / "Some-Release/some-rls.r05",
        PurePosixPath("Some-Release/some-rls.r06"): testfiles
        / "Some-Release/some-rls.r06",
    }


def test_scan_match_dynamic_hash_probe(testfiles, indexer, matcher, client):
    indexer.scan_paths([testfiles])

    result = matcher.match_files_dynamic(
        bdecode((testfiles / "test.torrent").read_bytes()), hash_probe=True
    )
    assert result.touched_files == []
    assert result.matched_files == {
        PurePosixPath("testfiles/file_a.txt"): testfiles / "file_a.txt",
        PurePosixPath("testfiles/file_b.txt"): testfiles / "file_b.txt",
        PurePosixPath("testfiles/file_c.txt"): testfiles / "file_c.txt",
    }

    with (testfiles / "file_a.txt").open("r+b") as f:
        f.seek(0)
        f.write(b"2")

    result = matcher.match_files_dynamic(
        bdecode((testfiles / "test.torrent").read_bytes()), hash_probe=False
    )
    assert result.touched_files == []
    assert result.matched_files == {
        PurePosixPath("testfiles/file_a.txt"): testfiles / "file_a.txt",
        PurePosixPath("testfiles/file_b.txt"): testfiles / "file_b.txt",
        PurePosixPath("testfiles/file_c.txt"): testfiles / "file_c.txt",
    }

    result = matcher.match_files_dynamic(
        bdecode((testfiles / "test.torrent").read_bytes()),
        add_limit_percent=100,
        add_limit_size=9999999,
        hash_probe=True,
    )
    assert result.touched_files == [PurePosixPath("testfiles/file_b.txt")]
    assert result.matched_files == {
        PurePosixPath("testfiles/file_a.txt"): None,
        PurePosixPath("testfiles/file_b.txt"): testfiles / "file_b.txt",
        PurePosixPath("testfiles/file_c.txt"): testfiles / "file_c.txt",
    }


def test_scan_match_dynamic_cutoff(testfiles, indexer, matcher, client):
    indexer.scan_paths([testfiles])

    with (testfiles / "file_a.txt").open("r+b") as f:
        f.seek(0)
        f.write(b"2")

    result = matcher.match_files_dynamic(
        bdecode((testfiles / "test.torrent").read_bytes()),
        add_limit_percent=5,
        add_limit_size=9999999,
        hash_probe=True,
    )
    assert result.success == False

    result = matcher.match_files_dynamic(
        bdecode((testfiles / "test.torrent").read_bytes()),
        add_limit_percent=5,
        add_limit_size=9999999,
        hash_probe=False,
    )
    assert result.success == True

    result = matcher.match_files_dynamic(
        bdecode((testfiles / "test.torrent").read_bytes()),
        add_limit_percent=99,
        add_limit_size=9999999,
        hash_probe=True,
    )
    assert result.success == True

    (testfiles / "file_a.txt").unlink()

    indexer.scan_paths([testfiles])

    result = matcher.match_files_dynamic(
        bdecode((testfiles / "test.torrent").read_bytes()),
        add_limit_percent=5,
        add_limit_size=9999999,
        hash_probe=True,
    )
    assert result.success == False

    result = matcher.match_files_dynamic(
        bdecode((testfiles / "test.torrent").read_bytes()),
        add_limit_percent=5,
        add_limit_size=9999999,
        hash_probe=False,
    )
    assert result.success == False

    result = matcher.match_files_dynamic(
        bdecode((testfiles / "test.torrent").read_bytes()),
        add_limit_percent=99,
        add_limit_size=9999999,
        hash_probe=True,
    )
    assert result.success == True


def test_scan_match_dynamic_match_hash_size(testfiles, indexer, matcher, client):
    indexer.scan_paths([testfiles])

    result = matcher.match_files_dynamic(
        bdecode((testfiles / "test.torrent").read_bytes()),
        match_hash_size=True,
        add_limit_percent=50,
        add_limit_size=9999999,
    )
    assert sorted(result.touched_files) == sorted(
        [PurePosixPath("testfiles/file_a.txt"), PurePosixPath("testfiles/file_c.txt")]
    )
    assert result.matched_files == {
        PurePosixPath("testfiles/file_a.txt"): testfiles / "file_a.txt",
        PurePosixPath("testfiles/file_b.txt"): None,
        PurePosixPath("testfiles/file_c.txt"): testfiles / "file_c.txt",
    }

    (testfiles / "file_a.txt").rename(testfiles / "secret_1.txt")
    (testfiles / "file_b.txt").rename(testfiles / "secret_2.txt")
    (testfiles / "file_c.txt").rename(testfiles / "secret_3.txt")

    indexer.scan_paths([testfiles])

    result = matcher.match_files_dynamic(
        bdecode((testfiles / "test.torrent").read_bytes()),
        match_hash_size=True,
        add_limit_percent=50,
        add_limit_size=9999999,
    )
    assert sorted(result.touched_files) == sorted(
        [PurePosixPath("testfiles/file_a.txt"), PurePosixPath("testfiles/file_c.txt")]
    )
    assert result.matched_files == {
        PurePosixPath("testfiles/file_a.txt"): testfiles / "secret_1.txt",
        PurePosixPath("testfiles/file_b.txt"): None,
        PurePosixPath("testfiles/file_c.txt"): testfiles / "secret_3.txt",
    }


def test_scan_match_dynamic_mixed_unsplitable_normal(
    testfiles, indexer, matcher, client
):
    (testfiles / "file_a.txt").rename(testfiles / "FILE  A.txt")
    (testfiles / "file_b.txt").rename(testfiles / "file_B.txt")
    (testfiles / "file_c.txt").rename(testfiles / "filE-c.txt")

    indexer.scan_paths([testfiles])

    result = matcher.match_files_dynamic(
        bdecode((testfiles / "test-unsplitable-normal.torrent").read_bytes())
    )
    assert result.touched_files == []
    assert result.matched_files == {
        PurePosixPath("testfiles/file_a.txt"): testfiles / "FILE  A.txt",
        PurePosixPath("testfiles/file_b.txt"): testfiles / "file_B.txt",
        PurePosixPath("testfiles/file_c.txt"): testfiles / "filE-c.txt",
        PurePosixPath("testfiles/Some-CD-Release/CD1/somestuff-1.r00"): testfiles
        / "Some-CD-Release/CD1/somestuff-1.r00",
        PurePosixPath("testfiles/Some-CD-Release/CD1/somestuff-1.r01"): testfiles
        / "Some-CD-Release/CD1/somestuff-1.r01",
        PurePosixPath("testfiles/Some-CD-Release/CD1/somestuff-1.r02"): testfiles
        / "Some-CD-Release/CD1/somestuff-1.r02",
        PurePosixPath("testfiles/Some-CD-Release/CD1/somestuff-1.r03"): testfiles
        / "Some-CD-Release/CD1/somestuff-1.r03",
        PurePosixPath("testfiles/Some-CD-Release/CD1/somestuff-1.r04"): testfiles
        / "Some-CD-Release/CD1/somestuff-1.r04",
        PurePosixPath("testfiles/Some-CD-Release/CD1/somestuff-1.r05"): testfiles
        / "Some-CD-Release/CD1/somestuff-1.r05",
        PurePosixPath("testfiles/Some-CD-Release/CD1/somestuff-1.r06"): testfiles
        / "Some-CD-Release/CD1/somestuff-1.r06",
        PurePosixPath("testfiles/Some-CD-Release/CD1/somestuff-1.rar"): testfiles
        / "Some-CD-Release/CD1/somestuff-1.rar",
        PurePosixPath("testfiles/Some-CD-Release/CD1/somestuff-1.sfv"): testfiles
        / "Some-CD-Release/CD1/somestuff-1.sfv",
        PurePosixPath("testfiles/Some-CD-Release/CD2/somestuff-2.r00"): testfiles
        / "Some-CD-Release/CD2/somestuff-2.r00",
        PurePosixPath("testfiles/Some-CD-Release/CD2/somestuff-2.r01"): testfiles
        / "Some-CD-Release/CD2/somestuff-2.r01",
        PurePosixPath("testfiles/Some-CD-Release/CD2/somestuff-2.r02"): testfiles
        / "Some-CD-Release/CD2/somestuff-2.r02",
        PurePosixPath("testfiles/Some-CD-Release/CD2/somestuff-2.r03"): testfiles
        / "Some-CD-Release/CD2/somestuff-2.r03",
        PurePosixPath("testfiles/Some-CD-Release/CD2/somestuff-2.r04"): testfiles
        / "Some-CD-Release/CD2/somestuff-2.r04",
        PurePosixPath("testfiles/Some-CD-Release/CD2/somestuff-2.r05"): testfiles
        / "Some-CD-Release/CD2/somestuff-2.r05",
        PurePosixPath("testfiles/Some-CD-Release/CD2/somestuff-2.r06"): testfiles
        / "Some-CD-Release/CD2/somestuff-2.r06",
        PurePosixPath("testfiles/Some-CD-Release/CD2/somestuff-2.r07"): testfiles
        / "Some-CD-Release/CD2/somestuff-2.r07",
        PurePosixPath("testfiles/Some-CD-Release/CD2/somestuff-2.rar"): testfiles
        / "Some-CD-Release/CD2/somestuff-2.rar",
        PurePosixPath("testfiles/Some-CD-Release/CD2/somestuff-2.sfv"): testfiles
        / "Some-CD-Release/CD2/somestuff-2.sfv",
        PurePosixPath("testfiles/Some-CD-Release/Sample/some-rls.mkv"): testfiles
        / "Some-CD-Release/Sample/some-rls.mkv",
        PurePosixPath("testfiles/Some-CD-Release/Subs/somestuff-subs.r00"): testfiles
        / "Some-CD-Release/Subs/somestuff-subs.r00",
        PurePosixPath("testfiles/Some-CD-Release/Subs/somestuff-subs.rar"): testfiles
        / "Some-CD-Release/Subs/somestuff-subs.rar",
        PurePosixPath("testfiles/Some-CD-Release/Subs/somestuff-subs.sfv"): testfiles
        / "Some-CD-Release/Subs/somestuff-subs.sfv",
        PurePosixPath("testfiles/Some-CD-Release/crap.nfo"): testfiles
        / "Some-CD-Release/crap.nfo",
    }


def test_scan_match_dynamic_normalized(testfiles, indexer, matcher, client):
    (testfiles / "file_a.txt").rename(testfiles / "FILE  A.txt")
    (testfiles / "file_b.txt").rename(testfiles / "file_B.txt")
    (testfiles / "file_c.txt").rename(testfiles / "filE-c.txt")

    indexer.scan_paths([testfiles])

    result = matcher.match_files_dynamic(
        bdecode((testfiles / "test.torrent").read_bytes())
    )
    assert result.touched_files == []
    assert result.matched_files == {
        PurePosixPath("testfiles/file_a.txt"): testfiles / "FILE  A.txt",
        PurePosixPath("testfiles/file_b.txt"): testfiles / "file_B.txt",
        PurePosixPath("testfiles/file_c.txt"): testfiles / "filE-c.txt",
    }


def test_scan_match_partial_scan(testfiles, indexer, matcher, client):
    (testfiles / "file_a.txt").rename(testfiles / "wrong.txt")

    indexer.scan_paths([testfiles])
    (testfiles / "wrong.txt").rename(testfiles / "file_a.txt")
    indexer.scan_paths([testfiles], full_scan=False)

    result = matcher.match_files_dynamic(
        bdecode((testfiles / "test.torrent").read_bytes())
    )
    assert result.touched_files == []
    assert result.matched_files == {
        PurePosixPath("testfiles/file_a.txt"): testfiles / "file_a.txt",
        PurePosixPath("testfiles/file_b.txt"): testfiles / "file_b.txt",
        PurePosixPath("testfiles/file_c.txt"): testfiles / "file_c.txt",
    }


def test_scan_invalid_encoding(testfiles, indexer, matcher, client):
    """Should just not error out when hitting non-utf-8"""
    with open(
        str(testfiles).encode() + b"/" + b"\x82\xa9\x82\xed\x82\xa2\x82\xa2\x94n", "wb"
    ) as f:  # Shift JIS
        f.write(b"cute horse")

    indexer.scan_paths([testfiles])
    indexer.db.utf8_compat_mode = True
    indexer.scan_paths([testfiles])


def test_scan_different_folder_in_torrent_unsplitable(testfiles, indexer, matcher, client):
    indexer.scan_paths([testfiles])

    result = matcher.match_files_dynamic(
        bdecode((testfiles / "Some-Release [test].torrent").read_bytes()),
        add_limit_size=100,
        add_limit_percent=10,
    )
    assert result.matched_files == {
        PurePosixPath("Some-Release [test]/Sample/some-rls.mkv"): testfiles
        / "Some-Release/Sample/some-rls.mkv",
        PurePosixPath("Some-Release [test]/Subs/some-subs.rar"): testfiles
        / "Some-Release/Subs/some-subs.rar",
        PurePosixPath("Some-Release [test]/Subs/some-subs.sfv"): testfiles
        / "Some-Release/Subs/some-subs.sfv",
        PurePosixPath("Some-Release [test]/some-rls.sfv"): testfiles
        / "Some-Release/some-rls.sfv",
        PurePosixPath("Some-Release [test]/some-rls.nfo"): testfiles
        / "Some-Release/some-rls.nfo",
        PurePosixPath("Some-Release [test]/some-rls.rar"): testfiles
        / "Some-Release/some-rls.rar",
        PurePosixPath("Some-Release [test]/some-rls.r00"): testfiles
        / "Some-Release/some-rls.r00",
        PurePosixPath("Some-Release [test]/some-rls.r01"): testfiles
        / "Some-Release/some-rls.r01",
        PurePosixPath("Some-Release [test]/some-rls.r02"): testfiles
        / "Some-Release/some-rls.r02",
        PurePosixPath("Some-Release [test]/some-rls.r03"): testfiles
        / "Some-Release/some-rls.r03",
        PurePosixPath("Some-Release [test]/some-rls.r04"): testfiles
        / "Some-Release/some-rls.r04",
        PurePosixPath("Some-Release [test]/some-rls.r05"): testfiles
        / "Some-Release/some-rls.r05",
        PurePosixPath("Some-Release [test]/some-rls.r06"): testfiles
        / "Some-Release/some-rls.r06",
    }


def test_scan_different_folder_in_torrent_missing_files_should_be_there_unsplitable(testfiles, indexer, matcher, client):
    (testfiles / "Some-Release" / "some-rls.r03").unlink()
    indexer.scan_paths([testfiles])

    result = matcher.match_files_dynamic(
        bdecode((testfiles / "Some-Release [test].torrent").read_bytes()),
        add_limit_size=100,
        add_limit_percent=10,
    )
    assert result.matched_files is None


def test_scan_different_folder_in_torrent_missing_files_can_not_be_there_unsplitable(testfiles, indexer, matcher, client):
    (testfiles / "Some-Release" / "some-rls.nfo").unlink()
    indexer.scan_paths([testfiles])

    result = matcher.match_files_dynamic(
        bdecode((testfiles / "Some-Release [test].torrent").read_bytes()),
        add_limit_size=100,
        add_limit_percent=10,
    )
    assert result.matched_files is not None


def test_scan_extra_folder_in_torrent_unsplitable(testfiles, indexer, matcher, client):
    indexer.scan_paths([testfiles])

    result = matcher.match_files_dynamic(
        bdecode((testfiles / "folder-does-not-exist.torrent").read_bytes()),
        add_limit_size=100,
        add_limit_percent=10,
    )
    assert result.matched_files == {
        PurePosixPath("folder-does-not-exist/Some-Release/Sample/some-rls.mkv"): testfiles
        / "Some-Release/Sample/some-rls.mkv",
        PurePosixPath("folder-does-not-exist/Some-Release/Subs/some-subs.rar"): testfiles
        / "Some-Release/Subs/some-subs.rar",
        PurePosixPath("folder-does-not-exist/Some-Release/Subs/some-subs.sfv"): testfiles
        / "Some-Release/Subs/some-subs.sfv",
        PurePosixPath("folder-does-not-exist/Some-Release/some-rls.sfv"): testfiles
        / "Some-Release/some-rls.sfv",
        PurePosixPath("folder-does-not-exist/Some-Release/some-rls.nfo"): testfiles
        / "Some-Release/some-rls.nfo",
        PurePosixPath("folder-does-not-exist/Some-Release/some-rls.rar"): testfiles
        / "Some-Release/some-rls.rar",
        PurePosixPath("folder-does-not-exist/Some-Release/some-rls.r00"): testfiles
        / "Some-Release/some-rls.r00",
        PurePosixPath("folder-does-not-exist/Some-Release/some-rls.r01"): testfiles
        / "Some-Release/some-rls.r01",
        PurePosixPath("folder-does-not-exist/Some-Release/some-rls.r02"): testfiles
        / "Some-Release/some-rls.r02",
        PurePosixPath("folder-does-not-exist/Some-Release/some-rls.r03"): testfiles
        / "Some-Release/some-rls.r03",
        PurePosixPath("folder-does-not-exist/Some-Release/some-rls.r04"): testfiles
        / "Some-Release/some-rls.r04",
        PurePosixPath("folder-does-not-exist/Some-Release/some-rls.r05"): testfiles
        / "Some-Release/some-rls.r05",
        PurePosixPath("folder-does-not-exist/Some-Release/some-rls.r06"): testfiles
        / "Some-Release/some-rls.r06",
    }

def test_scan_ignore_patterns(testfiles, indexer, matcher, client):
    indexer.ignore_file_patterns = ["*.txt"]
    indexer.scan_paths([testfiles])
    assert (
        matcher.match_files_exact(bdecode((testfiles / "test.torrent").read_bytes()))
        is None
    )
