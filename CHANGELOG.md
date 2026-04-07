# Changelog

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
