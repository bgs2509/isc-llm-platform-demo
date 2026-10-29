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
2. Web server: `git clone` this repository; on the GPU host run `site/build.py` and `deploy/render.py`, then
   copy the two git-ignored results (`site/dist` as `deploy/origin/site/`, `deploy/origin/auth.caddy`) with a
   `tar` pipe; `docker compose up -d` in `deploy/origin/`.
3. GPU host: a new key for the tunnel only. On the web server its `authorized_keys` line starts with
   `restrict,port-forwarding,permitlisten="127.0.0.1:19500",permitlisten="127.0.0.1:19501",command="/bin/false"`
   (options as in `man sshd`); install the unit from the template with `systemctl --user enable --now`.
4. Existing Caddy: add the block and the variable (`deploy/portal/`), validate, recreate the container.
5. Web server firewall: with `ufw` and an input policy of DROP, packets from the portal's Docker network to the
   docker0 address are dropped (`[UFW BLOCK] ... DPT=19080` in `/var/log/ufw.log`). Allow that one port:
   `sudo ufw allow from <portal network subnet> to 172.17.0.1 port 19080 proto tcp`.
6. Verify: `https://<host>:9443/` returns the home page; `/console/` and `/grafana/` answer 401 without the
   password and the console and the dashboard with it.

## Pitfalls met

1. The origin's site address has no host (`http://:19080`, with `bind` for the address): the portal passes the
   public name in `Host`, and a site address with a host makes Caddy answer an empty 200 to every path.
2. The origin's Caddyfile is a single-file bind mount: after `git pull` recreate the container
   (`docker compose up -d --force-recreate`), a restart keeps the old file.
3. Checks from the web server itself go over loopback and pass the firewall; check from a container on the
   portal's network or from outside.

## Security

1. The console starts real load on a GPU, so `/console/` and `/grafana/` are behind HTTP basic auth over HTTPS.
2. The password is in `deploy/.site-credentials` on the GPU host (mode 600, git-ignored).
3. The tunnel key should be restricted in `authorized_keys` to opening these two loopback ports only.
4. The origin listens on the docker0 address only, not on a public interface.

## Undo

Remove the block and the variable from the existing Caddy and recreate it; `docker compose down` in the origin
directory; stop the tunnel unit; delete the directory.
