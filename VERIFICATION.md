# Verification — 2026-11-01

## Real Windows cloud result: PASS

Verified implementation commit: [`63c1b4e31f0818d59d5b411da0f750c912e5990b`](https://github.com/bartholo4/workbuddy-plugins/commit/63c1b4e31f0818d59d5b411da0f750c912e5990b).

- [Native Windows run 41301284752](https://github.com/bartholo4/workbuddy-plugins/actions/runs/41301284752): **success**, GitHub-hosted Windows Server 2025.
- [Windows/Linux × Python 3.10/3.12 matrix 41301284940](https://github.com/bartholo4/workbuddy-plugins/actions/runs/41301284940): **all four jobs successful**.
- Native diagnostic artifact `13081881016`, SHA256 `497d18185319d6d80ed451e47d64282299fdce25a3ac19e93410236c82332484` (retention limited by GitHub).

The Windows job downloaded official WorkBuddy **5.9.3.42398134**, verified pinned SHA256, statically extracted NSIS/app-64.7z/Node ZIP without executing the installer, and ran its real **CLI 2.165.0** with bundled **Node 22.22.2**. It selected the shipped **lite-WB** bundle; the separate Linux adapter selects its headless bundle.

Passed in the real Windows host:

- Native plugin validate, marketplace add/install/list, unified five-command namespace.
- Selected-boundary conversation branching; same workspace; source database row unchanged.
- Insert-only registration against the exact synthetic 40-column schema.
- Reasoning seed creation and native EOF resume/fork roundtrip; **API duration 0**.
- Five additional independent style creations.
- Entire hook stdout/stderr discarded: final shell exit **2** still blocks.
- Missing interpreter: shell guard still blocks rather than forwarding to a model.
- Owned uninstall and installation idempotence.

Unit gates cover 57 core cases plus 2 packaging cases. Windows actually executes cross-process file-lock and PowerShell parser tests, including spaces, quotes, metacharacters and non-ASCII arguments; external Python exits 1 and 2 both produce final PowerShell exit 2. Platform-inapplicable POSIX/symlink-privilege cases are explicitly skipped; a missing Windows `pwsh` fails, never silently skips.

## Linux regression: PASS

Real official Linux WorkBuddy **5.6.2.40046327 / CLI 2.147.0** completed the same combined-plugin native flow, five-repeat style stress, discarded-output guard, missing-interpreter guard and synthetic database checks. The shared-core Linux run passed 54 cases with 3 genuine Windows/PowerShell-specific skips; both packaging cases passed.

## Scope and remaining limitations

- Desktop GUI buttons, list refresh and `workbuddy://chat` navigation are **not tested or claimed**. Windows proof is the real native CLI/hook/storage path, not a visual GUI simulation.
- Live model effects are **not tested or promised**. No paid model call is part of these tests. Reasoning persistence is not a guarantee of intelligence, wording or provider behavior.
- All native tests use newly created synthetic HOME/profile/workspace and a credential-free environment. No existing user profile, account, source history, security setting or vendor installation was modified.
- The public repository does not bundle vendor executables, private history, original private source files or credentials.
- Source code changes after the linked commit must be revalidated. Version/verification-document promotion does not replace CI for its resulting commit.
