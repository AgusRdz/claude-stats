# Changelog

## v0.2.3 (2026-04-07)

### Bug Fixes

- rewrite self-update as native Go with atomic same-fs replace

[Full changelog](https://github.com/Andrevops/claude-stats/compare/v0.2.2...v0.2.3)

## v0.2.2 (2026-04-07)

### Bug Fixes

- download to temp file before replacing binary during self-update
- regenerate signing key pair

[Full changelog](https://github.com/Andrevops/claude-stats/compare/v0.2.1...v0.2.2)

## v0.2.1 (2026-04-07)

### Bug Fixes

- revert action-gh-release to v2, v3 does not exist

[Full changelog](https://github.com/Andrevops/claude-stats/compare/v0.2.0...v0.2.1)

## v0.2.0 (2026-04-07)

### Features

- add ED25519 binary signing and build provenance attestation

### Bug Fixes

- invalid Docker container name in docker-install target
- upgrade GitHub Actions to Node.js 24 compatible versions

[Full changelog](https://github.com/Andrevops/claude-stats/compare/v0.1.0...v0.2.0)

## v0.1.0 (2026-04-07)

### Features

- add auto-release script with conventional commit detection
- add 'by Andrevops' subtitle to header
- rewrite as Go binary with cross-platform install
- initial project structure with pip-installable CLI

### Bug Fixes

- kill running claude-stats process before replacing binary on Windows
- locked binary on self-update, sessions off-by-one, running indicator
- remove double-width emoji from header to fix box alignment
- remove unused turnHasRead variable in efficiency command
- use dev as version fallback, real version comes from git tags
- correct GitHub URLs and add pipx install instructions

### Other

- docs: rewrite README for Go binary install paths
- Merge pull request #1 from AgusRdz/pr/go-binary

[Full changelog](https://github.com/Andrevops/claude-stats/commits/v0.1.0)
