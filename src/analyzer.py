import os
import re
import json
import requests
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser


def load_env():
    """Load environment variables from .env file."""
    load_dotenv()


@st.cache_data(ttl=300)
def fetch_github_context(repo_url: str, branch: str, traceback_text: str) -> dict:
    """
    Fetch source code context from GitHub based on traceback.

    Returns dict with keys: code, code_display, start_line, end_line, error_line, filepath, error
    """
    result = {
        "code": None,
        "code_display": None,
        "start_line": 0,
        "end_line": 0,
        "error_line": 0,
        "filepath": "",
        "error": None
    }

    try:
        # Parse repo URL to get owner/repo
        match = re.search(r'github\.com[/:]([^/]+)/([^/\s\.]+)', repo_url)
        if not match:
            result["error"] = "Invalid GitHub URL format"
            return result

        owner, repo = match.groups()
        repo = repo.rstrip('.git')

        # Find filename and line number from traceback
        # Format 1: File "path/to/file.py", line 42
        # Format 2: at path/to/file.py:42
        file_match = re.search(r'File ["\']([^"\']+)["\'], line (\d+)', traceback_text)
        if not file_match:
            file_match = re.search(r'at\s+([^\s:]+):(\d+)', traceback_text)

        if not file_match:
            result["error"] = "Could not find file/line in traceback"
            return result

        filepath = file_match.group(1)
        error_line = int(file_match.group(2))

        # Clean filepath - remove leading ./ or absolute paths
        filepath = re.sub(r'^[./\\]+', '', filepath)
        result["filepath"] = filepath
        result["error_line"] = error_line

        # Build GitHub raw URL
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{filepath}"

        # Fetch file with optional auth
        headers = {}
        github_token = os.environ.get("GITHUB_TOKEN")
        if github_token:
            headers["Authorization"] = f"token {github_token}"

        response = requests.get(raw_url, headers=headers, timeout=10)

        if response.status_code != 200:
            result["error"] = f"GitHub fetch failed: HTTP {response.status_code}"
            return result

        # Get 20 lines around error line (10 before, 10 after)
        lines = response.text.splitlines()
        start_line = max(1, error_line - 10)
        end_line = min(len(lines), error_line + 10)

        result["start_line"] = start_line
        result["end_line"] = end_line

        # Build code context for LLM (with >>> marker)
        code_lines = []
        for i in range(start_line - 1, end_line):
            line_num = i + 1
            prefix = ">>> " if line_num == error_line else "    "
            code_lines.append(f"{prefix}{line_num:4d} | {lines[i]}")
        result["code"] = "\n".join(code_lines)

        # Build display code with real line numbers and arrow marker
        display_lines = []
        for i in range(start_line - 1, end_line):
            line_num = i + 1
            marker = "▶" if line_num == error_line else " "
            display_lines.append(f"{line_num:4d} {marker} {lines[i]}")
        result["code_display"] = "\n".join(display_lines)

        return result

    except requests.RequestException as e:
        result["error"] = f"Network error: {str(e)}"
        return result
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
        return result


def extract_error_type(traceback_text: str) -> str:
    """Extract the error type from a traceback."""
    try:
        # Match common Python error types at end of traceback
        patterns = [
            r'(\w+Error)(?::|$)',
            r'(\w+Exception)(?::|$)',
            r'(\w+Warning)(?::|$)',
        ]
        for pattern in patterns:
            match = re.search(pattern, traceback_text)
            if match:
                return match.group(1)
        return "Unknown"
    except Exception:
        return "Unknown"


def analyze_with_langchain(traceback: str, code_context: str,
                           filepath: str, severity: str,
                           previous_patterns: list = None) -> tuple:
    """
    Analyze traceback using LangChain with GPT-4o-mini.

    Returns tuple: (result_dict, token_usage_dict)
    """
    error_result = {
        "root_cause": "Analysis failed",
        "explanation": "",
        "fix": {
            "description": "Unable to generate fix",
            "code_diff": "",
            "confidence": 0.0
        },
        "confidence_breakdown": {
            "traceback_clarity": 0.0,
            "code_context_quality": 0.0,
            "fix_certainty": 0.0,
            "reasoning": "Analysis failed"
        },
        "similar_bugs": [],
        "github_issue": {
            "title": "Bug: Analysis failed",
            "body": ""
        }
    }

    default_usage = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_usd": 0.0
    }

    if previous_patterns is None:
        previous_patterns = []

    try:
        # max_tokens=1200 — JSON response with diff blocks needs extra room
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=1200)

        patterns_instruction = ""
        if previous_patterns:
            patterns_str = ", ".join(previous_patterns[:3])
            patterns_instruction = f"""
PREVIOUS ERROR PATTERNS SEEN: {patterns_str}
If the current error matches one of these previous patterns, start your fix.description with "⚠️ Recurring pattern: " and increase your confidence scores by 0.1 (max 1.0).
"""

        prompt_template = """You are an expert software debugger.
Always respond with ONLY valid JSON. No markdown. No backticks. No explanation outside JSON.

Analyze this error and provide debugging assistance.

TRACEBACK:
{traceback}

CODE CONTEXT (file: {filepath}):
{code_context}

SEVERITY: {severity}
""" + patterns_instruction + """
Respond with this exact JSON structure:
{{
    "root_cause": "one sentence describing the root cause",
    "explanation": "2-3 sentences explaining the issue in detail",
    "fix": {{
        "description": "what needs to be changed",
        "code_diff": "unified diff format showing the fix",
        "confidence": 0.85
    }},
    "confidence_breakdown": {{
        "traceback_clarity": 0.85,
        "code_context_quality": 0.80,
        "fix_certainty": 0.75,
        "reasoning": "one sentence explaining why confidence is at this level"
    }},
    "similar_bugs": ["common bug pattern 1", "common bug pattern 2"],
    "github_issue": {{
        "title": "Bug: short description",
        "body": "## Summary\\n...\\n## Steps to Reproduce\\n...\\n## Suggested Fix\\n..."
    }}
}}"""

        prompt = PromptTemplate(
            input_variables=["traceback", "code_context", "filepath", "severity"],
            template=prompt_template
        )

        # Use LCEL chain composition
        chain = prompt | llm | StrOutputParser()

        raw_response = chain.invoke({
            "traceback": traceback,
            "code_context": code_context if code_context else "No code context available",
            "filepath": filepath,
            "severity": severity
        })

        # Estimate tokens (4 chars per token average)
        prompt_text = prompt_template.format(
            traceback=traceback,
            code_context=code_context or "No code context available",
            filepath=filepath,
            severity=severity
        )
        prompt_tokens = len(prompt_text) // 4
        completion_tokens = len(raw_response) // 4
        total_tokens = prompt_tokens + completion_tokens
        token_usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": total_tokens * 0.000005
        }

        # Parse JSON response
        try:
            # Clean response - remove any markdown code blocks if present
            cleaned = raw_response.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r'^```(?:json)?\n?', '', cleaned)
                cleaned = re.sub(r'\n?```$', '', cleaned)

            result = json.loads(cleaned)

            # Ensure confidence_breakdown exists with defaults
            if "confidence_breakdown" not in result:
                result["confidence_breakdown"] = {
                    "traceback_clarity": result.get("fix", {}).get("confidence", 0.5),
                    "code_context_quality": result.get("fix", {}).get("confidence", 0.5),
                    "fix_certainty": result.get("fix", {}).get("confidence", 0.5),
                    "reasoning": "Confidence breakdown not provided by model"
                }

            return (result, token_usage)

        except json.JSONDecodeError:
            error_result["root_cause"] = "Parse error"
            error_result["explanation"] = raw_response
            return (error_result, token_usage)

    except Exception as e:
        error_result["explanation"] = f"Analysis error: {str(e)}"
        return (error_result, default_usage)


def generate_report(result: dict, traceback: str, filepath: str, severity: str) -> str:
    """
    Generate a markdown report from analysis results.

    Returns a formatted markdown string.
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        root_cause = result.get("root_cause", "Unknown")
        explanation = result.get("explanation", "No explanation available")

        fix = result.get("fix", {})
        fix_description = fix.get("description", "No fix description")
        code_diff = fix.get("code_diff", "No diff available")
        confidence = fix.get("confidence", 0)

        similar_bugs = result.get("similar_bugs", [])
        bugs_list = "\n".join([f"- {bug}" for bug in similar_bugs]) if similar_bugs else "- None identified"

        github_issue = result.get("github_issue", {})
        issue_title = github_issue.get("title", "Bug: Unknown")
        issue_body = github_issue.get("body", "No issue body")

        report = f"""# Bug Analysis Report
**Generated:** {timestamp}
**Severity:** {severity}
**File:** {filepath}

## Root Cause
{root_cause}

## Explanation
{explanation}

## Suggested Fix
{fix_description}

```diff
{code_diff}
```

**Confidence:** {confidence:.0%}

## Similar Bug Patterns
{bugs_list}

## GitHub Issue Draft
**Title:** {issue_title}

{issue_body}

---
*Generated by AgentDebugger — github.com/ANUVIK2401*
"""
        return report

    except Exception as e:
        return f"# Error Generating Report\n\nFailed to generate report: {str(e)}"
