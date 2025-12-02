# Skill Creation Guide

Step-by-step guide for creating new skills in the Claude Code skills system.

## Quick Start Process

**5 steps to create a skill:**

1. Create SKILL.md with frontmatter
1. Add to skill-rules.json
1. Test triggers
1. Refine patterns
1. Keep under 500 lines

## Step 1: Create Skill File

### File Location

`.claude/skills/{skill-name}/SKILL.md`

**Naming conventions:**

- Lowercase only
- Use hyphens for spaces
- Gerund form preferred (verb + -ing): `testing-strategy`, `adapter-development`
- Descriptive and specific: `mcp-tools-development` not just `mcp`

### YAML Frontmatter Template

Every skill file must start with YAML frontmatter:

```markdown
---
name: my-new-skill
description: Brief description including keywords that trigger this skill. Mention topics, file types, and use cases. Be explicit about trigger terms.
---
```

**Description field:**

- Maximum 1024 characters
- Include ALL trigger keywords
- Mention file types if applicable
- List use cases and scenarios
- Be explicit about domain coverage

**Example:**

```yaml
---
name: adapter-development
description: Comprehensive guide for developing and modifying AIDB debug adapters (Python/JavaScript/Java). Use when working with adapter architecture, DAP protocol implementation, language-specific adapter code, JDTLS integration, debugpy/vscode-js-debug configuration, or troubleshooting adapter issues. Covers component-based design, process management, port allocation, and adapter lifecycle.
---
```

### Content Structure Template

```markdown
# My New Skill

## Purpose
What this skill helps with (1-2 sentences)

## When to Use
Specific scenarios and conditions:
- Scenario 1
- Scenario 2
- Scenario 3

## Related Skills
Links to complementary skills

## Key Information
The actual guidance, patterns, examples

## Resources
Links to resource files for deep dives
```

### Best Practices

**Content organization:**

- ✅ Clear, descriptive section headings
- ✅ Bullet lists for scannability
- ✅ Code blocks with syntax highlighting
- ✅ Real examples from the codebase
- ✅ Progressive disclosure (summary → details in resources)

**Line count:**

- ✅ Target: Under 500 lines
- ✅ Extract detailed content to `resources/` subdirectory
- ✅ Use concise summaries, link to resource files
- ✅ Remove redundancy and wordiness

**Forbidden:**

- ❌ Table of contents (agents don't need them)
- ❌ Line number references (change too frequently)
- ❌ Heading navigation links (agents scan natively)

## Step 2: Add to skill-rules.json

### File Location

`.claude/skills/skill-rules.json`

### Basic Template

```json
{
  "my-new-skill": {
    "type": "domain",
    "enforcement": "suggest",
    "priority": "medium",
    "promptTriggers": {
      "keywords": ["keyword1", "keyword2", "keyword3"]
    }
  }
}
```

### Field Explanations

**type:** (required)

- `"domain"` - Most skills (actionable guidance)
- `"guardrail"` - Critical prevention (rare)

**enforcement:** (required)

- `"suggest"` - Advisory (most common)
- `"block"` - Critical only (rare)
- `"warn"` - Low priority (rarely used)

**priority:** (required)

- `"critical"` - Must-have guidance
- `"high"` - Strongly recommended
- `"medium"` - Helpful but optional
- `"low"` - Nice to have

**affinity:** (optional)

Array of skill names (max 2) that work well together and should be auto-injected bidirectionally.

**Use when:** Skills are frequently needed together (e.g., adapter-development + dap-protocol-guide).
**Effect:** When a skill is injected, its affinity skills are also auto-injected (free of slot cost).

**promptTriggers:** (optional but recommended)

- `keywords` - Explicit terms (case-insensitive)

Skill activation uses AI-powered intent analysis via the `description` field in **skill-rules.json**, which is more reliable than keyword matching alone. See "Note on Description Fields" below for clarification.

### Complete Example

```json
{
  "adapter-development": {
    "type": "domain",
    "enforcement": "suggest",
    "priority": "high",
    "affinity": ["dap-protocol-guide", "mcp-tools-development"],
    "promptTriggers": {
      "keywords": [
        "adapter",
        "debug adapter",
        "DAP",
        "debugpy",
        "vscode-js-debug",
        "JDTLS",
        "process manager",
        "port manager"
      ]
    }
  }
}
```

## Step 3: Test Triggers

### Test UserPromptSubmit Hook

Tests if your skill is detected for a given prompt:

```bash
echo '{"session_id":"test","prompt":"your test prompt here"}' | \
  npx tsx .claude/hooks/skill-activation-prompt.ts
```

**Example:**

```bash
echo '{"session_id":"test","prompt":"Fix the Java adapter"}' | \
  npx tsx .claude/hooks/skill-activation-prompt.ts
```

**Expected output:**

```
🎯 SKILL ACTIVATION CHECK

📚 RECOMMENDED SKILLS:
  → adapter-development
```

### Testing Checklist

Test keyword triggers:

- [ ] Keyword triggers (test multiple keywords individually)
- [ ] Case variations (keywords are case-insensitive)
- [ ] Partial matches (do keywords work as expected?)

Test AI-powered intent analysis:

- [ ] Description field accurately describes skill purpose
- [ ] Skill activates on related but non-identical prompts
- [ ] Related but unrelated prompts don't trigger (false positive check)

## Step 4: Refine Patterns

Based on testing results, iterate:

### Add Missing Keywords

If skill should trigger but doesn't:

```json
"keywords": [
  "original keyword",
  "synonym1",
  "synonym2",
  "common abbreviation"
]
```

### Reduce False Positives

If skill triggers when it shouldn't:

Make keywords more specific:

```json
// Too broad
"keywords": ["test"]

// More specific
"keywords": ["E2E test", "integration test", "test framework"]
```

Ensure the `description` field in **skill-rules.json** clearly defines scope to help AI-powered intent analysis. (The frontmatter description is human documentation only.)

### Balance Coverage vs Precision

**Goal:** Trigger on relevant prompts, ignore unrelated ones

**Metrics:**

- True positives: Triggers when skill is helpful ✅
- False positives: Triggers when skill isn't needed ❌
- False negatives: Doesn't trigger when skill would help ❌

**Iterate until:** High true positive rate, low false positive rate

## Step 5: Follow Best Practices

### Keep Under 500 Lines

**Check line count:**

```bash
wc -l .claude/skills/my-new-skill/SKILL.md
```

**If over 500:**

1. Extract detailed examples → `resources/EXAMPLES.md`
1. Create topic-specific resources → `resources/SPECIFIC_TOPIC.md`
1. Keep only essential summary in main SKILL.md

### Use Progressive Disclosure

**Main SKILL.md:**

- High-level overview
- When to use this skill
- Quick reference
- Links to resource files

**Resource files:**

- Detailed examples
- Deep-dive explanations
- Advanced topics
- Troubleshooting guides

**Example:**

```markdown
## Key Concepts

Brief explanation of concept (2-3 sentences).

For complete details, see the resource file for this topic.
```

### Test with Real Scenarios

**Before writing extensive documentation:**

1. Use skill with 3+ real tasks
1. Identify what information is actually needed
1. Note what's missing or unclear
1. Iterate based on actual usage

**Don't:** Write comprehensive docs first, then realize they're not helpful

**Do:** Test with real scenarios, then document what works

### Validate Schema

Check skill-rules.json syntax:

```bash
cat .claude/skills/skill-rules.json | python -m json.tool > /dev/null
```

## Skill Types: When to Use Each

### Domain Skills (Most Common)

**Use when:**

- Providing technical guidance for specific area
- Documenting architectural patterns
- Explaining how to use a system
- Best practices for a technology

**Examples:**

- `adapter-development`
- `testing-strategy`
- `mcp-tools-development`

**Configuration:**

```json
{
  "type": "domain",
  "enforcement": "suggest"
}
```

### Guardrail Skills (Rare)

**Use when:**

- Preventing critical errors (via comprehensive guidance)
- Enforcing data integrity (via validation patterns)
- Warning about dangerous operations (via highlighted cautions)
- Compatibility requirements (via compatibility checklists)

**Examples:**

- `database-verification` (prevent wrong column names)
- `api-versioning` (prevent breaking changes)

**Configuration:**

```json
{
  "type": "guardrail",
  "enforcement": "block",
  "priority": "critical"
}
```

**High bar:** Only create guardrails for errors that:

- Cause runtime failures
- Corrupt data
- Break critical workflows
- Can't be easily fixed after the fact

## Common Mistakes

### Important: Understanding Description Fields

**CRITICAL CLARIFICATION** - Two different description fields serve different purposes:

- **YAML frontmatter `description`** (in SKILL.md) - Human documentation only. Not used by the AI detection system. Include it for reference, but it's NOT what triggers skill activation.
- **skill-rules.json `description`** - Read by the AI for intent analysis. This is what actually matters for skill activation. Use comprehensive language covering all topics, keywords, and use cases.

**Example:**

```yaml
# In SKILL.md frontmatter (human docs)
---
name: testing-strategy
description: Guide for testing
---
```

```json
// In skill-rules.json (AI reads this)
{
  "testing-strategy": {
    "type": "domain",
    "description": "Comprehensive guide for implementing AIDB tests following E2E-first philosophy, DebugInterface abstraction, MCP response health standards. Use when writing unit tests, integration tests, E2E tests, test fixtures, fixtures, or test documentation."
  }
}
```

Both should exist but they serve different purposes. Don't confuse which one the AI reads.

### Mistake 1: Too Many Keywords

**Problem:**

```json
"keywords": [
  "test", "tests", "testing", "tester", "testable",
  "spec", "specs", "specification", "specifications",
  // ... 50 more keywords
]
```

**Solution:** Be selective, use representative terms:

```json
"keywords": ["test", "E2E", "integration test", "test framework"]
```

### Mistake 2: Unclear Description Field

**Problem:**

```yaml
description: Skill for testing
```

**Solution:** Make description detailed and include all major topics:

```yaml
description: Guide for implementing AIDB tests following E2E-first philosophy, DebugInterface abstraction, and MCP response health standards. Use when writing unit tests, integration tests, E2E tests, test fixtures, or test documentation.
```

### Mistake 3: Not Testing Edge Cases

**Problem:** Only test happy path

**Solution:** Test variations:

- Different phrasings of the same concept
- Related but unrelated prompts (false positive check)
- Case variations (keywords are case-insensitive)
- Make sure description captures skill scope

### Mistake 4: Kitchen Sink Documentation

**Problem:** Put everything in main SKILL.md → 800+ lines

**Solution:** Progressive disclosure:

- Main file: < 500 lines, essentials only
- Resource files: Detailed deep dives
- Clear navigation between files

### Mistake 5: Forgetting to Update Description

**Problem:** Add keywords to skill-rules.json, forget to update SKILL.md description

**Solution:** Keep description and keywords in sync:

- `description` field in skill-rules.json covers all major topics
- `keywords` in skill-rules.json reflect description content
- Update both when adding new coverage
- YAML frontmatter description is for human reference only

## Skill Maintenance

### When to Update Skills

**Trigger updates when:**

- New modules/directories added → May need to update `description` if covering new areas
- New terminology introduced → Add `keywords`
- New docs created → Link in resources
- Skill drift detected → Refactor content
- Description becomes inaccurate → Update to reflect current scope

### Automated Checks

**Pre-commit hook:**

- Validates skill reference links
- Suggests new patterns for new code
- Catches broken resource links

**Manual checks:**

- `/wrap` command checklist
- Line count monitoring
- Test trigger accuracy

### Refactoring

**Signs skill needs refactoring:**

- Approaching 500 lines
- Becoming too broad (many unrelated topics)
- Low trigger accuracy (false positives/negatives)
- Outdated examples or patterns

**Refactoring strategies:**

- Split into multiple focused skills
- Extract content to resource files
- Tighten trigger conditions
- Update examples to current code

## Quick Reference

**File locations:**

- Skill content: `.claude/skills/{name}/SKILL.md`
- Configuration: `.claude/skills/skill-rules.json`
- Resources: `.claude/skills/{name}/resources/*.md`

**Testing commands:**

```bash
# Test detection
echo '{"session_id":"test","prompt":"test prompt"}' | \
  npx tsx .claude/hooks/skill-activation-prompt.ts

# Check line count
wc -l .claude/skills/{name}/SKILL.md

# Validate JSON
cat .claude/skills/skill-rules.json | python -m json.tool
```

**Skill Activation Mechanism:**

- UserPromptSubmit hook analyzes prompts using AI-powered intent analysis
- Matches against keywords and skill description
- Auto-injects relevant skills into conversation context
- Session tracking prevents duplicate skill injection

**Remember:**

- Keep main file < 500 lines
- Write comprehensive descriptions in **skill-rules.json** (this is read by the AI)
- YAML frontmatter descriptions are for human documentation
- Use keyword matching as a fallback to AI intent analysis
- Test with real scenarios first
- Use progressive disclosure
- Iterate based on usage
