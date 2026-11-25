# MAX candidate: source review, isolated install and live proof

As of2026-11-25, the owner selects the existing main gateway on5477 as the
deployment target. A separate trial and another Secret entry are no longer
required. See [the main rollout review](max-main-rollout.md) for the current
installed-state evidence, compatibility gap and promotion/rollback gates.
The trial instructions below remain historical candidate preparation evidence.

This is an isolated candidate procedure, not a production deployment. The source
has a webhook receiver and owner Settings controls. The credential-free boot is
verified below; no MAX live delivery has been proved. Do not publish upstream
before the live checks pass.

The TLS correction below was installed offline into the idle isolated taskenv
on2026-11-25. The owner trial is stopped; no active runtime was overwritten.

## Prepared trial on testserver

The owner waived browser/screenshots as a trial prerequisite and will define the
MAX screen. Do not repair a browser profile or wait for the singleton helper.
The prepared backend wheel is0.14.0, built from source11249e86 and its own staged
frontend (production inputs unchanged from9c73721). Wheel SHA256:
`e643610831f959d62d1a82840985e44f4a97e79e1d41c5bee5968dbbed5e7ad8`.
It contains the MAX backend, owner endpoints, console entrypoint and2599 bundled
asset entries. It is installed into the existing isolated source taskenv, not the
managed gateway. The already verified93 dependencies were reused without another
download or55-test rerun.

Concrete private trial root:
`/home/adminuser/.kiro/crew/workspace-member-codex-dev/_only_local/max-trial-11249e86`.
The wheel is retained there; `os-home` was the first private HOME. No auth, live
configuration, vault, profile or provider session was copied. A bounded,
credential-free headless boot on127.0.0.1:55476 returned health200 and unauthenticated
pairing403; that owned process was stopped. Version/gateway-help/secrets-help
entrypoints passed from the installed wheel outside the source checkout.

In an **ordinary owner terminal** on testserver, run:

```bash
cd /home/adminuser/.kiro/crew/workspace-member-codex-dev/kirocrew-max-source
sh scripts/max_trial.sh
```

The launcher refuses the agent sandbox marker; never clear it. It uses the fresh
short HOME `/home/adminuser/.max-trial-11249e86`, default data home
`/home/adminuser/.max-trial-11249e86/.kiro/crew`, loopback55476, no tunnel,
no automatic browser or cron scheduler,
and interactive approvals. It clears inherited environment credentials before
running the candidate. It supplies only vault references for MAX, never a token
value. Keep this foreground process in the owner terminal; it is not a service.
If55476 is occupied, stop for review rather than stopping the other listener.

### Restart after the owner's first boot

The owner's first boot reached health200 but exposed two launcher faults: its
deep HOME overflowed Linux's107-byte UNIX-socket path limit; clearing the whole
environment also removed `XDG_RUNTIME_DIR`. The corrected launcher starts in the
new short private HOME above. The former `os-home` is left untouched; no vault,
login, profile or KAS cache is moved or copied. Its former login link belongs to
the old instance and must not be reused. A normal first-start KAS download may
therefore occur again; it is not evidence of a running model turn.

Stop **only the owner's foreground trial** with Ctrl-C, then restart from the
owner's terminal (the command also works when that terminal is root):

```bash
sudo -u adminuser -H sh /home/adminuser/.kiro/crew/workspace-member-codex-dev/kirocrew-max-source/scripts/max_trial.sh
```

The preflight pins testserver/UID1002, rejects symlink/private-directory drift,
and checks the real `/run/user/1002` mode0700/owner and its same-owner bus socket.
It passes only that verified runtime and `unix:path=/run/user/1002/bus` into the
clean environment, requires delegated memory/pids controllers, and checks that
the user manager's default target is active. It neither creates a user session
nor changes a service, controller or policy. Failure stops before the product
CLI/engine. A real login session is needed if those checks fail; no substitute
runtime directory or disabled cgroup check is allowed.

On the inspected host the runtime owner/mode matched UID1002/0700, bus was a
same-owner socket, default.target was active and controllers included cpu,
memory and pids. Those are read-only prerequisites, **not measured cgroup scope
enforcement**. Before a model/tool turn, require the restarted candidate's
resource guard to report available; if unavailable, stop and report the reason.
OS-fence proof remains open. MAX remains disabled by default in the new HOME.

`KIROCREW_HOME` is no longer injected: the short HOME's standard `.kiro/crew`
already gives isolation. The source's reserved spec-env sanitizer remains
unchanged; no reserved namespace or caller identity is admitted to silence its
warning. The short default dashboard and MCP socket paths fit the UNIX limit.

In a second terminal, the supported owner sign-in command is:

```bash
cd /home/adminuser/.kiro/crew/workspace-member-codex-dev/kirocrew-max-source
sh scripts/max_trial.sh token
```

Open that private link only in a separate private window in the owner's browser.
Do not paste it into chat.
When the browser is on another machine, use the owner's existing trusted SSH
access with a local55476 forward to testserver's127.0.0.1:55476. No public listener
or new HTTPS ingress is needed for the polling trial. The agent did not mint or
exchange a dashboard token through an API or copy an existing login.

For the shortest **development/test live trial**, use a dedicated bot with no
active webhook or other receiver. The owner confirmed the existing Custom Secret
`bot_max_kda` in **Settings → Secrets**. Use that exact name, without renaming it.
The launcher maps `MAX_BOT_TOKEN=secret://bot_max_kda`; underscores are accepted
by the standard secret-name validator. The CLI currently supports
secret import/authorization, not secret set; do not use a made-up CLI or DevTools.
Confirm that the Secret was saved in this candidate on55476, not the working
gateway. No available change-card tool can select a different instance, and the
agent must not inspect or copy either vault to establish this.

MAX is initially disabled with an empty owner allowlist. The already running
process still has the former shell reference; updating the launcher cannot
replace a running process's environment. One candidate restart is needed for
this reference change. Stop only the foreground candidate with Ctrl-C, then use
its normal configuration command and restart (adminuser's ordinary terminal):

```bash
sh scripts/max_trial.sh config set max.delivery_mode polling
sh scripts/max_trial.sh config set max.enabled true
sh scripts/max_trial.sh
```

In **Settings → Channels → MAX**, press **Pair owner**. Send the displayed
`/start <code>` to that bot in a private chat within five minutes; no first sender
or group is trusted. Send `/help` and require a real MAX response. This proves
the transport/owner-command path without an LLM provider login. For an ordinary
text/model response, complete the candidate's normal ACP backend login against
this fresh HOME using the onboarding/provider flow; do not copy the working
provider's auth. KAS has the supported owner command below. Its pinned engine is
installed by the normal first-spawn path; `kas install` is also the supported
explicit preparation if the owner wants it before the first model turn.

```bash
sh scripts/max_trial.sh kas login
```

Then send a short text and test `/stop` during a running turn. A `/help` reply
alone does not prove an authenticated model turn or tool execution.

Stop/undo: Ctrl-C in the candidate foreground terminal. Leave the private trial
directory for owner review; no installed service or existing home needs restoring.
Do not publish the wheel or trial home: the latter will contain the owner's new
vault after setup. The source launcher and this instruction contain no secrets.

The real OS-fence proof remains open; no namespace/policy/Secrets boundary was
weakened. Polling is only this explicit development/test trial, **not production
readiness**. Production still needs the webhook setup/HTTPS443 path below and its
own live proof. Source/browser gates listed later retain their historical scope;
they do not reintroduce the owner's waived screenshot prerequisite for this trial.

## Versions and gates

### MAX TLS preflight on testserver,2026-11-24

Both source and the former prepared wheel already use `platform-api2.max.ru`.
The official [API overview](https://dev.max.ru/docs-api/) and
[changelog](https://dev.max.ru/docs-api/changelog-api) require that domain and
the Ministry CA after July19,2026. Do not fall back to the old domain just because
its certificate verifies against the OS store.

Bounded unauthenticated `GET /me`, hostname/chain verification enabled:

| Endpoint | Peer IP | HTTP | TLS verification | Total seconds |
|---|---|---|---|---|
| platform-api.max.ru |155.212.204.149|401|0, verified|3.993|
| platform-api2.max.ru, OS trust |155.212.204.149|000|20, unknown issuer; curl60|4.160|
| platform-api2.max.ru, official root scoped to curl |155.212.204.149|401|0, verified|3.491|

The new endpoint's issuer is Russian Trusted Sub CA. These results establish a
missing CA trust path on testserver, **not a Russian-IP restriction**. A401
without a credential proves transport only, not the owner's bot identity or a
real reply. The owner names the bot `@id2311384963_bot`; its authenticated
identity and `/help` remain unproved until the candidate uses the saved Secret.

The root was downloaded with ordinary verified HTTPS from
`https://gu-st.ru/content/Other/doc/russian_trusted_root_ca.cer`, not obtained
from the API handshake. The distribution URL is also documented by the
[Saratov government workstation guide](https://minforest.saratov.gov.ru/lesnoe-hozyaistvo/Инструкция%20по%20настройке%20АРМ%20пользователей%20для%20доступа%20в%20ЛКЛ%20ФГИС%20ЛК.pdf)
and the [Sber developer certificate guide](https://developers.sber.ru/docs/ru/salutespeech/quick-start/certificates).
Only the distribution URL is used from those guides; no insecure-download or
global trust commands from an example are executed.

Pinned root DER SHA256:
`d26d2d0231b7c39f92cc738512ba54103519e4405d68b5bd703e9788ca8ecf31`.
Subject and issuer: Russian Trusted Root CA, Ministry of Digital Development
and Communications; validity March1,2022–February27,2032. The separately downloaded
official Sub CA verified against this root; its DER SHA256 is
`bbbde2103e790b999ec62bd03cf625a5a2e7c316e10afe6a490eedead8b3fd9b`.
The API handshake plus `/me` succeeded with the **root alone**. Only that root
is packaged at `src/kiro_crew/max/russian_trusted_root_ca.pem` (PEM line endings
are normalized; pin DER, not the downloaded file's formatting).

`_max_ssl_context()` extends default trust only in MAX's `aiohttp.TCPConnector`.
It retains `CERT_REQUIRED`, hostname verification and the client's no-redirect
contract. No system/certifi store, global SSL environment, engine or other client
is changed. No CA download occurs at runtime. Re-verify the official distribution,
fingerprint and validity before replacing this packaged root.

The documented infra SSH path to the host behind `hub.kda7889.ru`
(`gw`,82.202.158.39:22) returned Connection refused before any remote curl.
No new SSH trust or route, proxy, receiver, firewall or DNS change was made.
There is no current evidence requiring a move to hub.

Prepared TLS wheel (source client and CA bytes checked against ZIP contents):
`/home/adminuser/.kiro/crew/workspace-member-codex-dev/_only_local/max-trial-11249e86/tls-candidate/kirocrew-0.14.0-py3-none-any.whl`.
SHA256 `dde97735a501acdf6963df3ded0a541fca5e8a01eca441526cd8e86d0eb487a7`.
The wheel includes2599 existing frontend asset entries and the CA package data.
Offline build exited0 (25.24s, peak RSS54568KiB). Targeted MAX/TLS tests:
57passed,7warnings,13.75s,exit0. Default SSL contexts remain unchanged in the test.

An earlier attempt to prepare a second runtime with the pinned93 dependencies offline
stopped on missing cached `pillow==13.0.0`; no network reinstall or dependency
fallback followed. `max-tls-test-env` is incomplete and is **not** the launcher's
runtime. The established source taskenv's dependencies and running wheel
were left untouched at that stage.

On November25 the listener on55476 and candidate CLI process were absent.
The prepared TLS wheel was then reinstalled **only** into `max-source-test-env`
offline with `--no-deps --reinstall-package kirocrew` (exit0,1.97s). No process
was killed. Installed `max/client.py` and the CA matched both wheel and source
byte-for-byte; the installed CA DER fingerprint matched the pin and loaded into
a standard SSL context retaining hostname/chain checks. Package metadata remained
0.14.0; `uv pip check` checked94 packages and exited0 with all compatible.
These checks import no product/CLI code and access no vault. No receiver,
engine, auth-mint or owner-only launcher was executed. The isolated runtime is
updated, but a restarted owner instance and live `/help` are still unproved.

For a future repeat, to apply without touching the working gateway, the owner
first stops **only the foreground trial** with Ctrl-C. The now-idle runtime can take the
prepared wheel offline, reusing its established dependencies:

```bash
sudo -u adminuser -H /home/adminuser/.local/bin/uv pip install --offline --no-deps --reinstall-package kirocrew --python /home/adminuser/.kiro/crew/workspace-member-codex-dev/max-source-test-env/bin/python /home/adminuser/.kiro/crew/workspace-member-codex-dev/_only_local/max-trial-11249e86/tls-candidate/kirocrew-0.14.0-py3-none-any.whl
sudo -u adminuser -H sh /home/adminuser/.kiro/crew/workspace-member-codex-dev/kirocrew-max-source/scripts/max_trial.sh
```

The agent can do the offline package update after the owner has stopped the
trial; the owner-only launcher remains guarded. No HOME/vault/provider login is
relocated by this update. Confirm the correct candidate Secret instance before
enabling MAX, then pair and require an actual `/help` reply from
`@id2311384963_bot`. An authenticated identity request is still pending; no token
was extracted for this preflight and no second receiver was started.

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

1. Use the owner's existing Secret `bot_max_kda` in the candidate's authenticated
   **Settings → Secrets**; never read or copy its value into the launcher.
2. Keep the Secret named `bot_max_kda` and a separate random webhook Secret named
   `max-webhook`. The webhook value must contain 32–256 ASCII letters, digits,
   underscores or hyphens. The operator-managed environment maps
   `MAX_BOT_TOKEN=secret://bot_max_kda` and
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
