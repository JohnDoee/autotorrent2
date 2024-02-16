import errno
import hashlib
import json
import logging
import os
import platform
import re
import shutil
from collections import namedtuple
from fnmatch import fnmatch
from pathlib import Path, PurePath

import chardet
import click
from libtc import TorrentProblems

from .exceptions import FailedToCreateLinkException, FailedToParseTorrentException

logger = logging.getLogger(__name__)

UNSPLITABLE_FILE_EXTENSIONS = [
    set([".rar", ".sfv"]),
    set([".rar", ".r00"]),
    set([".mp3", ".sfv"]),
    set([".vob", ".ifo"]),
]
UNSPLITABLE_FILE_MISSABLE = [  # If foldername does not match, these files can be missed
    "*.nfo",
    "*.sfv",
    "*.diz",
    "*.txt",
]

# # Not allowed anywhere in the names
# INVALID_CHARACTERS_NIX = ["/"]
# INVALID_CHARACTERS_WINDOWS = ["/", "<", ">", ":", '"', "\\", "|", "?", "*"]

# # Not allowed as a name or file basename
# INVALID_BASE_NAMES_NIX = []
# INVALID_BASE_NAMES_WINDOWS = [
#     "CON",
#     "PRN",
#     "AUX",
#     "NUL",
#     "COM1",
#     "COM2",
#     "COM3",
#     "COM4",
#     "COM5",
#     "COM6",
#     "COM7",
#     "COM8",
#     "COM9",
#     "LPT1",
#     "LPT2",
#     "LPT3",
#     "LPT4",
#     "LPT5",
#     "LPT6",
#     "LPT7",
#     "LPT8",
#     "LPT9",
# ]

# if os.name == "nt":
#     INVALID_CHARACTERS = INVALID_CHARACTERS_WINDOWS
#     INVALID_BASE_NAMES = INVALID_BASE_NAMES_WINDOWS
# else:
#     INVALID_CHARACTERS = INVALID_CHARACTERS_NIX
#     INVALID_BASE_NAMES = INVALID_BASE_NAMES_NIX

PIECE_SIZE = 20
HASHER_READ_BLOCK_SIZE = 2**18

AUTOTORRENT_CONF_NAME = "autotorrent.json"
STORE_DATA_PATH = "data"


def decode_str(s, try_fix=False):
    orig_s = s
    if not isinstance(s, str) and not isinstance(s, bytes):
        s = str(s)

    if isinstance(s, str):
        try:
            s = s.encode()
        except UnicodeEncodeError:
            if not try_fix:
                return None

    if isinstance(s, bytes):
        try:
            return s.decode()
        except UnicodeDecodeError:
            if not try_fix:
                return None
    else:
        try:
            s = bytes(orig_s)
        except TypeError:
            if not try_fix:
                return None

    encoding = chardet.detect(s)
    if encoding["encoding"]:
        try:
            return s.decode(encoding["encoding"])
        except UnicodeDecodeError:
            pass

    try:
        return os.fsdecode(s)
    except UnicodeDecodeError:
        return s.decode(errors="replace")


def normalize_filename(filename):
    filename = filename.strip(" ")
    name, ext = os.path.splitext(filename)
    name = re.sub(r"[ _.-]+", " ", name)
    return f"{name}{ext}".lower()


def is_unsplitable(files):
    """
    Checks if a list of files can be considered unsplitable, e.g. VOB/IFO or scene release.
    This means the files can only be used in this combination.
    """
    extensions = set(f.suffix.lower() for f in files)
    for exts in UNSPLITABLE_FILE_EXTENSIONS:
        if len(extensions & exts) == len(exts):
            return True

    for f in files:
        if f.name.lower() == "movieobject.bdmv":
            return True

    return False


def can_potentially_miss_in_unsplitable(filepath):
    """
    Checks if a file can be potentially missed in an unsplitable release
    while the release is still usable.
    """
    return re.match(
        r"^((samples?)|(proofs?)|((vob)?sub(title)?s?))$",
        filepath.parent.name,
        re.IGNORECASE,
    ) or any(fnmatch(filepath.name, pattern) for pattern in UNSPLITABLE_FILE_MISSABLE)


def get_root_of_unsplitable(path):
    """
    Scans a path for the actual scene release name, e.g. skipping cd1 folders.

    Returns None if no scene folder could be found
    """
    while path:
        name = path.name
        is_scene_path = re.match(
            r"^((cd[1-9])|(samples?)|(proofs?)|((vob)?sub(title)?s?))$",
            name,
            re.IGNORECASE,
        )
        is_disk_path = re.match(r"^((bdmv)|(disc\d*)|(video_ts))$", name, re.IGNORECASE)
        if (
            not is_disk_path
            and name.lower() == "backup"
            and path.parent.name.lower() == "bdmv"
        ):
            is_disk_path = True

        if not is_scene_path and not is_disk_path:
            return path

        path = path.parent


class PathRewriter:
    def __init__(self, path_mappings):
        self.paths = {}
        self.path_groups = {}
        self.handle_path_mappings(path_mappings)

    def handle_path_mappings(self, path_mappings):
        for i, path_mapping in enumerate(path_mappings):
            for path in path_mapping:
                path = Path(path)
                path_tuple = self._tuplify(path)
                self.paths[path_tuple] = i
                self.path_groups.setdefault(i, []).append(path)

    def rewrite_path(self, path, prefix_match=False):
        postfix_path = None
        orig_path = path
        while path:
            if postfix_path and not prefix_match:  # nothing matched
                break

            path_tuple = self._tuplify(path)
            path_group_id = self.paths.get(path_tuple)
            if path_group_id is not None:
                if postfix_path is None:
                    return list(self.path_groups[path_group_id])
                else:
                    return [p / postfix_path for p in self.path_groups[path_group_id]]

            if postfix_path is None:
                postfix_path = Path(path.name)
            else:
                postfix_path = Path(path.name) / postfix_path

            path = path.parent

        return [orig_path]

    def _tuplify(self, path):
        p = []
        while path.name:
            p.append(path.name)
            path = path.parent
        return tuple(p[::-1])


def validate_path(path):
    return True


def cleanup_torrent_path_segment(path_segment):  # TODO: more here?
    if not path_segment:
        return path_segment
    return path_segment.strip("/")


PieceCalculation = namedtuple(
    "PieceCalculation",
    [
        "start_piece",
        "start_offset",
        "first_complete_piece",
        "end_piece",
        "end_offset",
        "last_complete_piece",
        "pieces",
        "complete_pieces",
    ],
)


class Pieces:
    def __init__(self, piece_length, pieces, start_size=0):
        self.piece_length = piece_length
        if not isinstance(pieces, list):
            pieces = [
                pieces[i : i + PIECE_SIZE] for i in range(0, len(pieces), PIECE_SIZE)
            ]
        self.pieces = pieces
        self.start_size = start_size

    def __getitem__(self, key):
        if not isinstance(key, slice):
            raise TypeError("Must be a slice")

        if not isinstance(key.start, int):
            raise TypeError("The start must be an integer")

        if key.stop is not None:
            raise TypeError("The stop must be None")

        if key.step is not None:
            raise TypeError("The step must be None")

        return self.__class__(
            self.piece_length, self.pieces, self.start_size + key.start
        )

    def hash_piece(self, f):
        """Hashes a full piece from a single file, returns the hash-digest"""
        missing_size = self.piece_length
        hasher = hashlib.sha1()
        logger.debug(f"Trying to read {missing_size} bytes")

        while missing_size:
            d = f.read(min(16384, missing_size))
            if not d:
                logger.warning(
                    f"We expected to be able to read more data with missing size {missing_size}, bailing"
                )
                return None
            missing_size -= len(d)
            hasher.update(d)

        return hasher.digest()

    def calculate_offsets(self, size, is_last_file=False):
        start_piece, start_offset = divmod(self.start_size, self.piece_length)
        first_complete_piece = start_piece
        if start_offset:
            first_complete_piece += 1
            start_offset = self.piece_length - start_offset

        end_size = self.start_size + size
        end_piece, end_offset = divmod(end_size, self.piece_length)
        last_complete_piece = end_piece
        if end_offset and not is_last_file:
            last_complete_piece -= 1

        piece_calculation = PieceCalculation(
            start_piece,
            start_offset,
            first_complete_piece,
            end_piece,
            end_offset,
            last_complete_piece,
            self.pieces[start_piece : end_piece + 1],
            self.pieces[first_complete_piece : last_complete_piece + 1],
        )
        logger.debug(
            f"Piece calculation start_piece: {piece_calculation.start_piece} "
            f"start_offset: {piece_calculation.start_offset} "
            f"first_complete_piece: {piece_calculation.first_complete_piece} "
            f"end_piece: {piece_calculation.end_piece} "
            f"end_offset: {piece_calculation.end_offset} "
            f"last_complete_piece: {piece_calculation.last_complete_piece}"
        )
        return piece_calculation

    def probe_hash(self, size, fp):
        """
        Test a few pieces against the file if possible.

        Returns True if passed, False if failed, None if not possible
        """
        piece_calculation = self.calculate_offsets(size)
        if not piece_calculation.complete_pieces:
            return None

        pieces_to_verify = set([0])
        if len(piece_calculation.complete_pieces) > 1:
            pieces_to_verify.add(len(piece_calculation.complete_pieces) - 1)

        for piece in pieces_to_verify:
            fp.seek(piece_calculation.start_offset + piece * self.piece_length)
            if self.hash_piece(fp) != piece_calculation.complete_pieces[piece]:
                return False

        return True


class Torrent(
    namedtuple(
        "Torrent",
        ["name", "size", "piece_length", "filelist", "filelist_mapped", "trackers"],
    )
):
    def is_problematic(self):
        # TODO: check if the torrent can cause problems with some clients
        return False

    def verify_hash(self, fnmatches, file_mapping):
        """Returns a torrent_file mapping of failed and successful matched files"""
        # loop files, build list of pieces to verify
        pieces_to_verify = set()
        missing_pieces = set()
        for torrent_file in self.filelist:
            piece_calculation = torrent_file.pieces.calculate_offsets(
                torrent_file.size, is_last_file=torrent_file.is_last_file
            )
            torrent_file_pieces = set(
                range(piece_calculation.start_piece, piece_calculation.end_piece + 1)
            )
            for pattern in fnmatches:
                if fnmatch(torrent_file.path.name, pattern):
                    pieces_to_verify |= torrent_file_pieces
                    break
            else:
                if not file_mapping[torrent_file.path]:
                    missing_pieces |= torrent_file_pieces

        piece_status = {}
        file_piece_mapping = {}
        file_has_inner_pieces = {}
        hasher, hasher_piece, data_left, fp, skip_to_piece = (
            None,
            None,
            None,
            None,
            None,
        )
        for torrent_file in self.filelist:
            piece_calculation = torrent_file.pieces.calculate_offsets(
                torrent_file.size, is_last_file=torrent_file.is_last_file
            )
            file_has_inner_pieces[torrent_file] = (
                piece_calculation.first_complete_piece
                <= piece_calculation.last_complete_piece
            )
            full_path = file_mapping[torrent_file.path]
            if not full_path:
                piece_status[piece_calculation.start_piece] = None
                piece_status[piece_calculation.end_piece] = None
                skip_to_piece = piece_calculation.end_piece + 1
                continue

            for piece_index, piece in enumerate(
                piece_calculation.pieces, piece_calculation.start_piece
            ):
                file_piece_mapping.setdefault(piece_index, []).append(torrent_file)
                if skip_to_piece is not None and skip_to_piece > piece_index:
                    continue

                if piece_index not in pieces_to_verify:
                    continue

                if piece_index in piece_status:
                    continue

                if piece_index > piece_calculation.start_piece:
                    expected_tell = piece_calculation.start_offset + (
                        (piece_index - piece_calculation.first_complete_piece)
                        * self.piece_length
                    )
                else:
                    expected_tell = 0

                if not fp:
                    fp = full_path.open("rb")
                    if expected_tell:
                        fp.seek(expected_tell)

                if hasher_piece != piece_index:
                    hasher = hashlib.new("sha1", usedforsecurity=False)
                    hasher_piece = piece_index
                    data_left = min(
                        self.size - (piece_index * self.piece_length), self.piece_length
                    )
                    if fp.tell() != expected_tell:
                        fp.seek(expected_tell)

                while data_left > 0:
                    data = fp.read(min(HASHER_READ_BLOCK_SIZE, data_left))
                    hasher.update(data)
                    data_left -= len(data)
                    if not data:
                        break

                if data_left == 0:
                    piece_status[hasher_piece] = hasher.digest() == piece
                    if not piece_status[hasher_piece]:
                        skip_to_piece = piece_calculation.end_piece

            if fp:
                fp.close()
                fp = None

        file_status_mapping = {}
        for torrent_file in self.filelist:
            for pattern in fnmatches:
                if fnmatch(torrent_file.path.name, pattern):
                    piece_calculation = torrent_file.pieces.calculate_offsets(
                        torrent_file.size, is_last_file=torrent_file.is_last_file
                    )

                    inner_piece_status = [
                        piece_status.get(p)
                        for p in range(
                            piece_calculation.first_complete_piece,
                            piece_calculation.last_complete_piece + 1,
                        )
                    ]
                    edge_piece_status = []
                    if (
                        piece_calculation.start_piece
                        != piece_calculation.first_complete_piece
                    ):
                        edge_piece_status.append(
                            piece_status.get(piece_calculation.start_piece)
                        )
                        # check other files in same piece
                    if (
                        piece_calculation.end_piece
                        != piece_calculation.last_complete_piece
                    ):
                        edge_piece_status.append(
                            piece_status.get(piece_calculation.end_piece)
                        )

                    if (
                        inner_piece_status
                        and all(inner_piece_status)
                        and all([p != False for p in edge_piece_status])
                    ):
                        file_status_mapping[torrent_file] = "hash-success"
                    elif not inner_piece_status and all(edge_piece_status):
                        file_status_mapping[torrent_file] = "hash-success"
                    elif (
                        inner_piece_status
                        and all(inner_piece_status)
                        and all(
                            [
                                file_has_inner_pieces[tf]
                                for tf in file_piece_mapping[
                                    piece_calculation.start_piece
                                ]
                            ]
                        )
                        and all(
                            [
                                file_has_inner_pieces[tf]
                                for tf in file_piece_mapping[
                                    piece_calculation.end_piece
                                ]
                            ]
                        )
                    ):
                        file_status_mapping[torrent_file] = "hash-success"
                    else:
                        file_status_mapping[torrent_file] = "hash-failed"

                    break

        file_touch_status_mapping = {}
        for torrent_file in self.filelist:
            # if hash-failed or any pieces are failed, then it is touch-failed
            # if any of the files in any of the pieces are missing, then it is touched-success
            piece_calculation = torrent_file.pieces.calculate_offsets(
                torrent_file.size, is_last_file=torrent_file.is_last_file
            )
            file_piece_results = {
                piece_status[p]
                for p in range(
                    piece_calculation.start_piece, piece_calculation.end_piece + 1
                )
                if p in piece_status
            }
            if (
                file_status_mapping.get(torrent_file) == "hash-failed"
                or False in file_piece_results
            ):
                file_touch_status_mapping[torrent_file] = "touch-failed"
            elif None in file_piece_results:
                file_touch_status_mapping[torrent_file] = "touch-success"

        return file_status_mapping, file_touch_status_mapping

    def has_file_patterns(self, patterns):
        for torrent_file in self.filelist:
            for pattern in patterns:
                if fnmatch(torrent_file.path.name, pattern):
                    return True
        return False


TorrentFile = namedtuple(
    "TorrentFile", ["path", "size", "pieces", "is_last_file"], defaults=(False,)
)


def parse_torrent(
    torrent, utf8_compat_mode=False
):  # TODO: validate path, add support for transmission rewrite?
    if b"info" not in torrent:
        raise FailedToParseTorrentException("Info dict not found")
    info = torrent[b"info"]
    name = cleanup_torrent_path_segment(
        decode_str(info[b"name"], try_fix=utf8_compat_mode)
    )
    if name is None:
        raise FailedToParseTorrentException("Unable to parse name of torrent")

    pieces = Pieces(info[b"piece length"], info[b"pieces"])
    length = 0
    filelist = []
    if b"files" in info:
        last_i = len(info[b"files"]) - 1
        for i, f in enumerate(info[b"files"]):
            path = [
                cleanup_torrent_path_segment(decode_str(p, try_fix=utf8_compat_mode))
                for p in f[b"path"]
                if p
            ]
            if any(p is None for p in path):
                raise FailedToParseTorrentException(
                    "Broken path elements found in torrent, try utf-8 compat mode"
                )
            if not path:
                raise FailedToParseTorrentException("Empty path")
            if any(p is None for p in path):
                raise FailedToParseTorrentException(
                    "Invalid encoding in torrent file path"
                )
            if any(not validate_path(p) for p in path):
                raise FailedToParseTorrentException(
                    "Illegal entry in torrent file path"
                )

            path = os.path.sep.join([name] + path)
            filelist.append(
                TorrentFile(
                    PurePath(path),
                    f[b"length"],
                    pieces[length:],
                    is_last_file=(i == last_i),
                )
            )
            length += f[b"length"]
    else:
        filelist.append(
            TorrentFile(PurePath(name), info[b"length"], pieces, is_last_file=True)
        )
        length += info[b"length"]

    filelist_mapped = {f.path: f for f in filelist}

    trackers = [torrent.get(b"announce", b"").decode()]
    for tracker_group in torrent.get(b"announce-list", []):
        if not isinstance(tracker_group, list):
            tracker_group = [tracker_group]
        for tracker in tracker_group:
            if not isinstance(tracker, bytes):
                continue
            tracker = tracker.decode()
            if tracker not in trackers:
                trackers.append(trackers)
    trackers = [t for t in trackers if t]
    return Torrent(
        name, length, info[b"piece length"], filelist, filelist_mapped, trackers
    )


CreateLinkResult = namedtuple(
    "CreateLinkResult", ["path", "torrent_path", "config_path", "data_path"]
)


def _parse_chown(chown):
    chown = chown.split(":")
    chown_user = chown[0] or None
    if len(chown) > 1:
        chown_group = chown[1] or None
    else:
        chown_group = None

    try:
        uid = int(chown_user)
    except ValueError:
        uid = shutil._get_uid(chown_user)
        if uid is None:
            uid = -1

    try:
        gid = int(chown_group)
    except ValueError:
        gid = shutil._get_gid(chown_group)
        if gid is None:
            gid = -1
    return uid, gid


def chown(chown_str, path):
    chown_user, chown_group = _parse_chown(chown_str)
    if chown_user == -1 and chown_group == -1:
        return

    logger.debug(f"Got permissions chown_user={chown_user} chown_group={chown_group}")

    def walk(path):
        yield path

        if path.is_dir():
            for p in Path(path).iterdir():
                if p.is_dir() and not p.is_symlink():
                    yield from walk(p)
                else:
                    yield p

    for p in walk(path):
        logger.debug(f"Changing permission for {p}")
        os.chown(p, chown_user, chown_group, follow_symlinks=False)


def create_link_path(
    store_path_template,
    file_mapping,
    client_name,
    torrent_file_path,
    additional_kwargs,
    link_type,
    rw_cache=None,
    chown_str=None,
    dry_run=False,
    skip_store_metadata=False,
):
    kwargs = {
        "client": client_name,
        "torrent_name": torrent_file_path.stem,
    }
    kwargs.update(additional_kwargs)
    store_path = Path(store_path_template.format(**kwargs))

    if dry_run:
        if store_path.exists():
            raise FailedToCreateLinkException(f"Path {store_path} already exist")
        else:
            return None

    try:
        store_path.mkdir(parents=True)
    except FileExistsError:
        raise FailedToCreateLinkException(f"Path {store_path} already exist")

    if skip_store_metadata:
        data_store_path = store_path
        torrent_store_path = None
        autotorrent_store_path = None
    else:
        data_store_path = store_path / STORE_DATA_PATH
        data_store_path.mkdir()

        torrent_store_path = store_path / torrent_file_path.name
        shutil.copy(torrent_file_path, torrent_store_path)

        autotorrent_store_path = store_path / AUTOTORRENT_CONF_NAME
        autotorrent_store_path.write_text(json.dumps({}))

    for torrent_path, (action, actual_path) in file_mapping.items():
        link_path = data_store_path / torrent_path
        link_path.parent.mkdir(exist_ok=True, parents=True)
        if action == "link" or action == "cache_link":
            if rw_cache and action == "cache_link":
                actual_path = rw_cache.cache_file(actual_path, link_path, link_type)

            create_link(actual_path, link_path, link_type)
        elif action == "copy":
            shutil.copyfile(actual_path, link_path)

    if chown_str:
        chown(chown_str, data_store_path)

    return CreateLinkResult(
        store_path, torrent_store_path, autotorrent_store_path, data_store_path
    )


def create_link(actual_path, link_path, link_type):
    if link_type == "soft":
        link_path.symlink_to(actual_path)
    elif link_type == "hard":
        os.link(actual_path, link_path)
    elif link_type == "reflink":
        reflink(str(actual_path), str(link_path))


def reflink(path, destination):
    """
    Perform a reflink (if supported, currently only xfs, apfs, btrfs is)
    This code is modified from dvc (https://github.com/iterative/dvc/blob/f4bec650eddc8874b3f7ab2f8b34bc5dfe60fd49/dvc/system.py#L105).
    These libraries are available under the Apache 2.0 license, which can be obtained from http://www.apache.org/licenses/LICENSE-2.0.
    """
    system = platform.system()
    logger.debug(f"platform is {system}")
    try:
        if system == "Windows":
            ret = _reflink_windows(path, destination)
        elif system == "Darwin":
            ret = _reflink_darwin(path, destination)
        elif system == "Linux":
            ret = _reflink_linux(path, destination)
        else:
            ret = -1
    except IOError:
        ret = -1

    if ret != 0:
        raise Exception("reflink is not supported")


def _reflink_linux(path, destination):
    """
    Linux only reflink via syscall FICLONE on supported filesystems
    """
    import fcntl
    import os

    FICLONE = 0x40049409

    try:
        ret = 255
        with open(path, "r") as s, open(destination, "w+") as d:
            ret = fcntl.ioctl(d.fileno(), FICLONE, s.fileno())
    finally:
        if ret != 0:
            os.unlink(destination)

    return ret


def _reflink_windows(self, path, destination):
    return -1


def _reflink_darwin(self, path, destination):
    import ctypes

    LIBC = "libc.dylib"
    LIBC_FALLBACK = "/usr/lib/libSystem.dylib"
    try:
        clib = ctypes.CDLL(LIBC)
    except OSError as exc:
        logger.debug(
            f"unable to access '{LIBC}' (errno '{exc.errno}'). Falling back to '{LIBC_FALLBACK}'."
        )
        if exc.errno != errno.ENOENT:
            raise
        # NOTE: trying to bypass System Integrity Protection (SIP)
        clib = ctypes.CDLL(LIBC_FALLBACK)

    if not hasattr(clib, "clonefile"):
        return -1

    clonefile = clib.clonefile
    clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    clonefile.restype = ctypes.c_int

    return clonefile(
        ctypes.c_char_p(path.encode("utf-8")),
        ctypes.c_char_p(destination.encode("utf-8")),
        ctypes.c_int(0),
    )


def humanize_bytes(
    bytes, precision=1
):  # All credit goes to: http://code.activestate.com/recipes/577081-humanized-representation-of-a-number-of-bytes/
    """Return a humanized string representation of a number of bytes.
    >>> humanize_bytes(1)
    '1 byte'
    >>> humanize_bytes(1024)
    '1.0 kB'
    >>> humanize_bytes(1024*123)
    '123.0 kB'
    >>> humanize_bytes(1024*12342)
    '12.1 MB'
    >>> humanize_bytes(1024*12342,2)
    '12.05 MB'
    >>> humanize_bytes(1024*1234,2)
    '1.21 MB'
    >>> humanize_bytes(1024*1234*1111,2)
    '1.31 GB'
    >>> humanize_bytes(1024*1234*1111,1)
    '1.3 GB'
    """
    abbrevs = (
        (1 << 50, "PB"),
        (1 << 40, "TB"),
        (1 << 30, "GB"),
        (1 << 20, "MB"),
        (1 << 10, "kB"),
        (1, "bytes"),
    )
    if bytes == 1:
        return "1 byte"
    for factor, suffix in abbrevs:
        if bytes >= factor:
            break
    return "%.*f %s" % (precision, bytes / factor, suffix)


def add_status_formatter(status, torrent_path, message):
    status_specs = {
        "seeded": ["blue", "Seeded"],
        "exists": ["yellow", "Exists"],
        "missing_files": ["red", "Missing"],
        "failed": ["magenta", "Failed"],
        "added": ["green", "Added"],
    }
    status_spec = status_specs[status]

    status_msg = f"[{click.style(status_spec[1], fg=status_spec[0])}]"
    click.echo(f" {status_msg:18s} {torrent_path.name!r} {message}")
