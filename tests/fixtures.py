import shutil
from pathlib import Path, PurePosixPath

import click
import libtc
import pytest
import toml
from click.testing import CliRunner
from libtc.clients.tests.utils_testclient import TestClient

import autotorrent.__main__
from autotorrent.db import Database
from autotorrent.indexer import Indexer
from autotorrent.matcher import Matcher
from autotorrent.utils import PathRewriter
from autotorrent.__main__ import cli

__all__ = [
    "db",
    "indexer",
    "matcher",
    "client",
    "rewriter",
    "testfiles",
    "configfile",
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


class ConfigFile:
    config = None

    def __init__(self, tmp_path, client):
        self.config_path = tmp_path / 'config.toml'
        self.client = client

    def create_config(self):
        runner = CliRunner()
        result = runner.invoke(cli, ['check-config'])
        self.config = toml.loads(self.config_path.read_text())

    def save_config(self):
        self.config_path.write_text(toml.dumps(self.config))


@pytest.fixture
def configfile(tmp_path, monkeypatch, client):
    monkeypatch.setattr(click, "get_app_dir", lambda app: str(tmp_path.resolve()))
    monkeypatch.setattr(autotorrent.__main__, "parse_clients_from_toml_dict", lambda x:  {"testclient": {"client": client, "display_name": "testclient"}})

    cf = ConfigFile(tmp_path, client)
    cf.create_config()
    store_path = tmp_path.resolve() / "store_path" / "{torrent_name}"
    store_path.mkdir(parents=True, exist_ok=True)
    cf.config["autotorrent"]["store_path"] = str(store_path)
    cf.save_config()
    return cf


