#!/usr/bin/env python3
"""CloudOps Sentinel - Automated Database & Platform Log Analyzer.

Role Alignment: Associate Cloud Operations Engineer - Telemetry & Troubleshooting
Parses PostgreSQL server logs and Sentinel application logs to detect:
- Error and Fatal patterns (deadlocks, OOM, auth failures)
- Slow query events (>500ms or log_min_duration_statement)
- Connection saturation errors ('too many clients')
- Structured summary generation for incident triage and PagerDuty/Slack routing
"""

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List, TextIO

# Operational Exit Codes
EXIT_CLEAN = 0
EXIT_ARG_ERROR = 1
EXIT_WARNING_THRESHOLD = 2
EXIT_CRITICAL_THRESHOLD = 3

# Regex Patterns for PostgreSQL & Application Logs
RE_SEVERITY = re.compile(r"\b(FATAL|PANIC|ERROR|WARNING|NOTICE|INFO|DEBUG)\b", re.IGNORECASE)
RE_SLOW_QUERY = re.compile(
    r"(?:duration:\s*([0-9.]+)\s*ms|mean_exec_time:\s*([0-9.]+))", re.IGNORECASE
)
RE_AUTH_FAILURE = re.compile(r"(?:authentication failed|role .* does not exist)", re.IGNORECASE)
RE_DEADLOCK = re.compile(r"(?:deadlock detected|lock timeout)", re.IGNORECASE)
RE_CONNECTION_LIMIT = re.compile(r"(?:too many clients|connection slots are reserved)", re.IGNORECASE)


def parse_log_stream(stream: TextIO, slow_threshold_ms: float = 500.0) -> Dict:
    """Parses incoming log stream and aggregates operational telemetry."""
    severity_counts = Counter()
    slow_queries: List[Dict] = []
    auth_failures: List[str] = []
    deadlock_events: List[str] = []
    connection_limit_events: List[str] = []
    error_samples: List[str] = []
    total_lines = 0

    for line in stream:
        total_lines += 1
        line_clean = line.strip()
        if not line_clean:
            continue

        # 1. Parse JSON log if line is JSON-formatted
        is_json = False
        if line_clean.startswith("{") and line_clean.endswith("}"):
            try:
                record = json.loads(line_clean)
                is_json = True
                level = str(record.get("level", record.get("log_level", "INFO"))).upper()
                severity_counts[level] += 1
                msg = str(record.get("event", record.get("message", "")))
                if level in ["ERROR", "CRITICAL"]:
                    error_samples.append(msg[:180])
            except json.JSONDecodeError:
                pass

        # 2. Parse Standard PostgreSQL text logs
        if not is_json:
            sev_match = RE_SEVERITY.search(line_clean)
            if sev_match:
                sev = sev_match.group(1).upper()
                severity_counts[sev] += 1
                if sev in ["ERROR", "FATAL", "PANIC"]:
                    error_samples.append(line_clean[:180])

        # 3. Detect Slow Query Executions
        slow_match = RE_SLOW_QUERY.search(line_clean)
        if slow_match:
            duration = float(slow_match.group(1) or slow_match.group(2) or 0.0)
            if duration >= slow_threshold_ms:
                slow_queries.append({"duration_ms": duration, "sample": line_clean[:200]})

        # 4. Detect Operational Faults
        if RE_AUTH_FAILURE.search(line_clean):
            auth_failures.append(line_clean[:180])
        if RE_DEADLOCK.search(line_clean):
            deadlock_events.append(line_clean[:180])
        if RE_CONNECTION_LIMIT.search(line_clean):
            connection_limit_events.append(line_clean[:180])

    # Distinct top error messages
    top_errors = Counter(error_samples).most_common(5)

    return {
        "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_lines_analyzed": total_lines,
        "severity_distribution": dict(severity_counts),
        "critical_issues": {
            "fatal_or_panic_count": severity_counts.get("FATAL", 0) + severity_counts.get("PANIC", 0),
            "error_count": severity_counts.get("ERROR", 0) + severity_counts.get("CRITICAL", 0),
            "deadlocks_count": len(deadlock_events),
            "connection_exhaustion_count": len(connection_limit_events),
            "auth_failures_count": len(auth_failures),
        },
        "performance": {
            "slow_queries_count": len(slow_queries),
            "slow_query_samples": slow_queries[:5],
        },
        "top_error_patterns": [{"pattern": err, "occurrences": count} for err, count in top_errors],
    }


def main():
    parser = argparse.ArgumentParser(
        description="CloudOps Sentinel Log Analyzer for PostgreSQL and CloudOps APIs"
    )
    parser.add_argument("--file", "-f", help="Path to log file (reads stdin if omitted)")
    parser.add_argument("--json", action="store_true", help="Output summary in JSON format")
    parser.add_argument(
        "--slow-threshold",
        type=float,
        default=500.0,
        help="Slow query duration threshold in milliseconds (default: 500)",
    )
    parser.add_argument(
        "--warn-error-count",
        type=int,
        default=5,
        help="Error count to trigger warning exit code (default: 5)",
    )

    args = parser.parse_args()

    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8", errors="replace") as f:
                results = parse_log_stream(f, args.slow_threshold)
        except Exception as e:
            sys.stderr.write(f"Error opening log file: {e}\n")
            sys.exit(EXIT_ARG_ERROR)
    else:
        if sys.stdin.isatty():
            sys.stderr.write("Reading from stdin (paste log lines and press Ctrl+D or pipe input)...\n")
        results = parse_log_stream(sys.stdin, args.slow_threshold)

    # Output Formatting
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        crit = results["critical_issues"]
        perf = results["performance"]
        print("======================================================================")
        print(" CLOUDOPS SENTINEL - DATABASE LOG ANALYSIS REPORT")
        print("======================================================================")
        print(f" Analyzed Lines:       {results['total_lines_analyzed']}")
        print(f" Fatal/Panic Events:   {crit['fatal_or_panic_count']}")
        print(f" Error Events:         {crit['error_count']}")
        print(f" Deadlocks Detected:   {crit['deadlocks_count']}")
        print(f" Auth Failures:        {crit['auth_failures_count']}")
        print(f" Conn Limit Breaches:  {crit['connection_exhaustion_count']}")
        print(f" Slow Queries (>={args.slow_threshold}ms): {perf['slow_queries_count']}")
        print("----------------------------------------------------------------------")
        print(" Severity Distribution:")
        for sev, count in results["severity_distribution"].items():
            print(f"   - {sev.ljust(10)}: {count}")
        if results["top_error_patterns"]:
            print("----------------------------------------------------------------------")
            print(" Top Offending Error Patterns:")
            for item in results["top_error_patterns"]:
                print(f"   [{item['occurrences']}x] {item['pattern']}")
        print("======================================================================")

    # Determine Exit Code
    crit = results["critical_issues"]
    if (
        crit["fatal_or_panic_count"] > 0
        or crit["deadlocks_count"] > 0
        or crit["connection_exhaustion_count"] > 0
    ):
        sys.exit(EXIT_CRITICAL_THRESHOLD)

    if crit["error_count"] >= args.warn_error_count or results["performance"]["slow_queries_count"] > 0:
        sys.exit(EXIT_WARNING_THRESHOLD)

    sys.exit(EXIT_CLEAN)


if __name__ == "__main__":
    main()

