<!-- ai-generated: 90% - agent policy and tool permissions justification -->
# Agent Tool Policies

- Bash(rm *): The reviewer reads and comments; deleting files is the author's decision, not the reviewer's.
- Bash(git push *): The reviewer operates locally and must never push commits to the remote repository.
- Bash(docker *): Modifying container states or invoking docker daemons is reserved for the primary deployment agent.