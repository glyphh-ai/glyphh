"""The runtime link: the WebSocket every rrotor, local or self-hosted, holds to the server (`/v1/runtime/link`,
protocol 2). It carries licensing only: the licence key and a self-hosted runtime's licence and runtime keys down,
the runtime's node, key use and precedents up. Nothing of a program crosses it.

`protocol` is the messages, `hub` which server process holds which runtime's link, `presence` which runtime a token
is and whether it is online, `hello` a link's first message, `session` one link from its token to its close,
`inbound` what a hello changes and the replay check, and `reports` what a usage report changes."""
