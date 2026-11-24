# Contributing

Thank you for helping. This repository takes changes **only by pull request**.

## What is here

One thing: Ada. **Ada Cloud** is Ada as an API that Glyphh runs: its client in the SDKs (`Ada`), the `ada` and
`glyphh-cli` skills, the `glyphh` command, its contract (`contract/contract.json`, recorded from a real server), and
the plugin's account panel and sign-in. Nothing that is not Ada, its account or its sign-in belongs here (a test
checks the docs and skills name nothing else); other plugins and skills live in
[glyphh-ai/plugins](https://github.com/glyphh-ai/plugins).

## How a change gets in

1. Fork the repository and make a branch from `main`.
2. Make one focused change, with its tests, and run the checks the README names.
3. Open a pull request against `main` that says what it changes and why. Link the issue if there is one.
4. A Glyphh maintainer reviews it. It is merged only when the checks pass and every conversation is resolved.

`main` is protected: nobody, maintainers included, pushes to it directly, force-pushes or deletes it. Every change,
ours too, goes through a pull request.

## Releases

Only Glyphh maintainers release. Releases are cut from `main` after the pull requests in them have merged; release tags
are restricted to maintainers. A pull request never publishes a package, and contributors never need registry
credentials.

## Licence

By opening a pull request you agree that your contribution is licensed under the licence of the part you change (see
[LICENSE](LICENSE)): the MIT License for sdk/, contract/ and benchmarks/; the Glyphh terms for plugins/. No
separate agreement is needed: the pull request is your submission.

## Bugs, questions and security

Bugs and requests: open an issue. Security problems: do not open a public issue; email support@glyphh.ai.
