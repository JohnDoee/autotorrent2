import logging
import os
import sqlite3
from collections import namedtuple
from pathlib import Path

from .utils import decode_str, normalize_filename

logger = logging.getLogger(__name__)

SeededFile = namedtuple(
    "SeededFile", ["name", "path", "download_path", "infohash", "client", "size"]
)

InsertTorrentFile = namedtuple(
    "InsertTorrentFile", ["infohash", "name", "download_path", "paths"]
)


class SearchedFile(
    namedtuple(
        "SearchedFile", ["name", "path", "size", "normalized_name", "unsplitable_root"]
    )
):
    def to_full_path(self):
        return self.path / self.name


class Database:
    _insert_counter = 0

    def __init__(self, path, utf8_compat_mode=False):
        self.db = sqlite3.connect(path)
        self.utf8_compat_mode = utf8_compat_mode
        self.create_tables()

    def create_tables(self):
        c = self.db.cursor()
        c.execute(
            """CREATE TABLE IF NOT EXISTS files (
            name varchar NOT NULL,
            path varchar NOT NULL,
            size integer NOT NULL,
            normalized_name varchar NOT NULL,
            unsplitable_root varchar,
            UNIQUE(name, path)
        )"""
        )
        c.execute(
            """CREATE INDEX IF NOT EXISTS idx_normalized_name ON files(normalized_name)"""
        )
        c.execute("""CREATE INDEX IF NOT EXISTS idx_size ON files(size)""")
        c.execute(
            """CREATE TABLE IF NOT EXISTS client_torrents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name varchar NOT NULL,
            download_path varchar NOT NULL,
            infohash varchar NOT NULL,
            client varchar NOT NULL,
            UNIQUE(infohash, client)
        )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS client_torrentfiles (
            torrent_id integer NOT NULL,
            path varchar NOT NULL,
            size integer NOT NULL,
            UNIQUE(path, torrent_id)
        )"""
        )
        self.db.commit()

    def commit(self):
        self.db.commit()

    def insert_file_paths(self, iterable):
        """Take an interable that generates a tuple with the three
        fields defined in `create_insert` and normalize them for
        insertion into the DB"""

        def create_insert(args):
            path, size, unsplitable_root = args
            unsplitable_root = str(unsplitable_root)
            decoded_path = decode_str(os.fsencode(path), try_fix=self.utf8_compat_mode)
            if decoded_path is None:
                return None
            name_path, name = os.path.split(decoded_path)
            normalized_name = normalize_filename(name)
            logger.debug(
                f"Inserting name: {name!r} name_path: {name_path!r} size: {size} normalized_name: {normalized_name!r}  unsplitable_root {unsplitable_root!r}"
            )
            return (name, name_path, size, normalized_name, unsplitable_root)

        c = self.db.cursor()
        try:
            c.executemany(
                "INSERT OR IGNORE INTO files (name, path, size, normalized_name, unsplitable_root) VALUES (?, ?, ?, ?, ?)",
                [row for row in map(create_insert, iterable) if row is not None],
            )
        finally:
            c.close()

    def truncate_files(self):
        c = self.db.cursor()
        try:
            c.execute("DELETE FROM files")
        finally:
            c.close()

    def search_file(
        self,
        filename=None,
        size=None,
        path=None,
        normalized_filename=False,
        path_postfix=None,
        is_unsplitable=None,
        unsplitable_root=None,
    ):
        assert (
            filename is not None
            or size is not None
            or path is not None
            or normalized_filename is not None
        ), "must specify at least one argument"
        assert (
            unsplitable_root is None or is_unsplitable is None
        ), "must specify only unsplitable_root or is_unsplitable, not both"
        c = self.db.cursor()
        query, args = [], []
        if normalized_filename:
            query.append("normalized_name = ?")
            args.append(normalize_filename(normalized_filename))

        if filename:
            query.append("name = ?")
            args.append(filename)

        if size is not None:
            query.append("size = ?")
            args.append(size)

        if path is not None:
            query.append("path = ?")
            args.append(str(path))

        if path_postfix:
            path_postfix = str(path_postfix).lstrip(os.sep)
            if path_postfix != ".":
                query.append("path LIKE ?")
                args.append(f"%{os.sep}{path_postfix}")

        if is_unsplitable is not None:
            if is_unsplitable:
                query.append("unsplitable_root IS NOT NULL")
            else:
                query.append("unsplitable_root IS NULL")

        if unsplitable_root is not None:
            query.append("unsplitable_root = ?")
            args.append(str(unsplitable_root))

        query = (
            "SELECT name, path, size, normalized_name, unsplitable_root FROM files WHERE "
            + " AND ".join(query)
        )
        logger.debug(f"Doing query: {query!r} with args: {args!r}")
        return [
            SearchedFile(name, Path(path), size, normalized_name, unsplitable_root)
            for (name, path, size, normalized_name, unsplitable_root) in c.execute(
                query, args
            ).fetchall()
        ]

    def get_torrent_file_info(self, client, infohash):
        c = self.db.cursor()
        torrents = c.execute(
            "SELECT name, download_path FROM client_torrents WHERE client = ? AND infohash = ?",
            (
                client,
                infohash,
            ),
        ).fetchall()
        if not torrents:
            return None, None
        name, download_path = torrents[0]
        return name, Path(download_path)

    def insert_torrent_files_paths(self, client, insert_torrent_files):
        c = self.db.cursor()

        self.remove_torrent_files(
            client, [itf.infohash for itf in insert_torrent_files]
        )
        self.commit()

        c.executemany(
            "INSERT OR IGNORE INTO client_torrents (name, download_path, infohash, client) VALUES (?, ?, ?, ?)",
            [
                (
                    itf.name,
                    decode_str(itf.download_path, try_fix=self.utf8_compat_mode),
                    itf.infohash,
                    client,
                )
                for itf in insert_torrent_files
            ],
        )
        self.commit()

        infohash_id_mapping = dict(
            c.execute(
                f"SELECT infohash, id FROM client_torrents WHERE client = ? AND infohash IN ({','.join(['?'] * len(insert_torrent_files))})",
                (client, *[itf.infohash for itf in insert_torrent_files]),
            ).fetchall()
        )

        for itf in insert_torrent_files:
            insert_args = []
            for path, size in itf.paths:
                path = decode_str(path, try_fix=self.utf8_compat_mode)
                if path is None:
                    continue

                insert_args.append((infohash_id_mapping[itf.infohash], path, size))

            c.executemany(
                "INSERT OR IGNORE INTO client_torrentfiles (torrent_id, path, size) VALUES (?, ?, ?)",
                insert_args,
            )
        self.commit()

    def truncate_torrent_files(self, client=None):
        c = self.db.cursor()
        if client:
            c.execute(
                "DELETE FROM client_torrentfiles WHERE torrent_id IN (SELECT id FROM client_torrents WHERE client = ?)",
                (client,),
            )
            c.execute("DELETE FROM client_torrents WHERE client = ?", (client,))
        else:
            c.execute("DELETE FROM client_torrentfiles")
            c.execute("DELETE FROM client_torrents")
        self.db.commit()

    def remove_torrent_files(self, client, infohashes):
        c = self.db.cursor()
        for (id_,) in c.execute(
            f"SELECT id FROM client_torrents WHERE client = ? AND infohash IN ({','.join(['?'] * len(infohashes))})",
            (client, *infohashes),
        ):
            c.execute("DELETE FROM client_torrents WHERE id = ?", (id_,))
            c.execute("DELETE FROM client_torrentfiles WHERE torrent_id = ?", (id_,))
        self.db.commit()

    def remove_non_existing_infohashes(self, client, infohashes):
        c = self.db.cursor()
        self.remove_torrent_files(
            client,
            [
                infohash
                for infohash, in c.execute(
                    f"SELECT infohash FROM client_torrents WHERE client = ? AND infohash NOT IN ({','.join(['?'] * len(infohashes))})",
                    (client, *infohashes),
                ).fetchall()
            ],
        )

    def get_seeded_paths(self, paths):
        c = self.db.cursor()
        c.execute(
            f"""SELECT name, download_path, infohash, client, path, size FROM client_torrentfiles
                      LEFT JOIN client_torrents ON client_torrents.id = client_torrentfiles.torrent_id
                      WHERE path IN ({','.join(['?'] * len(paths))})""",
            [decode_str(p, try_fix=self.utf8_compat_mode) for p in paths],
        )

        return [
            SeededFile(name, Path(path), download_path, infohash, client, size)
            for (name, download_path, infohash, client, path, size) in c.fetchall()
        ]
