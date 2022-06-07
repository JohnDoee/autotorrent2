import logging
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from fnmatch import fnmatch
from pathlib import Path
from queue import SimpleQueue

from .db import InsertTorrentFile
from .utils import get_root_of_unsplitable, is_unsplitable

logger = logging.getLogger(__name__)

INSERT_QUEUE_MAX_SIZE = 1000


class IndexAction(Enum):
    ADD = 1
    MARK_UNSPLITABLE = 2
    FINISHED = 3


class Indexer:
    def __init__(self, db, ignore_file_patterns=None, ignore_directory_patterns=None):
        self.db = db
        self.ignore_file_patterns = ignore_file_patterns or []
        self.ignore_directory_patterns = ignore_directory_patterns or []

    def scan_paths(self, paths, full_scan=True):
        if full_scan:
            self.db.truncate_files()
        paths = [Path(p) for p in paths]
        queue = SimpleQueue()
        live_thread_count = 0
        with ThreadPoolExecutor(max_workers=len(paths) + 1) as executor:
            for path in paths:
                logger.info(f"Indexing path {path}")
                executor.submit(self._scan_path_thread, path, queue, root_thread=True)
                live_thread_count += 1

            while live_thread_count:
                action, args = queue.get()
                if action == IndexAction.ADD:
                    self.db.insert_file_path(*args)
                elif action == IndexAction.MARK_UNSPLITABLE:
                    self.db.mark_unsplitable_root(*args)
                elif action == IndexAction.FINISHED:
                    live_thread_count -= 1

        self.db.commit()

    def _match_ignore_pattern(self, ignore_patterns, p, ignore_case=False):
        name = p.name
        if ignore_case:
            name = name.lower()
        for ignore_pattern in ignore_patterns:
            if ignore_case:
                if fnmatch(name, ignore_pattern.lower()):
                    return True
            else:
                if fnmatch(name, ignore_pattern):
                    return True
        return False

    def _scan_path_thread(self, path, queue, root_thread=False):
        files = []
        for p in path.iterdir():
            if p.is_dir():
                if self._match_ignore_pattern(
                    self.ignore_directory_patterns, p, ignore_case=True
                ):
                    continue
                self._scan_path_thread(p, queue)
            elif p.is_file():
                if self._match_ignore_pattern(self.ignore_file_patterns, p):
                    continue
                files.append(p)
                size = p.stat().st_size
                queue.put((IndexAction.ADD, (p, size)))

        # TODO: probably not utf-8 problems resilient
        if is_unsplitable(files):  # TODO: prevent duplicate work (?)
            unsplitable_root = get_root_of_unsplitable(path)
            queue.put((IndexAction.MARK_UNSPLITABLE, (unsplitable_root,)))

        if root_thread:
            queue.put((IndexAction.FINISHED, ()))

    def scan_clients(self, clients, full_scan=False, fast_scan=False):
        for name, client in clients.items():
            if full_scan:
                self.db.truncate_torrent_files(name)
            self._scan_client(name, client, not full_scan and fast_scan)
        self.db.commit()

    def _scan_client(self, client_name, client, fast_scan):
        torrents = client.list()
        insert_queue = []
        for torrent in torrents:
            _, current_download_path = self.db.get_torrent_file_info(
                client_name, torrent.infohash
            )
            if fast_scan and current_download_path is not None:
                logger.debug(
                    f"torrent:{torrent!r} client:{client!r} Skip indexing because it is already there and fast-scan is enabled"
                )
                continue

            download_path = client.get_download_path(torrent.infohash)
            if str(download_path) == current_download_path:
                logger.debug(
                    f"torrent:{torrent!r} client:{client!r} Skip indexing because download path not changed"
                )
                continue

            files = client.get_files(torrent.infohash)
            if not files:
                logger.debug("No files found, not loaded")
            paths = []
            for f in files:
                f_path = download_path / f.path
                paths.append((str(f_path), f.size))
                f_path_resolved = f_path.resolve()
                if f_path_resolved != f_path:
                    paths.append((str(f_path_resolved), f.size))
            insert_queue.append(
                InsertTorrentFile(torrent.infohash, torrent.name, download_path, paths)
            )
            if len(insert_queue) > INSERT_QUEUE_MAX_SIZE:
                self.db.insert_torrent_files_paths(client_name, insert_queue)
                insert_queue = []
        if insert_queue:
            self.db.insert_torrent_files_paths(client_name, insert_queue)

        self.db.remove_non_existing_infohashes(
            client_name, [torrent.infohash for torrent in torrents]
        )
