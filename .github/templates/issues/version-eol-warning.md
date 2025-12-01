---
name: Version End-of-Life Warning
about: Template for versions approaching end-of-life
title: 📅 Upcoming EOL - [LANGUAGE] [VERSION] (EOL: [DATE])
labels:
  - test-matrix
  - maintenance
  - eol-warning
  - planning
assignees: []
---

## End-of-Life Timeline

**Language:** <!-- e.g., Python, JavaScript, Java -->
**Version:** <!-- e.g., 3.9, 16, 11 -->
**EOL Date:** <!-- e.g., 2025-10-05 -->
**Days Remaining:** <!-- Automatically calculated -->

## Impact Assessment

### Current Usage

- [ ] Audit current test matrix usage
- [ ] Check production environment dependencies
- [ ] Identify customer/user impact
- [ ] Review documentation references

### Migration Planning

- [ ] Identify replacement version(s)
- [ ] Assess compatibility with existing features
- [ ] Plan testing strategy for migration
- [ ] Estimate migration effort

## Migration Plan

### Target Versions

- **Primary replacement:** <!-- e.g., Python 3.12 -->
- **Alternative options:** <!-- e.g., Python 3.11 (LTS) -->

### Timeline

- [ ] **Week 1:** Complete impact assessment
- [ ] **Week 2:** Prepare migration PRs
- [ ] **Week 3:** Testing and validation
- [ ] **Week 4:** Deploy and monitor

### Tasks

- [ ] Update `src/tests/_docker/config/versions.yaml`
- [ ] Update CI workflows
- [ ] Update documentation
- [ ] Test adapter compatibility
- [ ] Prepare user communication

## Communication Plan

### Internal

- [ ] Notify development team
- [ ] Update project roadmap
- [ ] Review with stakeholders

### External (if applicable)

- [ ] Draft migration guide
- [ ] Update compatibility documentation
- [ ] Prepare user announcements

## Rollback Plan

- [ ] Document rollback procedure
- [ ] Identify rollback triggers
- [ ] Test rollback process

## Additional Notes

<!-- Any specific concerns, dependencies, or considerations -->

______________________________________________________________________

*This issue was automatically created by the version maintenance workflow.*
*Action required before EOL date to maintain security and support.*
