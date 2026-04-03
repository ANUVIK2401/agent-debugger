# AgentDebugger 🐛

An AI-powered debugging assistant that analyzes Python tracebacks, fetches relevant source code from GitHub, and provides actionable fixes using LLM-based root cause analysis.

## Features

- **Intelligent Root Cause Analysis** — Paste any Python traceback and get instant diagnosis powered by GPT-4o-mini
- **GitHub Code Context** — Automatically fetches source code from your repository with line numbers and error highlighting
- **Confidence Scoring** — 3-metric breakdown (traceback clarity, code quality, fix certainty) so you know how reliable the analysis is
- **Suggested Fixes** — Get unified diff patches you can apply directly
- **Batch Mode** — Analyze multiple errors at once, separated by `---`
- **Error Intelligence** — Tracks error patterns across sessions with frequency visualization
- **Export Reports** — Download analysis as markdown for documentation or sharing
- **GitHub Issue Drafts** — Auto-generated issue templates ready to paste

## Live Demo

**🚀 Try it now:** https://agentic-code-debugging.streamlit.app

### Key Features in Action:
- ✅ **85% confidence** root cause analysis
- ✅ **3-metric confidence breakdown** (traceback clarity, code quality, fix certainty)
- ✅ **Suggested fix** with unified diff patch
- ✅ **Similar bug patterns** detection
- ✅ **Auto-generated GitHub issue** templates
- ✅ **Export reports** as markdown
- ✅ **Batch mode** for multiple errors
- ✅ **Error intelligence** with frequency tracking

## Quick Start

```bash
# Clone the repository
git clone https://github.com/ANUVIK2401/agent-debugger
cd agent-debugger

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your OpenAI API key

# Run the app
streamlit run src/app.py
```

Open http://localhost:8501 in your browser.

## Configuration

Create a `.env` file with:

```env
OPENAI_API_KEY=sk-your-key-here
GITHUB_TOKEN=ghp-your-token-here  # Optional: for private repos
```

## Usage

1. **Paste a traceback** — Copy any Python error traceback into the input area
2. **Add GitHub URL** (optional) — Link to your repo to fetch actual source code context
3. **Select severity** — Tag the bug as Critical, High, Medium, or Low
4. **Click Analyze** — Get results in seconds

### Batch Mode

Toggle "Batch Mode" in the sidebar to analyze multiple errors at once. Separate each traceback with `---`:

```
Traceback (most recent call last):
  File "app.py", line 10, in main
    result = process(data)
KeyError: 'missing_key'
---
Traceback (most recent call last):
  File "utils.py", line 25, in calculate
    return x / y
ZeroDivisionError: division by zero
```

## Architecture

```
┌─────────────────┐
│  Streamlit UI   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│ GitHub Fetcher  │────►│ Source Code      │
│ (requests)      │     │ (20 lines ctx)   │
└────────┬────────┘     └──────────────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│ LangChain Chain │────►│ Structured JSON  │
│ (GPT-4o-mini)   │     │ Analysis Result  │
└────────┬────────┘     └──────────────────┘
         │
         ▼
┌─────────────────┐
│ Results Panel   │
│ + Export/History│
└─────────────────┘
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | Streamlit |
| LLM Orchestration | LangChain |
| Model | OpenAI GPT-4o-mini |
| GitHub Integration | requests + GitHub Raw API |
| Environment | python-dotenv |

## Project Structure

```
agent-debugger/
├── src/
│   ├── app.py          # Streamlit UI and session management
│   └── analyzer.py     # Core analysis logic and LLM chain
├── .env.example        # Environment template
├── .gitignore
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.10+
- OpenAI API key
- GitHub token (optional, for private repositories)

## License

MIT

---

Built by [Anuvik Thota](https://github.com/ANUVIK2401)
