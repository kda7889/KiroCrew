# MAX gates on a separate Ubuntu

Prepared commands only: no SSH connection, remote install or gateway operation
has been performed. Use an owner-selected machine, SSH alias and fresh directory.
Copy only the six reviewed source patches, never a data home, `.env`, vault,
auth store, signing key, SSH key, browser profile or installed venv.

## Resource decision

The local API surface gate passed 196 tests. GNU time reported maximum RSS
509784 KiB (about 498 MiB), swap count zero, elapsed 2.63 seconds. This is GNU
time's reported maximum, not the simultaneous RSS sum of parent and worker.
Vite's documented heavy single-fork range is 1.0–1.4 GB; this measurement belongs
only to the selected file. One worker was used, with the project's own settings.

The UI generator holds parsed ASTs for all production sources in a Map
(`website/scripts/gen-ui-index.mjs`); the complete SPA typecheck follows the
dashboard dependency graph. Prior heap failures at 640/1024 MiB are lower bounds,
not measurements of successful peak RSS. Local available memory was 2.9 GB TIGHT.
That does not leave a safe reserve for an unmeasured multi-GiB graph. Do not replay
those failed limits or start a parallel build.

Later, local available memory rose to 4.5 GB. The full strict UI-index gate
completed with a 3 GiB heap; regeneration added the MAX tab/label and its check
passed with maximum RSS 1837156 KiB (about 1.75 GiB), swaps zero. A later full
`npm run typecheck` found one unused React import in MaxPanel. After removing it,
the same full command passed with heap3072, maximum RSS3495336 KiB (about
3.33 GiB), elapsed67.14 seconds and swaps zero. Available memory before each
attempt was 4.4 GB AMPLE. The remote budget below remains conservative.

On the gate machine, require at least 6 GiB **MemAvailable** before each graph
gate. This reserves space above the proposed 4 GiB Node heap for native allocations,
the OS and other processes. It is a conservative admission rule, not a promise
that every graph fits. Record peak RSS and stop on a failure; do not automatically
loop with larger heaps. An 8 GiB host may qualify only when enough memory is free.

## Transfer reviewed source

First, in the owner's terminal on Ubuntu, choose and export `MAX_GATE_ROOT` as a
new absolute directory. The first mkdir must fail if it already exists:

```bash
: "${MAX_GATE_ROOT:?Choose a fresh absolute gate directory}"
mkdir "$MAX_GATE_ROOT"
mkdir "$MAX_GATE_ROOT/patches"
```

In the local owner terminal, set `MAX_GATE_SSH` to the configured SSH host alias
and `MAX_GATE_ROOT` to that same remote directory. This uses the owner's normal
SSH authentication; no credentials are copied into the task:

```bash
: "${MAX_GATE_SSH:?Choose the Ubuntu SSH alias}"
: "${MAX_GATE_ROOT:?Set the existing remote gate directory}"
scp /home/adminuser/.kiro/crew/workspace-member-codex-dev/max-integration.patch /home/adminuser/.kiro/crew/workspace-member-codex-dev/max-production.patch /home/adminuser/.kiro/crew/workspace-member-codex-dev/max-review.patch /home/adminuser/.kiro/crew/workspace-member-codex-dev/max-followup.patch /home/adminuser/.kiro/crew/workspace-member-codex-dev/max-ui-index.patch /home/adminuser/.kiro/crew/workspace-member-codex-dev/max-typecheck.patch "$MAX_GATE_SSH:$MAX_GATE_ROOT/patches/"
ssh "$MAX_GATE_SSH"
```

On Ubuntu, export `MAX_GATE_ROOT` again in the new shell, then:

```bash
set -euo pipefail
: "${MAX_GATE_ROOT:?Set the chosen gate directory}"
cd "$MAX_GATE_ROOT/patches"
sha256sum -c <<'HASHES'
317b771a01781f2f4057dec0786d98a3df1e8c847ea8c03d1d2bdfb6caa4dda6  max-integration.patch
3d9cd1b48f9841830cc7035cd396fd4ca70d7c819996df316a3c9355083cf71a  max-production.patch
2831a2473d662fc3672596977e8a8247b10309b6f5c01be461caa5c6164b6820  max-review.patch
58ebd5c6b9d6279fd46b87818b04563fefe70e70e3f730e89f4909d43070a92d  max-followup.patch
46a5c4e402ba02c6176d7687892a4b87850c8f0a856e864dc75e059cc67c2c99  max-ui-index.patch
31ccc2d06ba331c53b9a643f9d50fa39e73484bc05e78a279b2c30c27fc21999  max-typecheck.patch
HASHES
git clone --filter=blob:none --no-checkout https://github.com/kirodotdev/KiroCrew.git "$MAX_GATE_ROOT/source"
cd "$MAX_GATE_ROOT/source"
git fetch --depth=1 origin 230514b679ba349052d6f8fd1eae838bdd5ddd7d
git switch -c codex-dev/max-messenger 230514b679ba349052d6f8fd1eae838bdd5ddd7d
for patch in max-integration.patch max-production.patch max-review.patch max-followup.patch max-ui-index.patch max-typecheck.patch; do
  git apply --check --index "$MAX_GATE_ROOT/patches/$patch"
  git apply --index "$MAX_GATE_ROOT/patches/$patch"
done
test "$(git write-tree)" = 5e72ed4c19c35e74e42291dd33028182ee7194d8
git diff --cached --check
```

These six patches reconstruct source commit
`38882c4a593f3f4792208d91d4b68b471b4ff0df` plus the reviewed generated MAX index
and the unused-import fix
on public base `230514b6`. Later operator-documentation-only changes are excluded.
They do not recreate its commit metadata: HEAD remains the public base and the
candidate is staged. Record that distinction. This recipe runs full-source
type/index commands, not diff-scoped ratchets that could inspect the wrong HEAD.
The local reconstruction was verified in a temporary alternate index; unchanged
base blobs still need the public source fetch. This is not an offline repository.

## Run one gate at a time

Prerequisites: an already installed Node >=22.12.0, npm, Git and GNU time. The
tested local Node was 24.22.3. Do not bootstrap a gateway, provider login or agent.
Development dependencies below belong only to this new checkout.

```bash
cd "$MAX_GATE_ROOT/source/website"
node --version
npm ci --ignore-scripts --no-audit --no-fund --strict-ssl=true --cafile=/etc/ssl/certs/ca-certificates.crt
node scripts/patch-happy-dom-iframe.mjs
```

If TLS verification fails, stop and fix the machine's trusted CA configuration
through its owner. Never disable verification or copy an auth file to fix a build.

Run this admission check immediately before **each** following gate:

```bash
awk '/MemAvailable:/ { found=1; if ($2 < 6291456) { print "Need at least 6 GiB MemAvailable"; exit 1 } } END { if (!found) exit 1 }' /proc/meminfo
free -h
```

Then, sequentially in the foreground, keeping each output and exit code:

```bash
set -o pipefail
NODE_OPTIONS=--max-old-space-size=4096 /usr/bin/time -v npm run typecheck 2>&1 | tee "$MAX_GATE_ROOT/typecheck.log"
# Recheck memory admission here before the next command.
NODE_OPTIONS=--max-old-space-size=4096 /usr/bin/time -v npm run gen:ui -- --check 2>&1 | tee "$MAX_GATE_ROOT/ui-index.log"
```

Stop if typecheck fails. A UI freshness exit 3 means stale output, not an OOM:
after checking memory, run `npm run gen:ui` with the same Node heap, inspect
`git diff -- src/kiro_crew/docs/ui-index.generated.json website/src/uiLocations/guidePlans.gen.ts`
from the source root, and rerun the strict check. Do not substitute warning-only
mode or commit unreviewed generated output. Return diagnostics/logs and any new
generated diff for review; no push is part of this procedure.

No frontend build, runtime installation, listening port, MAX subscription or real
token is needed for these two gates. Passing them does not prove OS sandbox
enforcement or live delivery. Continue with the separately reviewed
[candidate procedure](max-candidate.md) only after the remaining source and OS
checks pass. Never reuse the installed gateway's credentials for this test.
