import { describe, it, expect } from "vitest";
import {
  filterUnacknowledgedSkills,
  applyInjectionLimits,
  filterAndPromoteSkills
} from "../skill-filtration.js";
import type { SkillRule } from "../types.js";

/**
 * Tests for skill filtering and promotion logic
 *
 * Validates filtering of acknowledged skills, promotion to fill 2-skill target,
 * and integration with the acknowledgment system.
 */

describe("Skill Filtering", () => {
  describe("filterUnacknowledgedSkills", () => {
    it("should filter out already acknowledged skills", () => {
      const skills = ["skill-a", "skill-b", "skill-c"];
      const acknowledged = ["skill-a", "skill-b"];

      const unacknowledged = filterUnacknowledgedSkills(skills, acknowledged);

      expect(unacknowledged).toEqual(["skill-c"]);
    });

    it("should return all skills when none acknowledged", () => {
      const skills = ["skill-a", "skill-b", "skill-c"];
      const acknowledged: string[] = [];

      const unacknowledged = filterUnacknowledgedSkills(skills, acknowledged);

      expect(unacknowledged).toEqual(["skill-a", "skill-b", "skill-c"]);
    });
  });

  describe("applyInjectionLimits", () => {
    // All domain skills for basic limit tests
    const domainRules: Record<string, SkillRule> = {
      "skill-a": { type: "domain" },
      "skill-b": { type: "domain" },
      "skill-c": { type: "domain" },
      "skill-d": { type: "domain" },
      "skill-e": { type: "domain" }
    };

    it("should inject up to 2 domain skills when acknowledgedCriticalCount = 0", () => {
      const critical = ["skill-a", "skill-b", "skill-c"];
      const recommended: string[] = [];
      const acknowledgedCriticalCount = 0;

      const { toInject } = applyInjectionLimits(
        critical,
        recommended,
        acknowledgedCriticalCount,
        domainRules
      );

      expect(toInject).toHaveLength(2);
      expect(toInject).toEqual(["skill-a", "skill-b"]);
    });

    it("should promote recommended skills to fill empty slots", () => {
      const critical = ["skill-a"];
      const recommended = ["skill-b", "skill-c", "skill-d"];
      const acknowledgedCriticalCount = 0;

      const { toInject, promoted } = applyInjectionLimits(
        critical,
        recommended,
        acknowledgedCriticalCount,
        domainRules
      );

      expect(toInject).toHaveLength(2);
      expect(toInject).toEqual(["skill-a", "skill-b"]);
      expect(promoted).toEqual(["skill-b"]);
    });

    it("should promote 2 recommended when no critical skills (target = 2)", () => {
      const critical: string[] = [];
      const recommended = ["skill-a", "skill-b", "skill-c"];
      const acknowledgedCriticalCount = 0;

      const { toInject, promoted } = applyInjectionLimits(
        critical,
        recommended,
        acknowledgedCriticalCount,
        domainRules
      );

      expect(toInject).toHaveLength(2);
      expect(toInject).toEqual(["skill-a", "skill-b"]);
      expect(promoted).toEqual(["skill-a", "skill-b"]);
    });

    it("should reduce target when critical skills already acknowledged", () => {
      const critical = ["skill-a"];
      const recommended = ["skill-b", "skill-c"];
      const acknowledgedCriticalCount = 1;

      const { toInject, promoted } = applyInjectionLimits(
        critical,
        recommended,
        acknowledgedCriticalCount,
        domainRules
      );

      expect(toInject).toHaveLength(1);
      expect(toInject).toEqual(["skill-a"]);
      expect(promoted).toEqual([]);
    });

    it("should inject 0 domain skills when 2 already acknowledged", () => {
      const critical: string[] = [];
      const recommended = ["skill-a", "skill-b"];
      const acknowledgedCriticalCount = 2;

      const { toInject, promoted } = applyInjectionLimits(
        critical,
        recommended,
        acknowledgedCriticalCount,
        domainRules
      );

      expect(toInject).toEqual([]);
      expect(promoted).toEqual([]);
    });

    it("should separate promoted from remaining recommended skills", () => {
      const critical = ["skill-a"];
      const recommended = ["skill-b", "skill-c", "skill-d", "skill-e"];
      const acknowledgedCriticalCount = 0;

      const { toInject, promoted, remainingSuggested } = applyInjectionLimits(
        critical,
        recommended,
        acknowledgedCriticalCount,
        domainRules
      );

      expect(toInject).toEqual(["skill-a", "skill-b"]);
      expect(promoted).toEqual(["skill-b"]);
      expect(remainingSuggested).toEqual(["skill-c", "skill-d", "skill-e"]);
    });

    it("should always include guardrail skills exempt from 2-skill cap", () => {
      const mixedRules: Record<string, SkillRule> = {
        "guardrail-a": { type: "guardrail" },
        "domain-a": { type: "domain" },
        "domain-b": { type: "domain" },
        "domain-c": { type: "domain" }
      };

      const critical = ["guardrail-a", "domain-a", "domain-b", "domain-c"];
      const recommended: string[] = [];
      const acknowledgedCriticalCount = 0;

      const { toInject } = applyInjectionLimits(
        critical,
        recommended,
        acknowledgedCriticalCount,
        mixedRules
      );

      // Guardrail always included + 2 domain skills (cap)
      expect(toInject).toContain("guardrail-a");
      expect(toInject).toContain("domain-a");
      expect(toInject).toContain("domain-b");
      expect(toInject).not.toContain("domain-c");
      expect(toInject).toHaveLength(3);
    });
  });

  describe("filterAndPromoteSkills (Integration)", () => {
    it("should not count acknowledged guardrails toward domain slot reduction", () => {
      const requiredSkills = ["critical-a", "guardrail-a"];
      const suggestedSkills = ["suggested-a", "suggested-b"];
      const acknowledged = ["guardrail-a"]; // guardrail — doesn't reduce domain slots
      const skillRules: Record<string, SkillRule> = {
        "critical-a": { type: "domain" },
        "guardrail-a": { type: "guardrail" },
        "suggested-a": { type: "domain" },
        "suggested-b": { type: "domain" }
      };

      const result = filterAndPromoteSkills(
        requiredSkills,
        suggestedSkills,
        acknowledged,
        skillRules
      );

      // Target = 2 - 0 (guardrail doesn't count) = 2 domain slots
      // critical-a (critical) + suggested-a (promoted)
      expect(result.toInject).toEqual(["critical-a", "suggested-a"]);
      expect(result.promoted).toEqual(["suggested-a"]);
      expect(result.remainingSuggested).toEqual(["suggested-b"]);
    });

    it("should reduce slots only for acknowledged domain skills", () => {
      const requiredSkills = ["critical-a", "guardrail-a"];
      const suggestedSkills = ["suggested-a", "suggested-b"];
      const acknowledged = ["critical-a", "guardrail-a"]; // 1 domain + 1 guardrail
      const skillRules: Record<string, SkillRule> = {
        "critical-a": { type: "domain" },
        "guardrail-a": { type: "guardrail" },
        "suggested-a": { type: "domain" },
        "suggested-b": { type: "domain" }
      };

      const result = filterAndPromoteSkills(
        requiredSkills,
        suggestedSkills,
        acknowledged,
        skillRules
      );

      // Target = 2 - 1 (only domain critical-a counts) = 1 domain slot
      // suggested-a promoted to fill the 1 slot
      expect(result.toInject).toEqual(["suggested-a"]);
      expect(result.promoted).toEqual(["suggested-a"]);
      expect(result.remainingSuggested).toEqual(["suggested-b"]);
    });

    it("should promote 2 suggested domain skills and always include guardrails", () => {
      const requiredSkills: string[] = [];
      const suggestedSkills = ["suggested-a", "guardrail-a", "suggested-b"];
      const acknowledged: string[] = [];
      const skillRules: Record<string, SkillRule> = {
        "suggested-a": { type: "domain" },
        "guardrail-a": { type: "guardrail" },
        "suggested-b": { type: "domain" }
      };

      const result = filterAndPromoteSkills(
        requiredSkills,
        suggestedSkills,
        acknowledged,
        skillRules
      );

      // Guardrail (guardrail-a) always included + 2 domain promoted
      expect(result.toInject).toContain("guardrail-a");
      expect(result.toInject).toContain("suggested-a");
      expect(result.toInject).toContain("suggested-b");
      expect(result.toInject).toHaveLength(3);
      expect(result.promoted).toEqual(["suggested-a", "suggested-b"]);
      expect(result.remainingSuggested).toEqual([]);
    });

    it("should include all skills when AI scores them (autoInject: false no longer filters)", () => {
      const requiredSkills = ["critical-a"];
      const suggestedSkills = ["suggested-a", "suggested-b"];
      const acknowledged: string[] = [];
      const skillRules: Record<string, SkillRule> = {
        "critical-a": { type: "domain" },
        "suggested-a": {
          type: "domain",
          autoInject: false
        },
        "suggested-b": { type: "domain" }
      };

      const result = filterAndPromoteSkills(
        requiredSkills,
        suggestedSkills,
        acknowledged,
        skillRules
      );

      // autoInject: false no longer blocks AI-scored skills from injection
      // critical-a (critical) + suggested-a (promoted) fill 2 slots
      expect(result.toInject).toEqual(["critical-a", "suggested-a"]);
      expect(result.promoted).toEqual(["suggested-a"]);
      expect(result.remainingSuggested).toEqual(["suggested-b"]);
    });
  });
});
