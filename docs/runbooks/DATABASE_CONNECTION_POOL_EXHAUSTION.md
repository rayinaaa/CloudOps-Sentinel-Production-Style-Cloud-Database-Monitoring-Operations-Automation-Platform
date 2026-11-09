# CloudOps Sentinel: Database Connection Pool Exhaustion Runbook 📘
**Standard Operating Procedure (SOP):** SRE-DB-CONN-002  
**Severity Level:** CRITICAL (P1) / HIGH (P2)  
**Target Metric:** `pool_saturation_pct >= 80%` (Warning) or `>= 90%` (Critical)  
**Target Alert Rule:** `DatabaseConnectionPoolWarning` / `DatabaseConnectionPoolCritical`  

---

## 1. Overview & Immediate Impact
When database connection pool saturation breaches **90%**, new incoming client connections are placed into wait queues or immediately rejected with:
`FATAL: remaining connection slots are reserved for non-replication superuser connections`

This runbook guides on-call engineers through immediate triage, connection draining, lock release, and pool reconfiguration.

---

## 2. Immediate Diagnostic Procedure (< 2 Minutes)

Execute the CloudOps Sentinel connection monitor script to identify connection states and active backends:

```bash
# 1. Run the connection monitor probe
./scripts/connection_monitor.sh
```

Alternatively, query PostgreSQL directly via `psql`:

```sql
-- Query connection state breakdown across all client backends
SELECT 
    state, 
    count(*), 
    current_setting('max_connections')::int AS max_limit,
    round(count(*)::numeric / current_setting('max_connections')::numeric * 100, 1) AS pct_of_max
FROM pg_stat_activity
WHERE backend_type = 'client backend'
GROUP BY state;
```

---

## 3. Identifying the Root Cause

### Scenario A: Lingering `idle in transaction` Connections (Most Common)
Applications opening a transaction (`BEGIN`) without committing or rolling back hold row/table locks and prevent vacuuming:

```sql
-- Find connections lingering in open transactions longer than 60 seconds
SELECT 
    pid, 
    usename, 
    client_addr, 
    round(extract(epoch from (now() - state_change))::numeric, 1) AS idle_sec,
    query
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND state_change < now() - INTERVAL '60 seconds'
ORDER BY idle_sec DESC;
```

### Scenario B: Long-Running Blocked Queries
Queries waiting on row locks or table locks:

```sql
-- Identify blocked queries and blocking PIDs
SELECT 
    blocked.pid AS blocked_pid,
    blocked.usename AS blocked_user,
    blocking.pid AS blocking_pid,
    blocking.usename AS blocking_user,
    blocked.query AS blocked_query,
    blocking.query AS blocking_query
FROM pg_stat_activity blocked
JOIN pg_locks bl_lock ON blocked.pid = bl_lock.pid
JOIN pg_locks b_lock ON bl_lock.locktype = b_lock.locktype 
    AND bl_lock.database IS NOT DISTINCT FROM b_lock.database
    AND bl_lock.relation IS NOT DISTINCT FROM b_lock.relation
    AND bl_lock.page IS NOT DISTINCT FROM b_lock.page
    AND bl_lock.tuple IS NOT DISTINCT FROM b_lock.tuple
    AND bl_lock.virtualxid IS NOT DISTINCT FROM b_lock.virtualxid
    AND bl_lock.transactionid IS NOT DISTINCT FROM b_lock.transactionid
    AND bl_lock.classid IS NOT DISTINCT FROM b_lock.classid
    AND bl_lock.objid IS NOT DISTINCT FROM b_lock.objid
    AND bl_lock.objsubid IS NOT DISTINCT FROM b_lock.objsubid
    AND bl_lock.pid != b_lock.pid
JOIN pg_stat_activity blocking ON b_lock.pid = blocking.pid
WHERE NOT bl_lock.granted;
```

---

## 4. Remediation Steps

### Step 4.1: Graceful Termination of Idle-in-Transaction Backends
Terminate rogue idle transactions older than 5 minutes:

```sql
-- Gracefully cancel currently executing queries first
SELECT pg_cancel_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND state_change < now() - INTERVAL '5 minutes';

-- If cancel does not release the connection within 10 seconds, forcefully terminate
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND state_change < now() - INTERVAL '5 minutes';
```

### Step 4.2: Bulk Emergency Connection Eviction
If the cluster is about to collapse under 98% saturation:

```sql
-- Evict all non-essential client connections except the current monitoring session
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE pid <> pg_backend_pid()
  AND usename NOT IN ('postgres', 'sentinel_admin')
  AND state = 'idle';
```

---

## 5. Post-Incident Hardening & Prevention

1. **Configure PostgreSQL Idle Session Timeout:**
   In PostgreSQL parameter configuration (`postgresql.conf` or AWS RDS DB Parameter Group):
   ```sql
   ALTER SYSTEM SET idle_in_transaction_session_timeout = '60000'; -- 60 seconds
   SELECT pg_reload_conf();
   ```
2. **Review Client Pool Sizing:**
   Ensure client application connection pools are sized according to the standard formula:
   $$\text{Pool Size} = ((\text{Core Count} \times 2) + \text{Effective Spindle Count})$$
   Avoid setting `pool_size` arbitrarily high (e.g. 100 per container instance).

