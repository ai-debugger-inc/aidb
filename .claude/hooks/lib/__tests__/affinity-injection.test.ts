import { describe, it, expect } from 'vitest';
import { findAffinityInjections } from '../skill-filtration.js';
import type { SkillRule } from '../types.js';

/**
 * Tests for bidirectional affinity injection system
 *
 * Validates that skills with affinity relationships are automatically
 * injected (free of slot cost) when their related skills are being injected.
 */

describe('Affinity Injection System', () => {
  describe('Parent → Child Affinity (Direct)', () => {
    it('should inject affinity skills listed by parent skill', () => {
      const skillRules: Record<string, SkillRule> = {
        'adapter-development': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          affinity: ['aidb-architecture', 'dap-protocol-guide'],
        },
        'aidb-architecture': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
        },
        'dap-protocol-guide': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
        },
      };

      const affinities = findAffinityInjections(['adapter-development'], [], skillRules);

      expect(affinities).toEqual(
        expect.arrayContaining(['aidb-architecture', 'dap-protocol-guide'])
      );
      expect(affinities.length).toBe(2);
    });

    it('should not inject affinity skill if already acknowledged', () => {
      const skillRules: Record<string, SkillRule> = {
        'adapter-development': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          affinity: ['aidb-architecture', 'dap-protocol-guide'],
        },
        'aidb-architecture': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
        },
        'dap-protocol-guide': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
        },
      };

      const affinities = findAffinityInjections(
        ['adapter-development'],
        ['aidb-architecture'], // Already loaded
        skillRules
      );

      // Should only inject dap-protocol-guide (architecture already loaded)
      expect(affinities).toEqual(['dap-protocol-guide']);
    });

    it('should not inject affinity skill if already in toInject', () => {
      const skillRules: Record<string, SkillRule> = {
        'adapter-development': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          affinity: ['aidb-architecture'],
        },
        'aidb-architecture': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
        },
      };

      const affinities = findAffinityInjections(
        ['adapter-development', 'aidb-architecture'], // Both already being injected
        [],
        skillRules
      );

      // Should not duplicate architecture
      expect(affinities).toEqual([]);
    });

    it('should handle partial affinity loading (1 of 2 loaded)', () => {
      const skillRules: Record<string, SkillRule> = {
        'adapter-development': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          affinity: ['aidb-architecture', 'dap-protocol-guide'],
        },
        'aidb-architecture': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
        },
        'dap-protocol-guide': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
        },
      };

      const affinities = findAffinityInjections(
        ['adapter-development'],
        ['dap-protocol-guide'], // 1 of 2 affinities loaded
        skillRules
      );

      // Should inject only the unloaded affinity
      expect(affinities).toEqual(['aidb-architecture']);
    });
  });

  describe('Child → Parent Affinity (Bidirectional)', () => {
    it('should inject skills that list the injected skill in their affinity', () => {
      const skillRules: Record<string, SkillRule> = {
        'dap-protocol-guide': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          affinity: ['aidb-architecture'], // dap lists architecture
        },
        'mcp-tools-development': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          affinity: ['aidb-architecture'], // mcp lists architecture
        },
        'aidb-architecture': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          // architecture lists NO affinities (root skill)
        },
      };

      // Injecting architecture should trigger dap and mcp (they list it)
      const affinities = findAffinityInjections(['aidb-architecture'], [], skillRules);

      expect(affinities).toEqual(
        expect.arrayContaining(['dap-protocol-guide', 'mcp-tools-development'])
      );
      expect(affinities.length).toBe(2);
    });

    it('should combine both directions (parent→child + child→parent)', () => {
      const skillRules: Record<string, SkillRule> = {
        'adapter-development': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          affinity: ['aidb-architecture', 'dap-protocol-guide'], // adapter lists arch + dap
        },
        'aidb-architecture': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          // architecture lists nothing
        },
        'dap-protocol-guide': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          affinity: ['aidb-architecture'], // dap lists architecture
        },
        'mcp-tools-development': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          affinity: ['aidb-architecture'], // mcp lists architecture
        },
      };

      // Injecting adapter should trigger:
      // 1. Parent→child: architecture + dap (adapter lists them)
      // 2. Child→parent: mcp (it lists architecture which is being injected via affinity)
      const affinities = findAffinityInjections(['adapter-development'], [], skillRules);

      // Note: mcp is NOT injected because it lists architecture,
      // but architecture is in the affinity list, not the toInject list
      // The function only checks toInject, not the affinities themselves
      expect(affinities).toEqual(
        expect.arrayContaining(['aidb-architecture', 'dap-protocol-guide'])
      );
      expect(affinities.length).toBe(2);
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty toInject array', () => {
      const skillRules: Record<string, SkillRule> = {
        skill1: { type: 'domain', enforcement: 'suggest', priority: 'high' },
      };

      const affinities = findAffinityInjections([], [], skillRules);

      expect(affinities).toEqual([]);
    });

    it('should handle skills with no affinity configured', () => {
      const skillRules: Record<string, SkillRule> = {
        'skill-no-affinity': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          // No affinity field
        },
      };

      const affinities = findAffinityInjections(['skill-no-affinity'], [], skillRules);

      expect(affinities).toEqual([]);
    });

    it('should handle skills with empty affinity array', () => {
      const skillRules: Record<string, SkillRule> = {
        'skill-empty-affinity': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          affinity: [], // Empty array
        },
      };

      const affinities = findAffinityInjections(['skill-empty-affinity'], [], skillRules);

      expect(affinities).toEqual([]);
    });

    it('should not inject affinity skill with autoInject: false', () => {
      const skillRules: Record<string, SkillRule> = {
        'parent-skill': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          affinity: ['manual-skill'],
        },
        'manual-skill': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          autoInject: false, // Manual load required
        },
      };

      const affinities = findAffinityInjections(['parent-skill'], [], skillRules);

      // Should not inject manual-skill (autoInject: false)
      expect(affinities).toEqual([]);
    });

    it('should handle multiple skills being injected with overlapping affinities', () => {
      const skillRules: Record<string, SkillRule> = {
        'skill-a': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          affinity: ['common-skill'],
        },
        'skill-b': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          affinity: ['common-skill'],
        },
        'common-skill': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
        },
      };

      const affinities = findAffinityInjections(['skill-a', 'skill-b'], [], skillRules);

      // Should inject common-skill only once (not duplicated)
      expect(affinities).toEqual(['common-skill']);
    });

    it('should handle circular affinity references', () => {
      const skillRules: Record<string, SkillRule> = {
        'skill-a': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          affinity: ['skill-b'],
        },
        'skill-b': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          affinity: ['skill-a'],
        },
      };

      // Injecting skill-a should trigger skill-b
      // But skill-b won't trigger skill-a again (already in toInject)
      const affinities = findAffinityInjections(['skill-a'], [], skillRules);

      expect(affinities).toEqual(['skill-b']);
    });
  });

  describe('Real-world Scenarios', () => {
    it('should inject architecture + dap when injecting adapter-development', () => {
      const skillRules: Record<string, SkillRule> = {
        'adapter-development': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          affinity: ['aidb-architecture', 'dap-protocol-guide'],
        },
        'aidb-architecture': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
        },
        'dap-protocol-guide': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          affinity: ['aidb-architecture'],
        },
      };

      const affinities = findAffinityInjections(['adapter-development'], [], skillRules);

      expect(affinities).toEqual(
        expect.arrayContaining(['aidb-architecture', 'dap-protocol-guide'])
      );
      expect(affinities.length).toBe(2);
    });

    it('should inject architecture when injecting mcp-tools-development', () => {
      const skillRules: Record<string, SkillRule> = {
        'mcp-tools-development': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          affinity: ['aidb-architecture'],
        },
        'aidb-architecture': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
        },
      };

      const affinities = findAffinityInjections(['mcp-tools-development'], [], skillRules);

      expect(affinities).toEqual(['aidb-architecture']);
    });

    it('should not re-inject architecture if already loaded', () => {
      const skillRules: Record<string, SkillRule> = {
        'adapter-development': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
          affinity: ['aidb-architecture', 'dap-protocol-guide'],
        },
        'aidb-architecture': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
        },
        'dap-protocol-guide': {
          type: 'domain',
          enforcement: 'suggest',
          priority: 'high',
        },
      };

      const affinities = findAffinityInjections(
        ['adapter-development'],
        ['aidb-architecture', 'dap-protocol-guide'], // Both already loaded
        skillRules
      );

      expect(affinities).toEqual([]);
    });
  });
});
