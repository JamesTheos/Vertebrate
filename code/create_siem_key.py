"""
create_siem_key.py
Provision or revoke API keys for the SIEM audit feed (/audit/api/siem).
The raw key is printed ONCE at creation — only its SHA-256 hash is stored.

Usage (inside the app container):
    python create_siem_key.py <name>                # create key, print it once
    python create_siem_key.py --deactivate <name>   # revoke a key
"""
import hashlib
import secrets
import sys

from models import db, SiemApiKey


def create_key(name):
    """Create an active key named `name`; returns the raw key (shown once)."""
    if SiemApiKey.query.filter_by(name=name).first():
        raise ValueError(f"SIEM API key '{name}' already exists")
    raw = secrets.token_urlsafe(32)
    db.session.add(SiemApiKey(
        name=name,
        key_hash=hashlib.sha256(raw.encode()).hexdigest(),
    ))
    db.session.commit()
    return raw


def deactivate_key(name):
    """Revoke the key named `name` — the feed rejects it immediately."""
    key = SiemApiKey.query.filter_by(name=name).first()
    if key is None:
        raise ValueError(f"No SIEM API key named '{name}'")
    key.active = False
    db.session.commit()


def main(argv):
    if len(argv) == 2 and not argv[1].startswith('-'):
        action, name = create_key, argv[1]
    elif len(argv) == 3 and argv[1] == '--deactivate':
        action, name = deactivate_key, argv[2]
    else:
        print(__doc__)
        return 1

    from app import create_app
    with create_app().app_context():
        try:
            result = action(name)
        except ValueError as e:
            print(f"Error: {e}")
            return 1
    if action is create_key:
        print(f"SIEM API key '{name}' created. Raw key (shown once, store it now):")
        print(result)
    else:
        print(f"SIEM API key '{name}' deactivated.")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
