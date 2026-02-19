# Developing a Strategy

Refer to the Hummingbot strategy development guide in the repo:

docs/STRATEGY\_DEVELOPMENT\_GUIDE.md in the hummingbot repository. This file describes the inheritance hierarchy, available executor types, how to build scripts and controllers, how to format the status command, and debugging techniques.

Also review the example scripts inside the scripts/ directory for working examples you can run and modify directly.

The V2 framework has three layers — pick the one that fits your use case:

\- **ScriptStrategyBase** — simple scripts with no config file, direct buy/sell/cancel API

\- **StrategyV2Base** — multi-pair strategies using typed executors (stop-loss, take-profit, DCA, grid, etc.)

\- **ControllerBase** — reusable, hot-swappable logic that runs in its own async loop and can be combined with other controllers

## Using AI Agents to Help

If you are using Claude CLI, you can ask it directly how to create a new Hummingbot strategy, but first ensure it has access to your local repo so it can read docs/STRATEGY\_DEVELOPMENT\_GUIDE.md. This keeps the instructions aligned with the current codebase.

If you are using another AI agent such as Antigravity, make sure the agent reads your claude.md.

This way, any AI assistant you use will generate strategy code that matches the official Hummingbot patterns and requirements.
