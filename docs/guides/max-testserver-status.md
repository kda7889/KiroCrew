# MAX after the testserver move — 2026-11-24

Read-only migration review, not a deployment or a successful preflight.
Source checkpoint: `6573ca6b0ca3bdd06e2dc54c112dd3d1e489a156`, branch
`codex-dev/max-messenger`, clean working tree at entry. Source root:
`/home/adminuser/.kiro/crew/workspace-member-codex-dev/kirocrew-max-source`.

**Follow-up result:** source npm dependencies restored; five MAX component tests
and three selected transport tests passed on testserver. Browser/OS/live evidence
is still missing. Native read-only process diagnostics returned an owner-scope
denial. Details below; initial inspection facts remain historical snapshots.

## Initial migration inspection

The worker's actual hostname is `testserver`. Resource status at inspection:
17.7 GB available, 24 CPUs, AMPLE; this replaces the parent's earlier 21.9 GB
sample, not a reservation. Disk has about 25 GB available. No build or workers
were started. Existing `website/dist` is a transferred build, stamped
`1.0.0-9c73721`, website tree `e846bde40c04f98e310c89699c733e6d750a64a2`.
It was not rebuilt or browser-tested on this host.

Node 24.22.3 and npm 10.9.8 are present. `website/node_modules` is absent, so the
prepared fixture runner cannot currently resolve its Playwright dependencies.
The lockfile still specifies Playwright/@playwright/test 1.58.2, TypeScript5.9.3,
Vite8.3.4, Vitest4.1.12 and React18.3.1. No npm install or browser download had
run at that inspection; the later authorized restoration is recorded below.
The worker-visible Playwright cache path is absent; that does not prove the
native gateway has no browser, because it uses a different browser manager.

The copied test interpreter works: Python3.12.13, pytest9.0.3 and formatting tools
are present. By itself that venv cannot resolve aiohttp. With the prior read-only
0.13.1 site-packages fallback, all 32 applicable source core requirements have
distribution metadata; cryptography50.0.2 violates this source's `>=42,<48` range.
This is a metadata check, not a working import/runtime proof. Missing pydantic/mcp
metadata is not itself a missing core requirement: neither is declared in this
source's core install list. Python source version is0.14.0; the fallback's
`kirocrew` metadata is0.13.1. Do not treat the mixed test environment as an
approved candidate installation, or change the installed gateway to repair it.

## Browser profile: evidence boundary

The parent reported native Chromium exit21, profile ownership `ai-ubuntu:1680`.
That fresh failure differs from the previous host's sandbox launch failure.
The worker did not relaunch Chromium or rerun denied namespace/browser probes.

The worker has `KIROCREW_SANDBOX_ACTIVE` set. Source declares `browser-profile`
HIDDEN, so its visible empty directory is a sandbox view, not evidence that the
real profile or singleton links are absent. No visible local Chromium process
was found in this process view; this says nothing about PID1680 on ai-ubuntu.
Actual current singleton metadata and the old owner's liveness remain unverified.

The existing repair script outside this repo hardcodes `EXPECTED_LOCK =
'Ai-Agents-793'`. Its historical backup contains that old lock target. Neither
matches the newly reported `ai-ubuntu:1680` owner. No repair/check/apply/rollback
mode of that script was executed or edited. Profile files, locks and backups
were not removed, moved, copied or opened for their contents.

The next permitted owner step is **metadata only**, in an ordinary terminal on
each relevant host. This script refuses the sandboxed agent context. It reads
only link metadata and the explicitly named PID's process identity/profile flag:

```bash
python3 - <<'PY'
import json, os, socket, stat, subprocess
from pathlib import Path
if os.environ.get('KIROCREW_SANDBOX_ACTIVE'):
    raise SystemExit('Use the existing ordinary host terminal; do not clear this marker')
print('host', socket.gethostname())
profile = Path('/home/adminuser/.kiro/crew/browser-profile')
for name in ('SingletonLock', 'SingletonSocket', 'SingletonCookie'):
    p = profile / name
    try:
        s = p.lstat()
        print(json.dumps({'name': name, 'uid': s.st_uid,
            'symlink': stat.S_ISLNK(s.st_mode), 'mtime_ns': s.st_mtime_ns,
            'target': os.readlink(p) if name == 'SingletonLock' and p.is_symlink() else None}))
    except FileNotFoundError:
        print(name, 'absent on this host view')
subprocess.run(['ps', '-p', '1680', '-o', 'pid=,comm=,lstart=,user='], check=False)
try:
    args = Path('/proc/1680/cmdline').read_bytes().split(b'\0')
    print('pid1680_profile_flags', [a.decode(errors='replace') for a in args
        if a.startswith(b'--user-data-dir=')])
except OSError as e:
    print('pid1680 metadata unavailable', type(e).__name__)
PY
```

Do not remove a lock based only on a migrated hostname or a missing PID on
testserver. Confirm old-host ownership/profile use first. This document does
not authorize a repair, closing another owner's browser, a profile reset, an
auth mint, a policy change or a gateway restart.

## Git transport and preservation

Both default Git and a command-local HTTP/1.1 `ls-remote origin refs/heads/main`
exceeded12 seconds. Only the diagnostic's own process groups were stopped.
No global Git configuration was changed. curl Smart-HTTP discovery GET with
`Git-Protocol: version=2` succeeded: HTTP200,191bytes,3.42s; HEAD returned405.
DNS/TCP/TLS therefore worked for that request. The exact later Git stall stage
is unknown; this is not proof of a dead server or invalid credentials.

Existing authenticated `gh api` reads succeeded without an auth flow:
public main was `177f0eacb1dc635bd7d9abc0cf1dd4aedd60b2cb`; the feature branch
ref returned404. Local origin/main remains `230514b679ba349052d6f8fd1eae838bdd5ddd7d`.
Eight MAX commits above that cached base were local at entry; compatibility with
the new public main has not been tested. A bounded API compare request also
timed out after12seconds, so no ahead/behind count against live main is claimed.
No fetch/rebase/push/PR was attempted.

The Git-sync state was read at
`/home/adminuser/.local/state/crew-repository-sync/last-results.json`:
checked2026-11-24T19:31:12Z, needs_attention0,20 repositories. This MAX checkout
is not among them. That green service result therefore does not mean MAX is
backed up remotely. The six previous source patches remain present, but that
recipe excludes the later browser/OS test and operator-doc commit. Preserve the
full local branch on any further move. Current task instructions prohibit push;
no remote preservation is claimed.

## Remaining gates and allowed sequence

1. Review the two-host singleton metadata. Native browser access stays pending
   while ownership is unresolved; no lock/profile repair is approved here.
2. Source npm restoration is now complete under the later owner authorization.
   A proper source Python environment still needs to satisfy its version ranges;
   the fallback cryptography mismatch remains. Do not modify the installed gateway
   environment or wait for another npm confirmation.
3. In an already permitted host context, run the prepared fixture browser runner:
   six PASS lines and review of its two screenshots are required. No real API,
   auth token, bot secret, subscription or backend listener is involved.
4. Run the prepared MAX real-kernel fence test through the normal approved
   procedure. Require one passed, not a skip. Do not clear sandbox markers or
   weaken namespaces/seccomp/AppArmor to manufacture a result.
5. Complete source review, then make a separate pinned candidate/live decision.
   Fresh owner Secrets/HTTPS and live smoke belong to that later step.

Previous full source gates/build measurements remain historical evidence from
ai-ubuntu. The initial inspection did not run them again; the new narrow tests
below are separate testserver evidence, not a new build/browser/OS pass.
Live MAX, installed gateway, listeners, credentials and upstream are unchanged.
See [candidate procedure](max-candidate.md) for the prepared commands and limits.

## Follow-up authorization and supported access

The owner subsequently authorized ordinary source checks and npm restoration
in this checkout. No separate confirmation is needed for that restoration.
Resource status immediately before it:17.5GB available, AMPLE. The command uses
the existing package lock, verified TLS and `--ignore-scripts`; the repository's
explicit happy-dom postinstall patch must run before component tests. This is
source dependency work, not an installed gateway update. Results follow.

The parent's longer `git ls-remote` subsequently obtained public main
`177f0eacb1dc635bd7d9abc0cf1dd4aedd60b2cb`. The earlier12s results are short
diagnostic deadlines, not evidence that Git access is absent. No transport or
credential change is justified by those timeouts alone.

The infra runbooks document an ordinary SSH jump and a reserve transfer route.
An ordinary read-only connection through the public jump failed with connection
refused; the documented VPN jump reached strict host-key verification and failed
because the worker had no trusted ED25519 host key for that jump. Batch mode and
strict checking stayed enabled; no trust file was edited. The reserve loopback
TCP forward is reachable, which does not authenticate its SSH endpoint or prove
anything about a browser process. Its separate transfer key is restricted to
file reception, not a general shell; it was not borrowed for process inspection.
No current hidden profile was read through another route. Old-host PID/profile
ownership remains unconfirmed; do not run the old repair or launch the affected
native profile based on these network facts.

### Source restoration and tests completed

The first network ci was interrupted after17m45.94s: actual exec exit143/SIGTERM,
maximum RSS388264KiB. It had logged1169 successful GETs, followed by a long quiet
log. This was **not proof of a hung download**. It was stopped before checking
tarball byte progress, which caused an unnecessary repeated Excalidraw download.
The diagnostic was corrected to inspect temporary artifact size/mtime. No other
process was signalled, and no current profile/browser lock was touched.

A standard offline ci then failed with ENOTCACHED for the exact locked
`@excalidraw/excalidraw@0.18.1` tarball: exit1,24.71s,RSS1359756KiB. A cache-index
comparison found no other missing nonoptional locked tarball URL. Manifests from
an incomplete install were not counted as a successful dependency restoration;
the failed ci had removed React, so tests were held until a complete ci passed.

The exact lockfile tarball was added with npm's normal cache command and verified
TLS. Its temporary file grew continuously; a one-byte HTTP206 range response
reported total size31234066bytes. Cache add finished exit0,11m18.62s,
maximum RSS167128KiB,swaps0. The lock's integrity was retained and the subsequent
ci performed normal integrity validation. No alternate package/version, omitted
dependency, disabled TLS check or registry rewrite was used.

Working directory for these commands is the source checkout's `website`:

```bash
npm cache add 'https://registry.npmjs.org/@excalidraw/excalidraw/-/excalidraw-0.18.1.tgz' --strict-ssl=true --cafile=/etc/ssl/certs/ca-certificates.crt
/usr/bin/time -v npm ci --offline --ignore-scripts --no-audit --no-fund
CI=1 node scripts/patch-happy-dom-iframe.mjs
/usr/bin/time -v node node_modules/vitest/vitest.mjs run src/pages/settings/MaxPanel.test.tsx --maxWorkers=1 --coverage.enabled=false
/usr/bin/time -v node node_modules/vitest/vitest.mjs run src/test/ApiClient.refactor.surface.test.ts --testNamePattern='MAX owner settings transport' --maxWorkers=1 --coverage.enabled=false
```

| Final check | Exit | Result | Maximum RSS KiB | Wall |
|---|---:|---|---:|---:|
| Offline ci |0|1207 packages|1428296|21.51s|
| MAX component file |0|5 passed|469396|4.25s|
| MAX transport filter |0|3 passed / 193 skipped|572308|4.53s|

All three runs reported zero swaps. Fresh resource checks were AMPLE17.8GB before
the final ci and17.9GB before tests; one test worker, sequential runs. The normal
happy-dom postinstall patch passed in fail-closed CI mode. Eight actual package
versions matched the lock: React18.3.1,ReactQuery5.96.0,Vite8.3.4,Vitest4.1.12,
TypeScript5.9.3,happy-dom20.11.6,Playwright/@playwright/test1.58.2. Fixture-runner
syntax and its real module imports also passed, without launching a browser or
static server. The Vite future-native-config warnings were not suppressed.

Package/lock, production source, public assets and Vite config did not change.
The full196 API tests, tsc, index and build were not repeated. These narrow tests
prove their own assertions under restored real dependencies, not whole-SPA,
browser rendering, OS confinement or live delivery. No real credentials,
subscription, listener, candidate install or gateway restart occurred.

### Proven owner boundary

The available native read-only tool was called once:
`debug_processes({format:"flat",kind:"browser",include_env:false})`.
It returned `member_scope_denied` with this exact message:

> This operation requires the owner. Use the member's scoped tools instead.

The worker did not retry with a different shape, principal, tool or shell reader.
The blocked-by-policy skill was read; ordinary source work continued. This proves
that this particular diagnostic requires an owner context, not that the tool is
missing. It also does not prove the old browser is unused.

The remaining profile step is read-only owner/host metadata in an already trusted
context: identify the actual ai-ubuntu PID1680 and whether it uses that profile,
then review the current testserver lock metadata through a supported owner path.
The earlier ordinary-host snippet is prepared for that purpose. Do not send
credentials through chat, loosen the member scope, clear a sandbox marker or use
the file-transfer key as a shell credential. A repair remains a separate decision
after real ownership evidence; the old hardcoded repair is still inapplicable.
