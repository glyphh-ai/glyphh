from enum import StrEnum


class NewHostHost(StrEnum):
    AWS = "aws"
    AZURE = "azure"
    DIGITALOCEAN = "digitalocean"
    DOCKER = "docker"
    FLY = "fly"
    GCP = "gcp"
    HETZNER = "hetzner"
    VPS = "vps"

    def __str__(self) -> str:
        return str(self.value)
