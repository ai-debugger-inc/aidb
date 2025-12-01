---
name: Version Update - Manual Review Required
about: Template for version updates requiring manual review
title: 🔄 Version Update Review - [LANGUAGE] [VERSION]
labels:
  - test-matrix
  - maintenance
  - manual-review
  - version-update
assignees: []
---

## Version Update Summary

**Language:** <!-- e.g., Python, JavaScript, Java -->
**Package:** <!-- e.g., debugpy, java-debug -->
**Update Type:** <!-- patch, minor, major -->
**Current Version:** <!-- e.g., 1.8.0 -->
**New Version:** <!-- e.g., 1.9.0 -->

## Changes Detected

<!-- Automatically populated by workflow -->

## Impact Assessment

### Compatibility

- [ ] Reviewed breaking changes in release notes
- [ ] Checked impact on existing debug adapter features
- [ ] Verified Docker image availability
- [ ] Assessed impact on test matrix

### Testing

- [ ] All integration tests pass with new version
- [ ] Smoke tests completed successfully
- [ ] Performance impact evaluated
- [ ] Edge cases verified

### Dependencies

- [ ] No conflicts with other language versions
- [ ] Adapter compatibility matrix updated
- [ ] Documentation updated if needed

## Release Planning

- [ ] Determine if this should trigger an aidb release
- [ ] Version bump strategy (patch/minor/major)
- [ ] Release notes prepared
- [ ] Migration guide needed (if breaking changes)

## Action Items

- [ ] Merge this version update
- [ ] Update documentation
- [ ] Communicate changes to users (if significant)
- [ ] Monitor for issues post-deployment

## Additional Notes

<!-- Any additional context, concerns, or observations -->

______________________________________________________________________

*This issue was automatically created by the version maintenance workflow.*
*Manual review is required due to minor/major version changes.*
