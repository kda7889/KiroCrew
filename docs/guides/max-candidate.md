# MAX candidate: source review, isolated install and live proof

This is an operator procedure, not an executed deployment. The source has a
webhook receiver and owner Settings controls. No MAX live delivery has been
proved. Do not publish upstream before the live checks pass.

## Versions and gates

Source: branch `codex-dev/max-messenger`, base
`230514b679ba349052d6f8fd1eae838bdd5ddd7d`, package **0.14.0**. The currently
installed gateway reports **0.13.1**. This is a candidate of a newer source tree,
not an adapter file to copy into the installed venv. Migration of an existing
0.13.1 data home has not been tested. Use a fresh isolated data home.

Before installation, record the candidate's full commit ID, require a clean
working tree and review the cumulative diff from that base. Complete the project's
format/import/type/i18n/UI-index gates, the targeted MAX and auth tests and the
frontend build in a resource window that permits them. The working report lists
the gates actually run and those still missing; component mocks are not a whole
SPA or browser proof. Never use 0.13.1 frontend assets to fill a candidate build.

Use the project's lightest applicable gate first. The API factory and its real
`ClientTransport` can be type-checked without loading the dashboard facade;
the existing facade composition test checks that MAX's methods reach that facade
unchanged. Target its MAX transport cases to prove relative same-origin paths and
empty POST bodies. These checks do not replace the complete panel/SPA typecheck.

The earlier 640/1024 MiB heap failures are historical attempts, not required
budgets or readiness conditions. Do not replay them. When resource status permits
the remaining graph-wide work, run `npm run typecheck`, then
`npm run gen:ui -- --check`, sequentially using normal project/runtime defaults.
If the latter reports stale output, run `npm run gen:ui`, review and commit the
generated changes, then check again. Do not use warning-only mode as a passing
freshness gate. No arbitrary wall-clock deadline is part of this procedure;
pairing/login expiry and protocol timeouts remain security requirements.
If the local host cannot admit that graph with a reserve, use the
[separate Ubuntu gate procedure](max-ubuntu-gates.md). It transfers only reviewed
source and runs no gateway, provider login, subscription or real token.

The root CONTRIBUTING guide and install guide own `make build` and its dependency
setup. A sparse checkout must first materialize their Makefile, packaging files
and frontend inputs. Do not build from a partly downloaded tree. Neither a failed
download nor a missing tool is a passing gate.

## Isolated candidate, only after source review

### Credential-free browser and OS evidence before a candidate

The production Vite bundle and SDK declaration emit were built locally from
source checkpoint `9c73721b`; the report records commands and RSS. This did not
stage assets into the installed gateway. Browser evidence remains missing:
Chromium with `chromiumSandbox: true` failed with **No usable sandbox** in the
agent execution context. No retry with sandbox disabled is allowed.

The prepared runner uses the real built SPA, the existing loopback-only static
preview helper and API fixtures. It starts no backend and performs no auth mint.
It checks disabled controls, teammate hiding, paired state, code display,
explicit subscription success and forbidden subscription failure. Every POST is
intercepted and must have an empty object body. Unexpected external requests fail.
The code and subscription responses are synthetic; they grant no access anywhere.

On a reviewed host where Chromium sandboxing and loopback previews are already
permitted, run from the source checkout in an ordinary operator terminal:

```bash
cd /home/adminuser/.kiro/crew/workspace-member-codex-dev/kirocrew-max-source/website
: "${MAX_PREFLIGHT_EVIDENCE:?Choose an absolute evidence directory}"
node scripts/verify-max-settings.mjs "$MAX_PREFLIGHT_EVIDENCE"
```

Expected result: six `PASS` lines and two screenshots. The runner closes Chromium
and its static preview after the checks. It does not amend the dashboard's allowed
preview origins or require a logged-in browser. Do not substitute an auth token,
live data home or backend endpoint. If the host refuses sandboxing or previews,
stop; do not disable namespace/seccomp/AppArmor policy. The six browser scenarios
have **not run successfully** in this agent context; syntax checks alone do not
prove them. Review screenshots after a successful run.

For MAX storage, `test/test_max_os_fence.py` is an explicit real-kernel check.
It uses a fresh temporary data home and synthetic state, asserts a different
mount namespace, denies reading/overwriting/creating MAX state, and requires a
writable sibling control. It never clears the launcher marker or relaxes policy.
The exact local check used this existing test interpreter and read-only
dependency path, with source taking precedence. Run from the source root in a
permitted ordinary host terminal; neither environment needs copying or updating:

```bash
PYTHONPATH=src:/home/adminuser/.kiro/crew-venv-0.13.1/lib/python3.12/site-packages /home/adminuser/.kiro/crew/workspace-member-codex-dev/max-test-env/bin/python -m pytest -o addopts='' test/test_max_os_fence.py -q -rs --disable-warnings --maxfail=1
```

These are this machine's existing paths, not a portable install command. Require
**one passed**, not a skip. The local run skipped because user namespaces were
unavailable. A separate source probe reported `inside_kirocrew_sandbox=true` and
`unshare(CLONE_NEWUSER): EPERM`, which describes this execution context, not the
capability of an ordinary host terminal. Neither result proves MAX OS isolation.
No sysctl, AppArmor, seccomp, namespace flag or runtime marker may be weakened to
obtain evidence. Keep this gate open if no permitted execution context is ready.

The next step after green source gates is to review a pinned candidate-install
plan: full commit/base/package versions, isolated data/venv, chosen free loopback
port, and stop/rollback steps. Before any real MAX setup, verify the candidate's
own built Settings shell with MAX disabled and no channel credentials: the owner
sees the setup hint and disabled pairing action, and non-owner API requests deny.
Use local fixtures for active pairing/subscription UI flows; do not register a
subscription to test a button. Do not copy the live home's files, vault, signing
keys, tokens or frontend assets. If bootstrap asks for an unrelated provider
sign-in, stop that step and use the fixture-backed UI check; do not alter the live
provider account to satisfy this preflight.

Run these steps in the source checkout only after the remaining gates and a
candidate-install decision. They are not instructions to change the current
gateway, service or managed venv.

```bash
git rev-parse HEAD
git status --short
make build
```

`make build` creates the checkout's `.venv` and builds its own SPA. Verify that
the package metadata reports 0.14.0 and the built assets include MAX Settings.
Do not run `kirocrew update`, the public installer, or systemd service commands.

For a temporary candidate within the same operator session, use the session's
scratch directory. Set `MAX_CANDIDATE_PORT` to a free loopback port first.

```bash
KIROCREW_HOME="$KIROCREW_SCRATCH/max-candidate-home" .venv/bin/kirocrew setup
KIROCREW_HOME="$KIROCREW_SCRATCH/max-candidate-home" .venv/bin/kirocrew doctor
: "${MAX_CANDIDATE_PORT:?Select a free candidate port first}"
KIROCREW_HOME="$KIROCREW_SCRATCH/max-candidate-home" KIROCREW_BIND=127.0.0.1 KIROCREW_PORT="$MAX_CANDIDATE_PORT" .venv/bin/kirocrew gateway
```

Keep this gateway in the operator's foreground terminal. Scratch and agent-launched
processes are temporary; a persistent rollout needs an owner-chosen location and
service plan later. Never copy the live data home or its credentials for this test.
The loopback candidate must not share a bot token with another active receiver.

## Secrets and production transport

1. The owner revokes the bot token exposed in chat. Enter its replacement only
   through the candidate's authenticated **Settings → Secrets**. Do not send it
   through chat, shell arguments, command output or a document.
2. Save a Secret named `max-bot` and a separate random webhook Secret named
   `max-webhook`. The webhook value must contain 32–256 ASCII letters, digits,
   underscores or hyphens. The operator-managed environment maps
   `MAX_BOT_TOKEN=secret://max-bot` and
   `MAX_WEBHOOK_SECRET=secret://max-webhook`. These are vault references, not
   credential values. The owner must arrange this environment before starting
   or explicitly restarting **only the candidate**.
3. In the candidate configuration editor, use base configuration, not an overlay:
   `max.enabled=true`, `max.delivery_mode=webhook`, `max.allowed_user_ids=[]`.
   Empty access denies all senders until a valid pairing code is consumed.
4. Only for the live step, the owner chooses an existing external HTTPS origin
   with a trusted complete certificate chain on port 443. Set `dashboard.url`
   to that origin without an explicit port, path, query, userinfo or fragment.
   This procedure does not open a port, configure a proxy or select a domain.
   The owner must separately authorize any required ingress change. A loopback
   listener can remain loopback behind an owner-managed proxy.
5. The proxy must route `POST /api/messaging/max` to the candidate, preserve
   `X-Max-Bot-Api-Secret`, avoid logging that header or request bodies, and keep
   the remaining dashboard routes behind normal dashboard authentication. Do not
   disable TLS verification or trust an unverified certificate to make a check pass.
6. Sign in as the **host owner**. Open **Settings → Channels → MAX** and press
   **Register webhook**. The button makes the owner-only, same-origin
   `POST /api/max/subscription` through the normal API transport. It takes the
   configured URL and server-held Secret; there is no DevTools step or token input
   in that action. A success notice means registration was accepted, not that a
   message arrived. A timeout is uncertain: inspect the subscription before retrying.
7. Press **Pair owner** on the same panel. Send its displayed `/start <code>` to
   the chosen bot in a private chat before five minutes elapse. Do not disclose
   this code. Confirm that the numeric owner appears in Settings. No first sender
   is trusted, and groups remain denied. Re-register after rotating the webhook Secret.

MAX permits polling for development/testing; the production path above uses
[webhooks](https://dev.max.ru/docs-api/methods/POST/subscriptions). Polling and a
webhook subscription must never run concurrently for one bot. Registration requires
HTTPS port 443, and the receiver must answer within 30 seconds. The code's ingress
budget is 20 seconds; ordinary model work runs after durable admission.

## Live proof and stop conditions

Record the exact candidate commit, package version, configured origin without
credentials, test time and each verdict. Do not capture codes, login links,
webhook headers or token values in screenshots or logs.

- Owner: harmless text reply, `/help`, `/agent`, `/new`, `/sessions`, `/stop`.
- Access: second account, group, callback from another account, expired/wrong/
  replayed pairing code all deny. Revoking or disabling the owner stops the
  channel through its config restart path; verify active turns and pending
  approvals stop as well. Do not accept a merely hidden UI button as enforcement.
- Approval: approve and deny one harmless action each; stop during a pending tool.
  Retry delivery of the same control must never approve a later tool. Controls
  are consumed before their effect: after a crash an owner may need a new command.
- Recovery: retry an ordinary update without repeating the turn; restart with a
  pending entry and with a running entry. A running entry gives a notice, not tool
  replay. This is bounded deduplication, not exactly-once execution.
- `/web` and `/mobile`: owner subject, chosen HTTPS origin, expiry and one-use
  exchange. A missing origin refuses a link instead of producing localhost.
- Verify final candidate assets and both narrow and wide Settings layouts in a
  real browser. Unit component tests do not prove CSS, navigation or proxy delivery.

Stop on a failed gate, ambiguous owner identity, unexpected side effect,
authentication bypass or unverified certificate. Keep the installed gateway
untouched. Full rollout, data migration and any upstream push/PR remain separate.

## Local storage boundary

The entire data-home `max` directory is declared HIDDEN, precreated before agent
spawn, refused when aliased, and denied to agent file tools. This covers inbox,
cursor and future journal/temp names. The declaration is tested; actual OS
enforcement still needs proof on the candidate host. A local pytest userns probe
reported EPERM, so those unit tests do not prove a working namespace sandbox.

Inbox files require owner-only POSIX permissions, a regular file with one link,
and stable identity. The code refuses a symlink at the file/parent and a writable
shared parent; it does not silently chmod a suspicious existing file. The platform
no-reparse helper covers the leaf on Windows; Windows ACLs and macOS were not
verified here. An owner-only directory is not isolation from a hostile process
running under the same OS account: SQLite still opens by pathname, including its
journal. Do not claim complete protection against ancestor/journal swaps or
same-UID races. Review the candidate's OS isolation before treating it as a
production boundary. Only one gateway/worker may own this inbox and bot.

Rollback of this isolated test: stop the foreground candidate, remove its MAX
subscription through MAX's supported owner controls, and leave the live gateway
unchanged. Do not re-enable polling until that subscription is removed. Preserve
the source commits and redacted evidence for review.
