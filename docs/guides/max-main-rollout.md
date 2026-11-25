# MAX on the existing main gateway: rollout review

## Target and current evidence

The owner's2026-11-25 instruction selects the existing main gateway on5477.
Use its existing `secret://bot_max_kda`; do not request another token, relocate
the data home, copy a vault or copy authentication files. The standalone trial
is not the target. This document is a deployment plan, not a completed deployment.

Read-only checks during this review returned:

- `GET http://127.0.0.1:5477/api/health`:200, version0.13.1,
  gateway_id `f3704e5eca384d209b3066401fe0c31d`.
- Port55476: connection refused; no duplicate trial receiver was started.
- `/home/adminuser/.local/bin/kirocrew` points through
  `/home/adminuser/.kiro/crew-venv-current/bin/kirocrew`; the stable link resolves
  to `/home/adminuser/.kiro/crew-venv-0.13.1`.
- That installed package has no `kiro_crew/max` directory and no
  `MAX_BOT_TOKEN` credential entry. Enabling a setting cannot install the channel.
- `uv pip check --python /home/adminuser/.kiro/crew-venv-0.13.1/bin/python`
  checked87 packages and reported incompatible `cryptography==50.0.2` against
  `cryptography>=42,<48`. This was already present; this review changed no
  installed dependency. Candidate metadata has the same constraint. All its
  other active core dependency requirements match the installed package inventory.
- The scoped `debug_gateway` tool returned `member_scope_denied`: owner required.
  It was not retried through another identity or a process-inspection workaround.

## Concrete package available for review

The existing0.14.0 candidate includes MAX, bundled frontend assets and the
client-scoped official CA. It is not a drop-in adapter for0.13.1.

Wheel:
`/home/adminuser/.kiro/crew/workspace-member-codex-dev/_only_local/max-trial-11249e86/tls-candidate/kirocrew-0.14.0-py3-none-any.whl`

SHA256, rechecked during this review:
`dde97735a501acdf6963df3ded0a541fca5e8a01eca441526cd8e86d0eb487a7`.
Requires Python>=3.12. Client/CA contents and prior targeted gates are recorded
in [candidate preparation](max-candidate.md). No rebuild or CA download is needed.
An existing-data-home migration from0.13.1 has not been tested; dependency
metadata agreement does not prove that migration or a live MAX reply.

## Supported update boundary

The installed `cli_parser_gateway.py:149-164` accepts `update [approve]` and
`--force` for a git update. It has no local-wheel argument.
`platform/wheel_engine.py:1-35` requires a fresh sibling runtime, atomic promotion
and a wheel digest authenticated by the pinned release-manifest signing key.
`cli_server_update.py:_update_managed_venv` uses that release engine with memory
readiness and snapshot hooks. These checks must remain in place.

The local wheel's SHA256 identifies its bytes; it is not a signed release
manifest. No such manifest for this candidate has been supplied or verified.
Available tools expose no scoped custom-package deployment action. A settings
card cannot add missing Python code, and `update approve` cannot approve this
wheel without a matching supported update request. Do not manufacture a release
signature, redirect the feed or modify the updater's trust root.

## Rollout gates

1. Have the deployment owner/reviewer accept the pinned local candidate and
   establish its supported promotion route. If using the managed release route,
   obtain a genuine signed release containing these bytes. Do not run an
   unrelated feed update and assume it contains this unpushed MAX integration.
2. Keep the running0.13.1 tree unchanged. Prepare the new runtime beside it,
   preserving optional installed features and the existing launch/service
   contract. Correct the cryptography range in the new tree only. Require
   dependency checks, import/entrypoint gates and the migration review before
   promotion. Do not overwrite the running venv or repoint it to the testenv.
3. Use the updater's memory readiness/snapshot and admission protocol before
   promotion. Establish rollback for any data/schema writes before a first
   main-data-home boot. Do not copy secret/auth material as an agent.
4. The owner performs the supported restart into the approved promoted tree;
   the agent does not stop its own supervisor or bypass sandbox provenance.
   Confirm main health/version and one receiver before enabling MAX.
5. Through the new version's supported Settings/credential controls, bind
   `MAX_BOT_TOKEN` to `secret://bot_max_kda`, select polling and enable MAX.
   Keep the owner allowlist empty until pairing; do not grant the first sender.
   Polling does not need a webhook secret. Do not create a second receiver.
6. In the same main Dashboard, use Settings → Channels → MAX → Pair owner.
   The owner sends `/start <code>` to `@id2311384963_bot`, then `/help`.
   Record the actual bot response without recording the token or pairing code.
   A model/tool turn needs its own confinement evidence; polling is not proof
   of production webhook deployment.

## Rollback gate

Retain `/home/adminuser/.kiro/crew-venv-0.13.1` and the previous managed launcher
target. If a new MAX channel fails, disable it through the supported settings
first. If a package rollback is needed, the deployment owner must restore the
previous approved runtime through the deployment mechanism and restart it.
Do not point an older runtime at a migrated data home until backward schema
compatibility or an approved recovery has been established. No generic rollback
command is supplied because that promotion/recovery route is not established.

## Remaining block

The available scoped tools cannot promote this unpublished local wheel through
the main install's signed-release updater. Owner-only diagnostics were refused.
The next deployment decision is the reviewed promotion route for this exact
candidate, including data migration and rollback. No additional Secret entry
or trial is needed. Main files, services, launcher links and credentials have
not been changed. Pair owner and a real `/help` reply remain unproved.
