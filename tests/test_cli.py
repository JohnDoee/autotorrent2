import pytest

import libtc

from click.testing import CliRunner
from libtc import bdecode, bencode
from pathlib import Path

from autotorrent.__main__ import cli

from .fixtures import *

@pytest.mark.parametrize("linktype", ["soft", "hard"]) # test server with reflink support?
def test_cli_add_link_type(testfiles, indexer, matcher, client, configfile, tmp_path, linktype):
    configfile.config["autotorrent"]["link_type"] = linktype
    configfile.save_config()

    runner = CliRunner()
    result = runner.invoke(cli, ['scan', '-p', str(testfiles)], catch_exceptions=False)
    assert result.exit_code == 0
    result = runner.invoke(cli, ['add', 'testclient', str(testfiles / "test.torrent")], catch_exceptions=False)
    assert result.exit_code == 0
    action, kwargs = client._action_queue[0]
    assert action == "add"
    link_file = (kwargs["destination_path"] / "testfiles" / "file_a.txt")
    assert not kwargs["stopped"]
    assert link_file.exists()
    if linktype == "soft":
        assert link_file.is_symlink()
    elif linktype == "hard":
        assert not link_file.is_symlink()
    else:
        raise Exception(f"Unknown link type {linktype}")


def test_cli_ignore_file_patterns(testfiles, indexer, matcher, client, configfile, tmp_path):
    configfile.config["autotorrent"]["ignore_file_patterns"] = ["*.txt"]
    configfile.save_config()

    runner = CliRunner()
    result = runner.invoke(cli, ['scan', '-p', str(testfiles)], catch_exceptions=False)
    assert result.exit_code == 0
    result = runner.invoke(cli, ['add', 'testclient', str(testfiles / "test.torrent")], catch_exceptions=False)
    assert result.exit_code == 0
    assert 'Failed' in result.output


def test_cli_ignore_directory_patterns(testfiles, indexer, matcher, client, configfile, tmp_path):
    configfile.config["autotorrent"]["ignore_directory_patterns"] = ['SaMpl*']
    configfile.save_config()

    runner = CliRunner()
    result = runner.invoke(cli, ['scan', '-p', str(testfiles)], catch_exceptions=False)
    assert result.exit_code == 0
    result = runner.invoke(cli, ['add', 'testclient', str(testfiles / "Some-Release.torrent")], catch_exceptions=False)
    assert result.exit_code == 0
    assert not client._action_queue


def test_cli_add_symlink_folder(testfiles, indexer, matcher, client, configfile, tmp_path):
    symlinked_testfiles = tmp_path / 'symlinked' / 'testfiles'
    symlinked_testfiles.parent.mkdir(parents=True, exist_ok=True)
    symlinked_testfiles.symlink_to(testfiles)

    runner = CliRunner()
    result = runner.invoke(cli, ['scan', '-p', str(symlinked_testfiles)], catch_exceptions=False)
    assert result.exit_code == 0
    result = runner.invoke(cli, ['add', 'testclient', '-e', str(testfiles / "test.torrent")], catch_exceptions=False)
    assert result.exit_code == 0
    action, kwargs = client._action_queue[0]
    assert action == "add"
    assert symlinked_testfiles.relative_to(kwargs["destination_path"]) == Path('testfiles')


def test_cli_add_symlink_files(testfiles, indexer, matcher, client, configfile, tmp_path):
    symlinked_testfiles = tmp_path / 'symlinked' / 'testfiles'
    symlinked_testfiles.mkdir(parents=True, exist_ok=True)
    for f in testfiles.iterdir():
        (symlinked_testfiles / f.name).symlink_to(f)

    runner = CliRunner()
    result = runner.invoke(cli, ['scan', '-p', str(symlinked_testfiles)], catch_exceptions=False)
    assert result.exit_code == 0
    result = runner.invoke(cli, ['add', 'testclient', '-e', str(testfiles / "test.torrent")], catch_exceptions=False)
    assert result.exit_code == 0
    action, kwargs = client._action_queue[0]
    assert action == "add"
    assert symlinked_testfiles.relative_to(kwargs["destination_path"]) == Path('testfiles')


def test_cli_add_symlink_store_path(testfiles, indexer, matcher, client, configfile, tmp_path):
    store_path = tmp_path.resolve() / "symlinked_store_path"
    store_path.symlink_to(configfile.config["autotorrent"]["store_path"])
    configfile.config["autotorrent"]["store_path"] = str(store_path / "{torrent_name}")
    configfile.save_config()

    runner = CliRunner()
    result = runner.invoke(cli, ['scan', '-p', str(testfiles)], catch_exceptions=False)
    assert result.exit_code == 0
    result = runner.invoke(cli, ['add', 'testclient', str(testfiles / "test.torrent")], catch_exceptions=False)
    assert result.exit_code == 0
    action, kwargs = client._action_queue[0]
    assert action == "add"
    assert (store_path / "test" / "data") == kwargs["destination_path"]


def test_cli_add_stopped_state(testfiles, indexer, matcher, client, configfile, tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ['scan', '-p', str(testfiles)], catch_exceptions=False)
    assert result.exit_code == 0
    result = runner.invoke(cli, ['add', 'testclient', '--stopped', '-e', str(testfiles / "test.torrent")], catch_exceptions=False)
    assert result.exit_code == 0
    action, kwargs = client._action_queue[0]
    assert action == "add"
    assert kwargs["stopped"]


def test_cli_add_extreme_limits(testfiles, indexer, matcher, client, configfile, tmp_path):
    configfile.config["autotorrent"]["add_limit_percent"] = 200
    configfile.save_config()

    runner = CliRunner()
    result = runner.invoke(cli, ['add', 'testclient', str(testfiles / "test.torrent")], catch_exceptions=False)
    assert result.exit_code == 0
    action, kwargs = client._action_queue[0]
    assert action == "add"


def test_cli_missing_variable_store_path(testfiles, indexer, matcher, client, configfile, tmp_path):
    store_path = tmp_path / "inaccessible"
    configfile.config["autotorrent"]["store_path"] = str(tmp_path / "garbage")
    configfile.save_config()

    runner = CliRunner()
    result = runner.invoke(cli, ['add', 'testclient', str(testfiles / "test.torrent")], catch_exceptions=False)
    assert result.exit_code == 1


def test_cli_inaccessible_store_path(testfiles, indexer, matcher, client, configfile, tmp_path):
    store_path = tmp_path / "inaccessible"
    store_path.mkdir(mode=0o000)
    try:
        configfile.config["autotorrent"]["store_path"] = str(store_path / "{torrent_name}")
        configfile.save_config()

        runner = CliRunner()
        result = runner.invoke(cli, ['scan', '-p', str(testfiles)], catch_exceptions=False)
        assert result.exit_code == 0
        result = runner.invoke(cli, ['add', 'testclient', str(testfiles / "test.torrent")], catch_exceptions=False)
        assert result.exit_code == 0
    finally:
        store_path.chmod(0o777)



def test_cli_store_path_passed_variables(testfiles, indexer, matcher, client, configfile, tmp_path):
    store_path = tmp_path.resolve() / "store_path"
    configfile.config["autotorrent"]["store_path"] = str(store_path / "{custom_variable}"/ "{torrent_name}")
    configfile.save_config()

    runner = CliRunner()
    result = runner.invoke(cli, ['scan', '-p', str(testfiles)], catch_exceptions=False)
    assert result.exit_code == 0
    result = runner.invoke(cli, ['add', 'testclient', '--store-path-variable', 'custom_variable=smart-choice', '--store-path-variable', 'unused=something', str(testfiles / "test.torrent")], catch_exceptions=False)
    assert result.exit_code == 0

    assert (store_path / "smart-choice" / "test").exists()


def test_cli_store_path_inferred_variables(testfiles, indexer, matcher, client, configfile, tmp_path):
    torrent_data = bdecode((testfiles / "test.torrent").read_bytes())
    torrent_data[b"info"][b"source"] = b"real-source"
    torrent_data[b"announce"] = b"http://example.com/horse?example=1"
    torrent_data[b"announce-list"] = [[b"http://example.com/horse?example=3", b"http://example.com/horse?example=2"]]
    (testfiles / "test.torrent").write_bytes(bencode(torrent_data))

    store_path = tmp_path.resolve() / "store_path"
    configfile.config["autotorrent"]["store_path"] = str(store_path / "{tracker_domain}" / "{torrent_source}" / "{torrent_name}")
    configfile.save_config()

    runner = CliRunner()
    result = runner.invoke(cli, ['scan', '-p', str(testfiles)], catch_exceptions=False)
    assert result.exit_code == 0
    result = runner.invoke(cli, ['add', 'testclient', '--store-path-variable', 'custom_variable=smart-choice', '--store-path-variable', 'unused=something', str(testfiles / "test.torrent")], catch_exceptions=False)
    assert result.exit_code == 0

    assert (store_path / "example.com" / "real-source" / "test").exists()


def test_cli_store_path_missing_in_torrent_variables(testfiles, indexer, matcher, client, configfile, tmp_path):
    torrent_data = bdecode((testfiles / "test.torrent").read_bytes())
    torrent_data[b"announce"] = b"http://example.com/horse?example=1"
    (testfiles / "test.torrent").write_bytes(bencode(torrent_data))

    store_path = tmp_path.resolve() / "store_path"
    configfile.config["autotorrent"]["store_path"] = str(store_path / "{tracker_domain}" / "{torrent_source}" / "{torrent_name}")
    configfile.save_config()

    runner = CliRunner()
    result = runner.invoke(cli, ['scan', '-p', str(testfiles)], catch_exceptions=False)
    assert result.exit_code == 0
    result = runner.invoke(cli, ['add', 'testclient', '--store-path-variable', 'torrent_source=other-source', '--store-path-variable', 'unused=something', str(testfiles / "test.torrent")], catch_exceptions=False)
    assert result.exit_code == 0

    assert (store_path / "example.com" / "other-source" / "test").exists()

def test_cli_inaccessible_scan_path(testfiles, indexer, matcher, client, configfile, tmp_path):
    inaccessible_test_file = testfiles / "inaccessible"
    inaccessible_test_file.mkdir(mode=0o000)
    try:
        runner = CliRunner()
        result = runner.invoke(cli, ['scan', '-p', str(testfiles)], catch_exceptions=False)
        assert result.exit_code == 0
    finally:
        inaccessible_test_file.chmod(0o777)

def test_cli_add_skip_store_metadata_disabled(testfiles, indexer, matcher, client, configfile, tmp_path):
    configfile.config["autotorrent"]["skip_store_metadata"] = False
    configfile.save_config()

    runner = CliRunner()
    result = runner.invoke(cli, ['scan', '-p', str(testfiles)], catch_exceptions=False)
    assert result.exit_code == 0
    result = runner.invoke(cli, ['add', 'testclient', str(testfiles / "test.torrent")], catch_exceptions=False)
    assert result.exit_code == 0
    action, kwargs = client._action_queue[0]
    assert action == "add"
    assert kwargs["destination_path"].name == "data"


def test_cli_add_skip_store_metadata_enabled(testfiles, indexer, matcher, client, configfile, tmp_path):
    configfile.config["autotorrent"]["skip_store_metadata"] = True
    configfile.save_config()

    runner = CliRunner()
    result = runner.invoke(cli, ['scan', '-p', str(testfiles)], catch_exceptions=False)
    assert result.exit_code == 0
    result = runner.invoke(cli, ['add', 'testclient', str(testfiles / "test.torrent")], catch_exceptions=False)
    assert result.exit_code == 0
    action, kwargs = client._action_queue[0]
    assert action == "add"
    assert kwargs["destination_path"].name != "data"