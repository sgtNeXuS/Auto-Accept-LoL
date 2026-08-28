# Security Policy

## Reporting a vulnerability

If you find a security issue in Auto-Accept-LoL (e.g. something that could
let a downloaded build run unintended code, or a credential/token leak),
please **do not open a public issue**.

Instead, use GitHub's private reporting:

1. Go to the [Security tab](https://github.com/sgtNeXuS/Auto-Accept-LoL/security/advisories/new) of this repo
2. Click "Report a vulnerability"

You should get an initial response within a few days. Non-security bugs
should go through the normal [issue tracker](https://github.com/sgtNeXuS/Auto-Accept-LoL/issues)
instead.

## Scope

This is a hobby project distributed as a signed Windows executable. Reports
about the release/build pipeline (`.github/workflows/`, `build.py`,
`NeXuS-CodeSigning.cer`) are especially welcome, since a compromise there
could affect anyone who downloads a release.
