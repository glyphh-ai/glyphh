Read README.md first. The platform is one of three parts (platform, server, runtimes) and keeps nothing of its own:
every page is the server's API, shown. The contract is `../server/docs/architecture.md` (the API table and the
section "The platform", which lists the routes the server sends a browser to); what is not built yet is
`../server/docs/roadmap.md`. Build the UI to Chris's design; the stack is the design agent's call.

- The browser never holds a token: the platform signs in as a confidential OAuth client of the server and keeps
  tokens in a sealed HttpOnly cookie; its route handlers call the server with them.
- UI words: plain British English, short, concrete. Labels never darker than #999 on a dark background.
- Tests before done: every route handler and API call; the pages against a fake server.
