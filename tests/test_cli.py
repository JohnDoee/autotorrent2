import pytest

import libtc

from click.testing import CliRunner

from autotorrent.__main__ import cli

from .fixtures import *

@pytest.mark.parametrize("linktype", ["soft", "hard"]) # test server with reflink support?
def test_cli_add_link_type(testfiles, indexer, matcher, client, configfile, tmp_path, linktype):
    configfile.config["autotorrent"]["link_type"] = linktype
    configfile.config["autotorrent"]["store_path"] = str(tmp_path / "store_path")
    configfile.save_config()

    runner = CliRunner()
    result = runner.invoke(cli, ['scan', '-p', str(testfiles)])
    assert result.exit_code == 0
    result = runner.invoke(cli, ['add', 'testclient', str(testfiles / "test.torrent")])
    assert result.exit_code == 0
    action, kwargs = client._action_queue[0]
    assert action == "add"
    link_file = (kwargs["destination_path"] / "testfiles" / "file_a.txt")
    assert link_file.exists()
    if linktype == "soft":
        assert link_file.is_symlink()
    elif linktype == "hard":
        assert not link_file.is_symlink()
    else:
        raise Exception(f"Unknown link type {linktype}")
