# Publishing the demo on a public web server

Goal: one site, `https://<host>:9443/`, with open documents and a password-protected live console and
Grafana. The GPU host stays behind its network and opens one outgoing SSH connection to the web server.

```
visitor --HTTPS:9443--> portal Caddy (terminates TLS, one proxy block)
                          --> origin container (host network, docker0 address :19080)
                                /          static site (build output of site/build.py)
                                /console/  password --> 127.0.0.1:19500 --+
                                /grafana/  password --> 127.0.0.1:19501 --+-- reverse SSH tunnel
                                                                              from the GPU host
                         GPU host: console 127.0.0.1:18500, Grafana 127.0.0.1:18501
```

The existing Caddy keeps terminating TLS because it already owns ports 80 and 9443 on the web server; the new
origin container is separate, so the change to the existing setup is one site block, one variable and one
`extra_hosts` line (`deploy/portal/`).

## Parts

1. `deploy/origin/` — compose file and Caddyfile of the origin; `auth.caddy` (bcrypt hash, git-ignored) comes
   from `deploy/render.py`, the pages from `site/build.py` (`site/dist` copied to `origin/site/`).
2. `deploy/portal/` — the block for the existing Caddy and the compose lines it needs.
3. `deploy/isc-tunnel.service.template` — systemd user unit for the reverse tunnel on the GPU host.
4. `deploy/publish.sh` — builds the pages on the GPU host and copies them to the web server.

## Steps

1. GPU host: `helm upgrade ... -f deploy/values-site.yaml` with `publicUrl: https://<host>:9443`.
2. Web server: copy `deploy/origin/` (with `auth.caddy`) and `site/dist` to a directory, `docker compose up -d`.
3. GPU host: install the tunnel unit with a key that may open only ports 19500 and 19501.
4. Existing Caddy: add the block and the variable (`deploy/portal/`), validate, recreate the container.
5. Verify: `curl -I https://<host>:9443/` returns 200; `/console/` asks for the password and then shows `live`;
   `/grafana/` shows the dashboard.

## Security

1. The console starts real load on a GPU, so `/console/` and `/grafana/` are behind HTTP basic auth over HTTPS.
2. The password is in `deploy/.site-credentials` on the GPU host (mode 600, git-ignored).
3. The tunnel key should be restricted in `authorized_keys` to opening these two loopback ports only.
4. The origin listens on the docker0 address only, not on a public interface.

## Undo

Remove the block and the variable from the existing Caddy and recreate it; `docker compose down` in the origin
directory; stop the tunnel unit; delete the directory.
