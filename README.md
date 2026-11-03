# Hardware & Machining Prototyping Assistant (E190)

A web application designed for student makers and shop stewards to plan hardware prototyping steps, track machining workflows, and manage safety sign-offs.

## Architecture & Conventions

- **Engineering Directives**: See [CLAUDE.md](CLAUDE.md) (mirrored to [AGENTS.md](AGENTS.md))
- **Execution Plan**: See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
- **Process Journal**: See [PROCESS.md](PROCESS.md)

## Multi-Agent Workflows

This repository uses cooperative multi-agent execution across Antigravity subagents and terminal Claude Code (`claude` CLI) instances with cross-model review and isolated worktrees.
