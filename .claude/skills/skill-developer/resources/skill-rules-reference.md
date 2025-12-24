# skill-rules.json - Complete Reference

Complete schema and configuration reference for `.claude/skills/skill-rules.json`.

______________________________________________________________________

## File Location

**Path:** `.claude/skills/skill-rules.json`

This JSON file defines all skills and their trigger conditions for the auto-activation system.

______________________________________________________________________

## Complete TypeScript Schema

```typescript
interface SkillRules {
    version: string;
    skills: Record<string, SkillRule>;
}

interface SkillRule {
    type: 'guardrail' | 'domain';
    description?: string;       // Sent to AI for intent analysis
    autoInject?: boolean;       // Allow automatic injection (default: true)
    requiredSkills?: string[];  // Dependencies that must be loaded first
    injectionOrder?: number;    // Sort order for injection
    promptTriggers?: {
        keywords?: string[];
    };
    affinity?: string[];        // Bidirectional complementary skills (max 2)
}
```

______________________________________________________________________

## Field Guide

### Top Level

| Field     | Type   | Required | Description                      |
| --------- | ------ | -------- | -------------------------------- |
| `version` | string | Yes      | Schema version (currently "1.0") |
| `skills`  | object | Yes      | Map of skill name → SkillRule    |

### SkillRule Fields

| Field            | Type     | Required | Description                                                          |
| ---------------- | -------- | -------- | -------------------------------------------------------------------- |
| `type`           | string   | Yes      | "guardrail" or "domain" (categorization only)                        |
| `description`    | string   | Optional | Sent to AI for intent analysis (recommended for all skills)          |
| `autoInject`     | boolean  | Optional | Allow automatic injection (default: true, set false for meta-skills) |
| `requiredSkills` | string[] | Optional | Dependencies that must be loaded first                               |
| `injectionOrder` | number   | Optional | Sort order for injection                                             |
| `promptTriggers` | object   | Optional | Keyword triggers for fallback detection                              |
| `affinity`       | string[] | Optional | Complementary skills (auto-inject bidirectionally, max 2)            |

### promptTriggers Fields

| Field      | Type     | Required | Description                                |
| ---------- | -------- | -------- | ------------------------------------------ |
| `keywords` | string[] | Optional | Exact substring matches (case-insensitive) |

### affinity Field

| Field      | Type     | Required | Description                                                     |
| ---------- | -------- | -------- | --------------------------------------------------------------- |
| `affinity` | string[] | Optional | Bidirectional complementary skills (auto-injected, max 2 items) |

**How it works (Bidirectional Auto-Injection):**

- Standard injection limit: 2 skills maximum (critical or promoted)
- Affinity skills auto-inject **bidirectionally** at **no slot cost** (don't count toward 2-skill limit)
- **Direction 1 (Parent→Child):** If skill A is injected and lists `affinity: ["B", "C"]`, both B and C auto-inject
- **Direction 2 (Child→Parent):** If skill A is injected and skill B lists `affinity: ["A"]`, skill B auto-injects
- Affinities respect session state: won't re-inject already-loaded skills
- Max 2 affinities per skill (rare; most have 0-1)

**Example:**

```json
{
  "adapter-development": {
    "affinity": ["aidb-architecture", "dap-protocol-guide"]
  },
  "dap-protocol-guide": {
    "affinity": ["aidb-architecture"]
  },
  "mcp-tools-development": {
    "affinity": ["aidb-architecture"]
  },
  "aidb-architecture": {
    // Root skill - no affinities
  }
}
```

**Scenario:** User asks "Fix the Java adapter"

- AI detects: `adapter-development` (critical)
- System injects: `adapter-development` (1 critical, counts toward limit)
- Affinity triggers: `aidb-architecture` + `dap-protocol-guide` (2 affinity, free)
- **Total: 3 skills injected** (1 critical + 2 affinity)

______________________________________________________________________

## Example: Domain Skill

Complete example of a domain skill with auto-injection:

```json
{
  "adapter-development": {
    "type": "domain",
    "autoInject": true,
    "requiredSkills": [],
    "affinity": ["aidb-architecture", "dap-protocol-guide"],
    "description": "Guide for AIDB adapter development covering component-based design, resource management, and DAP integration patterns",
    "promptTriggers": {
      "keywords": [
        "adapter",
        "debugpy",
        "vscode-js-debug",
        "java-debug",
        "JDT",
        "JDT LS",
        "launch orchestration",
        "process manager",
        "port manager"
      ]
    }
  }
}
```

### Key Points for Domain Skills

1. **type**: "domain" (categorization for organization)
1. **autoInject**: Set to true to allow automatic injection
1. **description**: Sent to AI for intent analysis (include relevant keywords)
1. **promptTriggers**: Keywords for fallback matching when AI analysis unavailable
1. **affinity**: Optional complementary skills that auto-inject together

______________________________________________________________________

## Validation

### Check JSON Syntax

```bash
cat .claude/skills/skill-rules.json | jq .
```

If valid, jq will pretty-print the JSON. If invalid, it will show the error.

### Common JSON Errors

**Trailing comma:**

```json
{
  "keywords": ["one", "two",]  // ❌ Trailing comma
}
```

**Missing quotes:**

```json
{
  type: "guardrail"  // ❌ Missing quotes on key
}
```

**Single quotes (invalid JSON):**

```json
{
  'type': 'guardrail'  // ❌ Must use double quotes
}
```

### Validation Checklist

- [ ] JSON syntax valid (use `jq`)
- [ ] All skill names match SKILL.md filenames
- [ ] Description field is clear and concise
- [ ] Keywords are specific to the skill domain
- [ ] Affinity skills actually exist in skill-rules.json
- [ ] Required skills actually exist in skill-rules.json
- [ ] No duplicate skill names
- [ ] Meta-skills have `autoInject: false`
- [ ] Domain skills have `autoInject: true`

______________________________________________________________________

**Related Files:**

- [SKILL.md](../SKILL.md) - Main skill guide
- [trigger-types.md](trigger-types.md) - Complete trigger documentation
