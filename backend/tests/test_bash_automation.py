"""Test suite for CloudOps Sentinel Linux & Bash Automation Utilities.

Validates:
- scripts/health_check.sh
- scripts/backup.sh
- scripts/restore.sh (with critical safety guard enforcement)
- scripts/log_analyzer.py
- scripts/disk_monitor.sh
- scripts/connection_monitor.sh
"""

import json
import os
import shutil
import subprocess
import sys

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
BACKUP_DIR = os.path.join(REPO_ROOT, "backups")


def run_bash_command(command: str) -> subprocess.CompletedProcess:
    """Executes a bash command either directly on Linux/macOS or inside WSL on Windows."""
    if sys.platform.startswith("win"):
        if not shutil.which("wsl"):
            pytest.skip("WSL is required for bash automation tests on Windows")
        drive, rest = os.path.splitdrive(REPO_ROOT)
        drive_letter = drive.rstrip(":").lower()
        wsl_repo_root = f"/mnt/{drive_letter}" + rest.replace("\\", "/")
        full_command = f"cd {wsl_repo_root} && {command}"
        wsl_cmd = ["wsl", "-d", "Ubuntu-22.04", "bash", "-c", full_command]
        res = subprocess.run(
            wsl_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    else:
        if not shutil.which("bash"):
            pytest.skip("bash is required for bash automation tests")
        full_command = f"cd '{REPO_ROOT}' && {command}"
        res = subprocess.run(
            ["bash", "-c", full_command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=os.environ.copy(),
        )

    # Check if postgres client tools were missing on Linux runner
    if res.returncode != 0 and "command not found" in res.stderr:
        for tool in ("pg_isready", "psql", "pg_dump", "pg_restore"):
            if tool in res.stderr:
                pytest.skip(
                    f"PostgreSQL client tool '{tool}' not installed in this environment"
                )

    return res


# Backward compatibility alias
run_in_wsl = run_bash_command


def test_health_check_script():
    """Verifies health_check.sh returns exit code 0 and valid JSON telemetry."""
    cmd = "LATENCY_WARN_THRESHOLD_MS=2000 ./scripts/health_check.sh"
    res = run_bash_command(cmd)
    assert res.returncode == 0, f"health_check.sh failed: {res.stderr}"

    # Extract JSON line from output
    json_lines = [
        line for line in res.stdout.strip().split("\n") if line.startswith("{")
    ]
    assert len(json_lines) > 0, "Expected JSON telemetry output"
    data = json.loads(json_lines[-1])
    assert data["status"] == "HEALTHY"
    assert data["database"] in ("sentinel_db", "FREEPDB1")
    assert data["max_connections"] > 0


def test_backup_script():
    """Verifies backup.sh creates dump archive, sha256 checksum, and metadata."""
    cmd = "./scripts/backup.sh"
    res = run_bash_command(cmd)
    assert res.returncode == 0, f"backup.sh failed: {res.stderr}"
    assert "Backup completed successfully" in res.stdout
    assert "SHA256:" in res.stdout

    # Verify backup files exist
    dumps = [f for f in os.listdir(BACKUP_DIR) if f.endswith(".dump")]
    assert len(dumps) > 0
    latest_dump = sorted(dumps)[-1]
    assert os.path.exists(os.path.join(BACKUP_DIR, f"{latest_dump}.sha256"))
    assert os.path.exists(os.path.join(BACKUP_DIR, f"{latest_dump}.meta.json"))


def test_restore_script_safety_violation_guard():
    """Verifies restore.sh refuses execution if targeted against primary database."""
    cmd = "TARGET_TEST_DB=sentinel_db ./scripts/restore.sh ./backups/*.dump"
    res = run_bash_command(cmd)
    # Must exit with non-zero code 1
    assert res.returncode == 1
    assert "CRITICAL SAFETY VIOLATION PREVENTED" in res.stderr


def test_restore_script_into_test_database():
    """Verifies restore.sh restores cleanly into an isolated test database."""
    cmd = "./scripts/restore.sh ./backups/*.dump sentinel_dr_test"
    res = run_bash_command(cmd)
    assert res.returncode == 0, f"restore.sh failed: {res.stderr}"
    assert "DISASTER RECOVERY RESTORE DRILL SUCCESSFUL" in res.stdout

    json_lines = [
        line for line in res.stdout.strip().split("\n") if line.startswith("{")
    ]
    assert len(json_lines) > 0
    data = json.loads(json_lines[-1])
    assert data["restored_database"] == "sentinel_dr_test"
    assert data["tenant_count"] >= 8
    assert data["user_count"] >= 16


def test_log_analyzer_script():
    """Verifies log_analyzer.py aggregates logs and returns structured summary."""
    sample_log = (
        "2026-11-08 00:00:01 UTC [100] ERROR: duplicate key value violates unique constraint\n"
        "2026-11-08 00:00:02 UTC [101] LOG: duration: 650.5 ms statement: SELECT * FROM tenants;\n"
        "2026-11-08 00:00:03 UTC [102] LOG: checkpoint starting"
    )
    cmd = f"echo -n '{sample_log}' | python3 ./scripts/log_analyzer.py --json"
    res = run_bash_command(cmd)
    data = json.loads(res.stdout)
    assert data["total_lines_analyzed"] >= 3
    assert data["critical_issues"]["error_count"] == 1
    assert data["performance"]["slow_queries_count"] == 1


def test_disk_monitor_script():
    """Verifies disk_monitor.sh evaluates filesystem and database sizes."""
    cmd = "./scripts/disk_monitor.sh"
    res = run_bash_command(cmd)
    assert res.returncode == 0, f"disk_monitor.sh failed: {res.stderr}"

    # Extract JSON line
    json_lines = [
        line.strip()
        for line in res.stdout.strip().split("\n")
        if line.strip().startswith("{")
    ]
    assert len(json_lines) > 0
    data = json.loads(json_lines[-1])
    assert data["database_name"] in ("sentinel_db", "FREEPDB1")
    assert data["catalog_size_bytes"] > 0
    assert data["filesystem_percent_used"] >= 0


def test_connection_monitor_script():
    """Verifies connection_monitor.sh audits connection saturation."""
    cmd = "./scripts/connection_monitor.sh"
    res = run_bash_command(cmd)
    assert res.returncode == 0, f"connection_monitor.sh failed: {res.stderr}"

    json_lines = [
        line for line in res.stdout.strip().split("\n") if line.startswith("{")
    ]
    assert len(json_lines) > 0
    data = json.loads(json_lines[-1])
    assert data["max_connections"] > 0
    assert data["saturation_pct"] >= 0.0
