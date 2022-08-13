import hashlib
import logging
import os
import re
import shlex
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import click
import toml
from libtc import (
    BTFailure,
    FailedToExecuteException,
    bdecode,
    bencode,
    parse_clients_from_toml_dict,
)
from libtc.utils import get_tracker_domain

from .__version__ import __version__
from .db import Database
from .exceptions import FailedToCreateLinkException
from .indexer import Indexer
from .matcher import Matcher
from .rw_cache import ReadWriteFileCache
from .utils import (
    FailedToParseTorrentException,
    PathRewriter,
    add_status_formatter,
    create_link_path,
    humanize_bytes,
    parse_torrent,
)

DEFAULT_CONFIG_FILE = """[autotorrent]
database_path = "./autotorrent.db"
link_type = "soft"
always_verify_hash = [ ]
paths = [ ]
same_paths = [ ]
add_limit_size = 128_000_000
add_limit_percent = 5
cache_touched_files = false
rw_file_cache_ttl = 86400
fast_resume = false
ignore_file_patterns = [ ]
ignore_directory_patterns = [ ]
"""

BASE_CONFIG_FILE = """[autotorrent]
database_path = "./autotorrent.db"
link_type = "soft"
always_verify_hash = [
    "*.nfo",
    "*.sfv",
    "*.diz",
]
paths = [ ]
same_paths = [ ]
add_limit_size = 128_000_000
add_limit_percent = 5
store_path = "/mnt/store_path/{client}/{torrent_name}"
skip_store_metadata = false
cache_touched_files = false
# rw_file_cache_chown = "1000:1000"
rw_file_cache_ttl = 86400
rw_file_cache_path = "/mnt/store_path/cache"
# WARNING: setting fast_resume to true can cause errors and problems.
fast_resume = false
ignore_file_patterns = [ ]
ignore_directory_patterns = [ ]

[clients]

"""

logger = logging.getLogger(__name__)


def parse_config_file(path, utf8_compat_mode=False):
    base_config = toml.loads(DEFAULT_CONFIG_FILE)
    config = toml.load(path)
    parsed_config = base_config["autotorrent"]
    parsed_config.update(config["autotorrent"])

    clients = parsed_config["clients"] = parse_clients_from_toml_dict(config)

    database_path = path.parent / Path(parsed_config["database_path"])
    parsed_config["db"] = db = Database(
        database_path, utf8_compat_mode=utf8_compat_mode
    )
    parsed_config["indexer"] = indexer = Indexer(
        db,
        ignore_file_patterns=parsed_config["ignore_file_patterns"],
        ignore_directory_patterns=parsed_config["ignore_directory_patterns"],
    )
    parsed_config["rewriter"] = rewriter = PathRewriter(parsed_config["same_paths"])
    parsed_config["matcher"] = matcher = Matcher(rewriter, db)

    rw_file_cache_chown = parsed_config.get("rw_file_cache_chown")

    if parsed_config.get("cache_touched_files"):
        parsed_config["rw_cache"] = rw_cache = ReadWriteFileCache(
            parsed_config["rw_file_cache_path"],
            parsed_config["rw_file_cache_ttl"],
            rw_file_cache_chown,
        )
    else:
        parsed_config["rw_cache"] = None

    parsed_config["fast_resume"] = parsed_config["fast_resume"]
    parsed_config["always_verify_hash"] = parsed_config["always_verify_hash"]
    parsed_config["paths"] = parsed_config["paths"]

    return parsed_config


def validate_config_path(ctx, param, value):
    if value is not None:  # check given path first
        config_path = Path(value)
        if not config_path.is_file():
            raise click.BadParameter(f"File {value!r} does not exist or is not a file.")
        return config_path

    # check the environment variables
    config_path = os.environ.get("AUTOTORRENT_CONFIG", "")
    if config_path:
        config_path = Path(config_path)
        if config_path.is_dir():
            config_path = config_path / "config.toml"
        if config_path.is_file():
            return config_path

    # path guess order
    # * ./config.toml
    # * ~/.config/autotorrent/config.toml (and windows equivalent)
    config_path = Path("config.toml")
    if config_path.is_file():
        return config_path

    config_parent_path = Path(click.get_app_dir("autotorrent"))
    if not config_parent_path.exists():
        config_parent_path.mkdir(parents=True)

    config_path = config_parent_path / Path("config.toml")
    if not config_path.exists():
        click.echo(
            f"Config file does not exist, creating an empty config file at path: {config_path!s}"
        )
        click.echo("Remember to modify it to actually do anything useful")

        config_path.write_text(BASE_CONFIG_FILE)

    return config_path


@click.group()
@click.option(
    "-c",
    "--config",
    help="Path to config file",
    callback=validate_config_path,
    type=click.Path(exists=True, dir_okay=False),
)
@click.option("-v", "--verbose", help="Verbose logging", flag_value=True, default=False)
@click.option(
    "-u",
    "--utf8-compat-mode",
    help="Try work around utf-8 errors, not recommended",
    flag_value=True,
    default=False,
)
@click.version_option(__version__)
@click.pass_context
def cli(ctx, config, verbose, utf8_compat_mode):
    if verbose:
        logging.basicConfig(
            level=logging.DEBUG, format="%(levelname)s:%(name)s:%(lineno)d:%(message)s"
        )
    # logger.debug(f"Using config file path: {config}")
    ctx.ensure_object(dict)
    ctx.obj.update(parse_config_file(config, utf8_compat_mode=utf8_compat_mode))


@cli.command(help="See what is seeded for a given path.")
@click.option(
    "-s",
    "--summary",
    help="End the listing with a summary",
    flag_value=True,
    default=False,
)
@click.option("-d", "--depth", type=int, default=0)
@click.argument("path", nargs=-1, type=click.Path(exists=True))
@click.pass_context
def ls(ctx, summary, depth, path):
    if path:
        paths = [Path(p) for p in path]
    else:
        paths = Path(".").iterdir()

    matcher = ctx.obj["matcher"]

    stats = {
        "count": 0,
        "total_seed_size": 0,
        "total_size": 0,
    }

    def scan_paths(paths):
        for path in paths:
            p = Path(os.path.abspath(path))
            map_result = matcher.map_path_to_clients(p)
            percent = (
                map_result.total_size
                and int((map_result.seeded_size / map_result.total_size) * 100)
                or 0
            )
            if (
                map_result.total_size == map_result.seeded_size
                and map_result.total_size > 0
            ):
                color = "green"
            elif map_result.seeded_size:
                color = "yellow"
                if percent == 0:
                    percent = 1
                if percent == 100:
                    percent = 99
            else:
                color = "red"

            stats["count"] += 1
            stats["total_size"] += map_result.total_size
            stats["total_seed_size"] += map_result.seeded_size

            click.echo(
                f"[{click.style((str(percent) + '%').rjust(4), fg=color)}] {os.fsencode(path).decode(errors='replace')}"
            )

    def dive_paths(paths, depth):
        if depth <= 0:
            scan_paths(paths)
        else:
            file_paths = []
            dir_paths = []
            for path in paths:
                if path.is_dir():
                    dir_paths.append(path)
                elif path.is_file():
                    file_paths.append(path)

            scan_paths(file_paths)
            for path in dir_paths:
                dive_paths(path.iterdir(), depth - 1)

    dive_paths(paths, depth)

    if summary:
        click.echo(f"Number of paths: {stats['count']}")
        click.echo(f"Total size {humanize_bytes(stats['total_size'])}")
        click.echo(f"Total seed size: {humanize_bytes(stats['total_seed_size'])}")
        click.echo(
            f"Total unseeded size: {humanize_bytes(stats['total_size'] - stats['total_seed_size'])}"
        )


@cli.command(help="Find unseeded paths.")
@click.option(
    "-e",
    "--escape-paths",
    help="Escape the output paths",
    flag_value=True,
    default=False,
)
@click.argument("path", nargs=-1, type=click.Path(exists=True))
@click.pass_context
def find_unseeded(ctx, escape_paths, path):
    if path:
        paths = [Path(p) for p in path]
    else:
        paths = Path(".").iterdir()

    matcher = ctx.obj["matcher"]

    for path in paths:
        p = Path(os.path.abspath(path))
        map_result = matcher.map_path_to_clients(p)
        path_seeds = {}
        for f, mapped_file in map_result.files.items():
            if f.is_symlink():
                continue
            ff = f
            is_seeded = len(mapped_file.clients) > 0
            while p in ff.parents or p == ff:
                if not is_seeded and ff in path_seeds:
                    break
                if path_seeds.get(ff):
                    break
                path_seeds[ff] = is_seeded
                ff = ff.parent
        only_unseeded_paths = set(
            [f for (f, is_seeded) in path_seeds.items() if not is_seeded]
        )
        base_unseeded_paths = []
        for f in only_unseeded_paths:
            if f.parent in only_unseeded_paths:
                continue
            base_unseeded_paths.append(f)
        for unseeded_path in base_unseeded_paths:
            unseeded_path = os.path.abspath(unseeded_path)
            if escape_paths:
                unseeded_path = shlex.quote(unseeded_path)
            click.echo(unseeded_path)


@cli.command(help="Checks if the config file exists and is loadable.")
@click.pass_context
def check_config(ctx):
    click.echo("We made it this far without a crash so the config must be loadable.")


@cli.command(
    help="Remove all torrents seeding data from a path. Does not delete the actual data."
)
@click.option("-l", "--client", help="Remove from a specific client", type=str)
@click.argument("path", nargs=-1, type=click.Path(exists=True), required=True)
@click.pass_context
def rm(ctx, client, path):
    matcher = ctx.obj["matcher"]
    clients = ctx.obj["clients"]
    clients = {
        name: c["client"]
        for (name, c) in clients.items()
        if not client or name == client
    }

    if not clients:
        click.echo("No clients found")
        quit(1)

    infohashes_to_remove = {}
    for orig_p in path:
        p = Path(os.path.abspath(orig_p))
        map_result = matcher.map_path_to_clients(p)
        for mapped_file in map_result.files.values():
            for client_name, infohash in mapped_file.clients:
                if client_name not in clients:
                    continue
                infohashes_to_remove.setdefault(client_name, set()).add(infohash)

    if not infohashes_to_remove:
        click.echo("Nothing found to remove")
        quit()

    for client_name, infohashes in infohashes_to_remove.items():
        click.echo(
            f"Removing {len(infohashes)} torrent{len(infohashes) != 1 and 's' or ''} from {client_name}"
        )
        client = clients[client_name]
        for infohash in infohashes:
            client.remove(infohash)


def validate_store_path_variable(ctx, param, value):
    result = []
    for kw in value:
        k, _, v = kw.partition("=")
        if not v:
            raise click.BadParameter("format must be 'key=value'")
        result.append((k, v))
    return result


@cli.command(help="Add new torrents to a client.")
@click.argument("client", type=str)
@click.option(
    "-e",
    "--exact",
    help='Exact matching mode. Can also be considered a "reseed" mode. Disables all other modes.',
    flag_value=True,
    default=False,
)
@click.option(
    "-s",
    "--hash-probe",
    help="Probe matched files for full pieces to ensure the data matches.",
    flag_value=True,
    default=False,
)
@click.option(
    "-a",
    "--hash-size",
    help="Hash size matching mode, checks for files with same size but different filenames.",
    flag_value=True,
    default=False,
)
@click.option(
    "--print-summary",
    help="Print a summary of all actions when done.",
    flag_value=True,
    default=False,
)
@click.option("--chown", help="Chown the data folder when creating links.", type=str)
@click.option(
    "--dry-run",
    help="Do not actually create links and add the torrents, just check what would happen.",
    flag_value=True,
    default=False,
)
@click.option(
    "--move-torrent-on-add",
    help="Move the torrent to this path after it has been added successfully to the client.",
    type=click.Path(),
)
@click.option(
    "--stopped",
    help="Add the torrent in stopped state.",
    flag_value=True,
    default=False,
)
@click.option(
    "-t",
    "--store-path-template",
    help="Pass a custom template instead of using the one defined in the config file.",
)
@click.option(
    "-v",
    "--store-path-variable",
    help="Variable used for store path using a key=value syntax.",
    callback=validate_store_path_variable,
    multiple=True,
)
@click.argument("torrent", nargs=-1, type=click.Path(exists=True, dir_okay=False))
@click.pass_context  # TODO: allow feedback while running
def add(
    ctx,
    client,
    exact,
    hash_probe,
    hash_size,
    torrent,
    print_summary,
    chown,
    dry_run,
    move_torrent_on_add,
    stopped,
    store_path_template,
    store_path_variable,
):
    torrent_paths = torrent
    client_name = client
    db = ctx.obj["db"]
    matcher = ctx.obj["matcher"]
    rw_cache = ctx.obj["rw_cache"]

    clients = ctx.obj["clients"]
    client = clients.get(client_name)
    if not client:
        raise click.BadParameter(f"Unknown client: {client_name}")
    client = client["client"]
    existing_torrents = {t.infohash: t for t in client.list()}
    store_path_variables = dict(store_path_variable)
    store_path = store_path_template or ctx.obj["store_path"]
    skip_store_metadata = ctx.obj.get("skip_store_metadata", False)

    if not client:
        click.echo(f"Client {client_name} not found found")
        quit(1)

    click.echo(
        f"Matching {len(torrent_paths)} torrent{len(torrent_paths) != 1 and 's' or ''}"
    )

    if not exact and not re.findall(r"\{[^\}]+\}", store_path):
        click.echo(
            f"Store path does not contain any variables and therefore will be the same for each torrent."
        )
        quit(1)

    stats = {"seeded": 0, "added": 0, "exists": 0, "failed": 0, "missing_files": 0}
    for torrent_path in torrent_paths:
        torrent_store_path_variables = dict(store_path_variables)
        torrent_path = Path(torrent_path)
        try:
            torrent_data = bdecode(torrent_path.read_bytes())
            torrent = parse_torrent(torrent_data, utf8_compat_mode=db.utf8_compat_mode)
        except (BTFailure, FailedToParseTorrentException):
            logger.exception("Failed to parse torrent file")
            add_status_formatter("failed", torrent_path, "failed to parse torrent file")
            stats["failed"] += 1
            continue
        if torrent.trackers:
            torrent_store_path_variables["tracker_domain"] = re.sub(
                r"[\\/]", "_", get_tracker_domain(torrent.trackers[0])
            )
        if b"source" in torrent_data[b"info"]:
            torrent_store_path_variables["torrent_source"] = re.sub(
                r"[\\/]", "_", torrent_data[b"info"][b"source"].decode()
            )
        if torrent.has_file_patterns(ctx.obj["ignore_file_patterns"]):
            add_status_formatter(
                "failed",
                torrent_path,
                "file contains ignored patterns and can therefore never be matched",
            )
            stats["failed"] += 1
            continue
        infohash = hashlib.sha1(bencode(torrent_data[b"info"])).hexdigest()
        if infohash in existing_torrents:
            add_status_formatter("seeded", torrent_path, "is already seeded")
            stats["seeded"] += 1
            continue

        found_bad_hash = False
        missing_size = None
        torrent_root_path = None
        if exact:
            torrent_root_path = matcher.match_files_exact(torrent_data)
            if torrent_root_path:
                hash_verify_result, hash_touch_result = torrent.verify_hash(
                    ctx.obj["always_verify_hash"],
                    {tf.path: torrent_root_path / tf.path for tf in torrent.filelist},
                )
                if any(
                    tf
                    for (tf, tf_result) in hash_verify_result.items()
                    if tf_result != "hash-success"
                ):
                    torrent_root_path = None
                    found_bad_hash = True
        else:
            match_result = matcher.match_files_dynamic(
                torrent_data,  # TODO: double parsed here
                match_hash_size=hash_size,
                add_limit_size=ctx.obj["add_limit_size"],
                add_limit_percent=ctx.obj["add_limit_percent"],
                hash_probe=hash_probe,
            )
            missing_size = match_result.missing_size
            if match_result.success:
                hash_verify_result, hash_touch_result = torrent.verify_hash(
                    ctx.obj["always_verify_hash"], match_result.matched_files
                )
                failed_torrent_files = {
                    tf.path: tf
                    for (tf, tf_result) in hash_verify_result.items()
                    if tf_result == "hash-failed"
                }
                missing_size += sum(tf.size for tf in failed_torrent_files.values())
                max_missing_size = min(
                    ctx.obj["add_limit_size"],
                    (ctx.obj["add_limit_percent"] * torrent.size) // 100,
                )
                if max_missing_size > missing_size:
                    if ctx.obj.get("cache_touched_files"):
                        touched_torrent_paths = set(match_result.touched_files) | {
                            tf.path
                            for (tf, tf_result) in hash_touch_result.items()
                            if (
                                tf_result == "touch-success"
                                or tf_result == "touch-failed"
                                and tf.path not in failed_torrent_files
                            )
                        }
                    else:
                        touched_torrent_paths = set()

                    link_file_mapping = {}
                    for (
                        torrent_data_path,
                        actual_path,
                    ) in match_result.matched_files.items():
                        if not actual_path:
                            continue
                        if torrent_data_path in failed_torrent_files:
                            action = "copy"
                        elif torrent_data_path in touched_torrent_paths:
                            action = "cache_link"
                        else:
                            action = "link"

                        link_file_mapping[torrent_data_path] = (action, actual_path)

                    try:
                        create_link_result = create_link_path(
                            store_path,
                            link_file_mapping,
                            client_name,
                            torrent_path,
                            torrent_store_path_variables,
                            ctx.obj["link_type"],
                            rw_cache=rw_cache,
                            chown_str=chown,
                            dry_run=dry_run,
                            skip_store_metadata=skip_store_metadata,
                        )  # TODO: feedback that things take time when caching
                        if dry_run:
                            torrent_root_path = "/tmp/autotorrent_dry_run"
                        else:
                            torrent_root_path = create_link_result.data_path
                    except FailedToCreateLinkException as e:
                        logger.debug(f"Failed to create path: {e}")
                        stats["exists"] += 1
                        add_status_formatter(
                            "exists",
                            torrent_path,
                            "the link folder already exist but this torrent is not seeded by the client",
                        )
                        continue
                    except NotADirectoryError as e:
                        logger.debug(f"Failed to create path: {e}")
                        stats["failed"] += 1
                        add_status_formatter(
                            "failed",
                            torrent_path,
                            "store path is not a folder",
                        )
                        continue
                    except PermissionError as e:
                        logger.debug(f"Failed to create path: {e}")
                        stats["failed"] += 1
                        add_status_formatter(
                            "failed",
                            torrent_path,
                            "permissions on the store path restrict the ability to create links",
                        )
                        continue
                else:
                    found_bad_hash = True

        if torrent_root_path:
            if dry_run:
                add_status_formatter("added", torrent_path, "added")
                stats["added"] += 1
            else:
                try:
                    client.add(
                        torrent_data,
                        torrent_root_path,
                        fast_resume=ctx.obj["fast_resume"],
                        stopped=stopped,
                    )
                except FailedToExecuteException as e:
                    logger.debug(f"Failed to add torrent: {e!r}")
                    add_status_formatter(
                        "failed", torrent_path, "failed to send torrent to client"
                    )
                    stats["failed"] += 1
                else:
                    add_status_formatter("added", torrent_path, "added")
                    stats["added"] += 1
                    if move_torrent_on_add:
                        move_torrent_on_add = Path(move_torrent_on_add)
                        move_torrent_on_add.mkdir(exist_ok=True, parents=True)
                        torrent_path.rename(move_torrent_on_add / torrent_path.name)

        else:
            percentage_info = None
            if missing_size is not None:
                percent = (
                    torrent.size and int((1 - (missing_size / torrent.size)) * 100) or 0
                )
                if missing_size < torrent.size:
                    color = "yellow"
                    if percent == 0:
                        percent = 1
                    if percent == 100:
                        percent = 99
                else:
                    color = "red"
                percentage_info = (
                    f"with {click.style((str(percent) + '%').rjust(3), fg=color)} found"
                )
            add_status_formatter(
                "missing_files",
                torrent_path,
                f"is missing data{percentage_info and ' ' + percentage_info or ''}"
                + (found_bad_hash and " due to bad file hashes" or ""),
            )
            stats["missing_files"] += 1
            continue

    if print_summary:
        click.echo("")
        click.echo("Summary:")
        click.echo(f" Added:          {stats['added']}")
        click.echo(f" Missing files:  {stats['missing_files']}")
        click.echo(f" Failed:         {stats['failed']}")
        click.echo(f" Folder exists:  {stats['exists']}")
        click.echo(f" Already seeded: {stats['seeded']}")
        click.echo(f" Total:          {sum(stats.values())}")


@cli.command(help="Cleanup RW cache for expired items.")
@click.pass_context
def cleanup_cache(ctx):
    rw_cache = ctx.obj["rw_cache"]
    if not rw_cache:
        click.echo("No RW cached configured")
        return

    removed_paths = rw_cache.cleanup_cache()
    click.echo(
        f"Done cleaning up cache, removed {len(removed_paths)} path{len(removed_paths) != 1 and 's' or ''}"
    )


@cli.command(help="Scan your local paths files.")
@click.option(
    "-p",
    "--path",
    help="Partial scan a given path, does not remove removed files from the database.",
    type=click.Path(exists=True),
)
@click.pass_context
def scan(ctx, path):
    indexer = ctx.obj["indexer"]
    if path:
        click.echo(f"Scanning single path {path}")
        indexer.scan_paths([path], full_scan=False)
    else:
        click.echo("Doing full scan")
        indexer.scan_paths(ctx.obj["paths"], full_scan=True)
    click.echo("Done scanning")


@cli.command(help="Scan your clients for files.")
@click.option("-l", "--client", help="Scan a specific client", type=str)
@click.option(
    "-f",
    "--full",
    help="Clear old data and do a full scan",
    flag_value=True,
    default=False,
)
@click.option(
    "-a",
    "--fast",
    help="Run a fast scan, does not detect moved torrents. Overwritten by full",
    flag_value=True,
    default=False,
)
@click.pass_context
def scan_clients(ctx, client, full, fast):
    indexer = ctx.obj["indexer"]
    clients = ctx.obj["clients"]
    clients = {
        name: c["client"]
        for (name, c) in clients.items()
        if not client or name == client
    }

    if not clients:
        click.echo("No clients found")
        quit(1)

    click.echo("Scanning clients")

    indexer.scan_clients(clients, full_scan=full, fast_scan=fast)


@cli.command(help="Test your connection to your clients.")
@click.option("-l", "--client", help="Check a specific client", type=str)
@click.pass_context
def test_connection(ctx, client):
    clients = ctx.obj["clients"]
    if client:
        clients = [c for (name, c) in clients.items() if name == client]
    else:
        clients = clients.values()

    if not clients:
        click.echo("No clients found")
        quit(1)

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = []
        for client in clients:
            futures.append((client, executor.submit(client["client"].test_connection)))

        for client, future in futures:
            if future.result():
                click.echo(f"{click.style('OK ', fg='green')} {client['display_name']}")
            else:
                click.echo(f"{click.style('BAD', fg='red')} {client['display_name']}")


# @cli.command(help="Remove unseeded folders from store paths")
# @click.argument("path", nargs=-1, type=click.Path(exists=True, file_okay=False, dir_okay=True))
# @click.option(
#     "-s",
#     "--skip-scan-clients",
#     help="Do not scan clients for seeded paths before finding unseeded paths.",
#     flag_value=True,
#     default=False,
# )
# @click.pass_context
# def cleanup_store_path(ctx, path, skip_scan_clients):
#     pass

# @cli.command(help="Reseed store paths")
# @click.argument("client", type=str)
# @click.argument("path", nargs=-1, type=click.Path(exists=True, file_okay=False, dir_okay=True))
# @click.option(
#     "-s",
#     "--skip-scan-clients",
#     help="Do not scan clients for seeded paths before finding unseeded paths.",
#     flag_value=True,
#     default=False,
# )
# @click.pass_context
# def reseed_store_path(ctx, path):
#     pass

# @cli.command(help="Build a bundle from torrents that can be distributed to find torrents to seed locally.")
# @click.pass_context
# def build_cross_seed_bundle(ctx):
#     pass


# @cli.command(help="Match a cross seed bundle with your scanned data.")
# @click.pass_context
# def compare_cross_seed_bundle(ctx):
#     pass

if __name__ == "__main__":
    cli()
