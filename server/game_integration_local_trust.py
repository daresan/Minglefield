"""Host-local release discovery trust, distinct from installation verification."""


def local_discovery_catalog(catalog, entries, approved_repositories):
    """Merge host-approved lock declarations into an advisory release catalog.

    Local sources do not become globally verified or installer-attested.
    An existing registry identity conflict is never silently overwritten.
    """
    if not isinstance(catalog, dict) or not isinstance(entries, list):
        return {"state": "unavailable", "integrations": []}, []
    items = catalog.get("integrations", [])
    if not isinstance(items, list):
        items = []
    merged = [dict(item) for item in items]
    known = {item.get("integration_id"): item for item in merged}
    approved = set(approved_repositories)
    normalized = []
    for entry in entries:
        item = dict(entry)
        source = item.get("release_source")
        repository = source.get("repository") if isinstance(source, dict) else None
        if repository not in approved:
            item["source_state"] = "source_not_trusted_by_host"
        elif item["integration_id"] in known:
            registered = known[item["integration_id"]]
            if (registered.get("release_source") == source and
                    registered.get("publisher") == item.get("publisher")):
                item["source_state"] = "registry_match"
            else:
                item["source_state"] = "source_mismatch"
        elif (isinstance(source, dict) and source.get("provider") == "github"
              and isinstance(repository, str)):
            merged.append({"integration_id": item["integration_id"],
                           "publisher": item.get("publisher"),
                           "release_source": source,
                           "trust_tier": "local"})
            known[item["integration_id"]] = merged[-1]
            item["source_state"] = "registry_match"
        else:
            item["source_state"] = "unsupported_release_provider"
        normalized.append(item)
    return {"state": "available", "integrations": merged}, normalized
