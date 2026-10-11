"""Print the server's OpenAPI spec: the contract the SDKs are generated from."""

import json

from glyphh_server.app import create_app

print(json.dumps(create_app().openapi(), indent=2, sort_keys=True))
