#!/usr/bin/env python3
"""Render deploy/Caddyfile.site from the template and deploy/.site-credentials.

Usage: deploy/render.py <site address, e.g. host.example.org:9443> [web root, default /var/www/isc-1]
The credentials file holds `user=` and `password=` lines; only a bcrypt hash goes into the output.
"""
import sys
from pathlib import Path

import bcrypt

here = Path(__file__).resolve().parent
cred = dict(line.split("=", 1) for line in (here / ".site-credentials").read_text().split() if "=" in line)
hashed = bcrypt.hashpw(cred["password"].encode(), bcrypt.gensalt(12)).decode().replace("$2b$", "$2a$", 1)
text = (here / "Caddyfile.site.template").read_text()
for key, value in {"{{SITE_ADDRESS}}": sys.argv[1], "{{USER}}": cred["user"], "{{HASH}}": hashed,
                   "{{WEB_ROOT}}": sys.argv[2] if len(sys.argv) > 2 else "/var/www/isc-1"}.items():
    text = text.replace(key, value)
(here / "Caddyfile.site").write_text(text)
print("written", here / "Caddyfile.site")
