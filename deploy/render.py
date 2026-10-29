#!/usr/bin/env python3
"""Write deploy/origin/auth.caddy (basic auth block with a bcrypt hash) from deploy/.site-credentials.

Usage: deploy/render.py
The credentials file holds `user=` and `password=` lines; only the hash is written.
"""
from pathlib import Path

import bcrypt

here = Path(__file__).resolve().parent
cred = dict(line.split("=", 1) for line in (here / ".site-credentials").read_text().split() if "=" in line)
hashed = bcrypt.hashpw(cred["password"].encode(), bcrypt.gensalt(12)).decode().replace("$2b$", "$2a$", 1)
out = here / "origin" / "auth.caddy"
out.write_text(f"basic_auth {{\n\t{cred['user']} {hashed}\n}}\n")
out.chmod(0o600)
print("written", out)
