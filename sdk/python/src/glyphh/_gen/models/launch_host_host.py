from enum import StrEnum


class LaunchHostHost(StrEnum):
    AWS = "aws"
    AZURE = "azure"
    DIGITALOCEAN = "digitalocean"
    GCP = "gcp"
    HETZNER = "hetzner"
    VPS = "vps"

    def __str__(self) -> str:
        return str(self.value)
