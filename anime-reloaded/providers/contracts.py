from __future__ import annotations

from abc import ABC, abstractmethod


class MetadataProvider(ABC):
    provider_id = ""

    @abstractmethod
    def list_genres(self):
        raise NotImplementedError

    @abstractmethod
    def popular(self, page=1, mode="sub", genre=None, mapping_cache=None, stream_provider_id=""):
        raise NotImplementedError

    @abstractmethod
    def recent(self, page=1, mode="sub", country="ALL", mapping_cache=None, stream_provider_id=""):
        raise NotImplementedError

    @abstractmethod
    def latest(self, page=1, mode="sub", country="ALL", mapping_cache=None, stream_provider_id=""):
        raise NotImplementedError

    @abstractmethod
    def search(self, query, mode="sub", page=1, genre=None, mapping_cache=None, stream_provider_id=""):
        raise NotImplementedError

    @abstractmethod
    def episodes(self, show_id, mode="sub", mapping_cache=None, stream_provider_id=""):
        raise NotImplementedError

    @abstractmethod
    def feed(self, library_entries, mode="sub", cache_path="", mapping_cache=None, stream_provider_id=""):
        raise NotImplementedError


class StreamProvider(ABC):
    provider_id = ""

    @abstractmethod
    def resolve_episode_stream(
        self,
        show_id,
        ep_num,
        mode="sub",
        provider_pref="auto",
        quality_pref="best",
        mapping_cache=None,
        metadata_provider_id="",
    ):
        raise NotImplementedError

