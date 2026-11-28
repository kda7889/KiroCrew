# MAX channel integration module

This directory is the entry point for the MAX integration, developed in the
public [kda7889/KiroCrew](https://github.com/kda7889/KiroCrew) source fork.
The integration release asset contains just the adapter, compatibility patch,
build recipe, tests and documentation. It does not contain a copy of the whole
Crew application or private host configuration.

**Integration module, not an auto-discovered plugin:** Crew 0.13.1 has a fixed
built-in channel registry. Installation requires the small core registration,
configuration and owner-route changes included in the patch. It cannot yet be
installed with `pip install` as an independent channel extension. The build
recipe applies that integration to the official wheel and audits the result.
The resulting runtime wheel necessarily contains Crew as well as MAX.

- Adapter: `src/kiro_crew/max/`.
- Core integration and version adaptation: `compat/max-0.13.1.patch` and manifests.
- Reproducible build: `scripts/max_backport_build.py`.
- Setup, chat commands, testing and contribution: [MAX guide](../../docs/guides/max-main-rollout.md).
- Session navigation reuses the same common controller as Telegram.

To integrate into another Crew version, adapt the core hooks against that
version and rerun the source and installed-package tests. Do not apply the
0.13.1 patch to arbitrary releases or bypass its base hashes. Once upstream
provides installable channel discovery, this adapter can move behind that
supported extension interface. Contributions towards that interface belong
with upstream; changes to MAX can be proposed in this fork today.

Apache-2.0; retain the repository LICENSE and NOTICE. The bundled public trust
certificate is used only by the MAX HTTP connector; global TLS is unchanged.

## Integration points for maintainers

| Seam | Files / purpose |
| --- | --- |
| Channel discovery | `channels.py`: register the MAX descriptor. |
| Configuration | `config/sections_max.py`, loader/pipeline/resolution: disabled by default, owner allowlist, polling/webhook mode. |
| Credentials | `config/loader_credentials.py`: resolve existing vault references; no direct vault reads. |
| Gateway lifecycle | `slack/gateway_runtime/channel_boot.py`, `orchestrator_init.py`, `slack/gateway.py`: start/close one receiver and register transport/dispatcher. |
| Owner management | `dashboard/handlers/max_pairing.py`, `dashboard/routes/connections.py`, token auth paths: authenticated owner-only pairing/config/subscription. |
| Native turns | `max/dispatch.py`: common `ChannelTurn`, agent resolver and session-specific trust. |
| Conversation selection | `max/sessions.py`: common `SessionResumeController`; active Crew Bot predicates follow existing Discord behavior. |
| Tool UI | `max/renderer.py`, `messaging/approval.py`, `messaging/renderer.py`: preserve numeric request IDs and display verified tool identity. |
| MAX wire protocol | `max/client.py`, `transport.py`, `webhook.py`: scoped TLS trust, redaction, callbacks, pacing and webhook retry handling. |
| Host isolation | `sandbox_leaves.py`, `sandbox_precreate.py`, `sandbox_seals.py`, `sandbox_tiers.py`, `security/paths_lists.py`: MAX state uses the existing protected channel-state boundary. |

`compat/max-0.13.1-base.json` lists every touched old-base file and its SHA256;
null entries are new files. The patch is authoritative for that version.
For a new upstream version, review these seams individually instead of replacing
an entire directory. The adapter files in the bundle reflect this fork's source
API; the static patch includes the corresponding 0.13.1 API adaptations.

Use the full development checkout for repository tests and their root safety
fixtures. The standalone bundle supports the audited build recipe; it does not
replace the repository's development environment. Preserve standard package
structure when extracting the archive, then run the recipe from its root.
