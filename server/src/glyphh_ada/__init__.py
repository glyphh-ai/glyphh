"""Ada Cloud (docs/specs/ada-cloud.md): Ada as an API inside glyphh-ai-server, behind GLYPHH_ADA_CLOUD.

The `app` process takes a request at the Ada host (`api/`), resolves its key to an org and a clearance, and puts one
message on a Redis stream; worker processes (`worker.py`, the `ada` and `adajobs` process groups) run the kernel
(ada-private's glyphh_spec and glyphh_postgres, installed privately) against the org's own Postgres schema and answer
on a reply list. The API never imports the kernel; the workers never trust a caller, only the messages the API wrote.

A worker is one single-threaded process per vCPU, so numpy's BLAS must not start a thread per CPU in each of them
(OpenBLAS does by default: four workers on four vCPUs ran 48 threads and answered a third as many reads). Set here,
before anything of this package imports numpy.
"""

import os

for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_name, "1")
