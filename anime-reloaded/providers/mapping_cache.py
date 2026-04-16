from __future__ import annotations

import json
import time
from pathlib import Path


class ProviderMappingCache:
    def __init__(self, path=""):
        self.path = Path(path) if path else None
        self.data = {
            "version": 1,
            "showMappings": {},
        }
        self._dirty = False
        self._load()

    def _load(self):
        if not self.path or not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return
        if isinstance(raw, dict):
            self.data["showMappings"] = raw.get("showMappings") or {}

    def _make_key(self, metadata_provider, metadata_id, stream_provider):
        return f"{metadata_provider}:{metadata_id}:{stream_provider}"

    def _normalise_entry(self, entry):
        item = dict(entry or {})
        item["status"] = str(item.get("status") or ("mapped" if item.get("streamId") else "unknown"))
        item["targetProvider"] = str(item.get("targetProvider") or item.get("streamProvider") or "").strip()
        item["targetId"] = str(item.get("targetId") or item.get("streamId") or "").strip()
        item["streamId"] = str(item.get("streamId") or "").strip()
        item["reason"] = str(item.get("reason") or "").strip()
        item["confidence"] = float(item.get("confidence") or 0)
        candidates = item.get("candidates")
        item["candidates"] = candidates if isinstance(candidates, list) else []
        return item

    def get_mapping_record(self, metadata_provider, metadata_id, stream_provider):
        metadata_provider = str(metadata_provider or "").strip()
        metadata_id = str(metadata_id or "").strip()
        stream_provider = str(stream_provider or "").strip()
        if not metadata_provider or not metadata_id or not stream_provider:
            return {}
        key = self._make_key(metadata_provider, metadata_id, stream_provider)
        entry = self.data["showMappings"].get(key) or {}
        return self._normalise_entry(entry)

    def remember_mapping_result(
        self,
        metadata_provider,
        metadata_id,
        stream_provider,
        *,
        status,
        stream_id="",
        confidence=0,
        reason="",
        candidates=None,
        meta=None,
    ):
        metadata_provider = str(metadata_provider or "").strip()
        metadata_id = str(metadata_id or "").strip()
        stream_provider = str(stream_provider or "").strip()
        stream_id = str(stream_id or "").strip()
        status = str(status or "").strip()
        if not metadata_provider or not metadata_id or not stream_provider or not status:
            return
        key = self._make_key(metadata_provider, metadata_id, stream_provider)
        record = {
            "metadataProvider": metadata_provider,
            "metadataId": metadata_id,
            "streamProvider": stream_provider,
            "streamId": stream_id,
            "targetProvider": stream_provider,
            "targetId": stream_id,
            "status": status,
            "confidence": float(confidence or 0),
            "reason": str(reason or "").strip(),
            "candidates": candidates if isinstance(candidates, list) else [],
            "updatedAt": int(time.time()),
        }
        if isinstance(meta, dict) and meta:
            record["meta"] = meta
        self.data["showMappings"][key] = record
        self._dirty = True

    def remember_show_mapping(self, metadata_provider, metadata_id, stream_provider, stream_id):
        self.remember_mapping_result(
            metadata_provider,
            metadata_id,
            stream_provider,
            status="mapped",
            stream_id=stream_id,
            confidence=1,
        )

    def remember_provider_mapping(
        self,
        source_provider,
        source_id,
        target_provider,
        target_id,
        *,
        status="mapped",
        confidence=1,
        reason="",
        candidates=None,
        meta=None,
    ):
        self.remember_mapping_result(
            source_provider,
            source_id,
            target_provider,
            status=status,
            stream_id=target_id,
            confidence=confidence,
            reason=reason,
            candidates=candidates,
            meta=meta,
        )

    def get_provider_show_id(self, source_provider, source_id, target_provider):
        return self.get_stream_show_id(source_provider, source_id, target_provider)

    def get_source_show_id(self, source_provider, target_provider, target_id):
        source_provider = str(source_provider or "").strip()
        target_provider = str(target_provider or "").strip()
        target_id = str(target_id or "").strip()
        if not source_provider or not target_provider or not target_id:
            return ""
        for raw_entry in (self.data.get("showMappings") or {}).values():
            entry = self._normalise_entry(raw_entry)
            if entry.get("status") != "mapped":
                continue
            if str(entry.get("metadataProvider") or "").strip() != source_provider:
                continue
            if str(entry.get("targetProvider") or "").strip() != target_provider:
                continue
            if str(entry.get("targetId") or "").strip() != target_id:
                continue
            return str(entry.get("metadataId") or "").strip()
        return ""

    def get_stream_show_id(self, metadata_provider, metadata_id, stream_provider):
        metadata_provider = str(metadata_provider or "").strip()
        metadata_id = str(metadata_id or "").strip()
        stream_provider = str(stream_provider or "").strip()
        if not metadata_provider or not metadata_id or not stream_provider:
            return ""
        if metadata_provider == stream_provider:
            return metadata_id
        entry = self.get_mapping_record(metadata_provider, metadata_id, stream_provider)
        if entry.get("status") != "mapped":
            return ""
        return str(entry.get("streamId") or "").strip()

    def decorate_show(self, show, metadata_provider, stream_provider, stream_id=""):
        item = dict(show or {})
        metadata_id = str(item.get("id") or "").strip()
        refs = item.get("providerRefs")
        if not isinstance(refs, dict):
            refs = {}

        refs["metadata"] = {
            "provider": metadata_provider,
            "id": metadata_id,
        }

        resolved_stream_id = str(stream_id or "").strip()
        if not resolved_stream_id and metadata_provider == stream_provider:
            resolved_stream_id = metadata_id
        if not resolved_stream_id:
            resolved_stream_id = self.get_stream_show_id(metadata_provider, metadata_id, stream_provider)
        if resolved_stream_id:
            refs["stream"] = {
                "provider": stream_provider,
                "id": resolved_stream_id,
            }
            self.remember_show_mapping(metadata_provider, metadata_id, stream_provider, resolved_stream_id)
        else:
            refs.pop("stream", None)

        item["providerRefs"] = refs
        return item

    def save(self):
        if not self.path or not self._dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self.data["version"],
            "showMappings": self.data["showMappings"],
        }
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        self._dirty = False
