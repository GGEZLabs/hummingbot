# Documentation Index

| Topic | File |
| ----- | ----- |
| Repository Overview | [repository-overview.md](repository-overview.md) |
| HBot Instance | [hbot-instance.md](hbot-instance.md) |
| HBot Installation & Running | [hbot-installation-running.md](hbot-installation-running.md) |
| AWS ECR | [aws-ecr.md](aws-ecr.md) |
| HBot Configuration | [hbot-configuration.md](hbot-configuration.md) |
| Running Strategies | [running-strategies.md](running-strategies.md) |
| Running Multiple Hummingbot Instances | [running-multiple-instances.md](running-multiple-instances.md) |
| Important Links | [important-links.md](important-links.md) |
| CLI Clipboard Operations | [cli-clipboard-operations.md](cli-clipboard-operations.md) |
| General Notes & Troubleshooting | [general-notes-troubleshooting.md](general-notes-troubleshooting.md) |
| Development & Deployment Workflow | [development-deployment-workflow.md](development-deployment-workflow.md) |
| Memory Management | [memory-management.md](memory-management.md) |
| Useful Command Reference | [useful-command-reference.md](useful-command-reference.md) |
| Developing a Strategy | [developing-a-strategy.md](developing-a-strategy.md) |
| Database & Hasura Changes | [database-hasura.md](database-hasura.md) |
| Environment Variables | [environment-variables.md](environment-variables.md) |
| Volume Pumper Controller | [volume-pumper-controller.md](volume-pumper-controller.md) |
| Telegram Tokens | [telegram-tokens.md](telegram-tokens.md) |

## Technical Guides

| Topic | File |
| ----- | ----- |
| Creating or developing a new exchange connector | [connector-development-guide.md](connector-development-guide.md) |
| Creating or developing a new strategy (v1 or v2) | [strategy-development-guide.md](strategy-development-guide.md) |
| Volume pumper controller, volume trading logic | [volume-pumper-controller-guide.md](volume-pumper-controller-guide.md) |

## Using AI Agents to Help

The technical guides above are the authoritative source of truth for their topics. Any AI assistant you use should read them before answering questions or generating code.

**Claude CLI** — can read the docs directly from your local repo. Just ask it about a topic and it will read the relevant guide automatically (configured via `CLAUDE.md`).

**Other AI agents (e.g. Antigravity)** — make sure the agent reads `CLAUDE.md` first. It references the correct guide files so the agent knows where to look.

| Task | Guide to point the agent to |
| ----- | ----- |
| Create or modify a connector | `docs/connector-development-guide.md` |
| Create or modify a strategy | `docs/strategy-development-guide.md` |
| Understand or modify the volume pumper | `docs/volume-pumper-controller-guide.md` |
