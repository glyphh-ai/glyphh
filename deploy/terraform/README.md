# rrotor with Terraform

One VM running the Docker Compose package (`deploy/compose`), its `/data` on a separate disk that outlives the
instance: `aws/` (EC2, EBS, an Elastic IP, Session Manager instead of SSH) and `gcp/` (Compute Engine, a persistent
disk, a static address, OS Login). Each has a usage example in `examples/basic/`, to copy into an empty folder. The
full guide is https://docs.glyphh.ai/terraform.

Terraform fetches the module itself from its `git::` source; nothing needs cloning.

```hcl
module "rrotor" {
  source        = "git::https://github.com/glyphh-ai/glyphh.git//deploy/terraform/aws?ref=main"
  public_host   = "rrotor.acme.com"
  runtime_id    = var.runtime_id
  runtime_token = var.runtime_token
}
```

Outputs: `connector_url`, `public_ip`, `instance_id`.

`node_count = 3` (a licence key with cluster sync) makes a cluster instead: three VMs across zones, each running
`deploy/compose/docker-compose.node.yml`, the cluster secret in the cloud's secret store, port 7778 between the nodes
only, and an AWS Network Load Balancer or Google's external HTTPS load balancer in front, health-checking `/readyz`.
See `examples/cluster/`.
