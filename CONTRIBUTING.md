# Contributing to gptcgt

Thank you for your interest in contributing to **gptcgt**! This guide will help you set up your local development environment and understand our contribution workflow.

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/iacompa/gptcgt.git
   cd gptcgt
   ```

2. **Set up the virtual environment**
   Requires Python 3.11+. We recommend using `venv`:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**
   Install the project along with its development dependencies using `pip` (the `-e` flag installs in editable mode):
   ```bash
   pip install -e ".[dev]"
   ```

4. **Environment Configuration**
   The application stores its configuration by default in `~/.gptcgt/`. Make sure you have valid API keys for the providers you intend to test or use `gptcgt`'s managed gateway.

## Development Workflow

- **Testing**: Run the test suite before submitting PRs to ensure nothing breaks.
  ```bash
  pytest
  ```
- **Linting & Formatting**: We enforce strict code style rules. We use `ruff` and `black`.
  ```bash
  black .
  ruff check .
  ```
- **Staging Smoke**: For post-deploy confidence against real services, run the manual staging smoke workflows documented in [docs/staging-smoke.md](docs/staging-smoke.md) and [docs/staging-web-smoke.md](docs/staging-web-smoke.md).
- **Deploy Promotion**: Use the gated staging-to-production workflow described in [docs/deploy-pipeline.md](docs/deploy-pipeline.md) when you want staging deploy, automatic smoke validation, and a production approval barrier in one run.

## Submitting a Pull Request

1. Fork the repository and create your feature branch: `git checkout -b feature/my-amazing-feature`
2. Write clean, modular code. Add tests if you are adding new features.
3. Commit your changes: `git commit -am 'Add my amazing feature'`
4. Push to the branch: `git push origin feature/my-amazing-feature`
5. Submit a Pull Request.

Make sure your PR passes all CI gates (tests, lints, and format checks).

## Architecture & Subsystems

If you are modifying core components, please keep the following architecture boundaries in mind:
- **TUI (`src/tui/`)**: Built on Textual. Must be async, non-blocking, and use the central AgentBus for state updates.
- **Agents (`src/agents/`)**: Individual LLM personalities. Must return structured data.
- **Tools (`src/tools/`)**: Must safely sandbox interactions (e.g., via E2B). Never execute untrusted code natively.
- **Core (`src/core/`)**: The AgentBus, Autonomous orchestrator, and State classes. Avoid tight coupling here.

## Security & Code Scanners

Please ensure `bandit` and `semgrep` pass locally if you modify any core sandbox execution components. The CI pipeline enforces strict secret redaction (no exposing API keys).

## License

By contributing, you agree that your contributions will be licensed under the MIT License for the client application.
