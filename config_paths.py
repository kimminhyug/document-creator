"""Explicit catalog: examples never impersonate production configuration."""
import json
from pathlib import Path


def entity_dir(root, group, identifier):
    root = Path(root).resolve()
    if group not in ('companies', 'products'):
        raise ValueError('unknown configuration group')
    catalog = root / 'config/catalog.json'
    entries = json.loads(catalog.read_text(encoding='utf-8')) if catalog.exists() else {}
    relative = entries.get(group, {}).get(identifier, f'config/{group}/{identifier}')
    target = (root / relative).resolve()
    allowed = (root / 'config' / group, root / 'examples/demo' / group)
    if not any(target.is_relative_to(base.resolve()) for base in allowed):
        raise ValueError('configuration path outside classified directories')
    return target
