import { describe, it, expect } from 'vitest';
import {
  filterUnacknowledgedSkills,
  applyInjectionLimits,
  filterAndPromoteSkills,
} from '../skill-filtration.js';
import type { SkillRule } from '../types.js';

/**
 * Tests for skill filtering and promotion logic
 *
 * Validates filtering of acknowledged skills, promotion to fill 2-skill target,
 * and integration with the acknowledgment system.
 */

describe('Skill Filtering', () => {
  describe('filterUnacknowledgedSkills', () => {
    it('should filter out already acknowledged skills', () => {
      const skills = ['skill-a', 'skill-b', 'skill-c'];
      const acknowledged = ['skill-a', 'skill-b'];
      const skillRules: Record<string, SkillRule> = {
        'skill-a': { type: 'domain', enforcement: 'suggest', priority: 'high' },
        'skill-b': { type: 'domain', enforcement: 'suggest', priority: 'high' },
        'skill-c': { type: 'domain', enforcement: 'suggest', priority: 'high' },
      };

      const unacknowledged = filterUnacknowledgedSkills(skills, acknowledged, skillRules);

      expect(unacknowledged).toEqual(['skill-c']);
    });

    it('should filter out skills with autoInject: false', () => {
      const skills = ['skill-a', 'skill-b', 'skill-c'];
      const acknowledged: string[] = [];
      const skillRules: Record<string, SkillRule> = {
        'skill-a': { type: 'domain', enforcement: 'suggest', priority: 'high' },
        'skill-b': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          autoInject: false,
        },
        'skill-c': { type: 'domain', enforcement: 'suggest', priority: 'high' },
      };

      const unacknowledged = filterUnacknowledgedSkills(skills, acknowledged, skillRules);

      expect(unacknowledged).toEqual(['skill-a', 'skill-c']);
    });
  });

  describe('applyInjectionLimits', () => {
    it('should inject up to 2 critical skills when acknowledgedCriticalCount = 0', () => {
      const critical = ['skill-a', 'skill-b', 'skill-c'];
      const recommended: string[] = [];
      const acknowledgedCriticalCount = 0; // No critical skills loaded yet

      const { toInject } = applyInjectionLimits(critical, recommended, acknowledgedCriticalCount);

      expect(toInject).toHaveLength(2);
      expect(toInject).toEqual(['skill-a', 'skill-b']);
    });

    it('should promote recommended skills to fill empty slots', () => {
      const critical = ['skill-a']; // 1 critical
      const recommended = ['skill-b', 'skill-c', 'skill-d'];
      const acknowledgedCriticalCount = 0;

      const { toInject, promoted } = applyInjectionLimits(
        critical,
        recommended,
        acknowledgedCriticalCount
      );

      // Should inject 1 critical + 1 promoted = 2 total
      expect(toInject).toHaveLength(2);
      expect(toInject).toEqual(['skill-a', 'skill-b']);
      expect(promoted).toEqual(['skill-b']);
    });

    it('should promote 2 recommended when no critical skills (target = 2)', () => {
      const critical: string[] = [];
      const recommended = ['skill-a', 'skill-b', 'skill-c'];
      const acknowledgedCriticalCount = 0;

      const { toInject, promoted } = applyInjectionLimits(
        critical,
        recommended,
        acknowledgedCriticalCount
      );

      // Should promote 2 recommended to reach target
      expect(toInject).toHaveLength(2);
      expect(toInject).toEqual(['skill-a', 'skill-b']);
      expect(promoted).toEqual(['skill-a', 'skill-b']);
    });

    it('should reduce target when critical skills already acknowledged', () => {
      const critical = ['skill-a']; // 1 unacknowledged critical
      const recommended = ['skill-b', 'skill-c'];
      const acknowledgedCriticalCount = 1; // 1 critical already loaded

      // Target = 2 - 1 = 1 slot available
      const { toInject, promoted } = applyInjectionLimits(
        critical,
        recommended,
        acknowledgedCriticalCount
      );

      // Should inject only 1 skill (target = 1)
      expect(toInject).toHaveLength(1);
      expect(toInject).toEqual(['skill-a']);
      expect(promoted).toEqual([]);
    });

    it('should inject 0 skills when 2 critical skills already acknowledged', () => {
      const critical: string[] = []; // No unacknowledged critical
      const recommended = ['skill-a', 'skill-b'];
      const acknowledgedCriticalCount = 2; // 2 critical already loaded (target met)

      // Target = 2 - 2 = 0 slots available
      const { toInject, promoted } = applyInjectionLimits(
        critical,
        recommended,
        acknowledgedCriticalCount
      );

      expect(toInject).toEqual([]);
      expect(promoted).toEqual([]);
    });

    it('should separate promoted from remaining recommended skills', () => {
      const critical = ['skill-a'];
      const recommended = ['skill-b', 'skill-c', 'skill-d', 'skill-e'];
      const acknowledgedCriticalCount = 0;

      const { toInject, promoted, remainingSuggested } = applyInjectionLimits(
        critical,
        recommended,
        acknowledgedCriticalCount
      );

      expect(toInject).toEqual(['skill-a', 'skill-b']);
      expect(promoted).toEqual(['skill-b']);
      expect(remainingSuggested).toEqual(['skill-c', 'skill-d', 'skill-e']);
    });
  });

  describe('filterAndPromoteSkills (Integration)', () => {
    it('should filter + promote when 1 critical already loaded', () => {
      const requiredSkills = ['critical-a', 'critical-b']; // critical-b already loaded
      const suggestedSkills = ['suggested-a', 'suggested-b'];
      const acknowledged = ['critical-b'];
      const skillRules: Record<string, SkillRule> = {
        'critical-a': { type: 'domain', enforcement: 'suggest', priority: 'high' },
        'critical-b': { type: 'domain', enforcement: 'suggest', priority: 'high' },
        'suggested-a': { type: 'domain', enforcement: 'suggest', priority: 'high' },
        'suggested-b': { type: 'domain', enforcement: 'suggest', priority: 'high' },
      };

      const result = filterAndPromoteSkills(
        requiredSkills,
        suggestedSkills,
        acknowledged,
        skillRules
      );

      // Target = 2 - 1 (acknowledged critical) = 1 slot
      // Should inject critical-a only (fills the 1 slot)
      expect(result.toInject).toEqual(['critical-a']);
      expect(result.promoted).toEqual([]);
      expect(result.remainingSuggested).toEqual(['suggested-a', 'suggested-b']);
    });

    it('should promote when all critical skills already loaded', () => {
      const requiredSkills = ['critical-a', 'critical-b']; // Both already loaded
      const suggestedSkills = ['suggested-a', 'suggested-b', 'suggested-c'];
      const acknowledged = ['critical-a', 'critical-b'];
      const skillRules: Record<string, SkillRule> = {
        'critical-a': { type: 'domain', enforcement: 'suggest', priority: 'high' },
        'critical-b': { type: 'domain', enforcement: 'suggest', priority: 'high' },
        'suggested-a': { type: 'domain', enforcement: 'suggest', priority: 'high' },
        'suggested-b': { type: 'domain', enforcement: 'suggest', priority: 'high' },
        'suggested-c': { type: 'domain', enforcement: 'suggest', priority: 'high' },
      };

      const result = filterAndPromoteSkills(
        requiredSkills,
        suggestedSkills,
        acknowledged,
        skillRules
      );

      // Target = 2 - 2 (acknowledged) = 0 slots
      // Should inject nothing (target met)
      expect(result.toInject).toEqual([]);
      expect(result.promoted).toEqual([]);
      expect(result.remainingSuggested).toEqual(['suggested-a', 'suggested-b', 'suggested-c']);
    });

    it('should promote 2 suggested when no critical skills', () => {
      const requiredSkills: string[] = [];
      const suggestedSkills = ['suggested-a', 'suggested-b', 'suggested-c'];
      const acknowledged: string[] = [];
      const skillRules: Record<string, SkillRule> = {
        'suggested-a': { type: 'domain', enforcement: 'suggest', priority: 'high' },
        'suggested-b': { type: 'domain', enforcement: 'suggest', priority: 'high' },
        'suggested-c': { type: 'domain', enforcement: 'suggest', priority: 'high' },
      };

      const result = filterAndPromoteSkills(
        requiredSkills,
        suggestedSkills,
        acknowledged,
        skillRules
      );

      // Target = 2, no critical → promote 2 suggested
      expect(result.toInject).toEqual(['suggested-a', 'suggested-b']);
      expect(result.promoted).toEqual(['suggested-a', 'suggested-b']);
      expect(result.remainingSuggested).toEqual(['suggested-c']);
    });

    it('should handle skills with autoInject: false correctly', () => {
      const requiredSkills = ['critical-a'];
      const suggestedSkills = ['suggested-a', 'suggested-b'];
      const acknowledged: string[] = [];
      const skillRules: Record<string, SkillRule> = {
        'critical-a': { type: 'domain', enforcement: 'suggest', priority: 'high' },
        'suggested-a': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          autoInject: false, // Manual load only
        },
        'suggested-b': { type: 'domain', enforcement: 'suggest', priority: 'high' },
      };

      const result = filterAndPromoteSkills(
        requiredSkills,
        suggestedSkills,
        acknowledged,
        skillRules
      );

      // Should skip suggested-a (autoInject: false) and promote suggested-b
      expect(result.toInject).toEqual(['critical-a', 'suggested-b']);
      expect(result.promoted).toEqual(['suggested-b']);
      expect(result.remainingSuggested).toEqual([]);
    });
  });
});
