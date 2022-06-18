import errno
import logging
import os
from collections import namedtuple
from math import ceil
from pathlib import Path

from .utils import (
    can_potentially_miss_in_unsplitable,
    get_root_of_unsplitable,
    is_unsplitable,
    parse_torrent,
)

MatchedFile = namedtuple("MatchedFile", ["torrent_file", "searched_files"])
MatchResult = namedtuple("MatchResult", ["root_path", "matched_files", "size"])
MappedFile = namedtuple("MappedFile", ["size", "clients"])
MapResult = namedtuple("MapResult", ["total_size", "seeded_size", "files"])
DynamicMatchResult = namedtuple(
    "DynamicMatchResult", ["success", "missing_size", "matched_files", "touched_files"]
)

logger = logging.getLogger(__name__)

EXACT_MATCH_FACTOR = 0.05


def is_relative_to(path, *other):
    """Return True if the path is relative to another path or False."""
    try:
        path.relative_to(*other)
        return True
    except ValueError:
        return False


class Matcher:
    def __init__(self, rewriter, db):
        self.rewriter = rewriter
        self.db = db

    def _match_filelist_exact(
        self,
        filelist,
        skip_prefix_path=None,
        match_normalized_filename=False,
    ):
        if skip_prefix_path:
            skip_prefix_path = Path(skip_prefix_path.strip(os.sep))
            filelist = [f for f in filelist if is_relative_to(f.path, skip_prefix_path)]
        filelist = sorted(
            filelist,
            key=lambda f: (not can_potentially_miss_in_unsplitable(f.path), f.size),
            reverse=True,
        )

        if not filelist:
            logger.warning(
                f"Empty filelist, bailing - skip_prefix_path:{skip_prefix_path}"
            )
            return None

        handled_root_paths = set()
        match_results = []
        for search_file in filelist[: ceil(len(filelist) * EXACT_MATCH_FACTOR)]:
            path_postfix = search_file.path.parent
            if match_normalized_filename:
                entry_matched_files = self.db.search_file(
                    normalized_filename=search_file.path.name,
                    size=search_file.size,
                    path_postfix=path_postfix,
                )
            else:
                entry_matched_files = self.db.search_file(
                    filename=search_file.path.name,
                    size=search_file.size,
                    path_postfix=path_postfix,
                )
            for entry_matched_file in entry_matched_files:
                if search_file.path:
                    root_path = entry_matched_file.path
                    for _ in search_file.path.parts[1:]:
                        root_path = root_path.parent
                else:
                    root_path = entry_matched_file.path
                if root_path in handled_root_paths:
                    logger.debug(
                        f"Skipping scan of root_path {handled_root_paths} for matches"
                    )
                    continue
                handled_root_paths.add(root_path)
                logger.debug(f"Scanning root_path {root_path} for matches")

                matched_files = [MatchedFile(search_file, [entry_matched_file])]
                matched_file_size = entry_matched_file.size
                for f in filelist:
                    if f == search_file:
                        continue
                    f_path = root_path / f.path
                    f_name = f_path.name
                    f_path = f_path.parent
                    if match_normalized_filename:
                        search_result = self.db.search_file(
                            normalized_filename=f_name, size=f.size, path=f_path
                        )
                    else:
                        search_result = self.db.search_file(
                            filename=f_name, size=f.size, path=f_path
                        )
                    matched_files.append(MatchedFile(f, search_result))
                    if search_result:
                        matched_file_size += f.size
                match_results.append(
                    MatchResult(root_path, matched_files, matched_file_size)
                )

        return match_results

    def _match_filelist_unsplitable(
        self,
        filelist,
        skip_prefix_path=None,
        match_normalized_filename=False,
    ):
        if skip_prefix_path:
            skip_prefix_path = Path(skip_prefix_path.strip(os.sep))
            filelist = [f for f in filelist if is_relative_to(f.path, skip_prefix_path)]
        filelist = sorted(
            filelist,
            key=lambda f: (not can_potentially_miss_in_unsplitable(f.path), f.size),
            reverse=True,
        )

        if not filelist:
            logger.warning(
                f"Empty filelist, bailing - skip_prefix_path:{skip_prefix_path}"
            )
            return None

        handled_root_paths = set()
        match_results = []
        for search_file in filelist[: ceil(len(filelist) * EXACT_MATCH_FACTOR)]:
            relative_path = search_file.path.relative_to(skip_prefix_path)
            if match_normalized_filename:
                entry_matched_files = self.db.search_file(
                    normalized_filename=search_file.path.name,
                    size=search_file.size,
                    path_postfix=relative_path.parent,
                )
            else:
                entry_matched_files = self.db.search_file(
                    filename=search_file.path.name,
                    size=search_file.size,
                    path_postfix=relative_path.parent,
                )

            for entry_matched_file in entry_matched_files:
                root_path = entry_matched_file.path
                for _ in range(len(relative_path.parts) - 1):
                    root_path = root_path.parent
                if root_path in handled_root_paths:
                    logger.debug(
                        f"Skipping scan of root_path {handled_root_paths} for matches"
                    )
                    continue
                handled_root_paths.add(root_path)

                root_path_is_correct_name = root_path.name == skip_prefix_path.name
                logger.debug(
                    f"Scanning root_path {root_path} for matches with root_path_is_correct_name={root_path_is_correct_name}"
                )

                matched_files = [MatchedFile(search_file, [entry_matched_file])]
                matched_file_size = entry_matched_file.size

                bad_path_found = False
                for f in filelist:
                    if f == search_file:
                        continue
                    f_path = root_path / f.path.relative_to(skip_prefix_path)
                    f_name = f_path.name
                    f_path = f_path.parent
                    if match_normalized_filename:
                        search_result = self.db.search_file(
                            normalized_filename=f_name, size=f.size, path=f_path
                        )
                    else:
                        search_result = self.db.search_file(
                            filename=f_name, size=f.size, path=f_path
                        )
                    matched_files.append(MatchedFile(f, search_result))
                    if search_result:
                        matched_file_size += f.size

                    if (
                        not search_result
                        and not root_path_is_correct_name
                        and not can_potentially_miss_in_unsplitable(f.path)
                    ):
                        bad_path_found = True
                        break

                if bad_path_found:
                    logger.debug(f"Bad path found wit root_path={root_path}")
                    continue

                match_results.append(
                    MatchResult(root_path, matched_files, matched_file_size)
                )

        return match_results

    def _match_best_file(
        self,
        torrent,
        torrent_file,
        searched_files,
        hash_probe=False,
        match_hash_size=False,
    ):
        searched_files = sorted(
            searched_files, key=lambda x: x.name == torrent_file.path.name, reverse=True
        )
        for searched_file in searched_files:
            if hash_probe:
                searched_file_path = searched_file.path / searched_file.name
                with searched_file_path.open("rb") as fp:
                    matched_hash_probe = torrent_file.pieces.probe_hash(
                        searched_file.size, fp
                    )
                    if (
                        matched_hash_probe is False
                        or not matched_hash_probe
                        and match_hash_size
                    ):
                        logger.debug(
                            f"File {searched_file_path} matched against {torrent_file.path} failed hash probe, skipping"
                        )
                        continue
            return searched_file
        return None

    def _select_best_candidate(
        self, torrent, candidates, hash_probe=False, match_hash_size=False
    ):
        evaluated_candidates = []
        for match_result in candidates:
            candidate_result = {}
            for matched_file in match_result.matched_files:
                candidate_result[
                    matched_file.torrent_file.path
                ] = self._match_best_file(
                    torrent,
                    matched_file.torrent_file,
                    matched_file.searched_files,
                    hash_probe=hash_probe,
                    match_hash_size=match_hash_size,
                )
            evaluated_candidates.append(candidate_result)
        return sorted(
            evaluated_candidates,
            key=lambda x: sum(y.size for y in x.values() if y is not None),
            reverse=True,
        )[0]

    def match_files_exact(self, torrent):
        torrent = parse_torrent(torrent, utf8_compat_mode=self.db.utf8_compat_mode)
        logger.info(f"Doing exact lookup for {torrent}")
        match_results = self._match_filelist_exact(torrent.filelist)
        usable_match_results = []
        for match_result in match_results:
            if any(
                not matched_file.searched_files
                for matched_file in match_result.matched_files
            ):
                logger.debug("Match with missing files found, skipping")
                continue
            usable_match_results.append(match_result)
        if not usable_match_results:
            logger.info(f"No exact match found for {torrent}")
            return None

        return usable_match_results[0].root_path

    def match_files_dynamic(
        self,
        torrent,
        match_hash_size=False,
        add_limit_size=0,
        add_limit_percent=0,
        hash_probe=False,
    ):
        if match_hash_size:
            hash_probe = True
        torrent = parse_torrent(torrent, utf8_compat_mode=self.db.utf8_compat_mode)

        path_files = {}
        for f in torrent.filelist:
            path_files.setdefault(f.path.parent, []).append(f)

        unsplitable_roots = set()
        for path, files in path_files.items():
            parts = path.parts
            while parts:
                if parts in unsplitable_roots:
                    break
                parts = parts[:-1]
            else:
                if is_unsplitable([f.path for f in files]):
                    unsplitable_root = get_root_of_unsplitable(Path(path))
                    unsplitable_roots.add(unsplitable_root.parts)

        best_possible_size = 0
        candidate_paths = {}
        for unsplitable_root in unsplitable_roots:
            # Unsplitable paths cannot be matched with hash_size, this is
            # because it will often contain lots of file of the same size
            # and there would be too many candidates.
            # match_results = self._match_filelist_exact(
            #     torrent.filelist,
            #     skip_prefix_path=os.path.sep.join(unsplitable_root),
            #     match_normalized_filename=True,
            # )
            match_results = self._match_filelist_unsplitable(
                torrent.filelist,
                skip_prefix_path=os.path.sep.join(unsplitable_root),
                match_normalized_filename=True,
            )
            candidate_paths[unsplitable_root] = sorted(
                match_results, key=lambda x: -x.size
            )
            if candidate_paths[unsplitable_root]:
                best_possible_size += candidate_paths[unsplitable_root][0].size

        candidate_files = {}
        for path, files in path_files.items():
            parts = path.parts
            while parts:
                if parts in unsplitable_roots:
                    break
                parts = parts[:-1]
            else:
                for torrent_file in files:
                    if match_hash_size:
                        searched_files = self.db.search_file(size=torrent_file.size)
                    else:
                        searched_files = self.db.search_file(
                            normalized_filename=torrent_file.path.name,
                            size=torrent_file.size,
                        )
                    candidate_files[torrent_file.path] = (torrent_file, searched_files)
                    if searched_files:
                        best_possible_size += torrent_file.size

        max_missing_size = min(
            add_limit_size, (add_limit_percent * torrent.size) // 100
        )
        current_missing_size = torrent.size - best_possible_size
        if current_missing_size > max_missing_size:
            logger.info(
                f"Torrent missing too much data, size:{torrent.size}, found data size:{best_possible_size}"
            )
            return DynamicMatchResult(False, current_missing_size, None, None)

        result_mapping = {}
        for path, candidates in candidate_paths.items():
            result_mapping.update(
                self._select_best_candidate(
                    torrent,
                    candidates,
                    hash_probe=hash_probe,
                    match_hash_size=match_hash_size,
                )
            )

        for path, (torrent_file, searched_files) in candidate_files.items():
            result_mapping[torrent_file.path] = self._match_best_file(
                torrent,
                torrent_file,
                searched_files,
                hash_probe=hash_probe,
                match_hash_size=match_hash_size,
            )

        missing_pieces = set()
        found_pieces = set()
        found_file_piece_mapping = {}
        current_missing_size = 0
        for torrent_file in torrent.filelist:
            piece_calculation = torrent_file.pieces.calculate_offsets(torrent_file.size)
            if result_mapping[torrent_file.path]:
                found_pieces.add(piece_calculation.start_piece)
                found_pieces.add(piece_calculation.end_piece)
                found_file_piece_mapping.setdefault(
                    piece_calculation.start_piece, []
                ).append(torrent_file.path)
                found_file_piece_mapping.setdefault(
                    piece_calculation.end_piece, []
                ).append(torrent_file.path)
            else:
                missing_pieces.add(piece_calculation.start_piece)
                missing_pieces.add(piece_calculation.end_piece)
                current_missing_size += torrent_file.size

        if current_missing_size > max_missing_size:
            logger.info(
                f"Torrent missing too much data after matching files, size:{torrent.size}, found data size:{best_possible_size} missing size:{current_missing_size} max missing size:{max_missing_size}"
            )
            return DynamicMatchResult(False, current_missing_size, None, None)

        touched_files = set()
        for piece in missing_pieces & found_pieces:
            touched_files |= set(found_file_piece_mapping[piece])

        return DynamicMatchResult(
            True,
            current_missing_size,
            {
                path: (searched_file and searched_file.to_full_path())
                for (path, searched_file) in result_mapping.items()
            },
            list(touched_files),
        )

    def map_path_to_clients(self, path):
        """
        Map a path and all its files to clients.
        """
        scanned_folders = set()
        total = {"size": 0}
        real_files_seen = set()
        real_files_mapping = {}
        path_seeded = {}
        path_check_queue = []

        def flush_check_queue():
            logger.debug("Flushing queue")
            for p in path_check_queue:
                resolved_p = p.resolve()
                size = p.stat().st_size
                if resolved_p not in real_files_seen:
                    total["size"] += size
                    real_files_seen.add(resolved_p)

                real_files_mapping[p] = resolved_p
                path_seeded[p] = MappedFile(size=size, clients=[])

            for seeded_file in self.db.get_seeded_paths(path_check_queue):
                path_seeded[seeded_file.path].clients.append(
                    (seeded_file.client, seeded_file.infohash)
                )

            path_check_queue.clear()

        def looper(path, initial_path=False):
            if path in scanned_folders:
                return
            logger.debug(f"Scanning path {path!s}")
            scanned_folders.add(path)

            for rewritten_path in self.rewriter.rewrite_path(
                path, prefix_match=initial_path
            ):
                if rewritten_path.is_file():
                    path_check_queue.append(rewritten_path)
                    continue
                try:
                    for p in rewritten_path.iterdir():
                        if p.is_dir():
                            looper(p)
                        elif p.is_file():
                            path_check_queue.append(p)
                except OSError as e:
                    if e.errno != errno.ELOOP:
                        raise e

            if len(path_check_queue) > 1000:
                flush_check_queue()

        looper(path)
        flush_check_queue()
        seeded_size = 0
        already_counted_paths = set()
        for p, mapped_file in path_seeded.items():
            if not mapped_file.clients:
                continue

            resolved_p = real_files_mapping[p]
            if resolved_p in already_counted_paths:
                continue

            already_counted_paths.add(resolved_p)
            seeded_size += mapped_file.size

        return MapResult(
            total_size=total["size"], seeded_size=seeded_size, files=path_seeded
        )
