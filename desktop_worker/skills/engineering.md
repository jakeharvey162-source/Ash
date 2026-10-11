keywords: build develop implement refactor debug programming code test review superpowers quality
# Test-first engineering workflow

When a user asks Ash to change a program:
1. Restate the required behavior and the existing constraints in a short acceptance checklist.
2. Inspect the relevant files, tests, license and available runtime before proposing changes.
3. Write or update a failing regression test where a test runner exists.
4. Make the smallest change that addresses the verified requirement.
5. Run relevant tests and static checks, then check the full affected user flow.
6. Separate passed tests, untested behavior and unresolved issues in the final report.
7. Request explicit confirmation before destructive commands or external side effects.

Do not claim an unexecuted test passed, invent benchmark numbers, or silently download software.
Prefer offline local tools and reproducible builds when they meet the user's needs.
This is an original Ash instruction inspired by test-first engineering practices;
it is not a copy or installation of the upstream Superpowers plugin.
