______________________________________________________________________

## description: Wrap up current work

Wrap up the current work by following the checklist below.

\*\*NOTE: If you are low on context and/or if any of the wrap tasks are easily
delegated, feel free to leverage subagents to complete the task(s) to stretch
your remaining context.

**Checklist:**

For all changes/additions made, please:

- Lint the code. It should pass pre-commit checks. If you find linting errors
  that are not related to your changes, please fix them as well, if possible.
- Verify whether tests need updating. If so, update or add tests to cover your
  changes. Ensure all tests pass. Always follow existing test patterns.
- When updating or adding new tests, ensure you re using existing fixtures and
  mocks where applicable. Ensure you adhere to established patterns in the given
  suite.
- Check to see if there are any related docs. If there are, update them as
  necessary to account for the changed/added code. Do not add unimportant/minute
  details to documentation.
- Check if any skills need updates (NOTE: all skill/resource docs should be \<=
  500 LOC):
  - NOT EVERYTHING NEEDS TO BE DOCUMENTED. Only document what is necessary for
    future maintainers/operators to understand the code and its usage.
  - Activate the "skill-developer" skill to assist with skill maintenance.
- Check that proper code reuse was employed, no DRY violations were introduced,
  and existing codebase patterns were followed. Be wary of magic strings/numbers
  and use constants/enums where appropriate. Activate the
  "code-reuse-enforcement" skill to assist with this if needed.
- If there are ANY actionable next steps or current problems/failures, detail
  them in the form of an actionable summary for the next session.

When finished, provide a commit message (without any single quotes) summarizing
the changes made.
