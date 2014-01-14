from __future__ import print_function, unicode_literals

import re
from HTMLParser import HTMLParser

from coherence import log
from coherence.upnp.core import DIDLLite
from coherence.upnp.core.utils import ReverseProxyUriResource
from coherence.upnp.core.DIDLLite import (
    Resource,
)
from coherence.backend import (
    BackendItem, Container, AbstractBackendStore,
)

import api
import settings

_htmlparser = HTMLParser()


class MoeFMProxyStream(ReverseProxyUriResource, log.Loggable):
    logCategory = 'moefm_stream'

    def __init__(self, uri, parent):
        self.parent = parent
        ReverseProxyUriResource.__init__(self, uri.encode("utf-8"))

    def log_playing(self):
        if self.parent.store.last_played_item is self:
            obj_id = self.parent.sub_id
            d = api.moefm.get(
                "/ajax/log?log_obj_type=sub&log_type=listen&obj_type=song&api=json", # noqa
                {"obj_id": obj_id}
            )
            d.addCallback(lambda res: self.debug(
                "Logged %s: %r", obj_id, res,
            ))
            d.addErrback(lambda res: self.warning(
                "Unable to log %s: %r", obj_id, res,
            ))

    def render(self, request):
        self.debug("render %r", self.parent.item_data)
        self.parent.container.remove_child(self.parent)
        self.parent.store.fill_playlist()
        self.parent.store.last_played_item = self
        reactor.callLater(self.parent.duration_seconds / 2, self.log_playing)
        return ReverseProxyUriResource.render(self, request)


class MoeFmPlaylistItem(BackendItem):
    logCategory = "moefm"
    next_sn = 0

    def __init__(self, item_data, container):
        BackendItem.__init__(self)
        self.item_data = item_data
        self.container = container
        self.sub_id = item_data["sub_id"]
        self.storage_id = "track-%s$%s" % (self.sub_id, container.get_id())
        self.__class__.next_sn += 1
        self.sort_key = self.__class__.next_sn

        track_number = None
        m = re.match(
            r"^song\.(\d+)\s+.*$",
            _htmlparser.unescape(item_data["title"]),
            re.I,
        )
        if m:
            track_number, = m.groups()

        title = _htmlparser.unescape(item_data["sub_title"])
        self.name = title
        self.title = title
        self.originalTrackNumber = track_number
        self.artist = _htmlparser.unescape(item_data["artist"])
        self.album = _htmlparser.unescape(item_data["wiki_title"])
        self.cover = item_data["cover"]["large"]
        self.duration = item_data["stream_time"]
        self.duration_seconds = int(item_data["stream_length"])
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
            self.debug("get_item %s %s %s", upnp_id, upnp_parent_id, self.name)
            item = DIDLLite.MusicTrack(upnp_id, upnp_parent_id, self.name)
            item.restricted = True
            item.name = self.name
            item.originalTrackNumber = self.originalTrackNumber
            item.title = self.title
            item.artist = self.artist
            item.album = self.album
            item.albumArtURI = self.cover
            item.duration = self.duration

            proxied_url = "%s%s" % (self.store.urlbase, self.get_id())
            proxied_url = proxied_url.encode("utf-8")
            self.url = proxied_url
            self.location = MoeFMProxyStream(self.item_data["url"], self)

            protocol = "http-get"

            res = Resource(
                proxied_url,
                ("%s:*:%s:*" % (protocol, self.mimetype)).encode("utf-8")
            )
            res.size = self.item_data["file_size"] * 1024
            res.duration = self.duration
            item.res.append(res)

            self.item = item

        return self.item

    def get_url(self):
        return self.url


class PlaylistBackendContainer(Container):
    def __init__(self, *args, **kwargs):
        Container.__init__(self, *args, **kwargs)
        self.sorting_method = lambda x, y: cmp(x.sort_key, y.sort_key)

    def remove_child(self, child, external_id=None, update=True):
        try:
            self.children.remove(child)
            # We'd like the item to be accessible even after removing it
            # self.store.remove_item(child)
        except ValueError:
            pass
        else:
            if update:
                self.update_id += 1

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

    def append_item(self, item, storage_id=None):
        if storage_id is None:
            storage_id = item.get_id()

        if storage_id is None:
            storage_id = self.getnextID()

        storage_id = str(storage_id)
        return super(MoeFmPlaylistStore, self).append_item(item, storage_id)

    def get_by_id(self, id):
        self.warning("get_by_id: %r", id)
        if isinstance(id, basestring):
            id = id.split("@", 1)
            id = id[0].split(".")[0]

        return self.store.get(str(id))

    def upnp_init(self):
        self.current_connection_id = None
        self.server.connection_manager_server.set_variable(
            0,
            "SourceProtocolInfo",
            ["http-get:*:audio/mpeg:*"],
            default=True,
        )

        root_item = Container(None, "Moe FM")
        self.root_item = root_item
        self.set_root_item(root_item)
        self.playlist_container = PlaylistBackendContainer(
            root_item, "Start listening",
        )
        root_item.add_child(self.playlist_container)

        dummy = PlaylistBackendContainer(root_item, "Dummy")
        root_item.add_child(dummy)

        self.fill_playlist()

    def fill_playlist(self):
        current_count = self.playlist_container.get_child_count()
        if current_count < settings.get("min_tracks_in_playlist", 120):
            self.debug("Filling playlist...")
            self.load_playlist().addCallback(lambda _: self.fill_playlist())

    def load_playlist(self):
        parent_item = self.playlist_container

        def got_response(resp_container):
            self.info("got playlist")
            resp = resp_container["response"]
            if resp["information"]["has_error"]:
                self.error("Got error response: %s" % resp)
                return

            items = []
            for item_data in resp["playlist"]:
                item = MoeFmPlaylistItem(item_data, parent_item)
                items.append(item)
                parent_item.add_child(item)

            self.update_completed()
            return items

        def got_error(error):
            self.warning("Unable to retrieve playlist")
            print("Error: %s" % error)
            return None

        d = api.moefm.get(
            "/listen/playlist?api=json",
            {"perpage": settings.get("tracks_per_request", 30)},
        )
        d.addCallback(got_response)
        d.addErrback(got_error)
        return d

    def update_completed(self):
        self.update_id += 1
        try:
            self.server.content_directory_server.set_variable(
                0, "SystemUpdateID", self.update_id,
            )
            container = self.playlist_container
            value = (container.get_id(), container.get_update_id())
            self.info("update_completed %s %s", self.update_id, value)
            self.server.content_directory_server.set_variable(
                0, "ContainerUpdateIDs", value,
            )
        except Exception as e:
            self.warning("%r", e)


if __name__ == '__main__':
    from twisted.internet import reactor

    def main():
        from coherence.base import Coherence, Plugins
        Plugins().set("MoeFmPlaylistStore", MoeFmPlaylistStore)
        conf = dict(settings.get("coherence_config", {}))
        conf.update({
            "plugin": [{"backend": "MoeFmPlaylistStore"}]
        })
        Coherence(conf)

    reactor.callWhenRunning(main)
    reactor.run()
