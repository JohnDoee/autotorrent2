# Changelog

## [1.1.1] - 2022-06-

### Add

- Torrents can be added in stopped state via CLI flag #20

### Change

- Renamed OK to Added to streamline messages #23

### Bugfix

- Symlinks are now not resolved when adding to client (updated libtc) #17

## [1.1.0] - 2022-06-07
### Add

- Option to ignore directory patterns during scan #18

### Change

- fast_resume is now set to false default everywhere as it can cause problems #15
- Disk scan now threaded with a pipeline design #14

## [1.0.3] - 2022-06-04
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
