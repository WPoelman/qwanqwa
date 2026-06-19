class ExportNameCache:
    """Minimal name cache adapter for exporters using an in-memory snapshot."""

    def __init__(self, names):
        self.names = names

    def get(self, canonical_id):
        entries = self.names.get(canonical_id, [])
        result = {}
        for entry in entries:
            key = entry.locale_id or entry.bcp_47_code
            if key is None:
                continue
            existing = result.get(key)
            if existing is None or (entry.is_canonical and not existing.is_canonical):
                result[key] = entry
        return result or None
