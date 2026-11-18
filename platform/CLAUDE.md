Read README.md first. The platform keeps nothing of its own: every page is the server's API, shown. The contract is
`../server/docs/architecture.md` (the API table and the section "The platform"). Glyphh's products were retired on
2026-11-18: only the sign-in, an empty Home and the staff view are left. Build the UI to Chris's design.

- The browser never holds a token: the platform signs in as a confidential OAuth client of the server and keeps
  tokens in a sealed HttpOnly cookie; its route handlers call the server with them.
- UI words: plain British English, short, concrete. Labels never darker than #999 on a dark background.
- Tests before done: every route handler and API call; the pages against a fake server.
