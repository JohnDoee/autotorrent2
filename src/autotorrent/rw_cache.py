import hashlib
import json
import logging
import shutil
import time
from pathlib import Path

from .utils import chown, create_link

logger = logging.getLogger(__name__)

RW_CACHE_DATA_PATH = "data"
CW_CACHE_CONF_NAME = "autotorrent.json"


class ReadWriteFileCache:
    def __init__(self, path, ttl, chown_str=None):
        self.path = Path(path)
        self.ttl = ttl
        self.chown_str = chown_str

    def cleanup_cache(self):
        removed_paths = []
        for path in self.path.iterdir():
            if time.time() - path.stat().st_mtime > self.ttl:
                logger.debug(f"Path {path} is older than ttl and should be deleted")
                conf_path = path / CW_CACHE_CONF_NAME
                conf = json.loads(conf_path.read_text())
                source_path = Path(conf["source_path"])
                for target_path in conf["target_paths"]:
                    link_type = target_path["link_type"]
                    target_path = Path(target_path["path"])
                    if not target_path.exists():
                        logger.warning(f"Target path {target_path!s} does not exist")
                        continue
                    logger.debug(f"Rewriting {target_path!s} to {source_path!s}")
                    target_path.unlink()
                    create_link(source_path, target_path, link_type)
                removed_paths.append(path)
                shutil.rmtree(path)
        return removed_paths

    def cache_file(self, path, target_path, link_type):
        full_folder_name = "__".join(path.parts[1:])
        folder_name = f"{full_folder_name[:25]}__{full_folder_name[-50:]}__{hashlib.sha1(str(path).encode()).hexdigest()}"
        folder_path = self.path / folder_name
        folder_data_path = folder_path / RW_CACHE_DATA_PATH
        folder_data_file = folder_data_path / path.name
        conf_path = folder_path / CW_CACHE_CONF_NAME
        if not folder_path.exists():
            logger.info(
                f"Seems like folder {folder_path!s} does not exist, copying file from {path!s}"
            )
            folder_path.mkdir()
            folder_data_path.mkdir()
            shutil.copyfile(path, folder_data_file)
            if self.chown_str is not None:
                chown(self.chown_str, folder_data_file)
            conf_path.write_text(
                json.dumps(
                    {
                        "source_path": str(path),
                        "target_paths": [],
                    }
                )
            )

        folder_path.touch()
        conf = json.loads(conf_path.read_text())
        conf["target_paths"].append(
            {
                "path": str(target_path),
                "link_type": link_type,
            }
        )
        conf_path.write_text(json.dumps(conf))
        return folder_data_file
