import shutil
from pathlib import Path, PurePosixPath

import pytest
import toml
from libtc.clients.tests.utils_testclient import TestClient

from autotorrent.db import Database
from autotorrent.indexer import Indexer
from autotorrent.matcher import Matcher
from autotorrent.utils import PathRewriter

__all__ = [
    "db",
    "indexer",
    "matcher",
    "client",
    "rewriter",
    "testfiles",
]


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "autotorrent.db")


@pytest.fixture
def indexer(db):
    return Indexer(db)


@pytest.fixture
def rewriter():
    return PathRewriter([])


@pytest.fixture
def matcher(db, rewriter):
    return Matcher(rewriter, db)


@pytest.fixture
def client():
    return TestClient()


@pytest.fixture
def testfiles(tmp_path):
    testfiles = Path(__file__).parent / "testfiles"
    shutil.copytree(testfiles, tmp_path / "testfiles")
    return tmp_path / "testfiles"