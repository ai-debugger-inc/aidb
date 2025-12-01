# Trigger Types - Complete Guide

Complete reference for configuring skill triggers in Claude Code's skill auto-activation system.

______________________________________________________________________

## Keyword Triggers (Explicit)

### How It Works

Case-insensitive substring matching in user's prompt. Used as a **fallback** when AI-powered intent analysis doesn't provide confident results (e.g., prompts shorter than 10 words).

### Use For

Topic-based activation where user explicitly mentions the subject.

### Configuration

```json
"promptTriggers": {
  "keywords": ["layout", "grid", "toolbar", "submission"]
}
```

### Example

- User prompt: "how does the **layout** system work?"
- Matches: "layout" keyword
- Activates: `project-catalog-developer`

### Best Practices

- Use specific, unambiguous terms
- Include common variations ("layout", "layout system", "grid layout")
- Avoid overly generic words ("system", "work", "create")
- Test with real prompts
- Keywords are primarily a fallback - AI intent analysis is the primary detection mechanism

______________________________________________________________________

## AI-Powered Intent Analysis (Primary)

### How It Works

The primary skill detection mechanism uses Claude API (defaults to Haiku 4.5, configurable via CLAUDE_SKILLS_MODEL) to analyze user prompts and match them against skill descriptions. This replaces regex-based intent pattern matching.

### Configuration

Skills are detected based on their `description` field:

```json
{
  "adapter-development": {
    "description": "Guide for AIDB adapter development covering component-based design, resource management, and DAP integration patterns",
    "promptTriggers": {
      "keywords": ["adapter", "debugpy", "launch orchestration"]
    }
  }
}
```

### How It Works

1. User submits a prompt
1. UserPromptSubmit hook sends prompt to Claude API with all skill descriptions
1. AI returns confidence scores for each skill
1. Skills above confidence threshold are automatically injected
1. If prompt is very short (\<10 words), keyword matching is used as fallback

### Best Practices

- Write clear, descriptive `description` fields that explain when the skill should be used
- Include domain-specific terminology in descriptions
- Keep descriptions focused on the skill's purpose
- Keywords serve as backup for very short prompts

______________________________________________________________________

## Testing Your Triggers

**Test keyword/intent triggers:**

```bash
echo '{"session_id":"test","prompt":"your test prompt"}' | \
  npx tsx .claude/hooks/skill-activation-prompt.ts
```

This will show which skills the system detects for your test prompt.

______________________________________________________________________

## What's NOT Implemented

The following trigger types are **not implemented** and should not be used:

### ❌ Intent Pattern Triggers (Regex)

- `intentPatterns` arrays in skill-rules.json
- Replaced by AI-powered intent analysis

### ❌ File Path Triggers

- `fileTriggers.pathPatterns`
- `fileTriggers.pathExclusions`
- No PreToolUse hook exists to process these

### ❌ Content Pattern Triggers

- `fileTriggers.contentPatterns`
- `fileTriggers.createOnly`
- No PreToolUse hook exists to process these

These fields may exist in older documentation or examples but are not read by the current implementation.

______________________________________________________________________

**Related Files:**

- [SKILL.md](../SKILL.md) - Main skill guide
- [skill-rules-reference.md](skill-rules-reference.md) - Complete skill-rules.json schema
- [hook-mechanisms.md](hook-mechanisms.md) - Hook system architecture
