import { describe, it, expect } from "vitest";
import { SHORT_PROMPT_WORD_THRESHOLD } from "../constants";

/**
 * Tests for keyword fallback logic
 *
 * Mirrors the algorithm in intent-analyzer.ts lines 314-329
 */

interface PromptTriggers {
  keywords?: string[];
}

interface SkillConfig {
  promptTriggers?: PromptTriggers;
}

/**
 * Fallback skill detection using simple keyword matching
 * (Mirrors intent-analyzer.ts lines 314-329)
 */
function fallbackToKeywords(
  prompt: string,
  skills: Record<string, SkillConfig>
): { required: string[]; suggested: string[] } {
  const promptLower = prompt.toLowerCase();
  const detected: string[] = [];

  for (const [name, config] of Object.entries(skills)) {
    const keywords = config.promptTriggers?.keywords || [];
    if (keywords.some((kw: string) => promptLower.includes(kw.toLowerCase()))) {
      detected.push(name);
    }
  }

  return { required: detected, suggested: [] };
}

/**
 * Check if prompt should use keyword fallback
 */
function shouldUseKeywordFallback(prompt: string): boolean {
  const wordCount = prompt.trim().split(/\s+/).length;
  return wordCount <= SHORT_PROMPT_WORD_THRESHOLD;
}

describe("Keyword Fallback Logic", () => {
  it("should use keyword matching for short prompts", () => {
    const shortPrompt = "fix adapter bug"; // 3 words < threshold

    const shouldUse = shouldUseKeywordFallback(shortPrompt);

    expect(shouldUse).toBe(true);
  });

  it("should NOT use keyword matching for long prompts", () => {
    const longPrompt =
      "Please help me fix the adapter bug that is causing issues with the DAP protocol";

    const shouldUse = shouldUseKeywordFallback(longPrompt);

    expect(shouldUse).toBe(false);
  });

  it("should perform case-insensitive keyword matching", () => {
    const prompt = "FIX THE ADAPTER BUG";
    const skills = {
      "adapter-development": {
        promptTriggers: {
          keywords: ["adapter", "debug adapter"]
        }
      }
    };

    const result = fallbackToKeywords(prompt, skills);

    expect(result.required).toContain("adapter-development");
  });

  it("should detect multiple keywords triggering same skill", () => {
    const prompt = "debug adapter issue";
    const skills = {
      "adapter-development": {
        promptTriggers: {
          keywords: ["adapter", "debug adapter", "DAP"]
        }
      }
    };

    const result = fallbackToKeywords(prompt, skills);

    // Both 'adapter' and 'debug adapter' match, but skill only added once
    expect(result.required).toEqual(["adapter-development"]);
  });

  it("should match partial keywords (substring includes)", () => {
    const prompt = "debugging adapters for Python";
    const skills = {
      "adapter-development": {
        promptTriggers: {
          keywords: ["adapter"]
        }
      }
    };

    const result = fallbackToKeywords(prompt, skills);

    // 'adapter' matches 'adapters' via includes()
    expect(result.required).toContain("adapter-development");
  });

  it("should return all detected skills as required (none as suggested)", () => {
    const prompt = "fix adapter and test";
    const skills = {
      "adapter-development": {
        promptTriggers: {
          keywords: ["adapter"]
        }
      },
      "testing-strategy": {
        promptTriggers: {
          keywords: ["test", "testing"]
        }
      }
    };

    const result = fallbackToKeywords(prompt, skills);

    expect(result.required).toHaveLength(2);
    expect(result.required).toContain("adapter-development");
    expect(result.required).toContain("testing-strategy");
    expect(result.suggested).toEqual([]); // Fallback always returns empty suggested
  });

  it("should return empty arrays when no keywords match", () => {
    const prompt = "completely unrelated topic";
    const skills = {
      "adapter-development": {
        promptTriggers: {
          keywords: ["adapter", "DAP"]
        }
      }
    };

    const result = fallbackToKeywords(prompt, skills);

    expect(result.required).toEqual([]);
    expect(result.suggested).toEqual([]);
  });

  it("should handle skills with empty keywords array", () => {
    const prompt = "test prompt";
    const skills = {
      "skill-without-keywords": {
        promptTriggers: {
          keywords: []
        }
      }
    };

    const result = fallbackToKeywords(prompt, skills);

    expect(result.required).toEqual([]);
  });
});
