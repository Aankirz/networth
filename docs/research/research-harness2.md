# Research: google-research/harness2 (Harness²)

Researched 2026-10-24. Sources: the repo via `gh` (README, docs/SETUP.md, docs/EXPERIMENTS.md, pyproject.toml, `harness2/core/*`, `harness2/substrate/*`, `harness2/benchmarks/tasks.py`, the issue list) and the arXiv abstract page. Anything I could not check is marked as unverified.

## Facts at a glance

| Item | Value |
|---|---|
| Repo | https://github.com/google-research/harness2 (public) |
| Name | Harness²: "Recursive Agent Harnessing for an Open World" |
| Paper | arXiv:2610.14224, submitted 9 Oct 2026 (Xu, Chen, ..., Lee, Pfister; Google Research) |
| License | Apache-2.0. Benchmarks and code under `third_party/` keep their own upstream licenses |
| Language | Python 3.12 or 3.13 (`requires-python >=3.12,<3.14`). OpenCode plugins are TypeScript |
| Version | 0.1.0, with no tags or releases (issue #106 asks for a tag) |
| Commits | 3: initial release 2026-10-08, "updates" 2026-10-09, "Fix arXiv link" 2026-10-14 (last push) |
| Stars | about 18.8k, gained in about 16 days, so it is popular |
| Open issues | Many, mostly correctness bugs found by early users (see Risks) |
| Support | "Not an officially supported Google product" |

## 1. What it does, in plain terms

A **harness** is everything around a model with frozen weights: system prompt, tools, memory, skills, subagents, and so on. Harness² is a framework where **an LLM edits an agent's harness files, re-runs the agent, compares the runs, and adopts a better harness**. It never touches model weights.

It has two loops:

- **Task-level recursion (Propose–Probe–Compose).** For one task:
  1. Run the base harness k times. These are the reference executions.
  2. An *editor* LLM proposes candidate harness edits. There are two kinds: "invariant" (general) edits and "domain" edits.
  3. Each candidate is *probed*: the agent runs the same task with that harness.
  4. A *composer* LLM looks at the behavioural contrasts between the trajectories and deliverables, then writes one refined harness.

  The key design point is that this works **without ground-truth feedback**. The prompts explicitly say "There is no rubric, grading criteria, answer key, reference solution or score anywhere". The scoring judge is only called *after* selection is committed, for reporting. Cost per task is 4k rollouts plus 3k improver stages.
- **Harnessing-level recursion.** After each task, a *reflector* stores the adopted harness and "evidence-supported lessons" in a per-domain library. Later tasks in the same domain read that library.

There are two scaling modes:

- `--mode parallel`: k general and k domain candidates, then k compositions.
- `--mode sequential`: k chained Propose–Probe–Compose steps.

Reported gains are up to +11.5 points on WorkBuddy-Bench, +4.5 on JobBench and +11.8 pp on LAB, with GLM-5 and Gemini 3.5 Flash.

### Core abstractions (from the code)

- **Harness tree (c1..c8).** Eight editable components stored as files:
  - system prompt
  - guardrails
  - memory
  - tool guidance
  - subagents
  - skills
  - scripts
  - plugins

  They are declared in a `harness.yaml` manifest. The agent runtime itself (the CLI, its tool implementations, the provider) is frozen and is not part of the tree.
- **Substrate** (`substrate/base.py`). The executor framework. Its interface is `surface()`, `materialise()`, `execute()`, `read_trajectory()` and `preflight()`. Only **OpenCode** (the default) and **Codex** (`--substrate cx`) ship.
- **BenchmarkAdapter** (`core/spec.py`). About 12 methods a benchmark must implement:
  - `tasks`, `domain_of`, `task_prompt`, `task_files`
  - `execute`, `delivered`, `trajectory`
  - `deliverable_files`, `deliverable_text`
  - `base_harness`, `validate_tree`, `score`

  The docstring says "Implement these and the whole method works". The only benchmarks wired in are JobBench, LAB and WorkBuddy-Bench. `tasks.discover()` is hard-coded to those three, so a custom benchmark means changing code, not adding config.
- **Proposer** (`core/proposer.py`). Runs improver sessions as agentic CLI sessions over a workspace. Each session has up to 120 steps and a 1 h timeout. It keeps an audit trail and a cache.
- **Ledger, library, selection, report.** Cost and accounting, the per-domain lessons store, the adoption logic, and the CLI commands `harness2`, `harness2-judge`, `harness2-report`, `harness2-setup`, `harness2-check`, `harness2-demo` and `harness2-bridge`.

## 2. Requirements, and whether it works with Claude

**Platform:** Linux, Python 3.12, uv, Node.js 20+ and the Google Cloud CLI. LAB also needs Pandoc and Poppler; WorkBuddy needs Docker. Setup clones pinned upstream benchmarks, applies patches, installs its own Bun runtime, and downloads data from Hugging Face.

`harness2-demo` runs offline with deterministic editors and needs no credentials. It is the only path that needs no model.

**Models:** Everything is configured for **Vertex AI**: `GOOGLE_CLOUD_PROJECT` plus `gcloud auth application-default login`. There are three model slots:

- `HARNESS2_SOLVER_MODEL`: the executor, in OpenCode `provider/model` form.
- `HARNESS2_IMPROVER_MODEL`: the editor, composer and reflector.
- `HARNESS2_JUDGE_MODEL`.

**Claude support:**

- **Improver: yes, but only via Claude on Vertex.** The `claude_cli` channel shells out to the `claude` CLI with `CLAUDE_CODE_USE_VERTEX=1`. It explicitly *strips* `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL` and the Bedrock variables from the environment (`_DROP_ENV` in `proposer.py`). A direct Anthropic API key will not work there without patching.
- **Executor: unverified.** The executor is OpenCode, which accepts `provider/model` ids. The config only checks for a slash, so `anthropic/<model>` *might* work, but nothing in the docs or code shows it was tested.
- **Judge:** LAB adds a `vertex/` prefix for `claude*` and `gemini*` ids. There is a patch file named `harvey-labs-judge-vertex-anthropic.diff`.
- **Shipped configuration:** Gemini executor and judge, and "Vertex Claude or Gemini as the improver".

**Compute and cost:** All the compute is API calls; no GPUs are needed. Cost per task at k=1 is 4 rollouts plus 3 long agentic improver sessions. The authors warn that LAB alone has 1,143 tasks, so start small.

**Other gaps:**

- `.env.example` is referenced in the README, but there is no such file in the repo tree (a GitHub API lookup returns 404). You write `.env` by hand.
- The executor has unrestricted network access, and Codex runs with its sandbox disabled. The authors saw a rollout download its own grading rubric.

## 3. Using it in a 24h hackathon on an investment-agent harness

**The objective does not fit.** Our job is to optimize one harness (prompts, tools, skills) against a frozen, labelled eval of about 25 headlines. Harness² does something else: it refines the harness **per task, at test time, without labels**, and accumulates per-domain lessons. Its output is a set of per-task adopted harnesses, not one harness tuned to beat an eval set. The scoring judge is deliberately kept out of the loop. To use our labels, we would have to change the selection logic.

**If we use it anyway, these are the steps and time costs:**

1. **Linux box, Python 3.12, uv, Node 20, gcloud with Vertex access that includes Claude on Vertex, then `harness2-demo`: about 1–2 h.** Expect longer if nobody has a GCP project with Claude on Vertex enabled. That is a hard blocker if we only have an Anthropic API key.
2. **Port our agent onto OpenCode: about 3–6 h, the biggest unknown.** Harness² can only run OpenCode or Codex executors. Our prompts become `systemprompt.md` and `guardrails.md`, skills go into `skills/`, and tools become OpenCode TS plugins or `scripts/`. If our agent runs on the Claude Agent SDK or our own runtime, we would instead have to write a new Substrate (5 methods) plus a launcher.
3. **Write an `InvestmentAdapter` (the BenchmarkAdapter methods), add it to `tasks.discover()` and the CLI benchmark switch, and wire our scorer into `score()`: about 3–4 h.**
4. **Run with `--k 1 --mode parallel` over 25 headlines.** That is about 100 rollouts plus 75 improver sessions. Wall time is maybe 1–3 h depending on concurrency (`--workers` runs domains in parallel, tasks within a domain run in order). Then `harness2-judge`, plus `--bases` for the baseline comparison, and `harness2-report`.
5. **Hand-merge the per-task adopted harnesses and lessons into one harness, then re-run our eval: about 1–2 h.**

**Total: about 9–17 h of a 24 h hackathon, with a real risk of being blocked on step 1 or 2.**

## 4. Risks and recommendation

**Maturity:** v0.1.0, released 16 days ago, 3 commits, no tags. Users have already filed silent-failure bugs:

- #109: an improver outage is saved as `ok`, and resume never re-runs the task.
- #80: `judge_one` trusts the payload's pass counts, so a passing task can read as a failure.
- #121: JobBench keeps rollouts killed at their time limit as finished runs.
- #111: OpenCode rollouts share installs, temp files and workspaces.
- #77: the LAB runner fails silently when the `timeout` command is missing.
- #98: the report drops improver spend when a mode fails.
- #95: the judge cannot route to OpenAI-compatible endpoints.

The code is careful (a typed Protocol, preflight checks, a cost ledger), but the benchmark plumbing is young.

**License:** Apache-2.0 is fine for a hackathon or commercial use. The benchmark datasets and `third_party/` code have their own licenses, which matters only if we redistribute them.

**Setup:** Linux, Vertex and OpenCode are three separate environment dependencies. The benchmarks are hard-wired, the objective does not match ours, and the Claude path is Vertex-only.

**Verdict: in 24 h, borrow the idea, not the tool.**

**Ideas worth stealing:**

- Treat the harness as a small tree of editable files with a validator.
- Propose–Probe–Compose. Propose several separate edits, split into general and domain-specific ones. Probe each one on real runs. Have a composer read the *contrast between trajectories*, not just the scores, and merge the winners.
- If a proposal fails validation, retry once with the error message, then keep the current harness.
- Keep a persistent "lessons" file that the proposer reads on every iteration.
- Block the executor's network from the answer key. In our case that means headline outcomes.

### Minimal homegrown version (about 150–250 lines of Python, 3–5 h to build)

```
harness/                      # the only thing the optimizer may edit
  system_prompt.md
  tool_descriptions.md
  skills/*.md
  lessons.md                  # persistent, appended by the reflector
eval/headlines.jsonl          # 25 frozen items + labels/rubric; split 15 train / 10 held-out
optimize.py
```

`optimize.py` runs this loop:

1. `run_eval(harness, items)`: run our real agent in parallel over the items. Save the trajectory, the output and the score for each item (deterministic checks plus an LLM judge with a fixed rubric).
2. `propose(harness, failing_traces, lessons, n=4)`: a Claude call returns N *independent* unified diffs to harness files, with a mix of general and headline-type-specific edits. Reject a diff that does not apply or breaks the validator, retry it once with the error, and otherwise drop it.
3. `probe`: run each candidate on the train split.
4. `compose`: a Claude call gets the candidate diffs, per-item score deltas and paired trajectories (base vs. candidate on the same headline), then writes one merged diff.
5. **Accept only if the train score improves and the held-out score does not drop.** Then commit the harness with git and have the reflector append 1–3 evidence-backed lessons to `lessons.md`.
6. Repeat 3–6 times. Pick the final harness by held-out score once at the end, then freeze it.

**Expected cost:** with 4 candidates and 15 train items, one iteration is about 60–75 agent runs plus 2 Claude proposer and composer calls. Iterations take about 15–40 min depending on agent latency, so 4–6 iterations fit comfortably in a 24 h window and leave time for the demo.

**Main risk: overfitting to 25 items.** Use the train/held-out split, require gains on several items rather than one, and keep labels out of the agent's reach.
