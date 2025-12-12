# AIDB Claude Code Skills

This directory contains skills that provide comprehensive guidance for AIDB development. Skills auto-activate based on your prompts and file edits.

## What Are Skills?

Skills are modular knowledge bases that Claude loads when needed. They provide:

- Architecture patterns and best practices
- Code reuse guidance (constants, enums, utilities)
- Common pitfalls and how to avoid them
- Working code examples from the actual codebase

## Installed Skills

### 1. adapter-development (CRITICAL GUIDANCE)

**When it activates:**

- Editing files in `src/aidb/adapters/`
- Editing files in `src/aidb/session/`
- Mentioning "adapter", "debugpy", "vscode-js-debug", "java-debug"
- Working with process management or port management

**What it covers:**

- Component-based adapter architecture
- ProcessManager, PortManager, LaunchOrchestrator
- Lifecycle hooks (PRE_LAUNCH, POST_LAUNCH, etc.)
- Language-specific patterns (Python/JavaScript/Java)
- Resource cleanup and process tagging

**Priority:** CRITICAL - Automatically injected into context when detected

**Main file:** `adapter-development/SKILL.md`

### 2. dap-protocol-guide (HIGH PRIORITY)

**When it activates:**

- Editing files in `src/aidb/dap/`
- Mentioning "DAP", "debug adapter protocol", "initialize request"
- Working with breakpoints, stack traces, variables

**What it covers:**

- Authoritative DAP reference: `src/aidb/dap/protocol/`
- Request/response sequences
- Protocol types (SetBreakpointsRequest, StackTraceRequest, etc.)
- Language-specific differences
- Common pitfalls

**Priority:** HIGH - Automatically injected into context when detected

**Main file:** `dap-protocol-guide/SKILL.md`

### 3. testing-strategy (HIGH PRIORITY)

**When it activates:**

- Editing files in `src/tests/`
- Mentioning "test", "DebugInterface", "E2E", "pytest"
- Working with test infrastructure

**What it covers:**

- E2E-first philosophy (E2E → Integration → Unit)
- DebugInterface abstraction
- MCP response validation (structure + content + efficiency)
- Framework test patterns (Django, Express, Spring Boot)
- Working examples and templates

**Priority:** HIGH - Automatically injected into context when detected

**Main file:** `testing-strategy/SKILL.md`

### 4. mcp-tools-development (HIGH PRIORITY)

**When it activates:**

- Editing files in `src/aidb_mcp/`
- Mentioning "MCP tool", "agent optimization", "tool handler"
- Working with MCP server

**What it covers:**

- MCP tool architecture
- Agent-optimized responses (accuracy + clarity + speed)
- Request validation patterns
- Error handling for user-facing tools
- Performance considerations

**Priority:** HIGH - Automatically injected into context when detected

**Main file:** `mcp-tools-development/SKILL.md`

### 5. code-reuse-enforcement (CRITICAL GUIDANCE)

**When it activates:**

- Editing ANY Python file in `src/`
- Adding URL strings, file paths, error messages
- Mentions of "constant", "enum", "magic string"

**What it covers:**

- All 10 constants files in the codebase
- All 25+ enum files
- Utility packages (aidb_common.io, aidb_common.path, etc.)
- DRY patterns and violation examples
- Constants discovery workflow

**Priority:** CRITICAL - Automatically injected into context when detected

**Main file:** `code-reuse-enforcement/SKILL.md`

## How Skills Activate

Skills auto-activate via the `UserPromptSubmit` hook, which uses two mechanisms:

1. **AI-powered intent analysis** (primary) - The hook analyzes your entire prompt using Claude to understand intent
1. **Keyword matching** (fallback) - If intent analysis is unavailable, simple keyword matching from `skill-rules.json` is used

### Activation Mechanisms

**Primary: AI Intent Analysis**

- Claude analyzes the semantic meaning of your prompt
- Understands context and implied topics
- Example: "I need to work on the Python adapter" → detects adapter-development context

**Fallback: Keyword Matching**

- Direct string matching in prompts from `skill-rules.json`
- Example: "adapter" keyword in prompt → activates adapter-development
- Activated only if intent analysis is unavailable

### Priority Levels

When multiple skills match, they are automatically injected based on priority:

- **CRITICAL** - Always injected (fundamental architecture guidance)
- **HIGH** - Always injected (important patterns and best practices)
- **MEDIUM** - Injected when relevant
- **LOW** - Available if requested manually

### Auto-Injection

All matched skills are automatically injected into your conversation context. The system tracks which skills have been injected in the current session to prevent re-injection of the same skill multiple times.

## Skill Rules Configuration

Skills are configured in `skill-rules.json` with these key fields:

```json
{
  "version": "1.0",
  "skills": {
    "adapter-development": {
      "type": "domain",
      "enforcement": "block",
      "priority": "critical",
      "description": "Domain knowledge about adapter architecture and patterns",
      "promptTriggers": {
        "keywords": ["adapter", "debugpy", "vscode-js-debug", "java-debug"]
      },
      "affinity": ["aidb-architecture", "dap-protocol-guide"],
      "autoInject": true,
      "requiredSkills": []
    }
  }
}
```

**Configuration Fields:**

- `type` - Skill category (domain, guardrail, infrastructure)
- `enforcement` - How to handle skill guidance: block, suggest, or warn
- `priority` - When multiple skills match: CRITICAL, HIGH, MEDIUM, LOW
- `description` - Sent to AI for intent analysis (determines when skill is relevant)
- `promptTriggers.keywords` - Keywords that trigger the skill
- `affinity` - Other skills that are conceptually related
- `autoInject` - Automatically inject into context (default: true)
- `requiredSkills` - Other skills that must be injected first

## Session Tracking

The system tracks which skills have been injected into the current session:

- When a skill is activated and matches your prompt/context, it is injected
- The skill is marked as "used in this session"
- If the same skill matches again later in the session, it is not re-injected
- New sessions reset the tracking (all skills available to inject again)

**Why?** Prevents redundant skill injection while ensuring you see each skill's guidance once per session.

## Progressive Disclosure Pattern

Skills follow the "500-line rule" - main SKILL.md stays under 500 lines by splitting detailed content into resource files:

```
skill-name/
├── SKILL.md              # <500 lines, overview + navigation
└── resources/
    ├── topic-1.md        # <500 lines, detailed guidance
    ├── topic-2.md        # <500 lines, detailed guidance
    └── topic-3.md        # <500 lines, detailed guidance
```

**Claude loads:**

1. Main SKILL.md first (quick overview)
1. Resource files on-demand (when needed)

**Value:** Massive skills stay usable without hitting context limits

## Using Skills Manually

If auto-activation doesn't trigger, invoke manually:

```
User: "Use the adapter-development skill"
```

Claude will load the skill and apply its guidance.

## Skill Quality Standards

All AIDB skills follow these standards:

✅ **Accuracy** - Reflects actual AIDB architecture
✅ **Completeness** - Covers essential topics
✅ **Navigation** - Clear structure with resource references
✅ **Code Examples** - Real patterns from AIDB codebase
✅ **References** - Points to actual source files
✅ **Length** - Main file \<500 lines (or justified)

## Testing Skill Activation

### Test Intent Analysis

When you include adapter-related context in your prompt, the system performs intent analysis to detect that you're working on adapter code and automatically inject the adapter-development skill.

Example:

```
User: "I'm implementing the Python adapter for debugging support"
→ System detects adapter context → adapter-development skill auto-injected
```

### Test Keyword Matching (Fallback)

If intent analysis is unavailable, keyword matching from `skill-rules.json` provides fallback activation:

```
User: "I need to modify the adapter"
→ System detects "adapter" keyword → adapter-development skill auto-injected
```

### Manual Skill Invocation

You can also manually invoke a skill if needed:

```
User: "Use the adapter-development skill"
→ Skill is immediately loaded and injected
```

## Adding New Skills

To create a new skill:

1. Create skill directory:

   ```bash
   mkdir -p .claude/skills/my-skill/resources
   ```

1. Create main SKILL.md with frontmatter:

   ```markdown
   ---
   name: my-skill
   description: Brief description (max 1024 chars, include all keywords)
   ---

   # My Skill

   [Content under 500 lines]

   ## Navigation
   - [Topic 1](resources/topic-1.md)
   - [Topic 2](resources/topic-2.md)
   ```

1. Create resource files (each \<500 lines)

1. Add to `skill-rules.json`:

   ```json
   {
     "my-skill": {
       "type": "domain",
       "priority": "medium",
       "description": "Brief description",
       "promptTriggers": {
         "keywords": ["my", "skill"]
       },
       "autoInject": true
     }
   }
   ```

1. Test activation

## Troubleshooting

### Skill not activating

1. Check keywords in prompt match `skill-rules.json`
1. Verify intent analysis is working properly
1. Check Claude logs for errors
1. Try keyword matching fallback with explicit keyword

### False positives (activates too often)

1. Make keywords more specific
1. Tighten intent patterns
1. Review affinity path configuration

## Performance

Skill activation is designed to be fast:

- Hook execution: \<100ms
- Intent analysis: Fast AI inference
- Skill loading: Instant (Claude reads markdown)
- No network calls or heavy computation

## Related Documentation

- Hooks system: `.claude/hooks/README.md`
- Main settings: `.claude/settings.json`

## Summary

AIDB skills provide:

- **Auto-activation** via intent analysis and keyword matching
- **Architecture guidance** from real codebase
- **Code reuse** enforcement
- **Best practices** for all domains
- **Progressive disclosure** to manage context

Skills ensure consistent, high-quality AIDB development while guiding you toward proper patterns and practices.
