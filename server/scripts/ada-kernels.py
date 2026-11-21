"""Install every kernel Ada versions list (src/glyphh_ada/ada_versions.json) that the venv does not have, each into a
folder of its own, /opt/ada/<kernel>, at the commit the list names (docs/specs/ada-cloud.md, 12.4). The latest
stable's kernel is the venv's, from uv.lock. Run by the Dockerfile's deps stage with the deploy key mounted:

    python scripts/ada-kernels.py src/glyphh_ada/ada_versions.json /opt/ada

A worker started for one of those kernels puts its folder first on its path (glyphh_ada/worker.py)."""

import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path

REPO = "git+https://github.com/glyphh-ai/ada-private"


def main(listing: str, root: str) -> list[str]:
    here = importlib.metadata.version("glyphh-kernel")
    versions = json.loads(Path(listing).read_text())["versions"]
    wanted = {v["kernel"]: v["commit"] for v in versions if v.get("installed", True)}
    made = []
    for kernel, commit in wanted.items():
        if kernel == here:
            continue
        target, spec = Path(root) / kernel, f"glyphh-kernel @ {REPO}@{commit}"
        command = ["uv", "pip", "install", "--python", sys.executable, "--no-deps", "--target", str(target), spec]
        subprocess.run(command, check=True)
        made.append(kernel)
    return made


if __name__ == "__main__":
    print("installed:", main(sys.argv[1], sys.argv[2]))
