from src.llm_clients.gemini_client import GeminiClient
from src.llm_clients.nvidia_client import NvidiaClient
from src.llm_clients.groq_client import GroqClient
from src.tools.file_ops import read_file, write_file
import os


class DebugWriterA:
    """Root Cause Analysis specialist."""
    def __init__(self):
        self.llm = GeminiClient()

    def analyze(self, error_input: str, context: str = "") -> str:
        prompt = f"""
You are a senior SRE performing Root Cause Analysis (RCA).

PROJECT CONTEXT:
{context}

ERROR / LOGS:
{error_input}

TASK:
1. Identify the most likely root cause.
2. Trace the error back to the originating component (app, infra, network, config).
3. Provide a step-by-step fix.
4. Rate severity: CRITICAL / HIGH / MEDIUM / LOW.

OUTPUT FORMAT:
SEVERITY: [level]
ROOT_CAUSE: [one-line summary]
ANALYSIS:
- [detailed point 1]
- [detailed point 2]
FIX:
```
[exact commands or code changes]
```
""".strip()
        return self.llm.call(prompt)


class DebugWriterB:
    """Security-focused debugger."""
    def __init__(self):
        self.llm = GroqClient()
    def analyze(self, error_input: str, context: str = "") -> str:
        prompt = f"""
You are a Security Engineer analyzing a production incident.

PROJECT CONTEXT:
{context}

ERROR / LOGS:
{error_input}

TASK:
1. Check if this error has security implications (exposed secrets, auth failures, injection).
2. Identify if any CVEs or known vulnerabilities are related.
3. Suggest a secure fix.

OUTPUT FORMAT:
SECURITY_RISK: [YES/NO]
ANALYSIS:
- [point 1]
- [point 2]
FIX:
```
[commands or code]
```
""".strip()
        return self.llm.call(prompt)


class DebugWriterC:
    """Performance-focused debugger."""
    def __init__(self):
        self.llm = NvidiaClient()

    def analyze(self, error_input: str, context: str = "") -> str:
        prompt = f"""
You are a Performance Engineer analyzing a production issue.

PROJECT CONTEXT:
{context}

ERROR / LOGS:
{error_input}

TASK:
1. Check if this is a performance-related issue (OOM, CPU throttle, connection pool, timeout).
2. Identify bottlenecks.
3. Suggest optimizations.

OUTPUT FORMAT:
PERF_ISSUE: [YES/NO]
ANALYSIS:
- [point 1]
- [point 2]
FIX:
```
[commands or config changes]
```
""".strip()
        return self.llm.call(prompt)


class DebugReviewer:
    """Synthesizes all 3 analyses into a unified incident report."""
    def __init__(self):
        self.llm = GeminiClient()
    def review_and_merge(self, analysis_a: str, analysis_b: str, analysis_c: str, validation_report: str = "") -> tuple[str, str]:
        feedback_section = ""
        if validation_report:
            feedback_section = f"""
ADDITIONAL USER FEEDBACK (MUST ADDRESS):
{validation_report}
"""
        prompt = f"""
You are a Lead SRE reviewing 3 independent analyses of a production incident.

ANALYSIS A (Root Cause):
{analysis_a}

ANALYSIS B (Security):
{analysis_b}

ANALYSIS C (Performance):
{analysis_c}
{feedback_section}
TASK:
1. Synthesize the findings into a single, actionable INCIDENT REPORT.
2. Prioritize the most impactful fix.
3. Note any security concerns.
4. Provide a clear remediation plan.
5. Address all user feedback points if any.

OUTPUT FORMAT:
REASONING:
- [key finding 1]
- [key finding 2]
- [key finding 3]

REPORT:
## Incident Report
**Severity:** [CRITICAL/HIGH/MEDIUM/LOW]
**Root Cause:** [summary]
**Security Impact:** [YES/NO - details]
**Performance Impact:** [YES/NO - details]

### Remediation Steps
1. [step 1]
2. [step 2]
3. [step 3]
""".strip()

        response = self.llm.call(prompt)
        try:
            if "REPORT:" in response:
                parts = response.split("REPORT:", 1)
                reasoning = parts[0].replace("REASONING:", "").strip()
                report = parts[1].strip()
                return (report, reasoning)
            return (response, "AI Review Completed")
        except Exception:
            return (analysis_a, "Fallback to Analysis A")


class DebugExecutor:
    """Saves the incident report to a file."""
    def run(self, content: str, project_path: str):
        directory = os.path.join(project_path, "debug_reports")
        os.makedirs(directory, exist_ok=True)
        import time
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(directory, f"incident_{timestamp}.md")
        write_file(path, content)
        print(f"✅ Wrote incident report to {path}")


class SelfHealer:
    """Auto-fix agent that applies code patches."""
    def __init__(self):
        self.llm = GeminiClient()
        
    def fix_code(self, file_content: str, error_log: str) -> str:
        """
        Attempts to fix the code based on the error log.
        Returns the new file content.
        """
        try:
            task = read_file("configs/prompts/debug/healer.md")
        except Exception:
            task = "You are a Patch Engineer. Fix the code based on the error."
            
        prompt = f"{task}\n\nERROR LOG:\n{error_log}\n\nBROKEN CODE:\n{file_content}"
        
        # Call LLM
        response = self.llm.call(prompt)
        
        # Cleanup response if it contains markdown code blocks despite instructions
        clean_response = response.replace("```python", "").replace("```javascript", "").replace("```", "").strip()
        return clean_response
