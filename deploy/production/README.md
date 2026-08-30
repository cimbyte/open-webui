# Production deployment

The container image is built on GitHub-hosted x64 and ARM64 runners and stored
in GHCR. Production must run on the Raspberry Pi cluster or a managed cloud
service. T14 and Legion are developer workstations. They must not be used as a
production runtime, reverse proxy, Actions runner, image or artifact store,
update server, tunnel endpoint, or deployment relay.

The repository does not perform deployment. The image workflow publishes:

- `ghcr.io/cimbyte/open-webui:git-<full-git-sha>`, an immutable source revision
- `ghcr.io/cimbyte/open-webui:main-slim`, a moving convenience tag

Deploy only an inspected digest. Resolve it from the immutable tag and put the
resulting `sha256:<64 hex characters>` value in the Kubernetes template. Never
deploy the moving tag directly.

```sh
docker buildx imagetools inspect ghcr.io/cimbyte/open-webui:git-<full-git-sha>
```

## Raspberry Pi or single-node Kubernetes

The slim image supports both `linux/arm64` and `linux/amd64`. It uses external
model APIs and downloads optional embedding or speech models on first use. Do
not add the Ollama or CUDA variants to the Pi deployment.

Before applying the template:

1. Confirm the target node is ARM64, has at least 3 GiB of available memory,
   and has enough persistent storage. Do not copy an existing workstation node
   selector into this deployment.
2. Create `open-webui-secrets` out of band with a stable random
   `WEBUI_SECRET_KEY`. Add provider credentials to that Secret only when they
   are needed.
3. If the GHCR package is private, create a read-only registry pull secret and
   reference it with `imagePullSecrets`. Do not store a registry token in Git.
4. Replace the invalid digest placeholder in
   `kubernetes/open-webui.yaml`, then apply the file.
5. Expose the ClusterIP Service through an HTTPS and WebSocket-capable ingress
   or tunnel on its own production hostname. Do not route it through a developer
   workstation.
6. Verify `/health`, persistence across a pod restart, login, WebSockets, and
   rollback to the previous digest before directing users to it.

The template intentionally uses one replica and `Recreate` because the default
SQLite database and ReadWriteOnce volume are single-writer resources. Back up
the data volume before upgrades. Move to managed PostgreSQL, shared object
storage, and Redis before adding replicas.

## Managed cloud

The same Kubernetes template can be used on a managed cluster after selecting a
production storage class. A managed container service is also suitable if it
supports a persistent volume, WebSockets, health probes, secrets, and a
digest-pinned private GHCR image. Start with one instance at 2 vCPU and 4 GiB
memory. Use the platform's workload identity or secret manager for registry and
application credentials.

Deployment automation should use cloud-native workload identity. A future Pi
deployment job may use a dedicated, restricted Pi account and ephemeral
tailnet identity. It must accept only the allowlisted GHCR repository and an
immutable digest. It must not grant a shell or reuse the Nomadic backend deploy
command. No such job is included until those production credentials and the
restricted server-side command exist.
