import shutil
from datetime import datetime
from pathlib import Path, PurePosixPath

import pytest
from libtc import TorrentData, TorrentFile, TorrentState, bdecode

from .fixtures import *
from autotorrent.utils import parse_torrent


def test_verify_hash_all_files_success(testfiles, indexer, matcher, client):
    torrent = parse_torrent(bdecode((testfiles / "test.torrent").read_bytes()))
    hash_result, touch_result = torrent.verify_hash(['*'], {
        PurePosixPath('testfiles/file_a.txt'): testfiles / 'file_a.txt',
        PurePosixPath('testfiles/file_b.txt'): testfiles / 'file_b.txt',
        PurePosixPath('testfiles/file_c.txt'): testfiles / 'file_c.txt',
    })
    assert len(hash_result) == 3
    assert set(hash_result.values()) == {'hash-success'}
    assert not touch_result


def test_verify_hash_missing_files(testfiles, indexer, matcher, client):
    torrent = parse_torrent(bdecode((testfiles / "test.torrent").read_bytes()))
    hash_result, touch_result = torrent.verify_hash(['*'], {
        PurePosixPath('testfiles/file_a.txt'): testfiles / 'file_a.txt',
        PurePosixPath('testfiles/file_b.txt'): testfiles / 'file_b.txt',
        PurePosixPath('testfiles/file_c.txt'): None,
    })
    assert {k.path: v for (k, v) in hash_result.items()} == {
        PurePosixPath('testfiles/file_a.txt'): 'hash-success',
        PurePosixPath('testfiles/file_b.txt'): 'hash-failed',
        PurePosixPath('testfiles/file_c.txt'): 'hash-failed',
    }
    assert {k.path: v for (k, v) in touch_result.items()} == {
        PurePosixPath('testfiles/file_b.txt'): 'touch-failed',
        PurePosixPath('testfiles/file_c.txt'): 'touch-failed',
    }

    hash_result, touch_result = torrent.verify_hash(['*'], {
        PurePosixPath('testfiles/file_a.txt'): testfiles / 'file_a.txt',
        PurePosixPath('testfiles/file_b.txt'): None,
        PurePosixPath('testfiles/file_c.txt'): testfiles / 'file_c.txt',
    })
    assert {k.path: v for (k, v) in hash_result.items()} == {
        PurePosixPath('testfiles/file_a.txt'): 'hash-success',
        PurePosixPath('testfiles/file_b.txt'): 'hash-failed',
        PurePosixPath('testfiles/file_c.txt'): 'hash-success',
    }
    assert {k.path: v for (k, v) in touch_result.items()} == {
        PurePosixPath('testfiles/file_a.txt'): 'touch-success',
        PurePosixPath('testfiles/file_b.txt'): 'touch-failed',
        PurePosixPath('testfiles/file_c.txt'): 'touch-success',
    }

    hash_result, touch_result = torrent.verify_hash(['*'], {
        PurePosixPath('testfiles/file_a.txt'): None,
        PurePosixPath('testfiles/file_b.txt'): testfiles / 'file_b.txt',
        PurePosixPath('testfiles/file_c.txt'): testfiles / 'file_c.txt',
    })
    assert {k.path: v for (k, v) in hash_result.items()} == {
        PurePosixPath('testfiles/file_a.txt'): 'hash-failed',
        PurePosixPath('testfiles/file_b.txt'): 'hash-failed',
        PurePosixPath('testfiles/file_c.txt'): 'hash-success',
    }
    assert {k.path: v for (k, v) in touch_result.items()} == {
        PurePosixPath('testfiles/file_a.txt'): 'touch-failed',
        PurePosixPath('testfiles/file_b.txt'): 'touch-failed',
    }


def test_verify_hash_bad_files(testfiles, indexer, matcher, client):
    torrent = parse_torrent(bdecode((testfiles / "test.torrent").read_bytes()))
    bad_file_a = testfiles / 'file_a_bad.txt'
    bad_file_b = testfiles / 'file_b_bad.txt'
    bad_file_c = testfiles / 'file_c_bad.txt'

    # first piece only shared with file_a is bad
    shutil.copy(testfiles / 'file_a.txt', bad_file_a)
    with bad_file_a.open('rb+') as f:
        f.seek(1)
        f.write(b'\x00')

    hash_result, touch_result = torrent.verify_hash(['*'], {
        PurePosixPath('testfiles/file_a.txt'): bad_file_a,
        PurePosixPath('testfiles/file_b.txt'): testfiles / 'file_b.txt',
        PurePosixPath('testfiles/file_c.txt'): testfiles / 'file_c.txt',
    })

    assert {k.path: v for (k, v) in hash_result.items()} == {
        PurePosixPath('testfiles/file_a.txt'): 'hash-failed',
        PurePosixPath('testfiles/file_b.txt'): 'hash-success',
        PurePosixPath('testfiles/file_c.txt'): 'hash-success',
    }
    assert {k.path: v for (k, v) in touch_result.items()} == {
        PurePosixPath('testfiles/file_a.txt'): 'touch-failed',
    }

    # second piece shared between file_a and file_b as edge pieces with file_a bad
    shutil.copy(testfiles / 'file_a.txt', bad_file_a)
    with bad_file_a.open('rb+') as f:
        f.seek(9)
        f.write(b'\x00')

    hash_result, touch_result = torrent.verify_hash(['*'], {
        PurePosixPath('testfiles/file_a.txt'): bad_file_a,
        PurePosixPath('testfiles/file_b.txt'): testfiles / 'file_b.txt',
        PurePosixPath('testfiles/file_c.txt'): testfiles / 'file_c.txt',
    })

    assert {k.path: v for (k, v) in hash_result.items()} == {
        PurePosixPath('testfiles/file_a.txt'): 'hash-failed',
        PurePosixPath('testfiles/file_b.txt'): 'hash-failed',
        PurePosixPath('testfiles/file_c.txt'): 'hash-success',
    }
    assert {k.path: v for (k, v) in touch_result.items()} == {
        PurePosixPath('testfiles/file_a.txt'): 'touch-failed',
        PurePosixPath('testfiles/file_b.txt'): 'touch-failed',
    }

    # second piece shared between file_a and file_b as edge pieces with file_b bad
    shutil.copy(testfiles / 'file_b.txt', bad_file_b)
    with bad_file_b.open('rb+') as f:
        f.seek(1)
        f.write(b'\x00')

    hash_result, touch_result = torrent.verify_hash(['*'], {
        PurePosixPath('testfiles/file_a.txt'): testfiles / 'file_a.txt',
        PurePosixPath('testfiles/file_b.txt'): bad_file_b,
        PurePosixPath('testfiles/file_c.txt'): testfiles / 'file_c.txt',
    })

    assert {k.path: v for (k, v) in hash_result.items()} == {
        PurePosixPath('testfiles/file_a.txt'): 'hash-failed',
        PurePosixPath('testfiles/file_b.txt'): 'hash-failed',
        PurePosixPath('testfiles/file_c.txt'): 'hash-success',
    }
    assert {k.path: v for (k, v) in touch_result.items()} == {
        PurePosixPath('testfiles/file_a.txt'): 'touch-failed',
        PurePosixPath('testfiles/file_b.txt'): 'touch-failed',
    }

    hash_result, touch_result = torrent.verify_hash(['file_b.txt'], {
        PurePosixPath('testfiles/file_a.txt'): testfiles / 'file_a.txt',
        PurePosixPath('testfiles/file_b.txt'): bad_file_b,
        PurePosixPath('testfiles/file_c.txt'): testfiles / 'file_c.txt',
    })

    assert {k.path: v for (k, v) in hash_result.items()} == {
        PurePosixPath('testfiles/file_b.txt'): 'hash-failed',
    }
    assert {k.path: v for (k, v) in touch_result.items()} == {
        PurePosixPath('testfiles/file_a.txt'): 'touch-failed',
        PurePosixPath('testfiles/file_b.txt'): 'touch-failed',
    }

    shutil.copy(testfiles / 'file_c.txt', bad_file_c)
    with bad_file_c.open('rb+') as f:
        f.seek(0)
        f.write(b'\x00')

    hash_result, touch_result = torrent.verify_hash(['file_b.txt'], {
        PurePosixPath('testfiles/file_a.txt'): testfiles / 'file_a.txt',
        PurePosixPath('testfiles/file_b.txt'): bad_file_b,
        PurePosixPath('testfiles/file_c.txt'): bad_file_c,
    })

    assert {k.path: v for (k, v) in hash_result.items()} == {
        PurePosixPath('testfiles/file_b.txt'): 'hash-failed',
    }
    assert {k.path: v for (k, v) in touch_result.items()} == {
        PurePosixPath('testfiles/file_a.txt'): 'touch-failed',
        PurePosixPath('testfiles/file_b.txt'): 'touch-failed',
        PurePosixPath('testfiles/file_c.txt'): 'touch-failed',
    }

    hash_result, touch_result = torrent.verify_hash(['file_c.txt'], {
        PurePosixPath('testfiles/file_a.txt'): testfiles / 'file_a.txt',
        PurePosixPath('testfiles/file_b.txt'): testfiles / 'file_b.txt',
        PurePosixPath('testfiles/file_c.txt'): bad_file_c,
    })

    assert {k.path: v for (k, v) in hash_result.items()} == {
        PurePosixPath('testfiles/file_c.txt'): 'hash-failed',
    }
    assert {k.path: v for (k, v) in touch_result.items()} == {
        PurePosixPath('testfiles/file_b.txt'): 'touch-failed',
        PurePosixPath('testfiles/file_c.txt'): 'touch-failed',
    }
