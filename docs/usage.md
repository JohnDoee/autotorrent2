# Usage

A number of common use-cases and how to handle them are described here. For the exhaustive feature list check out the CLI.

## Torrent add

###### Commands:
- at2 add
- at2 scan
- at2 cleanup-cache

###### Config fields:
- link_type
- always_verify_hash
- paths
- same_paths
- add_limit_size
- add_limit_percent
- store_path
- cache_touched_files
- rw_file_cache_ttl
- rw_file_cache_path

Match torrents with data on your disk, where every torrent starts its life. First we have to `at2 scan` to discover files Autotorrent2 can match against.
Our ubuntu isos are now indexed and we can add them to a torrent client. The client we are using is called transmission-ubuntu.

`at2 add transmission-ubuntu ubuntu-20.04.torrent` - it turns out the torrent is a little bit different as it has an .nfo file and transmission will need to write part of a piece to ubuntu-20.04.iso.
The file is read-only because it is owned by a different user and therefore it is cached locally. It can be pointed back to the original file AFTER transmission is done writing to the cached file.

Autotorrent2 supports caching files which can be enabled and disabled with the `cache_touched_files` setting.

The time is now `rw_file_cache_ttl` seconds later and we want to cleanup the cache, i.e. re-link files with the original file instead of having multiple copies of the same file indefinitely. Run `at2 cleanup-cache` and the file is gone from the cache.

## Torrent reseed

###### Commands:
- at2 add
- at2 scan

###### Config fields:
- always_verify_hash
- paths
- same_paths

New computer, new seedbox, new something. You want to reseed the old torrents and you have all the torrents and all the data available. Edit `paths` to the correct paths, run `at2 scan` to index your data.

With the data indexed you are ready to add the torrents with `at2 add -e *.torrent` - the `-e` option is the exact match mode, aka. reseed mode.

## Find seeded and unseeded files

###### Commands:
- at2 ls
- at2 find-unseeded
- at2 scan-clients

For one reason or another, you have removed torrents from your client but not deleted the files on disk. This can be for multiple reasons, e.g. the files might be in use for cross-seeding purposes.

First we scan the clients with `at2 scan-clients` so we have a local index of all the seeded files. It takes the filelist from the clients and saves it.

Now we can do `at2 ls` to see what is seeded in the current folder. While it is interesting to see how much is seeded the practical purpose is to find the exact files not seeded.

This can be done with `at2 find-unseeded /mnt/data/torrent-data/` which will spit out the paths not seeded.

A common trick is to do is use -e option and rm like: `at2 find-unseeded -e /mnt/data/torrent-data/ | xargs rm -r --` WARNING: make sure the clients are recently scanned and the output without the rm part looks correct as this command just deletes files.


## Torrent removal

###### Commands:
- at2 rm
- at2 scan-clients

The normal process for removing data is to do it from the torrent client, these commands can help you do it the other way and remove from multiple clients at once.

Like with ls we need to `at2 scan-clients` first to have an up-to-date local list of seeded files. Run `at2 rm /path/to/torrent` to remove everything seeded in that path directly or indirectly, i.e. linked files too. No torrents left hanging.

## Test configuration

###### Commands:
- at2 check-config
- at2 test-connection

Sometimes you want to check if what you are doing is correct and working.
The two commands list can test this easily.

## Torrent discovery

Command: TODO

This feature is not implemented yet but you can look at some of the other tools while you wait.

With the original autotorrent you would have to go out and find the potential torrents you would want to seed. This works for some flows but people just want stuff found and seeded.

There has been a huge resurgance in this exact field with tools like [mmgoodnow/cross-seed](https://github.com/mmgoodnow/cross-seed), [BC44/Cross-Seed-AutoDL](https://github.com/BC44/Cross-Seed-AutoDL), [boban-bmw/cross-seedarr](https://github.com/boban-bmw/cross-seedarr), [ccf-2012/seedcross](https://github.com/ccf-2012/seedcross) and (my own) [JohnDoee/flexget-cross-seed](https://github.com/JohnDoee/flexget-cross-seed).

The listed tools have an air of impreciseness around them, if files cannot be easily discovered via external search tools.