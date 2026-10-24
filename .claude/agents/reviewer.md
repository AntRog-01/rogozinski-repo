---
name: reviewer
disallowedTools:
  - Bash(rm *)
  - Bash(git push *)
  - Bash(docker *)
---
<!-- ai-generated: 90% - reviewer sub-agent specification -->
# Reviewer Agent
The reviewer reads code, runs local static tests, and verifies compliance against CHECKS.md.