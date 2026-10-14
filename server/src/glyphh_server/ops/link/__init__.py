"""The runtime link: the WebSocket every rrotor, local or hosted, holds to the Cloud (`/v1/runtime/link`, protocol 1).

`protocol` is the messages, `hub` which server process holds which runtime's link, `presence` which runtime a token
is and whether it is online, `hello` a link's first message, `session` one link from its token to its close,
`inbound` what the rrotor's results, events and deploys change, and `calls` what other code sends down a link: a
call, a continue, a cancel, a deploy."""
