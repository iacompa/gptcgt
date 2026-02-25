# gptcgt (Hydra)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Textual](https://img.shields.io/badge/built%20with-Textual-green.svg)](https://textual.textualize.io/)

**gptcgt** is a terminal-native, multi-agent AI coding IDE. It transforms your CLI into a powerful, verifiable coding assistant that puts multiple top-tier models head-to-head to write, analyze, and verify your code—directly inside E2B Firecracker sandboxes.

*(CLI Demo Video Coming Soon)*

## Why gptcgt?
While visual IDEs (Cursor, Windsurf) force you out of the terminal, `gptcgt` lives exactly where you work: inside your SSH sessions, tmux panes, and Neovim environments.

### The Arbiter (Our Moat)
Stop praying that LLM-generated code works. Wait for proof. 
When using **Ensemble** or **Battle** mode, `gptcgt` pits Claude 3.5 Sonnet, GPT-4o, and DeepSeek against each other in real-time. The **Arbiter** then evaluates the solutions deterministically inside an isolated Firecracker microVM across 6 stages:
1. Structural Syntax Check (Python `compile()`, AST)
2. Lint Cleanliness
3. Test Execution (Pytest, Jest, etc.)
4. Security Scanning (Regex, Semgrep, Bandit)
5. Diff Minimalism
6. Cyclomatic Complexity Delta

## Features
- **Multi-Model Orchestration**: Anthropic, OpenAI, DeepSeek, Google, and xAI.
- **5 Operation Modes**:
  - `Scout` (1 cr): Fast navigation and structure analysis, Tree-Sitter ast extraction.
  - `Standard` (5 cr): Single-file edits and quick features.
  - `Ensemble` (25 cr): Parallel generation across multiple models with Arbiter verdict.
  - `Architect` (100 cr): Deep project planning and multi-stage execution.
  - `Battle` (25 cr): Two specific models compete for the best implementation, judged by the Arbiter.
- **Interactive Canvas Mode**: Select-to-Prompt, inline hunk diff editing, and code annotations right in the terminal.
- **Secure Sandboxing**: Filesystem changes and test executions are isolated by default via E2B.
- **Real-time Cost Tracking**: Know exactly what you've spent down to the cent per-task. 

## Installation

Requires Python 3.11+.

```bash
pip install gptcgt
```

## Quick Start
1. Navigate to your project directory:
   ```bash
   cd my-project
   ```
2. Launch the IDE:
   ```bash
   gptcgt
   ```
3. Type `/login` to use our managed API gateway, or optionally provide your own API keys in the Settings panel (`Ctrl+P` -> Settings).
4. Start chatting! Try: *"Refactor this authentication class to use dependency injection."*

## Architecture Highlights
- **Underlying UI**: Built entirely on [Textual](https://github.com/Textualize/textual), maximizing async, non-blocking component rendering. 
- **Language Intelligence**: Dual-mode [Tree-sitter](https://tree-sitter.github.io/tree-sitter/) AST parsing with fallback regex heuristics.
- **Cross-file safety**: LSP (Language Server Protocol) integration mapped inside the sandbox validates symbol references.

## Documentation
Full documentation is available at [gptcgt.ai/docs](https://gptcgt.ai/docs). Review our pricing model and security practices there.

## License
MIT License. See [LICENSE](LICENSE) for details. Note: Some server-side API proxy routing elements and infrastructure belong to IA Compa LLC.
