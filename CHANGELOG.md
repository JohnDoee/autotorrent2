# Changelog

## [1.0.] - 2022-
### Added

- Option to ignore file patterns during scan #7

### Bugfix

- Bumped libtc version to resolve qBittorrent issues #9

## [1.0.2] - 2022-06-01
### Added

- Default config where possible
- Updated libtc version to support labels

## [1.0.1] - 2022-05-30
### Bugfix

- Made `same_paths` config option optional #4
- Fixed problem with torrents that might make add crash #2
  (empty path segments because of encoding)
- Hardlinks now working and compatible with Python 3.7 incl. tests for it.

## [1.0.0] - 2022-05-29
### Added

- Initial release
