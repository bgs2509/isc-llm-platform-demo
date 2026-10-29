# Publishing the demo on a public web server

Goal: one site, `https://<host>:9443/`, with open documents and a password-protected live console and
Grafana. The GPU host stays behind its network; it opens one outgoing SSH connection to the web server.

```
visitor --HTTPS:9443--> web server (Caddy)
                          |  /               static site (build output of site/build.py)
                          |  /console/       password -> 127.0.0.1:19500 -+
                          |  /grafana/       password -> 127.0.0.1:19501 -+-- reverse SSH tunnel
                                                                           |   from the GPU host
                         GPU host: console 127.0.0.1:18500, Grafana 127.0.0.1:18501
```

## Prerequisites on the web server

1. Caddy 2 with ports 80 and 443 reachable from the internet (Caddy gets and renews the certificate for the
   host name over them, even though the site itself listens on 9443) and port 9443 open.
2. A directory for the static files (default `/var/www/isc-1`) writable by the account used for the copy.
3. An SSH account that the GPU host may use for the reverse tunnel.

## Steps

1. Chart: `helm upgrade llm-platform chart/llm-platform -f deploy/values-site.yaml ...` with
   `publicUrl: https://<host>:9443` (Grafana is then served under `/grafana/`).
2. Site files: `WEB_HOST=<ssh name> deploy/publish.sh` (builds on the GPU host, copies `site/dist`).
3. Web server: render the site block with `deploy/render.py <host>:9443` (uses `deploy/.site-credentials`,
   writes only a bcrypt hash), add the content of `deploy/Caddyfile.site` to the Caddy configuration, validate
   (`caddy validate`) and reload.
4. Tunnel: fill `{{SSH_TARGET}}` in `deploy/isc-tunnel.service.template`, install it as a systemd user unit
   on the GPU host (`systemctl --user enable --now isc-tunnel`).
5. Verify: `curl -I https://<host>:9443/` returns 200; `/console/` asks for the password; after login the
   page shows `live`; `/grafana/` shows the dashboard.

## Security

1. The console starts real load on a GPU, so `/console/` and `/grafana/` are behind HTTP basic auth over HTTPS.
2. The password lives in `deploy/.site-credentials` on the GPU host (mode 600, git-ignored); share it only
   with the people who should run tests. To change it, edit the file and render again.
3. The tunnel exposes only the two local ports, bound to the web server's loopback.

## Undo

Remove the site block and reload Caddy, stop the tunnel unit, delete the static directory.
