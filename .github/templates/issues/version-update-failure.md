---
name: Version Update Failure Investigation
about: Template for investigating failed version updates
title: 🔧 Version Update Failure - [LANGUAGE] [VERSION]
labels:
  - test-matrix
  - maintenance
  - bug
  - investigation
  - version-update
assignees: []
---

## Update Failure Summary

**Language:** <!-- e.g., Python, JavaScript, Java -->
**Package:** <!-- e.g., debugpy, java-debug -->
**Failed Version:** <!-- e.g., 1.9.0 -->
**Current Version:** <!-- e.g., 1.8.0 -->
**Failure Stage:** <!-- e.g., Testing, Compatibility Check, Auto-merge -->

## Failure Details

### Error Information

```
<!-- Paste error logs/output here -->
```

### Workflow Run

- **Run ID:** <!-- Link to failed GitHub Actions run -->
- **Branch:** <!-- e.g., maintenance -->
- **Commit:** <!-- SHA of failed commit -->

## Investigation Checklist

### Initial Analysis

- [ ] Review error logs and failure point
- [ ] Check if failure is transient or persistent
- [ ] Verify workflow configuration
- [ ] Confirm version availability

### Compatibility Assessment

- [ ] Check release notes for breaking changes
- [ ] Verify adapter API compatibility
- [ ] Review Docker image availability
- [ ] Test manual installation

### Testing Analysis

- [ ] Identify which tests failed
- [ ] Reproduce failures locally
- [ ] Check for environment-specific issues
- [ ] Verify test configuration correctness

### Dependency Analysis

- [ ] Check for conflicting dependencies
- [ ] Verify minimum version requirements
- [ ] Review transitive dependency changes
- [ ] Assess impact on other packages

## Root Cause Analysis

### Primary Cause

<!-- Describe the main reason for the failure -->

### Contributing Factors

<!-- List any secondary factors that contributed -->

### Environment Factors

<!-- OS, Python version, Docker, etc. specific issues -->

## Resolution Plan

### Immediate Actions

- [ ] <!-- e.g., Pin to working version, disable auto-update for this package -->
- [ ] <!-- e.g., Create hotfix for critical issue -->
- [ ] <!-- e.g., Rollback to previous version -->

### Short-term Solution

- [ ] <!-- e.g., Update test configuration -->
- [ ] <!-- e.g., Add compatibility shim -->
- [ ] <!-- e.g., Update minimum requirements -->

### Long-term Fix

- [ ] <!-- e.g., Refactor incompatible code -->
- [ ] <!-- e.g., Update workflow to handle this scenario -->
- [ ] <!-- e.g., Improve testing coverage -->

## Prevention Measures

### Workflow Improvements

- [ ] Add pre-flight checks
- [ ] Improve error handling
- [ ] Enhance logging/monitoring
- [ ] Add retry mechanisms

### Testing Enhancements

- [ ] Add integration tests for new scenario
- [ ] Improve test coverage
- [ ] Add compatibility matrix tests
- [ ] Enhance CI validation

### Process Updates

- [ ] Update documentation
- [ ] Improve failure notification
- [ ] Add manual override procedures
- [ ] Enhance review process

## Follow-up Actions

- [ ] Update version pinning if needed
- [ ] Monitor for similar issues
- [ ] Review and update automation
- [ ] Document lessons learned

## Timeline

- [ ] **Investigation:** <!-- Target completion date -->
- [ ] **Root cause identified:** <!-- Target date -->
- [ ] **Solution implemented:** <!-- Target date -->
- [ ] **Monitoring period:** <!-- Duration -->

______________________________________________________________________

*This issue was automatically created after a version update failure.*
*Investigation required to prevent future occurrences.*
