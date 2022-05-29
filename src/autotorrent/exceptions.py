class FailedToParseTorrentException(Exception):
    """A torrent was not possible to parse for some reason"""


class FailedToCreateLinkException(Exception):
    """Failed to create links"""
