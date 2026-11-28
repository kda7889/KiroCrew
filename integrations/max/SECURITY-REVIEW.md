# Publication security review — 2026-11-28

| Finding class | Confirmed MAX code findings | Dependency observations |
| --- | --- | --- |
| Critical / High | 0 in the reviewed integration paths | See inherited package advisories below; upstream severity is retained. |
| Medium / Low | 0 remaining in the reviewed integration paths | Electron fast-uri advisories fixed in the fork lockfile. |
| Informational | Limited review scope | This is not a certification of the entire upstream application. |

## Scope and evidence

Reviewed MAX private-message ingress, numeric owner pairing, owner API/Origin
checks, session/Bot callback ownership, binding persistence, model/tool admission,
session trust, stop behavior, egress credential screening, TLS scope and the
version-pinned build recipe. Source and installed-wheel tests exercise these
boundaries with synthetic users and tokens. The shared turn and sandbox policy
remain authoritative; MAX does not grant unrestricted shell access.

The new MAX Integration workflow uses only pull_request/push/workflow_dispatch,
a read-only token, GitHub-hosted Ubuntu, SHA-pinned actions and checkout with
persist-credentials false. It uses no bot credentials or service access. External
PRs execute as unprivileged test code. Inherited upstream paid review workflows
are not represented as successful local reviews. No self-hosted runners or
Actions secrets were configured in this fork at review time.

Repository settings: public fork and contribution routes enabled; default Actions
permission read-only and Actions review approval disabled; secret scanning and
push protection enabled; Dependabot alerts/security updates and private
vulnerability reporting enabled. Read these settings again before attaching a
runner or adding a repository secret. Do not attach a personal persistent runner
to untrusted public pull requests.

A high-confidence token/private-key pattern scan covered 27,372 materialized
tracked text files. Candidates are inherited redaction/security fixtures and
examples, not proof of a live leaked credential. Sparse-unavailable files and
all historical Git objects were not exhaustively scanned. The MAX publication
diff and release allowlist receive separate review; private runtime artifacts,
credentials, pairing codes and conversations are excluded.

## Dependency observations and limits

The MAX module adds no third-party runtime dependency. The backport deliberately
preserves the official 0.13.1 dependency contract. Compatibility checks are not
a vulnerability audit, and a compatible old stack is not necessarily current.

The exact testserver dependency inventory was checked with pip-audit. It reported
advisories for cryptography 46.0.7, pyOpenSSL 25.3.0 and opentelemetry-api 1.44.0.
Examples include [GHSA-m2h6-j472-rp4c](https://github.com/advisories/GHSA-m2h6-j472-rp4c),
[GHSA-g6cj-pr64-35w5](https://github.com/advisories/GHSA-g6cj-pr64-35w5),
[GHSA-jwv3-5hgf-82ww](https://github.com/advisories/GHSA-jwv3-5hgf-82ww),
[GHSA-537c-gmf6-5ccf](https://github.com/advisories/GHSA-537c-gmf6-5ccf),
[GHSA-vp96-hxj8-p424](https://github.com/advisories/GHSA-vp96-hxj8-p424),
[GHSA-5pwr-322w-8jr4](https://github.com/advisories/GHSA-5pwr-322w-8jr4),
[GHSA-xcq7-p3pf-p88h](https://github.com/advisories/GHSA-xcq7-p3pf-p88h) and
[GHSA-mf5v-w3w3-f6cg](https://github.com/advisories/GHSA-mf5v-w3w3-f6cg).
Confidence that these package versions are flagged: high. Exploitability across
all Crew features was not established. MAX uses Python ssl/aiohttp for HTTPS,
not a custom cryptography verifier or PKCS7 decrypt endpoint; that observation
does not clear other features of the application.

Several fixes require cryptography >=48/49/50, outside the old upstream <48
constraint. Widening a cryptographic dependency contract silently in a messenger
patch is not an accepted fix. The backport remains a development compatibility
route; upgrading the underlying Crew/dependency stack needs its own tested
change. Maintainers should integrate MAX into their supported current stack and
run its security/dependency gates before production deployment.

npm audit --omit=dev reported zero website runtime advisories. Electron's
inherited fast-uri issue was corrected with a compatible lockfile update;
its tests and dependency audit are rerun after that change. Development-only
and future advisories remain the responsibility of normal dependency maintenance.
