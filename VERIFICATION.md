# Verification status — 2026-11-01

## Passed locally in the cloud

- 57 shared-core tests on Linux: 54 pass, 3 platform-specific skips (two Windows filesystem/lock checks and actual PowerShell parser). Windows CI requires PowerShell; missing `pwsh` fails its parser gate rather than skipping it.
- 2 packaging tests: one combined native plugin, idempotent installation, uninstall preserves unrelated hooks.
- Compileall and privacy/layout scan: no private history, original private source files, credentials, vendor executables or cloud-absolute paths shipped.
- Real Linux WorkBuddy 5.6.2.40046327 / CLI 2.147.0: native validate, marketplace install/list, all five namespaced commands, selected-boundary branch, insert-only exact-schema synthetic database, source row unchanged, reasoning EOF roundtrip with API duration 0.
- Final combined-plugin native stress gate: five independent style creates, entire hook stdout/stderr discarded and missing interpreter still block in the host via final exit code 2. Ordinary and unrelated prompts remain silent exit 0 with dependencies available.
- Official Windows 5.9.3.42398134 installer SHA256 and static extraction verified; bundled CLI 2.165.0 and Node 22.22.2 identified. Installer was not executed.

## Still required

- Actual Windows unit/native GitHub Actions results, including final PowerShell shell exit-code propagation and native stress gates. A YAML file or Linux pass is not Windows proof.
- Desktop GUI interaction, list refresh and `workbuddy://chat` navigation are not claimed.
- Live model effects are not tested or promised. No paid model call is part of these tests.

The repository is a candidate until the actual Windows gate succeeds. Tests use only synthetic isolated profiles and do not modify an existing user profile, accounts, permissions, credentials or security settings.
