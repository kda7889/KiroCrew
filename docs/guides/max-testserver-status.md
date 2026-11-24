# MAX after the testserver move — 2026-11-24

Read-only migration review, not a deployment or a successful preflight.
Source checkpoint: `6573ca6b0ca3bdd06e2dc54c112dd3d1e489a156`, branch
`codex-dev/max-messenger`, clean working tree at entry. Source root:
`/home/adminuser/.kiro/crew/workspace-member-codex-dev/kirocrew-max-source`.

## What is present

The worker's actual hostname is `testserver`. Resource status at inspection:
17.7 GB available, 24 CPUs, AMPLE; this replaces the parent's earlier 21.9 GB
sample, not a reservation. Disk has about 25 GB available. No build or workers
were started. Existing `website/dist` is a transferred build, stamped
`1.0.0-9c73721`, website tree `e846bde40c04f98e310c89699c733e6d750a64a2`.
It was not rebuilt or browser-tested on this host.

Node 24.22.3 and npm 10.9.8 are present. `website/node_modules` is absent, so the
prepared fixture runner cannot currently resolve its Playwright dependencies.
The lockfile still specifies Playwright/@playwright/test 1.58.2, TypeScript5.9.3,
Vite8.3.4, Vitest4.1.12 and React18.3.1. No npm install or browser download ran.
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
2. Separately authorize a source-only dependency restoration in this checkout,
   using the lockfile and a proper source test environment. Do not reuse or
   modify the installed gateway environment. This inspection performs no install.
3. In an already permitted host context, run the prepared fixture browser runner:
   six PASS lines and review of its two screenshots are required. No real API,
   auth token, bot secret, subscription or backend listener is involved.
4. Run the prepared MAX real-kernel fence test through the normal approved
   procedure. Require one passed, not a skip. Do not clear sandbox markers or
   weaken namespaces/seccomp/AppArmor to manufacture a result.
5. Complete source review, then make a separate pinned candidate/live decision.
   Fresh owner Secrets/HTTPS and live smoke belong to that later step.

Previous source gates/build measurements remain historical evidence from
ai-ubuntu. No new source/build/browser/OS success is claimed on testserver.
Live MAX, installed gateway, listeners, credentials and upstream are unchanged.
See [candidate procedure](max-candidate.md) for the prepared commands and limits.
