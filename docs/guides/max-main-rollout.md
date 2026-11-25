# MAX on the existing main gateway: rollout review

## Current owner-run step

The parent confirmed the manager on2026-11-25 at21:45UTC: system scope,
`/etc/systemd/system/kirocrew.service`, drop-in `primary.conf`,
reported MainPID1466, launcher `crew-venv-current/bin/kirocrew gateway --no-open`.
User scope is not installed. Do not repeat `service status`: its process-tree
output was large, not evidence of thousands of errors.
The helper additionally requires and checks `User=adminuser` before stopping.

The prepared operation is:

```bash
sudo /usr/bin/python3 -I /home/adminuser/.kiro/crew/workspace-member-codex-dev/kirocrew-max-source/scripts/max_main_owner_install.py
```

Run only from an ordinary interactive owner terminal on testserver. The agent
does not execute this helper, including any preflight or undo mode. Root is
required for the existing **system** service and its private recovery files.
The helper imports no product code, mints no credentials and changes no trust
root, public bind, firewall, DNS or provider login.

It performs one bounded deployment:

1. Verify the host/root/terminal/sandbox guard, exact service launcher and
   account, runtime link, package SHA256, baseline0.13.1 health/readiness and
   free space. A pre-existing MAX drop-in is refused, not overwritten.
2. Stop only the system `kirocrew.service`; require inactive/MainPID0, an empty
   or removed service cgroup and no listener on5477 before touching code.
3. As the owner, make opaque, uncompressed archives of **the entire existing
   `/home/adminuser/.kiro/crew` and `/home/adminuser/.kiro/crew-venv-0.13.1`**.
   This includes hidden files, conversation transcripts, stores, config, the
   existing vault and other in-home state. This is owner-only local recovery,
   not an agent vault read or transfer to another instance. Nothing is sent off
   the server. `/var/backups/kirocrew-max/main-*` and its logs/manifests are
   root-owned0700/0600; the agent must not read them.
4. Compare both archives against the stopped source trees, preserve UID/GID,
   modes, ACLs and xattrs, and record archive SHA256 values before installation.
   Runtime Unix sockets are omitted by tar; no ordinary data file is excluded.
   Nested mounts, unsupported special files and external symlinks in mutable
   config/history/store/workspace/app/agent paths refuse the operation rather
   than claim incomplete recovery coverage. Arbitrary external data is not a
   recovery target.
5. Install only the pinned kirocrew wheel as adminuser, offline with no
   dependency changes, then require `pip check`. Set only MAX polling, its empty
   owner allowlist and enabled flag through the normal CLI. Create only the new
   root-owned `90-max-channel.conf` with the **reference**
   `MAX_BOT_TOKEN=secret://bot_max_kda`; the Secret value is never printed.
6. Reload systemd, start the existing system unit, and require both
   `/api/health` version0.14.0 and `/api/ready` before reporting success.

On an install/config/start/readiness failure, the helper stops that same unit
again, verifies the archives and idle state, retains the failed data/runtime
trees, restores both pre-migration archives, removes only its unchanged new
drop-in, and starts the original0.13.1 service. A backup failure before any
mutation merely restarts the untouched original service. A failed recovery
keeps all archives and retained trees for the owner; it does not delete data.
Every installer/archive child has its own process group. Timeout or interruption
ends only that owned group before recovery. If the child cannot be reaped, the
helper leaves the service stopped and retains the recovery point; it does not
restore files while an installer could still be writing them.

For a later manual rollback, the helper prints the exact command containing
the private backup directory:

```text
sudo /usr/bin/python3 -I /home/adminuser/.kiro/crew/workspace-member-codex-dev/kirocrew-max-source/scripts/max_main_owner_install.py --undo /var/backups/kirocrew-max/main-<printed-name>
```

Undo refuses changed drop-ins, altered archives, insufficient recovery space or
an already attempted recovery before replacing data. Current post-install data
is retained in the private backup, rather than overwritten. A later rollback
returns the earlier state; new work must be merged from that retained copy.

The helper has synthetic tests for owner/sandbox guards, archive/restore of
hidden files and symlinks, archive tampering, foreign units, changed drop-ins,
non-clobbering undo, stop/backup/install failure ordering and successful ordering.
No real service action, main-data backup, root mode or MAX receiver was run by
the agent. Existing pairing behavior and its canonical BPMN are unchanged.

After the owner operation succeeds, open the existing main Dashboard, choose
Settings → Channels → MAX → Pair owner, send `/start <code>` privately to
`@id2311384963_bot`, then `/help`. Package health/readiness does not prove that
exchange or a confined model/tool turn, nor production webhook delivery.

## Reviewed compatible candidate

The dependency blocker described below was reproduced and then fixed in source:
`cryptography>=42,<51` preserves the main install's50.0.2 and pyOpenSSL26.4.0.
No main dependency was changed. An isolated testenv took cryptography50.0.2
from official PyPI with normal TLS, after one offline cache miss.
The web-push, WeCom media, Weixin media and MAX TLS suites passed151 tests
(2 warnings,25.18s). These cover AES-GCM, CBC, EC signing and the MAX TLS context;
they do not prove existing-data-home migration or live MAX delivery. The denied
synthetic credentials probe was not repeated.

New wheel, built offline from this source:
`/home/adminuser/.kiro/crew/workspace-member-codex-dev/_only_local/max-main-compatible/kirocrew-0.14.0-py3-none-any.whl`

SHA256: `1a55ffb83739890fbb514fc349b3049cef4044c9cd13ba7b0bc6cc4ed9054d62`.
This supersedes the earlier `dde97735` wheel for main deployment only. The CA,
endpoint and frontend inputs were not changed. An offline dry-run against the
main interpreter, explicitly retaining pyOpenSSL26.4.0, resolved69 core packages
and proposed changing **only kirocrew**, with no other dependency changes.
After installing the new wheel only in the isolated testenv, `uv pip check`
reported94 compatible packages. The testenv is not a replacement for the main
runtime or its optional packages.

The verified local package-install command, **only after the main gateway is
stopped through its actual manager and a recovery point is secured**, is:

```bash
/home/adminuser/.local/bin/uv pip install --offline --no-deps --reinstall-package kirocrew --python /home/adminuser/.kiro/crew-venv-0.13.1/bin/python /home/adminuser/.kiro/crew/workspace-member-codex-dev/_only_local/max-main-compatible/kirocrew-0.14.0-py3-none-any.whl
/home/adminuser/.local/bin/uv pip check --python /home/adminuser/.kiro/crew-venv-0.13.1/bin/python
```

These are not a complete live rollout command. Running them against a live
install would overwrite code its gateway and children can still import.
The current agent cannot stop/restart its supervisor. The installed lifecycle
code also refuses to restart an installed-but-stopped service outside its
manager, so inventing `stop && install && restart` is incorrect. An explicit
`stop --port5477` bypasses service handling and could let an auto-restarting unit
race the install; it is not the deployment command either.

The manager/scope question is closed by the parent's output above.
`debug_gateway` already returned owner-only `member_scope_denied`; it is not
retried. Use the root owner-run operation above, not a port-only stop or an
unmanaged replacement. Main health returned200/version0.13.1 after candidate
verification. No main install, service, config or vault was changed by the agent.

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
  installed dependency. The earlier candidate had the same constraint. All its
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

Local owner installation is supported independently of the signed updater:
`docs/guides/install.md:443-450` documents `pip install dist/*.whl` with a
suitable Python. The absence of a local-wheel argument in `kirocrew update`
does not forbid this manual installation path. The earlier review was too
restrictive in treating a signed release as the only possible deployment path.

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

1. Use the documented local-wheel installation path for this owner-requested
   custom build, independently of the signed release updater. The compatible
   `1a55ffb8` wheel supersedes the incompatible `dde97735` wheel. A further
   generic approval of the plan is not required.
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

The root owner helper archives both the original runtime and entire data home
before any package or config mutation. Its automatic recovery and printed
`--undo` command restore them together, while retaining the failed/current trees.
It never pairs old code with newer migrated data. The existing stable launcher
link is not changed. No agent lifecycle action or real recovery has been run.

## Earlier dependency blocker (resolved above)

The earlier `dde97735` wheel is dependency-incompatible with the installed feature set.
This is not resolved by running the command as the owner. The owner's Secrets
entry is already in the correct main vault. No additional Secret entry or trial
is needed. Main files, services, launcher links and credentials have not been
changed. Pair owner and a real `/help` reply remain unproved.

## Completed local-install and rollback review

Read-only package-metadata comparison found that the main install includes
`pyOpenSSL==26.4.0`, requiring `cryptography>=49,<51`. The0.14.0 wheel requires
`cryptography>=42,<48`. The ranges have no overlap. Downgrading cryptography to47
would break the installed pyOpenSSL/WebRTC feature set; leaving50 installed
would violate the candidate's declared dependency. The testenv cannot be used
as a replacement: it lacks19 main packages, including aiortc, pyOpenSSL,
pywhispercpp, boto3 and amazon-transcribe.

This exact non-mutating command was run and exited1, with `No solution found`
and the two incompatible cryptography ranges:

```bash
/home/adminuser/.local/bin/uv pip install --offline --dry-run --python /home/adminuser/.kiro/crew-venv-0.13.1/bin/python /home/adminuser/.kiro/crew/workspace-member-codex-dev/_only_local/max-trial-11249e86/tls-candidate/kirocrew-0.14.0-py3-none-any.whl pyOpenSSL==26.4.0
```

An earlier `--no-deps` dry run proposed replacing only kirocrew and cryptography.
That is not a valid installation solution: `--no-deps` hides the pyOpenSSL
conflict. Do not turn that dry run into a real install command.

Static migration comparison against the actual installed package found1841
added or changed Python files in this wheel, not just MAX:

- `config/migration.py`, `taskq/migrate.py`, `memory_schema.py`,
  `knowledge/store_parts/schema_migrations.py` and `secrets/migrate.py` are
  byte-identical. This is evidence about those modules only.
- `config/loader_writeback.py` adds a refusal before backing up an outside
  pending settings edit; existing config migration backup/locking stays.
- `config/loader_document.py` changes undeclared KAS preference handling and
  drops retired config keys on locked base-document writes. Reverting Python
  packages does not restore dropped settings.
- `history_schema.py` adds the `project_picked` metadata field.
- `channel_transcript_migration.py` adds merging/removal of drifted cron-chat
  copies. Reverting Python packages cannot recreate removed transcript files.
- `mate_config_migration.py` skips unsafe path-like identity rows.

Therefore a code-only rollback is insufficient. The installed snapshot parser
supports `snapshot --strict` and `restore <archive> --mode replace`, and refuses
an incomplete strict backup with exit3. Its component list does not explicitly
cover every transcript/identity migration path; a default snapshot must not be
claimed as a complete recovery point without checking that coverage. Neither
snapshot nor restore was run by the agent, and no vault/auth material was copied.

The installed self-protection contract (`security/denied_rules_catalog.py`,
comment before `self-protection-cron-adopt`, and `argv_floor_self.py` predicates
`_is_self_restart`, `_is_self_update`) reserves supervisor update/restart actions
from an agent shell. No alternate service, signal or interpreter route was used.
After a dependency-compatible wheel and state recovery point exist, the owner
must perform the normal lifecycle transition from a host terminal. Giving a
stop/install/restart command for this wheel now would cause either dependency
breakage or an unprotected data migration; there is no safe owner installation
command for these exact current bytes.

The dependency correction, full-data recovery helper and package gates are now
recorded at the top of this document. Execution remains an owner operation;
neither its backups nor a successful real recovery is claimed from synthetic tests.
