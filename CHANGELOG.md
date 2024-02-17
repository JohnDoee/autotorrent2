# Changelog

## [1.3.0] - 2024-02-17

### Add

- Dockerfile and docker support #51 (thanks kannibalox)

### Change

- Moved to os.scanfile for more efficient disk scanning #45 (thanks kannibalox)
- Using prefix tree when inserting into sqlite for more efficiency #41 (thanks kannibalox)

### Bugfix

- reflink never actually worked #40 (Thanks undrog)

## [1.2.3] - 2022-08-13

### Add

- Possible to disable metadata in store path #32

### Change

- Exception logger on failed torrent parse #36
- Bumped libtc version to qbittorrent tag support version #33

### Bugfix

- Scan stalls when an exception occures #34
- Making sure all trackers are bytes, fixing #48

## [1.2.2] - 2022-08-06

### Bugfix

- Announce-list was not parsed correctly #31

## [1.2.1] - 2022-07-30

### Add

- Support for more custom variables used in store_path, both from torrent and cli #28

### Change

- Verifying store_path has at least one variable as it otherwise will use weird paths #12

### Bugfix

- Catching permission error, not-a-directory error on add related to store_path #12

## [1.2.0] - 2022-06-18

### Add

- Torrents can be added in stopped state via CLI flag #20

### Change

- Unsplitable algorithm improved to support more use-cases
- Renamed OK to Added to streamline messages #23
- More information shared on failed to add exception #21

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
