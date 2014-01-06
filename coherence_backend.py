from __future__ import print_function, unicode_literals

import re
from HTMLParser import HTMLParser

from coherence.upnp.core import DIDLLite
from coherence.upnp.core.DIDLLite import (
    Resource,
)
from coherence.backend import (
    BackendItem, Container, AbstractBackendStore,
)

import api
import settings

_htmlparser = HTMLParser()


class MoeFmPlaylistItem(BackendItem):
    logCategory = "moefm"

    def __init__(self, item_data):
        BackendItem.__init__(self)
        self.item_data = item_data
        self.name = _htmlparser.unescape(item_data["title"])
        self.title = _htmlparser.unescape(item_data["title"])
        self.artist = _htmlparser.unescape(item_data["artist"])
        self.album = item_data["sub_title"]
        self.cover = item_data["cover"]["large"]
        self.duration = item_data["stream_time"]
        if not re.match(r"^\d{2}:\d{2}:\d{2}(?:\.\d+)?", self.duration):
            self.duration = "0:" + self.duration  # Add hour part

        self.mimetype = "audio/mpeg"

        self.item = None

    def get_id(self):
        return self.storage_id

    def get_item(self):
        if self.item is None:
            upnp_id = self.get_id()
            upnp_parent_id = self.parent.get_id()
            item = DIDLLite.MusicTrack(upnp_id, upnp_parent_id, self.name)
            item.restricted = True
            item.name = self.name
            item.title = self.title
            item.artist = self.artist
            item.album = self.album
            item.albumArtURI = self.cover
            item.duration = self.duration

            protocol = "http-get"

            res = Resource(
                self.item_data["url"],
                "%s:*:%s:*" % (protocol, self.mimetype)
            )
            res.size = self.item_data["file_size"] * 1024
            res.duration = self.duration
            item.res.append(res)

            self.item = item

        return self.item

    def get_url(self):
        return self.url


class PlaylistBackendContainer(Container):
    def get_item(self):
        if self.item is None:
            self.item = DIDLLite.PlaylistContainer(
                self.storage_id, self.parent_id, self.name
            )

        self.item.childCount = self.get_child_count()
        return self.item


class MoeFmPlaylistStore(AbstractBackendStore):
    logCategory = "moefm"
    name = "Moe FM"
    implements = ["MediaServer"]
    wmc_mapping = {"16": 1000}

    def __init__(self, server, **kwargs):
        AbstractBackendStore.__init__(self, server, **kwargs)
        self.init_completed()

    def __repr__(self):
        return self.__class__.__name__

    def upnp_init(self):
        self.current_connection_id = None
        if self.server:
            self.server.connection_manager_server.set_variable(
                0,
                "SourceProtocolInfo",
                ["http-get:*:audio/mpeg:*"],
                default=True,
            )

        root_item = Container(None, "Moe FM")
        self.set_root_item(root_item)
        playlist_item = PlaylistBackendContainer(root_item, "Start listening")
        root_item.add_child(playlist_item)
        self.load_playlist(playlist_item)

    def load_playlist(self, parent_item):
        def got_response(resp_container):
            self.info("got playlist")
            resp = resp_container["response"]
            if resp["information"]["has_error"]:
                self.error("Got error response: %s" % resp)
                return

            items = []
            for item_data in resp["playlist"]:
                item = MoeFmPlaylistItem(item_data)
                items.append(item)
                parent_item.add_child(item)

            return items

        def got_error(error):
            self.warning("Unable to retrieve playlist")
            print("Error: %s" % error)
            return None

        d = api.moefm.get(
            "/listen/playlist?api=json",
            {"perpage": settings.get("tracks_per_request", 2)}
        )
        d.addCallback(got_response)
        d.addErrback(got_error)
        return d

if __name__ == '__main__':
    from twisted.internet import reactor

    def main():
        from coherence.base import Coherence, Plugins
        Plugins().set("MoeFmPlaylistStore", MoeFmPlaylistStore)
        Coherence({
            "logging": {
                "level": "warn",
            },
            "plugin": [{"backend": "MoeFmPlaylistStore"}]
        })

    reactor.callWhenRunning(main)
    reactor.run()
