import logging
import os
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from fnmatch import fnmatch
from pathlib import Path
from queue import Empty, SimpleQueue

from .db import InsertTorrentFile
from .utils import get_root_of_unsplitable, is_unsplitable

logger = logging.getLogger(__name__)

INSERT_QUEUE_MAX_SIZE = 1000

SCAN_PATH_QUEUE_TIMEOUT_SECONDS = 10


class PathTrieNode:
    __slots__ = ("children", "is_file", "is_unsplitable", "size")

    def __init__(self):
        self.children = {}
        self.is_file = False  # In a typical string-based trie, this would mark the end of the string
        self.is_unsplitable = False
        self.size = None


class PathTrie:
    def __init__(self):
        self.root = PathTrieNode()

    def insert_path(self, path, size):
        current = self.root
        for segment in path.parts:
            ch = segment
            node = current.children.get(ch)
            if node is None:
                node = PathTrieNode()
                current.children.update({ch: node})
            current = node
        current.is_file = True
        current.size = size

    def mark_unsplitable(self, path):
        current = self.root
        for segment in path.parts:
            current = current.children.get(segment)
        current.is_unsplitable = True

    def walk(self, func):
        """Recursively walk the entire tree, applying `func` to all end
        nodes (which will always be a files)"""
        return self._walk_node(self.root, func, "", None)

    def _walk_node(self, node, func, current_path, unsplitable_root):
        """Provides the recursivity needed to actually walk the tree"""
        directories = []
        files = []
        for name, child in node.children.items():
            if child.is_file:
                files.append((name, child))
            else:
                directories.append((name, child))
        # Descend directory-first to ensure unsplittable roots are applied properly
        for name, child in directories:
            unsplitable_root_for_children = unsplitable_root
            new_path = Path(current_path, name)
            if child.is_unsplitable and unsplitable_root is None:
                unsplitable_root_for_children = new_path
            yield from self._walk_node(
                child, func, new_path, unsplitable_root_for_children
            )
        for name, child in files:
            yield func(child, Path(current_path, name), unsplitable_root)


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
        paths = [Path(p) for p in paths]
        path_tree = PathTrie()
        queue = SimpleQueue()
        futures = {}

        with ThreadPoolExecutor(max_workers=len(paths) + 1) as executor:
            for path in paths:
                logger.info(f"Indexing path {path}")
                futures[str(path)] = executor.submit(
                    self._scan_path_thread, path, queue, root_thread=True
                )

            while len(futures):
                action, args = None, ()
                try:
                    action, args = queue.get(timeout=SCAN_PATH_QUEUE_TIMEOUT_SECONDS)
                except Empty:
                    logger.debug(
                        "No action received from queue in %d seconds, checking threads",
                        SCAN_PATH_QUEUE_TIMEOUT_SECONDS,
                    )
                    for path in list(futures):
                        future = futures[path]
                        if future.done():
                            if future.exception() is not None:
                                logger.error(
                                    f"Thread for path {path} encountered an exception: {future.exception()}"
                                )
                            del futures[path]
                if action == IndexAction.ADD:
                    path_tree.insert_path(*args)
                elif action == IndexAction.MARK_UNSPLITABLE:
                    path_tree.mark_unsplitable(*args)
                elif action == IndexAction.FINISHED:
                    del futures[args]

        # Helper function to modify walk results for DB usage
        def db_insert(child, full_path, unsplitable_root):
            return (str(full_path), child.size, str(unsplitable_root))

        self.db.commit()
        if full_scan:
            self.db.truncate_files()
        self.db.insert_file_paths(path_tree.walk(db_insert))
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
        try:
            for p in os.scandir(path):
                if p.is_dir():
                    if self.ignore_directory_patterns and self._match_ignore_pattern(
                        self.ignore_directory_patterns, Path(p), ignore_case=True
                    ):
                        continue
                    self._scan_path_thread(Path(p), queue)
                elif p.is_file():
                    if self.ignore_file_patterns and self._match_ignore_pattern(
                        self.ignore_file_patterns, Path(p)
                    ):
                        continue
                    files.append(Path(p))
                    size = p.stat().st_size
                    queue.put((IndexAction.ADD, (Path(p), size)))

            # TODO: probably not utf-8 problems resilient
            if is_unsplitable(files):  # TODO: prevent duplicate work (?)
                unsplitable_root = get_root_of_unsplitable(path)
                queue.put((IndexAction.MARK_UNSPLITABLE, (unsplitable_root,)))
        except OSError as e:
            logger.error(f"Failed to scan {path}: {e}")

        if root_thread:
            queue.put((IndexAction.FINISHED, (str(path))))

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
