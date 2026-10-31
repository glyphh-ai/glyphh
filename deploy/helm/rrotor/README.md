# rrotor Helm chart

rrotor, the runtime that hosts your programs and CLIs, on Kubernetes. One rrotor per release: a StatefulSet of one
replica, its `/data` on its own volume, an Ingress at the one public host; or, with `cluster.enabled=true` and a
licence key with cluster sync, `replicas` nodes (default 3) of one runtime behind the same Service and Ingress.
`values.yaml` says what each setting does, and what the cluster must allow for the sandbox.

Install it from a checkout of this repository:

```sh
git clone --depth 1 https://github.com/glyphh-ai/glyphh.git
helm install rrotor glyphh/deploy/helm/rrotor -n rrotor --create-namespace \
  --set publicHost=rrotor.acme.com \
  --set runtime.id=<runtime id> --set runtime.token=<runtime token> \
  --set ingress.className=nginx --set ingress.certManagerClusterIssuer=letsencrypt
```

The connector is then at `https://<publicHost>/mcp`; apps call it with a runtime key. The image is
`ghcr.io/glyphh-ai/rrotor` at the chart's `appVersion`.
