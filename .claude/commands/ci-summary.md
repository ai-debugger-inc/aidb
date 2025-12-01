______________________________________________________________________

## description: Review a CI run's detailed summary and investigate failures/flakes.

Review the provided CI summary, focusing on any failed or flaky tests. Analyze
the logs and error messages to identify the root causes of these issues.
Summarize your findings, including any patterns or commonalities among the
failures.

Review the detailed summary –– and download the associated test log artifacts if
needed –– via:

```bash
dev-cli ci ${RUN_ID} summary --detailed
```

The run ID is provider either as command input by the user or derived from
session context/gh cli run fetching.

**IMPORTANT**: You must make use of logging artifacts to perform deep
investigations. Use related skills, like the troubleshooting skill, to
understand which logs are where and what logs might be most applicable to the
issues at hand.
