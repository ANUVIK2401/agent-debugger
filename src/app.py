import streamlit as st
import os
from analyzer import (
    load_env, fetch_github_context, analyze_with_langchain,
    generate_report, extract_error_type
)
from datetime import datetime
import pandas as pd

st.set_page_config(
    page_title="AgentDebugger",
    page_icon="🐛",
    layout="wide"
)

load_env()

# Session state initialization
if "has_result" not in st.session_state:
    st.session_state.has_result = False
if "result" not in st.session_state:
    st.session_state.result = None
if "token_usage" not in st.session_state:
    st.session_state.token_usage = None
if "history" not in st.session_state:
    st.session_state.history = []
if "analyses_count" not in st.session_state:
    st.session_state.analyses_count = 0
if "github_data" not in st.session_state:
    st.session_state.github_data = None
if "current_report" not in st.session_state:
    st.session_state.current_report = None
if "error_patterns" not in st.session_state:
    st.session_state.error_patterns = {}
if "batch_results" not in st.session_state:
    st.session_state.batch_results = None
if "batch_mode" not in st.session_state:
    st.session_state.batch_mode = False

# ── SIDEBAR ──────────────────────────────────────
with st.sidebar:
    st.title("AgentDebugger 🐛")
    st.caption("Powered by LangChain + GPT-4o-mini")
    st.divider()

    # Batch mode toggle
    batch_mode = st.toggle("🔁 Batch Mode", value=st.session_state.batch_mode, key="batch_toggle")
    st.session_state.batch_mode = batch_mode

    st.divider()

    st.metric("Analyses Run", st.session_state.analyses_count)

    if st.session_state.has_result and st.session_state.token_usage:
        st.subheader("Token Usage")
        usage = st.session_state.token_usage
        st.text(f"Prompt tokens: {usage['prompt_tokens']}")
        st.text(f"Completion tokens: {usage['completion_tokens']}")
        st.text(f"Total tokens: {usage['total_tokens']}")
        st.text(f"Estimated cost: ${usage['estimated_cost_usd']:.5f}")

    st.divider()

    # Error Intelligence Section
    if len(st.session_state.error_patterns) > 1:
        st.subheader("🧠 Error Intelligence")
        try:
            # Find most common error
            top_error = max(st.session_state.error_patterns,
                           key=st.session_state.error_patterns.get)
            top_count = st.session_state.error_patterns[top_error]
            st.write(f"Most common: **{top_error}** ({top_count}x)")

            # Bar chart of error frequencies
            df = pd.DataFrame({
                "Error Type": list(st.session_state.error_patterns.keys()),
                "Count": list(st.session_state.error_patterns.values())
            })
            df = df.set_index("Error Type")
            st.bar_chart(df, height=150)
        except Exception:
            pass
        st.divider()

    st.subheader("Recent Analyses")
    for idx, item in enumerate(st.session_state.history):
        label = f"{item['severity'][:2]} {item['traceback_preview'][:40]}..."
        if st.button(label, key=f"history_{idx}", use_container_width=True):
            st.session_state.has_result = True
            st.session_state.result = item["result"]
            st.session_state.token_usage = item["token_usage"]
            st.session_state.github_data = item.get("github_data")
            st.session_state.current_report = item.get("report")
            st.session_state.batch_results = None
            st.rerun()

# ── MAIN AREA ────────────────────────────────────
if "OPENAI_API_KEY" not in os.environ:
    st.error("Set OPENAI_API_KEY in your .env file")
    st.code("OPENAI_API_KEY=sk-...")
    st.stop()

left_col, right_col = st.columns([5, 7])

# LEFT COLUMN - Input
with left_col:
    st.subheader("📋 Input")

    sample_traceback = '''Traceback (most recent call last):
  File "app/main.py", line 42, in process_request
    result = calculate_value(data)
  File "app/utils.py", line 15, in calculate_value
    return data["value"] / data["divisor"]
KeyError: 'divisor' '''

    if batch_mode:
        traceback_input = st.text_area(
            "Paste multiple tracebacks separated by '---'",
            height=300,
            placeholder=sample_traceback + "\n---\n" + sample_traceback
        )
    else:
        traceback_input = st.text_area(
            "Paste traceback or error log",
            height=220,
            placeholder=sample_traceback
        )

    repo_url = st.text_input(
        "GitHub repo URL (optional)",
        placeholder="https://github.com/user/repo"
    )

    sub_col1, sub_col2 = st.columns(2)
    with sub_col1:
        branch = st.text_input("Branch", value="main")
    with sub_col2:
        severity = st.selectbox(
            "Severity",
            ["🔴 Critical", "🟠 High", "🟡 Medium", "🟢 Low"]
        )

    analyze_btn = st.button("🔍 Analyze", type="primary", use_container_width=True)

# Helper function to render single result
def render_result(result, github_data, token_usage, severity_val, show_download=True):
    """Render a single analysis result."""
    try:
        st.subheader("🎯 Results")

        # Calculate overall confidence from breakdown
        breakdown = result.get("confidence_breakdown", {})
        if breakdown:
            avg_confidence = (
                breakdown.get("traceback_clarity", 0) +
                breakdown.get("code_context_quality", 0) +
                breakdown.get("fix_certainty", 0)
            ) / 3
        else:
            avg_confidence = result.get("fix", {}).get("confidence", 0)

        metric_cols = st.columns(3)
        with metric_cols[0]:
            st.metric("Severity", severity_val.split()[0])
        with metric_cols[1]:
            st.metric("Confidence", f"{avg_confidence:.0%}")
        with metric_cols[2]:
            st.metric("Status", "✅ Done")

        st.info(f"**Root Cause:** {result.get('root_cause', 'Unknown')}")

        # Code context with real line numbers
        if github_data and github_data.get("code_display"):
            filepath = github_data.get('filepath', 'unknown')
            start_line = github_data.get('start_line', 0)
            end_line = github_data.get('end_line', 0)
            error_line = github_data.get('error_line', 0)

            st.subheader(f"📁 Code Context")
            st.caption(f"📍 {filepath} · Lines {start_line}–{end_line} · Error at line {error_line}")
            st.code(github_data["code_display"], language="python")

        st.subheader("💡 Explanation")
        st.write(result.get("explanation", "No explanation available"))

        # Confidence Breakdown Panel
        with st.expander("📊 Confidence Breakdown", expanded=False):
            try:
                breakdown = result.get("confidence_breakdown", {})
                cb_cols = st.columns(3)
                with cb_cols[0]:
                    tc = breakdown.get("traceback_clarity", 0)
                    st.write("**Traceback Clarity**")
                    st.progress(tc)
                    st.caption(f"{tc:.0%}")
                with cb_cols[1]:
                    ccq = breakdown.get("code_context_quality", 0)
                    st.write("**Code Context Quality**")
                    st.progress(ccq)
                    st.caption(f"{ccq:.0%}")
                with cb_cols[2]:
                    fc = breakdown.get("fix_certainty", 0)
                    st.write("**Fix Certainty**")
                    st.progress(fc)
                    st.caption(f"{fc:.0%}")
                reasoning = breakdown.get("reasoning", "No reasoning provided")
                st.caption(f"💭 {reasoning}")
            except Exception:
                st.write("Confidence breakdown not available")

        with st.expander("🔧 Suggested Fix", expanded=True):
            fix = result.get("fix", {})
            st.write(fix.get("description", "No description"))
            st.code(fix.get("code_diff", "No diff available"), language="diff")
            conf = fix.get("confidence", 0)
            st.progress(conf)
            st.caption(f"Confidence: {conf:.0%}")

        with st.expander("⚠️ Similar Bug Patterns"):
            similar_bugs = result.get("similar_bugs", [])
            if similar_bugs:
                for bug in similar_bugs:
                    st.warning(f"⚠️ {bug}")
            else:
                st.write("No similar patterns identified")

        with st.expander("📝 GitHub Issue Draft"):
            github_issue = result.get("github_issue", {})
            st.text_input("Issue Title", value=github_issue.get("title", ""), key=f"issue_title_{id(result)}")
            st.text_area("Issue Body", value=github_issue.get("body", ""), height=200, key=f"issue_body_{id(result)}")
            st.caption("Copy above → paste into GitHub Issues")

        # Download button
        if show_download and st.session_state.current_report:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                label="📥 Download Report",
                data=st.session_state.current_report,
                file_name=f"debug_report_{timestamp}.md",
                mime="text/markdown",
                use_container_width=True
            )

    except Exception as e:
        st.error(f"Error rendering result: {str(e)}")


# RIGHT COLUMN - Results
with right_col:
    # Batch mode results
    if st.session_state.batch_results:
        batch = st.session_state.batch_results
        st.subheader("🔁 Batch Analysis Results")

        # Summary
        n_errors = len(batch["results"])
        avg_conf = sum(r.get("fix", {}).get("confidence", 0) for r in batch["results"]) / n_errors if n_errors > 0 else 0
        total_cost = sum(u.get("estimated_cost_usd", 0) for u in batch["usages"])

        st.success(f"**{n_errors} errors analyzed** · Avg confidence: {avg_conf:.0%} · Total cost: ${total_cost:.5f}")

        # Each result in expander
        for i, (res, usage, tb) in enumerate(zip(batch["results"], batch["usages"], batch["tracebacks"])):
            root_cause = res.get("root_cause", "Unknown")[:50]
            with st.expander(f"Error {i+1}: {root_cause}...", expanded=(i == 0)):
                render_result(res, batch["github_data"], usage, severity, show_download=False)

    # Single mode results
    elif st.session_state.has_result and st.session_state.result:
        render_result(
            st.session_state.result,
            st.session_state.github_data,
            st.session_state.token_usage,
            severity,
            show_download=True
        )

# ── ANALYSIS LOGIC ───────────────────────────────
if analyze_btn:
    if not traceback_input.strip():
        st.warning("Please paste a traceback")
        st.stop()

    try:
        # Get previous error patterns for intelligence
        prev_patterns = list(st.session_state.error_patterns.keys())[:3]

        if batch_mode:
            # Batch mode: split by ---
            tracebacks = [t.strip() for t in traceback_input.split("---") if t.strip()]

            if not tracebacks:
                st.warning("No valid tracebacks found")
                st.stop()

            results = []
            usages = []
            github_data = {"code": None, "error": "Batch mode"}

            # Fetch GitHub context once if URL provided
            if repo_url.strip():
                with st.spinner("🔍 Fetching GitHub context..."):
                    github_data = fetch_github_context(repo_url, branch, tracebacks[0])

            # Analyze each traceback
            for i, tb in enumerate(tracebacks):
                with st.spinner(f"🧠 Analyzing error {i+1}/{len(tracebacks)}..."):
                    code_for_analysis = github_data.get("code") or ""
                    filepath = github_data.get("filepath") or "unknown"
                    result, token_usage = analyze_with_langchain(
                        tb, code_for_analysis, filepath, severity, prev_patterns
                    )
                    results.append(result)
                    usages.append(token_usage)

                    # Track error pattern
                    error_type = extract_error_type(tb)
                    if error_type != "Unknown":
                        st.session_state.error_patterns[error_type] = \
                            st.session_state.error_patterns.get(error_type, 0) + 1

            # Store batch results
            st.session_state.batch_results = {
                "results": results,
                "usages": usages,
                "tracebacks": tracebacks,
                "github_data": github_data
            }
            st.session_state.has_result = False
            st.session_state.analyses_count += len(tracebacks)

            # Combined token usage for sidebar
            total_usage = {
                "prompt_tokens": sum(u["prompt_tokens"] for u in usages),
                "completion_tokens": sum(u["completion_tokens"] for u in usages),
                "total_tokens": sum(u["total_tokens"] for u in usages),
                "estimated_cost_usd": sum(u["estimated_cost_usd"] for u in usages)
            }
            st.session_state.token_usage = total_usage

            st.rerun()

        else:
            # Single mode
            # Fetch GitHub context
            github_data = {"code": None, "code_display": None, "error": "No URL provided"}
            if repo_url.strip():
                with st.spinner("🔍 Fetching GitHub context..."):
                    github_data = fetch_github_context(repo_url, branch, traceback_input)

            # Run LangChain analysis
            with st.spinner("🧠 Running LangChain analysis..."):
                code_for_analysis = github_data.get("code") or ""
                filepath = github_data.get("filepath") or "unknown"
                result, token_usage = analyze_with_langchain(
                    traceback_input, code_for_analysis, filepath, severity, prev_patterns
                )

            # Generate report
            report = generate_report(result, traceback_input, filepath, severity)

            # Track error pattern
            error_type = extract_error_type(traceback_input)
            if error_type != "Unknown":
                st.session_state.error_patterns[error_type] = \
                    st.session_state.error_patterns.get(error_type, 0) + 1

            # Store in session state
            st.session_state.has_result = True
            st.session_state.result = result
            st.session_state.token_usage = token_usage
            st.session_state.github_data = github_data
            st.session_state.current_report = report
            st.session_state.batch_results = None
            st.session_state.analyses_count += 1

            # Add to history (prepend, max 5)
            history_item = {
                "timestamp": datetime.now().isoformat(),
                "severity": severity,
                "traceback_preview": traceback_input[:50],
                "result": result,
                "token_usage": token_usage,
                "github_data": github_data,
                "report": report
            }
            st.session_state.history.insert(0, history_item)
            st.session_state.history = st.session_state.history[:5]

            st.rerun()

    except Exception as e:
        st.error(f"Error: {str(e)}")
