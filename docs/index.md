# Autotorrent2

Autotorrent2 is the successor to Autotorrent. The original autotorrent was made to match data on disk with data
in torrents even when slight differences or alterations occured. Autotorrent2 can do that too.

The purpose of Autotorrent2 is to extend to the whole pipeline of a torrent lifecycle from discovery to removal.
Actions that often are cumbersome and timeconsuming to do by hand.


## Feature comparison

| Feature                                 | Autotorrent | Autotorrent2 |
|-----------------------------------------|-------------|--------------|
| Torrent to data match                   | Yes         | Yes          |
| Torrent removal                         | No          | Yes          |
| Handle read-only files being written to | No          | Yes          |
| Discover how much is seeded in a folder | No          | Yes          |
| Handle broken encoding (utf-8)          | No          | Yes          |
| Multi-client support                    | Partial     | Yes          |
| Different torrent clients support       | Yes         | Yes          |
| (Conditional) hash verification         | No          | Yes          |
| Torrent discovery                       | No          | On TODO      |

## Installation

Check out the Github README.

## Links

[Github](https://github.com/JohnDoee/autotorrent2)