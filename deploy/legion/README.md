# Legion Tailnet deployment

This deployment is the user-approved private Tailnet endpoint for
`https://legion.tailae1646.ts.net:8449/web/`. Open WebUI runs in a separate
loopback-only container. The existing Nomadic gateway authenticates the
Tailscale identity and proxies only `/web/` to it.

The bridge and Open WebUI secrets stay in mode-0600 files under
`~/.config/nomadic-open-webui`. Open WebUI data stays in the named Docker
volume `nomadic-open-webui-data`. Neither secret belongs in Git.

The service uses the immutable source tag for commit `5fe3dbd5c`. Replace the
tag with its published digest after the multi-architecture workflow completes.
The container binds `127.0.0.1:18782` through host networking so it can reach
the loopback-only Nomadic bridge at `127.0.0.1:8490`.
