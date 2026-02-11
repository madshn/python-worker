---
description: Software Factory Manager. Validates projects against factory standards.
---

# /bob — Software Factory Manager (Child Copy)

This is a baked-in copy of Bob's command interface for use within this project. The master version lives at `~/ops/bob/bob.md`.

## Usage

```
/bob validate [path]    — Audit project against factory standards
/bob status             — Show factory health summary
/bob learn [topic]      — Capture learning to local knowledge base
/bob bigfeature [desc]  — End-to-end autonomous feature development
/bob ux                 — UX constitution management
/bob ux create          — Create new UX constitution
/bob ux review          — Review/adjust existing constitution
/bob ux status          — Show constitution status
```

### Related Commands

```
/ux-test [route]        — AI visual review of any page (separate command)
```

## Arguments

```
$ARGUMENTS
```

---

## Available Commands (Child Project)

### validate

Audit this project against Bob factory standards.

```
/bob validate        # Validate current project
/bob validate .      # Explicit current directory
/bob validate --strict  # Force full dev rigor
```

**Execution:**
1. Spawn validator agent
2. Generate report
3. Present findings

### status

Show brief factory status for this project.

```
/bob status
```

**Output:**
- Classification (dev/ops/fun)
- Last validation date and commit SHA
- Commits since last visit
- Key metrics

### learn

Capture a learning to this project's local knowledge base.

```
/bob learn "Discovery or pattern worth remembering"
/bob learn --category stack "Framework-specific gotcha"
/bob learn --category ops "Deployment pattern"
```

**Execution:**
1. Parse learning text from arguments
2. Auto-detect category if not specified:
   - Tool/framework names → `stack`
   - Workflow/automation terms → `ops`
   - Otherwise → `universal`
3. Detect git context (current SHA, recent commit)
4. Prompt for enrichment (title, tags, confidence)
5. Append to `learnings/[category].md`

**Categories:**
| Category | File | What to Capture |
|----------|------|-----------------|
| `stack` | `learnings/stack.md` | Framework gotchas, library patterns, build issues |
| `ops` | `learnings/ops.md` | Deployment, CI/CD, automation patterns |
| `universal` | `learnings/universal.md` | Cross-cutting patterns, architecture insights |

**Format:**
```markdown
### [YYYY-MM-DD] Title

**Category:** [category]
**Tags:** [comma, separated]
**Source:** [project] @ [sha]
**Confidence:** [high/medium/low]

[Description — 2-4 sentences]

**Pattern:** (optional)
[Code or config example]

**Anti-pattern:** (optional)
[What NOT to do]
```

**Note:** Local learnings are pulled by Bob during `/bob rounds`. Approved learnings are promoted to the factory knowledge base.

### ux

Manage UX constitution for this project.

```
/bob ux              # Auto-detect mode (create vs review)
/bob ux create       # Create new constitution from existing docs
/bob ux review       # Review/adjust existing constitution
/bob ux status       # Quick status check
```

**Execution:**
1. Check for `docs/ux-constitution.md`
2. If not found → spawn `ux-creator` agent (analyze docs, guide creation)
3. If found → spawn `ux-reviewer` agent (guided review/adjustment)

**Create mode (no constitution exists):**
- Analyzes CLAUDE.md, README, ROADMAP for context
- Pre-populates 6 UX passes with inferences
- Suggests reference designs with clickable links
- Guides through validation and gap filling
- Generates `docs/ux-constitution.md`

**Review mode (constitution exists):**
- Asks for trigger: degradation | pivot | redesign
- Degradation: UX quality declined after new features
- Pivot: Fundamental direction change needed
- Redesign: Same architecture, new visual treatment
- Updates affected sections, versions the change

**Status:**
```
/bob ux status
# Output: version, last update, change log summary
```

### bigfeature

End-to-end autonomous feature development from specification to verified implementation.

```
/bob bigfeature "Add user authentication with OAuth2"
/bob bigfeature --resume            # Continue interrupted session
/bob bigfeature --status            # Check current progress
/bob bigfeature --preflight         # Run pre-flight only
/bob bigfeature --abort             # Abort (preserves artifacts)
```

**When to Use:**
- Feature spans 3+ files
- Has testable acceptance criteria
- Benefits from overnight/unattended execution
- Worth ~15-30 min setup overhead

**Parallel Worktree Support:**

Multiple bigfeatures can run in parallel across git worktrees. Each worktree maintains isolated state.

**Claude handles directory changes:** For sequential work or resuming, Claude `cd`s to the worktree itself. Do NOT tell users they need to manually cd and start new Claude sessions.

```bash
# Claude switches to worktree and continues working:
cd .worktrees/feature-a
/bob bigfeature --resume

# Only for true parallelism: separate terminal sessions needed
# Terminal 1: claude → work on feature-a
# Terminal 2: claude → work on feature-b
```

State file lives at `{worktree}/.claude/.bigfeature-state.json`.

Set unique ports per worktree: `export PORT=5174` before starting dev server.

**Flow Overview:**
```
Phase 0: PRE-FLIGHT     — Verify environment ready (Git, MCP, tests, permissions)
Phase 1: SPECIFICATION  — Generate spec.md via /speckit.specify
Phase 2: UX DESIGN      — Run 6-pass UX pipeline (if UI feature)
Phase 3: PLANNING       — Generate plan.md via /speckit.plan
Phase 4: TASKS          — Generate tasks.md via /speckit.tasks
Phase 5: TASK REGISTRATION — Register tasks into native Task system with dependencies
   ─── CHECKPOINT ───   — Human chooses: start now | review | abort
Phase 6: EXECUTION      — Work through TaskList (tasks persist through /compact)
Phase 7: VERIFICATION   — Full test suite, UX review, factory validation
Phase 8: HANDOFF        — PR ready for human review
```

**Pre-Flight Blockers:**

| Level | Meaning | Action |
|-------|---------|--------|
| HARD | Cannot proceed | Must fix |
| SOFT | Degraded capability | Warn, continue |

HARD blockers: Dirty git, detached HEAD, CLAUDE.md missing, test port in use
SOFT blockers: MCP unavailable, remote approval not configured

**State Management:**

Progress tracked in `.claude/.bigfeature-state.json` (relative to worktree root):
- Current phase and iteration
- Artifact paths (spec, plan, tasks)
- Validation status
- Blockers encountered

**State file location:** `$(git rev-parse --show-toplevel)/.claude/.bigfeature-state.json`
- In normal repo: `{project}/.claude/.bigfeature-state.json`
- In worktree: `{project}/.worktrees/{name}/.claude/.bigfeature-state.json`

**Resume capability:** `/bob bigfeature --resume` picks up from last completed phase. Must be run from same directory as original session.

**Completion Criteria:**

Execution is complete when ALL conditions met:
- All tasks in TaskList show `completed`
- Unit tests pass (0 failures)
- E2E tests pass (0 failures)
- Lint + type check pass
- Build succeeds

**Full Documentation:** `~/ops/bob/patterns/bigfeature/`
- `README.md` — Complete flow details
- `preflight-checklist.md` — All blocker checks
- `task-execution-protocol.md` — Task-driven execution protocol
- `state-schema.json` — State file schema

---

## For Full Factory Access

For create, adopt, rounds, and other factory operations, use Bob master:

```bash
cd ~/ops/bob
# Then run /bob commands from there
```

**Note:** `/bob learn` captures to this project's local `learnings/` folder. Bob pulls these during rounds and promotes approved learnings to the factory.

---

## Error Handling

| Error | Response |
|-------|----------|
| Unknown subcommand | "This child copy supports: validate, status, learn, bigfeature, ux. For full access, use ~/ops/bob/" |
| Path not found | "Path not found: [path]" |
