---
name: Version End-of-Life - Immediate Removal Required
about: Template for versions that have reached end-of-life
title: ⚠️ EOL Version Removal Required - [LANGUAGE] [VERSION]
labels:
  - test-matrix
  - maintenance
  - eol
  - high-priority
  - security
assignees: []
---

## ⚠️ URGENT: End-of-Life Version Detected

**Language:** <!-- e.g., Python, JavaScript, Java -->
**Version:** <!-- e.g., 3.8, 14, 8 -->
**EOL Date:** <!-- e.g., 2024-10-07 -->
**Status:** 🔴 **OVERDUE REMOVAL**

## Security Impact

> **Warning:** This version is no longer receiving security updates and poses a potential security risk.

### Immediate Actions Required

- [ ] Remove from test matrix configuration
- [ ] Update CI/CD pipelines
- [ ] Verify no production dependencies
- [ ] Document removal in changelog

## Removal Checklist

### Configuration Updates

- [ ] Remove from `src/tests/_docker/config/versions.json`
- [ ] Update Docker configurations
- [ ] Remove from CI test matrix
- [ ] Clean up related workflows

### Code Changes

- [ ] Remove version-specific code paths
- [ ] Update minimum version requirements
- [ ] Clean up compatibility shims
- [ ] Update type annotations/imports

### Documentation

- [ ] Update compatibility matrix
- [ ] Remove from installation guides
- [ ] Update API documentation
- [ ] Add to breaking changes log

### Testing

- [ ] Remove version-specific tests
- [ ] Update integration test configurations
- [ ] Verify remaining versions work correctly
- [ ] Test upgrade/migration paths

## Dependencies Check

### Direct Dependencies

- [ ] Verify no adapter dependencies on EOL version
- [ ] Check third-party package compatibility
- [ ] Review minimum version requirements

### User Impact

- [ ] Assess user base on EOL version
- [ ] Prepare migration communication
- [ ] Provide upgrade instructions
- [ ] Set deprecation timeline for dependents

## Migration Path

### Recommended Replacement

**Target Version:** <!-- e.g., Python 3.12, Node.js 20 -->
**Migration Effort:** <!-- Low/Medium/High -->

### Breaking Changes

<!-- List any breaking changes users need to know about -->

### Compatibility Notes

<!-- Any specific compatibility considerations -->

## Timeline

- [ ] **Day 1:** Create removal PR
- [ ] **Day 2:** Complete testing
- [ ] **Day 3:** Merge and deploy
- [ ] **Day 7:** Monitor for issues

## Rollback Plan

**If issues arise:**

1. Temporarily re-enable version in emergency
1. Create hotfix branch
1. Deploy rollback within 4 hours
1. Investigate root cause

## Communication

- [ ] Internal team notification sent
- [ ] User-facing changelog updated
- [ ] Security advisory if applicable
- [ ] Migration guide published

______________________________________________________________________

*This issue was automatically created by the version maintenance workflow.*
*IMMEDIATE ACTION REQUIRED - Version is beyond end-of-life.*
