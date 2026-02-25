# Contributing to gptcgt

Thank you for your interest in contributing to gptcgt!

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/iacompa/gptcgt.git
   cd gptcgt
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -e ".[dev]"
   ```

## Code Standards
- **Python Version**: We use Python 3.11+.
- **Formatting**: We use `black` for code formatting.
- **Linting**: We use `ruff` for linting.
- **Pre-commit**: Please install the pre-commit hooks (`pre-commit install`) before submitting a pull request.

## Open vs Proprietary
The core orchestrator, TUI, and local agent pipeline are open source under the MIT license.
The server-side billing, hosted proxy infrastructure, and Next.js web dashboard are proprietary components of IA Compa LLC and are not included in the public open source repository.

## Pull Request Process
1. Fork the repository and create your branch from `main`.
2. Ensure all tests pass.
3. Update documentation if necessary.
4. Submit a PR with a clear description of the problem and your solution.
