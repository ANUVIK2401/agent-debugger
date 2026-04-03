# AgentDebugger 🐛
> AI-powered agentic debugger inspired by TraceRoot.AI

![Demo](demo.gif)

## What it does
Paste a Python traceback → AgentDebugger fetches your
GitHub source code, runs a LangChain chain with GPT-4o,
and returns: root cause, unified diff fix, confidence
score, and a pre-written GitHub issue.

## Architecture
```
Traceback Input
      │
      ▼
GitHub Fetcher ──► Raw source code (20 lines context)
      │
      ▼
LangChain Chain (GPT-4o)
      │
      ▼
JSON Parser ──► root_cause, fix, confidence, issue
      │
      ▼
Streamlit UI ──► Results + Session History
```

## Setup
```bash
git clone https://github.com/ANUVIK2401/agent-debugger
cd agent-debugger
pip install -r requirements.txt
cp .env.example .env  # add your OPENAI_API_KEY
streamlit run src/app.py
```

## Tech Stack
| Layer | Technology |
|-------|-----------|
| UI | Streamlit |
| LLM Chain | LangChain + GPT-4o |
| GitHub API | requests |
| Config | python-dotenv |

---
Built by [Anuvik Thota](https://github.com/ANUVIK2401)
Inspired by [TraceRoot.AI](https://traceroot.ai)
