# Two-Tier Skill System

Complete guide to the meta-skills vs domain-skills distinction and automatic skill detection.

## Overview

Skills are categorized into two tiers with different activation and injection behavior:

### Meta-Skills (Awareness Only, Never Injected)

**Purpose:** Provide background context and awareness

**Characteristics:**

- Detected via keywords and AI intent analysis
- Never auto-injected (`autoInject: false`)
- Agent is aware of them but doesn't load full content
- Provide passive awareness and context

**Example:** `skill-developer` (meta-skill)

**When detected:** Display in status message but don't inject content

**Configuration in skill-rules.json:**

```json
{
  "skill-developer": {
    "autoInject": false
  }
}
```

### Domain Skills (Actionable Guidance, Auto-Injected)

**Purpose:** Provide specific technical guidance for tasks

**Characteristics:**

- Detected based on prompt keywords and AI intent analysis
- Automatically injected when detected (`autoInject: true`)
- Up to 2 CRITICAL skills injected per prompt (3 with affinity bonus)
- RECOMMENDED skills shown but not injected
- Provide actionable domain-specific guidance

**Affinity Bonus:**

Skills can declare complementary relationships via `affinity` configuration. When complementary skills are detected together, the injection limit increases from 2 to 3, allowing both related skills to load.

**Example:** `adapter-development` declares affinity with `dap-protocol-guide`. When a prompt triggers both skills (e.g., "Fix DAP initialization in Java adapter"), both inject even though it exceeds the standard 2-skill limit.

**Examples:**

- `adapter-development`
- `testing-strategy`
- `mcp-tools-development`

**When detected:** Automatically inject skill content into context (no manual Skill tool call needed)

## Automatic Skill Detection

**You never need to explicitly request skills.** The system automatically detects them through:

### 1. Keyword Matching

Prompt is analyzed for domain-specific keywords defined in `skill-rules.json`:

```json
"adapter-development": {
  "promptTriggers": {
    "keywords": ["adapter", "debug adapter", "DAP", "JDTLS", "debugpy"]
  }
}
```

**Example:**

- Prompt: "Fix the Java adapter cleanup issue"
- Detected: `adapter-development` (keyword: "adapter")

### 2. File Context

File-based detection is planned but **NOT CURRENTLY IMPLEMENTED**. Detection currently relies on keywords and AI intent analysis.

## AI-Powered Intent Analysis

**Overview:**

The skill detection system uses Claude API (defaults to Haiku 4.5, configurable via CLAUDE_SKILLS_MODEL) to analyze prompt intent and assign confidence scores to skills, dramatically reducing false positives from keyword matching.

### How It Works

1. User submits prompt
1. AI analyzes PRIMARY task intent
1. Assigns confidence scores (0.0-1.0) to each skill
1. High confidence (>0.65) → CRITICAL (must acknowledge)
1. Medium confidence (0.3-0.65) → RECOMMENDED (optional)

### Setup Requirements

**API Key Configuration:**

1. Create `.claude/hooks/.env` file:

   ```bash
   cp .claude/hooks/.env.example .claude/hooks/.env
   ```

1. Add your Anthropic API key:

   ```env
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   ```

1. Get API key from https://console.anthropic.com/

**Note:** API key is **required**. The hook will fail with helpful setup instructions if missing.

### Performance

- **Latency:** ~200ms (first call), \<10ms (cached) - 4-5x faster than Sonnet 4.5
- **Cost:** ~$0.0015 per analysis (Haiku 4.5 pricing: $1/\$5 per million tokens)
- **Cache TTL:** 1 hour
- **Cache location:** `.claude/hooks/.cache/intent-analysis/`
- **Monthly cost:** ~\$1-2 at 100 prompts/day

### Error Handling

- **Missing API key:** Hook fails with helpful setup instructions
- **API errors:** Falls back to keyword matching automatically
- **Cache errors:** Ignored, fetches fresh from API
- **Network errors:** Falls back to keyword matching

### Example: False Positive Elimination

**Before (keyword matching):**

```
Prompt: "Fix precommit issues in skills system"

Detected skills:
  ⚠️ adapter-development (false positive - "adapter" in file path)
  ⚠️ dap-protocol-guide (false positive - "protocol" in error)
  ⚠️ ci-cd-workflows (false positive - "workflow" mention)
  ✅ skill-developer (correct)
```

**After (AI intent analysis):**

```
Prompt: "Fix precommit issues in skills system"

AI Analysis:
  Primary intent: "Fix skill system configuration"

Detected skills:
  ✅ skill-developer (0.95 confidence - primary intent is skill work)

Result: No false positives!
```

### Implementation Details

**Core Logic:** `.claude/hooks/lib/intent-analyzer.ts`

```typescript
// AI analyzes prompt with skill descriptions
const analysis = await analyzeIntent(userPrompt, skillRules);

// Categorize by confidence
const required = analysis.skills.filter(s => s.confidence > 0.65);
const suggested = analysis.skills.filter(s => s.confidence >= 0.3 && s.confidence <= 0.65);
```

**Prompt Engineering:**

The AI receives:

- User's prompt
- Available skills with descriptions
- Instructions to focus on PRIMARY task intent
- Guidance to distinguish main task from passing mentions

**Caching Strategy:**

- MD5 hash of prompt as cache key
- 1-hour TTL to balance freshness vs cost
- Automatic cache directory creation
- Read-through cache pattern

## Hook Flow

### UserPromptSubmit Hook (Detection)

**When:** Before Claude sees your prompt

**Process:**

1. Analyze prompt for keywords
1. Perform AI-powered intent analysis for confidence scoring
1. Identify relevant skills (both meta and domain)
1. Auto-inject CRITICAL skills (confidence > 0.65) up to 2 per prompt
1. Show RECOMMENDED skills for optional manual loading

**Output Example:**

```
📚 AUTO-LOADED SKILLS

🧠 ALWAYS ACTIVE:
  → skill-developer (skill maintenance awareness)

🔥 AUTO-INJECTED (CRITICAL):
  → adapter-development (0.85 confidence)

💡 RECOMMENDED (optional):
  → testing-strategy (0.48 confidence - use Skill tool to load)
```

## Workflow Examples

### Scenario 1: Generic prompt (no domain skills)

**User prompt:** "What's the status of the project?"

**Detection:**

- Keywords: None matching domain skills
- Intent: Informational query
- Result: Only `skill-developer` suggested

**Behavior:**

- Meta-skills only → No skills auto-injected
- Flow: Instant response without skill context

**User experience:** ✅ No friction, immediate answer

### Scenario 2: Domain-specific prompt

**User prompt:** "Fix the Java adapter cleanup issue"

**Detection:**

- Keywords: "adapter", "Java"
- AI analysis: High confidence (0.85) for adapter work
- Result: `adapter-development` marked as CRITICAL

**Auto-Injection:**

- CRITICAL skill → Automatically inject `adapter-development` skill content
- Flow: Skill content loaded before agent responds, no manual action needed

**User experience:** ✅ Instant access to relevant expertise, zero friction

### Scenario 3: Multi-domain prompt

**User prompt:** "Add E2E tests for the Express framework"

**Detection:**

- Keywords: "E2E", "tests", "Express", "framework"
- AI analysis: `testing-strategy` (0.92 critical), `ci-cd-workflows` (0.45 recommended)

**Auto-Injection:**

- CRITICAL: `testing-strategy` → Auto-inject
- RECOMMENDED: `ci-cd-workflows` → Show but don't inject (agent can manually load if needed)
- Flow: Critical skill injected, recommended skill suggested

**User experience:** ✅ Primary guidance auto-loaded, optional context available

### Scenario 4: Already-injected skill deduplication

**User prompt (second message):** "How should I debug this adapter issue?"

**Detection:**

- AI analysis: `adapter-development` (0.88 confidence for adapter question)
- Session state: `adapter-development` already injected in previous turn

**Behavior:**

- CRITICAL skill already in `injectedSkills` → Skip re-injection (prevent duplicate context)
- Shown in AUTO-LOADED banner but content not re-injected
- Flow: Seamless continuation without redundant context

**User experience:** ✅ Deduplication prevents context bloat across conversation turns

## Session State Management

**State file location:** `.claude/hooks/state/{session_id}-skills-suggested.json`

**State structure:**

```json
{
  "timestamp": 1699564800000,
  "suggestedSkills": [],
  "recommendedSkills": [],
  "acknowledged": true,
  "acknowledgedSkills": ["adapter-development", "testing-strategy"],
  "injectedSkills": ["adapter-development", "testing-strategy"],
  "injectionTimestamp": 1699564800000
}
```

**State lifecycle:**

1. UserPromptSubmit detects skills via AI analysis
1. CRITICAL skills (up to 2) are automatically injected
1. Injected skills tracked in `acknowledgedSkills` and `injectedSkills` arrays
1. RECOMMENDED skills shown but not injected
1. Subsequent prompts reuse already-injected skills (no duplicate injection)
1. State persists for conversation duration

## Benefits of Two-Tier System

### For Users

**Zero friction on all prompts:**

- Questions, status checks, explanations → instant responses
- Domain work → skills auto-loaded transparently
- No manual Skill tool calls needed

**Guaranteed expertise on domain prompts:**

- Technical work → automatically receive relevant guidance
- Up to 2 CRITICAL skills injected per prompt
- RECOMMENDED skills suggested for optional loading
- 95% of technical prompts get proper skill coverage

**Transparent and seamless:**

- Clear "📚 AUTO-LOADED SKILLS" banner shows what was injected
- One-time injection per conversation per skill
- Meta-skills provide passive awareness without content injection

### For Skill System

**Optimal signal-to-noise ratio:**

- Meta-skills always present (background awareness)
- Domain skills auto-injected when relevant
- Up to 2 CRITICAL skills per prompt (prevents context overload)

**Maintains skill coverage goals:**

- ~95% of technical prompts covered by auto-injected skills
- ~5% generic prompts flow without injection
- 100% prompts have meta-skill awareness

**Clear separation of concerns:**

- Meta-skills = passive awareness (not injected)
- Domain skills = active guidance (auto-injected when CRITICAL)
- Each tier has distinct purpose and behavior

## Adding New Skills

### Default: Domain Skill

Most skills should be domain skills (auto-injected when detected):

```json
"my-new-skill": {
  "type": "domain",
  "priority": "medium",
  "autoInject": true,
  "promptTriggers": {
    "keywords": ["relevant", "keywords"]
  }
}
```

**Note:** While older documentation versions referenced `intentPatterns` and `fileTriggers`, these features are not implemented. Current detection uses AI-powered intent analysis (primary) and keyword matching (fallback for short prompts).

### Rare: Meta-Skill

Only create a meta-skill if it:

- Is always relevant to every prompt
- Provides passive awareness, not actionable guidance
- Should NOT be injected (`autoInject: false`)

**Current meta-skills:**

- `skill-developer` (skills system awareness)

**To add a new meta-skill:**

1. Add to skill-rules.json with `autoInject: false`
1. Document why it's a meta-skill (high bar to justify)

## Troubleshooting

### Skill not auto-injecting when it should

**Check:**

1. Is `autoInject: true` in skill-rules.json? (should be for domain skills)
1. Is UserPromptSubmit detecting it? (check hook output for skill name)
1. Is AI analysis marking it as CRITICAL (>0.65 confidence)?
1. Already injected this conversation? (check state file)

### Skill injecting when it shouldn't

**Check:**

1. Should it be in `META_SKILLS` array? (is it truly passive awareness?)
1. Are triggers too broad? (refine keywords/patterns)
1. Is it really domain guidance or meta-awareness?

## Implementation Files

**Hook files:**

- `.claude/hooks/lib/intent-analyzer.ts` - AI-powered skill detection and intent analysis

**Configuration:**

- `.claude/skills/skill-rules.json` - Skill trigger definitions (keywords, descriptions)
- `.claude/settings.json` - Hook registration
