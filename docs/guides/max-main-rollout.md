# MAX integration for Kiro Crew

The [MAX integration module](../../integrations/max/README.md) adds MAX private messages to Kiro Crew.
Its release bundle contains the adapter and integration files rather than the
whole application; this public fork hosts development and contributions. The supported installed
backport is **0.13.1+max.4**, based on the official 0.13.1 wheel. The regular
source tree also contains the MAX adapter. Start here when installing or
continuing this work; `max-candidate.md` records earlier experiments.

## Everyday use

Pair your owner account once, then send `/help` to the MAX bot.

| Command | Result |
| --- | --- |
| `/sessions [search]` | List existing conversations; select one with a button. |
| `/bots [search]` | Select an existing active Crew Bot conversation. |
| `/status` | Show the current conversation and its agent. |
| `/agents` | List agent templates. |
| `/agent name` | Select a template for a separate MAX conversation. |
| `/new` | Leave the selected conversation and start a separate MAX conversation. |
| `/unlink` | Detach the selected conversation without deleting its history. |
| `/stop` | Stop the running MAX turn, even if its saved binding has changed. |
| `/web`, `/mobile` | Get the existing dashboard/mobile entry points. |

An **agent template** chooses how a new assistant runs. A **Crew Bot** is an
existing persistent assistant with its own conversation and project context.
A **session** is a conversation history. Choosing a session continues that
history; it does not create or reconfigure a Bot. Create Bot chats in the
normal dashboard first. While a turn is running, stop it before switching.

Tool approvals accept `1` (once), `2` (deny), `3` (trust this session),
`/approve` or `/deny`. The displayed English option text also works. Trust is
limited to the selected session and the existing Crew policy; it does not
remove sandbox restrictions. An unanswered prompt denies after five minutes.
Request ID zero is valid and is retained, fixing the original dropped reply.

The navigation follows the built-in Telegram channel: the shared
`SessionResumeController` and binder own selection, persistence, rollback and
binding validation. Picker buttons are scoped to the paired owner, message and
expiring nonce. MAX-specific code handles MAX API messages and callbacks.

## Install the focused backport

Python 3.12+, Git and uv are needed to build. Use the upstream
[installation guide](install.md) for Crew setup and model authentication. Build
in a new caller-owned temporary directory:

```sh
git clone https://github.com/kda7889/KiroCrew.git
cd KiroCrew
export KIROCREW_SCRATCH="$(mktemp -d)"
curl --fail --location --output "$KIROCREW_SCRATCH/base.whl" \
  https://github.com/kirodotdev/KiroCrew/releases/download/v0.13.1/kirocrew-0.13.1-py3-none-any.whl
python3 scripts/max_backport_build.py \
  "$KIROCREW_SCRATCH/base.whl" "$KIROCREW_SCRATCH/build"
uv venv --python 3.12 "$KIROCREW_SCRATCH/runtime"
uv pip install --python "$KIROCREW_SCRATCH/runtime/bin/python" \
  "$KIROCREW_SCRATCH/build/dist/kirocrew-0.13.1+max.4-py3-none-any.whl"
```

This builds and installs into a separate environment; it does not switch an
existing service. Retain your normal optional extras and host repairs when
planning an upgrade. Check dependencies before promotion and keep the previous
runtime available. Do not install over a running environment.

The recipe verifies the official wheel hash, RECORD, pinned build inputs and
32 patch files. It preserves all baseline package files, dependency metadata,
entrypoint, frontend and license notices. Its audit is `build-result.json`.
The accepted clean wheel SHA256 is
`b9f4e7d569a4cf01cd16a236ba9ceb9a4330f05fca7d7b066b1a19afac423ef4`.
Local builds are unsigned fork builds; the signed upstream updater is unchanged.

## Configure and pair

Create a MAX bot using MAX's bot management and save its token using Crew's
normal Secrets controls. Supply `MAX_BOT_TOKEN=secret://your_secret_name` to
the gateway environment. Use a secret reference, not a token in Git or shell
history. In the selected runtime, configure polling for development:

```sh
kirocrew config set max.delivery_mode polling
kirocrew config set max.enabled true
```

Start that runtime through your normal gateway/service procedure. Run only one
receiver for a bot token. Keep `max.allowed_user_ids` empty until pairing; the
first sender is never automatically trusted.

On the source frontend, use Settings → Channels → MAX → Pair owner. The 0.13.1
backport retains the original frontend and has no MAX Settings button. It
provides host-owner-authenticated `GET /api/max/config` and
`POST /api/max/pairing` instead. From an authenticated owner API client on the
gateway host, send the POST with the same-origin `Origin` header and dashboard
session cookie. Native `kirocrew token --port 5477 --ttl 10m` provides the
existing owner login flow; never publish its URL or token. The response has
`code`, `expires_in: 300` and `attempts: 5`. Send `/start <code>` to your bot,
then `/help`. The code is single-use; a configured owner cannot be silently
replaced. No direct vault access is needed.

Polling is the verified development route. Webhook source support requires an
external HTTPS endpoint on port 443, `MAX_WEBHOOK_SECRET` and the owner-only
`POST /api/max/subscription`; registration alone does not prove delivery.

## Verification and deployment record

The max.4 source suite passed **180 tests** (including the build recipe tests); the isolated installed-wheel suite
passed **148 tests** with the root host-isolation fixtures retained. Regression
coverage includes real configuration defaults, request ID zero, session trust,
owner/stale picker rejection, Bot binding, status agent identity, stop during
binding failure, exact-secret screening, API wire format and send pacing.
The owner confirmed MAX pairing, a normal model reply, then max.4 menus,
conversation selection and a real tool permission interaction on testserver.

The testserver system service pins its `ExecStart` directly to the versioned
max.4 environment. This protects it from changes to the mutable current-runtime
symlink. Existing AppArmor profiles and nine pre-existing host repairs remain
in force; all 87 runtime distributions satisfy dependency checks. A private
operator artifact directory retains the wheel, audit, host patch and exact
constraints; root-only rollback records retain the previous service setting.
Those host artifacts and credentials are not public release inputs.

Supported here: one paired owner, private text chats, model/tool turns,
approvals, existing sessions and active Crew Bot conversations. Groups, media,
new Bot creation from MAX, production webhook delivery and mobile login are
not claimed as live-tested parity with Telegram.

See the [publication security review](../../integrations/max/SECURITY-REVIEW.md)
for inherited dependency advisories and the limits of the old development backport.

## Develop and contribute

Open issues and pull requests at [kda7889/KiroCrew](https://github.com/kda7889/KiroCrew).
Follow [CONTRIBUTING.md](../../CONTRIBUTING.md). Keep MAX behavior in
`src/kiro_crew/max/` and reuse `messaging/session_resume.py`, `messaging/turn.py`
and `messaging/approval.py` rather than creating parallel conversation state.
Tests live in `test/test_max_*.py`; helper fixtures are in
`test/max_sessions_helpers.py`. The descriptive process is
[the owner BPMN](../architecture/max-owner.bpmn) and its adjacent SVG.

For source tests, use the repository development environment:

```sh
PYTHONPATH=src python -m pytest -n0 \
  test/test_max_sessions.py test/test_max_approvals.py \
  test/test_max_channel.py test/test_max_webhook.py test/test_max_tls.py \
  test/test_messaging_approval.py test/test_approval_timeout_cause.py \
  test/test_max_backport_build.py
```

For an installed backport, install the repository's test tooling into an
isolated environment and use its site-packages without installing this source:

```sh
PYTHONPATH=.:test /absolute/candidate/bin/python -m pytest --noconftest \
  -p conftest -p max_backport_compat -n0 \
  -o pythonpath=/absolute/candidate/lib/python3.12/site-packages \
  test/test_max_sessions.py test/test_max_approvals.py \
  test/test_max_channel.py test/test_max_webhook.py test/test_max_tls.py \
  test/test_messaging_approval.py -k 'not pairing_model_and_svg'
```

Update the static backport patch and manifests when changing adapter behavior.
Keep the official base hashes; do not substitute locally repaired installations.
Rebuild and retest the actual wheel before proposing another runtime. The
compatibility plugin replaces only a newer startup-download stub absent in
0.13.1; the remaining root isolation fixtures stay enabled.

An external channel package is not currently a drop-in replacement: channel
registration and credential injection are core seams in this version. This
focused public fork remains the continuation point until upstream supplies an
installable channel API or accepts the integration. Public code and the
reproducible recipe let others use and improve it without private host files.
