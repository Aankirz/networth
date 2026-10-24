# Agent-spec + skill-driven harness: patterns from SimbianOS, zoya-harness, investment-os

Read-only study. Paths cited as `path:line`. Code excerpts are short summaries, not copies.
SimbianOS harness root: `/Users/ankitkiran/Desktop/SimbianOS/python/security_assistant/apps/agentic_harness/`.

## 1. What an "agent spec" is in SimbianOS

Not a YAML file on disk — a **versioned DB row** (`JobSpec`, table via `JobSpecVersion` rows
`harness_spec_versions`). The spec *definition* is a Pydantic model, created/validated by
`CreateJobSpecRequest` (`dataclasses.py:1461`). Fields (`dataclasses.py:1466-1477`):
- `name`, `description`, `prompt` (free text with `{{name}}` placeholders)
- `controls: AgentControls` (`dataclasses.py:987`) — the single object that shapes the agent:
  permissions (tool allow/deny, skill/memory/path/sql grants — `Permissions`, `dataclasses.py:656`),
  `budget: Budget` (`dataclasses.py:769` — per-session caps: max_iterations, cost, duration; `None`=unlimited),
  sandbox/python-execution limits.
- `input_schema: list[InputSchemaField]` — **author guidance / UI form only, never a payload validator** (`dataclasses.py:1421-1446`).
- `execution: ExecutionContract` — driver = AGENT (LLM loop) vs PROGRAM (a pinned executable); `on_unhandled_exception` policy.
- `result_schema_ref: {name, version}` — the JSON result contract the session must finalize into.
- `goal_condition: GoalContract` — verifier = NONE | AGENT | PROGRAM, a natural-language `condition`, and `on_unsatisfied` policy.
- `config: SpecConfig` — values bound to the prompt's `{{placeholders}}` + per-skill overrides.
- `spec_metrics` — eval metric prompts.

**Versioning** (`docs/agents-2-0/AGENT_SPEC_VERSIONING.md`, impl `jobs/versioning.py`): a version =
definition + exact pinned versions of every artifact it uses (skills, memories, result schema,
executables). Lifecycle `experimental → latest(stable) → archived/rejected`; promote/rollback/reject;
sessions attributed to the version they ran on. This is the backbone of "build agents iteratively against evals."

**Spec → running agent**: `runner.run_session()` (`runner.py:44`) is the thin one-shot orchestrator:
`seed_controls_for_new_session` → create session row → allocate workspace → `_sync_session_artifacts`
(SyncEngine hot-loads skills/memories per pinned versions) → `build_harness_for_session` →
`harness.build_and_run(initial_message)`. The real builder is `AgentFactory.build_agent()`
(`agent_factory.py:1-33, :453`): it is "the single seam for building any Simbian agent" (top-level
and every sub-agent), turning one `AgentControls` into a configured `strands.Agent` with hooks,
skills plugin, and permission-filtered tool pool.

## 2. Skills & tools: definition, discovery, binding

**Skills** are `SKILL.md` files (progressive disclosure, Anthropic "Agent Skills" style).
Format = YAML frontmatter + markdown body. SimbianOS example `skills/.../sql_injection/SKILL.md`:
`name`, `description` (with "Triggered by:" cues), `metadata{...}`; body is the instructions.
Loading: `SandboxAgentSkills` plugin (`sandbox_agent_skills.py:1-60`) reads `.simbian/skills/<name>/SKILL.md`
and hands them to Strands' vended `AgentSkills` plugin. Three tiers:
- Tier 1: system-prompt `<available_skills>` XML block (name+description of every loaded skill).
- Tier 2: a `skills(skill_name)` tool loads one skill's full body + a listing of its `scripts/ references/ assets/`.
- Tier 3: ordinary `file_read` of those resource files.
Runtime dir is flat; SyncEngine copies `TenantArtifact(kind=skill, status=latest)` → `.simbian/skills/<name>/`
at session start, filtered by the spec's permission grants (which skills the controls let the session read).

**Tools** come from two sources, unified as MCP-named tools (`mcp__{server}__{tool}`):
- In-process Django modules each expose `get_tools()`, registered in `_MODULE_TOOL_PROVIDERS`
  (`tools/registry.py:59`) — case_management, context_manager, entities, integration, pentest, reporting,
  response_actions, user_communication. `ToolRegistry` (`tools/registry.py:78`) discovers, connects, catalogs.
- External MCP servers discovered dynamically (`tools/mcp_discovery.py`).
Tools are **bound to an agent by filtering the pool through `AgentControls` permissions** in
`AgentFactory`. **Deferred tools + `tool_search`** (`agent_factory.py:219-268`): only a core set is
declared directly; the rest are listed by name in `<available-deferred-tools>` and the agent calls
`tool_search(name=...)` to load a schema on demand — this is exactly the mechanism this very
environment uses. Keeps the tool array small for large catalogs.

There is no single global skill "registry" object; the registry is the artifact store
(`TenantArtifact`) + per-spec permission grants + the flat `.simbian/skills/` hot-load dir.

## 3. The harness loop

- **Planning/prompt composition** (`agent_factory.py`): static system prompt (`STATIC_SYSTEM_PROMPT`,
  overridable) + dynamic-context boundary appended (live `session_space.md` / memory via
  `ContextRefreshHook`) + `<available_skills>` + model catalog block + deferred-tools list.
- **Tool calls**: Strands event loop; each completed call is traced to `trace/tool_calls.jsonl`,
  raw outputs under `trace/tool_outputs/` (README "Key files").
- **Sub-agents** (`tools/sub_agent_definitions.py:1-55`): exactly two worker types — `worker`
  (general, inherits session prompt+skills+tools minus session-mgmt/spawn) and `explore`
  (read-only: editor/file_write/python_repl/shell denied). Spawned via `spawn_worker`/`fork_agent`;
  controls narrowed by `filter_controls()`. Sub-agents can't hold session-lifecycle or workflow-write tools.
- **Stopping conditions**: (a) budget hooks raise `BudgetExceeded` / `IterationBudgetExceeded` /
  `DurationBudgetExceeded` (`agent_factory.py:55-57`); (b) goal verifier — `goal_evaluator.py:255`
  evaluates the `goal_condition`; if unsatisfied it reprompts the main agent up to
  `max_goal_reprompts` (`dataclasses.py:866-873`), then terminates with
  `TerminalReason.GOAL_CONTINUATIONS_EXCEEDED` (`goal_evaluator.py:164`); satisfied → `USER_COMPLETE`.
- **State**: everything is a session filesystem (`workspace/session_fs.py`) with four semantic groups
  (workspace / memory / traces / events). Conversation is replayable from `transcript.jsonl`
  (`sessions/transcript_loader.py`). Completion requires evidence (`evidence_tool_use_ids` referencing
  successful MCP calls, or a reason) — README "Workflow completion evidence". Retries: MSSP pushes retry
  twice (30s, 2m); evidence refs that aren't yet persisted are retryable.

## 4. Evals & quality gates

`apps/agent_evals/` owns the eval domain; `docs/agents-2-0/EVAL_ARCHITECTURE.md`,
`EVAL_SCRIPT_CONTRACT.md`. An eval is a declarative package: `eval.json` (applicability
`always|deterministic|semantic`, category `regression|capability`, custom policy) +
`deterministic.json`/`rubric.json` graders + `policy.json`. Targets exactly one Agent Spec
(`<agent-spec>/<eval-id>`, e.g. `soc/groundedness`). Graders: deterministic (async Python checks) and
semantic (rubric dimensions each scored, N/A removed from denominator, uncertainty → review). Runs
as a normal Program-backed "eval-runner" Agent Spec; results are `EvalRun` rows attributed to the
`subject_spec_version`. Evals are the referee for promote/rollback decisions (not automated yet).

## 5. Patterns worth porting to a 1-day harness (and what to skip)

PORT (high value, low cost):
1. **SKILL.md as the unit of capability** — frontmatter `{name, description, metadata{tools, triggers}}`
   + markdown body; progressive disclosure (list in system prompt → load body on demand). Both repos use it.
2. **Agent spec as one declarative file** that names prompt + allowed skills/tools + budget + result schema +
   goal condition. (SimbianOS makes it a DB row; for 1 day use a YAML/JSON file.)
3. **One AgentControls/permissions object** = the single knob for tool/skill scoping + budget caps.
4. **Budget + goal as explicit stopping conditions** via hooks: max tool-calls / cost cap /
   iteration cap, plus an optional goal-check reprompt loop with a hard `max_reprompts`.
5. **Deferred tools + a `tool_search`** when the tool catalog is large (keeps context small).
6. **Guardrails as deterministic post-checks** (investment-os `harness/narrate.py`): every number in
   output must appear in a tool result → else regenerate then fail closed; banned-phrase filter;
   disclaimer appended by code; full audit log of prompt/tools/output/versions.
7. **Frozen eval + autoresearch loop** (investment-os, Karpathy pattern): agent may edit only
   `odds.py`/`prompts/*.md`; a frozen judge keeps a change only if the metric beats a bootstrap noise
   floor; sealed test never mounted. Great fit for an investment agent.
8. **Sub-agent = same factory, narrowed controls** — one `build_agent` seam, a read-only `explore` variant.

SKIP (too heavy for 24h): multi-tenant Postgres-schema isolation; full artifact versioning +
promotion propagation + MSSP push-down (`AGENT_SPEC_VERSIONING.md` is ~200 lines of edge cases);
gRPC sandbox worker / nsjail; the eval `TenantArtifact` lifecycle machinery; DRF/async REST session API.
Use files + git instead of the versioning DB; a subprocess or Docker instead of the sandbox.

### Minimal file layout that mirrors the good patterns
```
investment-agent/
├── agents/
│   └── analyst.yaml         # spec: name, prompt, skills:[], tools:[], budget{max_tool_calls,cost_usd},
│                            #        result_schema, goal_condition
├── skills/
│   └── odds-lookup/
│       ├── SKILL.md         # frontmatter {name, description, metadata{tools, triggers}} + body
│       └── scripts/…        # tier-3 resources
├── tools/                   # @tool functions; each registered with a risk class
│   └── registry.py          # discover() -> {name: tool}; bind by spec.tools
├── harness/
│   ├── run.py               # load spec -> build agent (prompt+skills+scoped tools+hooks) -> loop
│   ├── hooks.py             # BudgetHook (tool-call/cost cap), GoalHook (reprompt<=N), SafetyGate
│   ├── skills.py            # parse SKILL.md, inject <available_skills>, load body on skills(name)
│   ├── guardrails.py        # number-traceability check, banned phrases, disclaimer, audit log
│   └── models.py            # one get_model(role, provider) adapter  (copy zoya/models.py)
├── evals/
│   ├── prepare_eval.py      # FROZEN judge (Brier/calibration) — nothing else may edit
│   └── golden/…             # golden questions
└── program.md               # human research instructions for the autoresearch loop
```

## 6. What zoya-harness already has (user's own code — reuse directly)

zoya already implements most of the above on Strands; it is the fastest starting point.
- **SKILL.md harness** `zoya/harness.py:1-17` — skills directory, trigger regex index (0 model calls),
  per-skill tool scoping, stable prompt prefixes, reuses Strands `Skill`/`AgentSkills`. SKILL.md format
  identical to SimbianOS: `zoya/skills/shopping/SKILL.md` frontmatter = `name`, `description`,
  `metadata: {tools:[...], triggers:[{action, pattern}]}` + markdown body. `GENERIC_TOOLS` always-available
  set `zoya/harness.py:38`. `SKILLS_DIR` `zoya/config.py:172`.
- **Router / dispatch** `zoya/router.py:1` — rules → trigger index → learned picks → router model
  (`RouteChoice` structured output `router.py:351`). Learned picks cached with TTL (`config.py:177`).
- **Agent build + loop** `zoya/orchestrator.py:273` — `Agent(system_prompt, tools, hooks=[...])`.
- **Bounded autonomy / stopping** `TaskLimits(HookProvider)` `orchestrator.py:100` — before every model
  call, stop if over cost cap or 40 tool calls (`TaskLimitExceeded`). `ReasoningSchedule`, `StepTracker`.
  Native cancel via Strands `cancel_signal` (`orchestrator.py:381`).
- **Safety gate** `zoya/safety.py` — `TOOL_RISK` risk registry (`safety.py:78`, unknown=confirm,
  `risk_of()` :162), single-use voice confirmation token bound to sha256 of the action summary,
  `ConfirmationGate` hook wired in `orchestrator.py:281`. Maps cleanly to "always confirm before
  anything irreversible" — for investing: confirm before any order/transfer.
- **Model provider adapter** `zoya/models.py:152` `get_model(role, provider)` — one function switches
  OpenAI / Bedrock / Fireworks via `MODEL_PROVIDER`; agent code never touches providers. Copy wholesale.
- **Evals** `evals/` (autotune, harness) and `tests/evals/` (router_eval.py, safety_replay.py, replay
  harnesses) — a replay/eval pattern to extend.
- **Observability**: Strands OpenTelemetry → CloudWatch/X-Ray (README).

Recommendation: fork zoya-harness's `harness.py`+`skills`+`safety.py`+`orchestrator`(hooks)+`models.py`,
drop the voice/Mac layers, swap skills for investment ones, add investment-os's deterministic
guardrails (`narrate.py` number-traceability) and the frozen-eval autoresearch loop.
