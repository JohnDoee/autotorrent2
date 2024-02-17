# Autotorrent2

![Test result](https://github.com/JohnDoee/autotorrent2/actions/workflows/main.yml/badge.svg?branch=master)

Match torrents and data, remove torrents based on data, cleanup your disk for unseeded files.
Autotorrent2 does everything you currently miss in your flow.

## Supported

* Torrent clients: rtorrent, Deluge, Transmission and qBittorrent
* OS: Any, but only tested on linux
* Python: 3.7+ are the only tested versions, might work with lower 3.x.

## Quickstart guide

Install Autotorrent2

```bash
python3 -m venv ~/.autotorrent # Create virtual environment where we install autotorrent2
~/.autotorrent/bin/pip install autotorrent2 # Actually install autotorrent2

# Optional, add at2 to your commandline
echo "alias at2=~/.autotorrent/bin/at2" >> ~/.bashrc
source ~/.bashrc
```

The first time Autotorrent2 is run without a known config file, it will create a base config file.

```bash
at2 check-config
```

The default location is ~/.config/autotorrent/config.toml - edit it to match your setup.
See the example configuration file for setting description [found here](config.example.toml).

Test the connections and see if it can connect to all your configured clients.

```bash
at2 test-connection
```

Now you are ready to actually use it, check out the [Usage page for fun things to do](https://johndoee.github.io/autotorrent2/usage/) and [CLI page for featurelist](https://johndoee.github.io/autotorrent2/cli/)

## Note about running autotorrent2 in a script

It can be fun to run scripts automatically and see cross-seeding just happen.
Autotorrent2 is not really designed for multiple instances at once so it is recommenced to use a lock to prevent this.

Instead of just `at2` then use e.g. `flock ~/.autotorrent.lock -c 'at2'` which prevents multiple instances of Autototrrent2 at once.

## Note about Docker

If you use Autotorrent2 in a docker container or with a torrent client running in docker then the recommendation is to align the paths.
If your torrent data is located in /mnt/data outside docker then you should map it similarly inside the docker container and you will save yourself from a lot of headaches.

Personally I recommend mounting your data source as read-only because bittorrent clients are write-happy that might corrupt your data.

## Docker usage

There is a docker image published automatically now.

Basic usage:

```bash
docker run -ti --rm -v ${PWD}/autotorrent.db:autotorrent.db -v ${PWD}/config.toml:config.toml ghcr.io/johndoee/autotorrent2:master check-config
```

Cron usage, check config every 5 minute.

```bash
docker run -ti --rm -v ${PWD}/autotorrent.db:autotorrent.db -v ${PWD}/config.toml:config.toml ghcr.io/johndoee/autotorrent2:master cron '*/5 * * * *' check-config
```

## Todo

Assortment of stuff that is planned.

- [ ] When Autotorrent2 is working on a task, e.g. copying a file to cache, then it might look like as it is stalled. An indicator should be added.
- [ ] Client normalization indexing, e.g. index based on how transmission and qbittorrent handles problematic filenames
- [ ] Torrent discovery for a torrent site.

## Known bugs

Assortment of stuff I am not sure I can do much about.

- [ ] Transmission (3.x) does not parse all emojis correctly and will return the wrong filename. [This is fixed in Transmission 4.0.2.](https://github.com/transmission/transmission/pull/5096)

## License

MIT