from collections.abc import MutableMapping


def flatten_dict(d: MutableMapping, parent_key: str = "", sep: str = ".") -> dict:
    items = []
    for k, v in d.items():
        # Combine parent key and current key
        new_key = f"{parent_key}{sep}{k}" if parent_key else k

        if isinstance(v, MutableMapping):
            # Recursively flatten internal dictionaries
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)
