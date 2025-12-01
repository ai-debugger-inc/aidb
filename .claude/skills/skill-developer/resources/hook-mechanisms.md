# Hook Mechanisms - Deep Dive

Technical deep dive into how the UserPromptSubmit hook works in the skills auto-activation system.

______________________________________________________________________

## System Overview

The skills system uses **only the UserPromptSubmit hook** for automatic skill detection and injection. There is **no PreToolUse hook** in the current implementation.

**Key Architecture:**

- UserPromptSubmit hook detects relevant skills via AI analysis
- Skills are automatically injected into the conversation context
- No blocking mechanism - all skills are advisory/auto-injected
- Session tracking prevents duplicate injection

______________________________________________________________________

## UserPromptSubmit Hook Flow

### Execution Sequence

```
User submits prompt
    ↓
.claude/settings.json registers UserPromptSubmit hook
    ↓
skill-activation-prompt.sh executes
    ↓
npx tsx skill-activation-prompt.ts
    ↓
Hook reads stdin (JSON with prompt + session info)
    ↓
Loads skill-rules.json
    ↓
DETECTION PHASE:
  - Check if prompt is very short (<10 words)
    → If yes: Use keyword matching (fallback)
    → If no: Use AI-powered intent analysis (primary)
  - AI sends prompt + all skill descriptions to Claude API (configurable model)
  - AI returns confidence scores for each skill
    ↓
FILTRATION PHASE:
  - Load session state (.claude/hooks/state/{session_id}-skills-suggested.json)
  - Remove already-injected skills (deduplication)
  - Filter out skills with autoInject: false
    ↓
AFFINITY RESOLUTION:
  - Check affinity arrays (bidirectional relationships)
  - Auto-inject affinity skills (free of slot cost)
    ↓
DEPENDENCY RESOLUTION:
  - Check requiredSkills arrays
  - Ensure dependencies are loaded first
  - Sort by injectionOrder
    ↓
INJECTION:
  - Read skill SKILL.md files from disk
  - Prepend skill content to stdout
  - Output formatted banner showing loaded skills
  - Update session state with injected skills
    ↓
stdout → Claude's context (injected as system message)
    ↓
Claude sees: [auto-loaded skill content] + [banner] + user's prompt
```

### Key Points

- **Exit code**: Always 0 (allow)
- **stdout**: Injected into Claude's context as system message
- **Timing**: Runs BEFORE Claude processes prompt
- **Behavior**: Non-blocking, automatic skill injection
- **Purpose**: Automatically provide relevant context to Claude

### Input Format

```json
{
  "session_id": "abc-123",
  "transcript_path": "/path/to/transcript.json",
  "cwd": "/root/git/your-project",
  "permission_mode": "normal",
  "hook_event_name": "UserPromptSubmit",
  "prompt": "Fix the Java adapter"
}
```

### Output Format (to stdout)

The hook outputs two parts:

**1. Skill Content (prepended to context):**

```markdown
<skill name="adapter-development">
[Full content of adapter-development/SKILL.md]
</skill>

<skill name="aidb-architecture">
[Full content of aidb-architecture/SKILL.md via affinity]
</skill>
```

**2. Banner (visible to user):**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📚 AUTO-LOADED SKILLS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<skill name="adapter-development">
[adapter-development content]
</skill>

<skill name="aidb-architecture">
[aidb-architecture content via affinity]
</skill>

💡 Meta-skills: skill-developer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Claude receives the full skill content in its context and can reference it when responding.

______________________________________________________________________

## AI-Powered Intent Analysis

### How It Works

The primary detection mechanism uses the Anthropic API to analyze user prompts:

**Implementation:** `.claude/hooks/lib/anthropic-client.ts`

**Process:**

1. Collect all skill `description` fields from skill-rules.json
1. Build a prompt asking AI to score relevance of each skill
1. Send to Claude API via Anthropic SDK (model configurable via CLAUDE_SKILLS_MODEL)
1. Parse JSON response with confidence scores
1. Return skills above threshold

**Example AI Prompt:**

```
You are analyzing a user prompt to determine which skills are relevant.

User prompt: "Fix the Java adapter"

Available skills:
- adapter-development: Guide for AIDB adapter development...
- testing-strategy: Guide for implementing tests...
- dap-protocol-guide: Guide for DAP protocol types...

Return JSON array of relevant skills with confidence scores.
```

**Example AI Response:**

```json
[
  {"skill": "adapter-development", "confidence": 0.95},
  {"skill": "dap-protocol-guide", "confidence": 0.70}
]
```

### Fallback: Keyword Matching

For very short prompts (\<10 words), the hook uses simple keyword matching instead of AI analysis:

**Implementation:** `.claude/hooks/lib/keyword-matcher.ts`

**Process:**

1. Extract `promptTriggers.keywords` from skill-rules.json
1. Check if any keyword appears in prompt (case-insensitive substring match)
1. Return matching skills

______________________________________________________________________

## Affinity System (Bidirectional Auto-Injection)

### How It Works

Skills can declare "affinity" relationships that cause automatic bidirectional injection:

**Configuration:**

```json
{
  "adapter-development": {
    "affinity": ["aidb-architecture", "dap-protocol-guide"]
  },
  "dap-protocol-guide": {
    "affinity": ["aidb-architecture"]
  }
}
```

**Injection Logic:**

**Direction 1 (Parent→Child):**

- If `adapter-development` is detected
- Its affinity skills (`aidb-architecture`, `dap-protocol-guide`) auto-inject

**Direction 2 (Child→Parent):**

- If `dap-protocol-guide` is detected
- Any skill listing it in affinity (e.g., `adapter-development`) auto-injects

**Implementation:** `.claude/hooks/lib/skill-filtration.ts`

**Key Features:**

- Affinity skills are "free" (don't count toward standard 2-skill limit)
- Respects session state (won't re-inject already-loaded skills)
- Max 2 affinities per skill
- Helps load complementary context automatically

______________________________________________________________________

## Session State Management

### Purpose

Prevent duplicate injection in the same conversation - once a skill is loaded, don't inject it again.

### State File Location

`.claude/hooks/state/{conversation_id}-skills-suggested.json`

### State File Structure

```json
{
  "conversation_id": "abc-123",
  "skills_injected": [
    "adapter-development",
    "aidb-architecture"
  ],
  "last_updated": "2025-01-15T10:30:00Z"
}
```

### How It Works

1. **First detection** of a skill:

   - Hook injects skill content
   - Updates session state: adds skill to skills_injected array
   - Skill content available to Claude

1. **Second detection** (same conversation):

   - Hook checks session state
   - Finds skill in skills_injected array
   - Skips injection (skill already loaded)
   - No output, no message

1. **Different conversation**:

   - New conversation ID = new state file
   - Hook injects skill again

**Implementation:** `.claude/hooks/lib/session-manager.ts`

______________________________________________________________________

## What's NOT Implemented

The following features are **documented in older versions** but **not implemented** in the current system:

### ❌ PreToolUse Hook

- No PreToolUse hook is registered in `.claude/settings.json`
- No `skill-verification-guard.ts` file exists
- No blocking mechanism exists
- Exit code 2 blocking is not used

### ❌ File Triggers

- `fileTriggers.pathPatterns` - not read by any hook
- `fileTriggers.contentPatterns` - not read by any hook
- `fileTriggers.pathExclusions` - not read by any hook
- `fileTriggers.createOnly` - not read by any hook

### ❌ Skip Conditions

- `skipConditions.sessionSkillUsed` - not read by any hook
- `skipConditions.fileMarkers` - not read by any hook
- `skipConditions.envOverride` - not read by any hook

### ❌ Block Messages

- `blockMessage` field - never displayed
- No blocking mechanism to show messages

### ❌ Intent Pattern Triggers (Regex)

- `intentPatterns` arrays - not read by any hook
- Replaced by AI-powered intent analysis

______________________________________________________________________

## Exit Code Behavior

### Exit Code Reference Table

| Hook             | Exit Code | stdout    | stderr      | Behavior               |
| ---------------- | --------- | --------- | ----------- | ---------------------- |
| UserPromptSubmit | 0         | → Context | → User only | Skill content injected |

**Key Points:**

- UserPromptSubmit always returns exit code 0 (allow)
- stdout contains skill content and banner
- No blocking mechanism exists in current implementation

______________________________________________________________________

## Performance Considerations

### Target Metrics

- **UserPromptSubmit**: < 2 seconds (includes AI API call)
- **Keyword fallback**: < 100ms

### Performance Bottlenecks

1. **AI API Call** (primary bottleneck)

   - Anthropic API latency: ~1-2 seconds
   - Only used for prompts ≥10 words
   - Defaults to fast Haiku 4.5 model (configurable via CLAUDE_SKILLS_MODEL)

1. **Loading skill-rules.json** (every execution)

   - Parsed from disk each time
   - ~50 skills in current implementation
   - Negligible impact (\<10ms)

1. **Reading skill SKILL.md files**

   - One file read per injected skill
   - Typically 2-3 skills per prompt
   - ~50-200KB total content

1. **Session state I/O**

   - Read: Check already-loaded skills
   - Write: Update with newly-injected skills
   - JSON file operations (\<10ms)

### Optimization Strategies

**Reduce AI calls:**

- Short prompts use keyword fallback (no API call)
- Session deduplication prevents re-analysis

**Reduce skill content:**

- Keep SKILL.md files under 500 lines (faster to read and parse)
- Progressive disclosure (link to resource files for details)

**Cache considerations:**

- skill-rules.json is re-read each time (enables hot-reloading)
- Session state is cached in memory during hook execution

______________________________________________________________________

## Hook Registration

The hook is registered in `.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": {
      "command": ".claude/hooks/skill-activation-prompt.sh",
      "timeout": 30000
    }
  }
}
```

**Key Configuration:**

- `timeout`: 30 seconds (allows time for AI API call)
- No PreToolUse hook is registered

______________________________________________________________________

**Related Files:**

- [SKILL.md](../SKILL.md) - Main skill guide
- [skill-rules-reference.md](skill-rules-reference.md) - Configuration reference
- [trigger-types.md](trigger-types.md) - Trigger configuration guide
