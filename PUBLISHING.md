# Publishing Weapon Lab

The order matters. The MCP Registry accepts the listing only after the PyPI package is live. It also checks that the
README on PyPI carries `mcp-name: io.github.hpdkhoa/weaponlab-mcp`. README.md holds that line as an HTML comment.

## 1. GitHub

Push `main` to https://github.com/hpdkhoa/weaponlab-mcp and tag the release (`git tag v0.1.0`, `git push --tags`).

## 2. PyPI

Use your PyPI API token from your password manager. Do not keep it in a file.

    python -m pip install build twine
    python -m build
    python -m twine check dist/*
    python -m twine upload dist/*

twine asks for the token (user name `__token__`). Check it after: `pip install weaponlab-mcp` in a fresh
environment, then `weaponlab-mcp` starts the server (it waits for a client on stdin; Ctrl+C stops it).

## 3. The MCP Registry

In this folder (server.json is here):

    mcp-publisher login github
    mcp-publisher publish

`login github` proves you own the io.github.hpdkhoa namespace. Search for it afterwards:
https://registry.modelcontextprotocol.io/v0/servers?search=weaponlab

## Each release

Run the tests first: `python -m pytest tests` (the ToangTown checks run only on the machine that has the game).

Raise the version in three places: `pyproject.toml`, `src/weaponlab/__init__.py`, and `server.json` (both `version`
fields). Add the release to CHANGELOG.md. Build and upload to PyPI first, then `mcp-publisher publish`.
