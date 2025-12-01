---
name: Debug Adapter Capability Mismatch
about: Automatically created when the adapter watchdog detects capability changes
title: '[ADAPTER-WATCHDOG] Capability mismatch detected for {{ADAPTER_NAME}}'
labels:
  - adapter
  - capability-mismatch
  - automated
assignees: []
---

## Adapter Capability Mismatch Detected

**Adapter:** {\{ADAPTER_NAME}}
**Detection Date:** {\{DETECTION_DATE}}
**Release Version:** {\{RELEASE_VERSION}}

### Summary

The automated adapter watchdog has detected changes in the upstream debug adapter that may affect aidb's capabilities.

### Release Information

**Release Notes Source:** {\{RELEASE_SOURCE}}
**Release Date:** {\{RELEASE_DATE}}

### Detected Changes

{\{DETECTED_CHANGES}}

### Current aidb Capabilities

{\{CURRENT_CAPABILITIES}}

### Recommended Actions

{\{RECOMMENDED_ACTIONS}}

### Analysis Details

<details>
<summary>LLM Analysis Results</summary>

{\{LLM_ANALYSIS}}

</details>

### Next Steps

- [ ] Review the upstream release notes in detail
- [ ] Assess impact on current aidb functionality
- [ ] Update aidb adapter configuration if needed
- [ ] Test compatibility with new adapter version
- [ ] Update documentation if capabilities changed
- [ ] Close this issue when resolved

______________________________________________________________________

*This issue was automatically created by the [Adapter Capability Watchdog](/.github/workflows/adapter-watchdog.yaml). If this appears to be a false positive, please add the `false-positive` label.*
