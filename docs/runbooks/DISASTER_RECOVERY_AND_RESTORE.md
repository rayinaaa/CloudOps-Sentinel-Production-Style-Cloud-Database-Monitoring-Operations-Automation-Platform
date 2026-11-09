# CloudOps Sentinel: Disaster Recovery & Database Restoration Runbook 📘
**Standard Operating Procedure (SOP):** SRE-DR-RES-003  
**Severity Level:** CRITICAL (P1)  
**Recovery Objectives:** Recovery Time Objective (RTO) $\le 15$ minutes; Recovery Point Objective (RPO) $\le 1$ hour  
**Target Architecture:** PostgreSQL 16 on Docker / AWS RDS  

---

## 1. Safety Policy & Cardinal Rules
1. **NEVER restore directly into a live primary database without explicit Change Advisory Board (CAB) signoff.**
2. **Always perform preflight validation** (file presence, byte size $> 0$, SHA256 integrity checksum match) before invoking restoration utilities.
3. **Always test restore into an isolated staging catalog** (`sentinel_dr_test`) to verify schema and data integrity prior to promoting to production.

---

## 2. Automated Non-Destructive Disaster Recovery Drill

CloudOps Sentinel provides the [`scripts/restore.sh`](file:///c:/Users/rayin/OneDrive/Desktop/C/scripts/restore.sh) utility with built-in safety interlocks:

```bash
# 1. Locate latest verified database dump
LATEST_BACKUP=$(ls -t backups/*.dump | head -n 1)
echo "Selected backup: ${LATEST_BACKUP}"

# 2. Execute automated non-destructive restore into isolated test database
./scripts/restore.sh "${LATEST_BACKUP}" sentinel_dr_test
```

### Safety Interlock Test
Attempting to restore into the primary database will be safely intercepted and rejected:
```bash
# Must return exit code 1 (Safety Violation)
./scripts/restore.sh "${LATEST_BACKUP}" sentinel_db
```

---

## 3. Restoring from Amazon S3 Backup Snapshots

When recovering from an S3 disaster recovery snapshot:

```bash
# 1. List available S3 snapshots ordered by timestamp
aws s3 ls "s3://${S3_BACKUP_BUCKET}/db-snapshots/" --recursive | sort | tail -n 5

# 2. Download the chosen snapshot and its SHA256 sidecar
SNAPSHOT_NAME="sentinel_db_20261108_020000.dump.gz"
aws s3 cp "s3://${S3_BACKUP_BUCKET}/db-snapshots/${SNAPSHOT_NAME}" /tmp/${SNAPSHOT_NAME}
aws s3 cp "s3://${S3_BACKUP_BUCKET}/db-snapshots/${SNAPSHOT_NAME}.sha256" /tmp/${SNAPSHOT_NAME}.sha256

# 3. Validate SHA256 checksum integrity
EXPECTED_SHA=$(awk '{print $1}' /tmp/${SNAPSHOT_NAME}.sha256)
ACTUAL_SHA=$(sha256sum /tmp/${SNAPSHOT_NAME} | awk '{print $1}')

if [ "${EXPECTED_SHA}" != "${ACTUAL_SHA}" ]; then
    echo "[CRITICAL] Checksum mismatch! Corrupted snapshot. Do not proceed." >&2
    exit 1
fi
echo "[INFO] Checksum verified: ${ACTUAL_SHA}"

# 4. Decompress snapshot
gunzip -k /tmp/${SNAPSHOT_NAME}
DUMP_FILE="/tmp/${SNAPSHOT_NAME%.gz}"

# 5. Restore into target test database
pg_restore -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d sentinel_dr_test \
    --clean --if-exists --no-owner --no-privileges "${DUMP_FILE}"
```

---

## 4. Post-Restoration Data Verification Checklist

Run diagnostic queries against the restored test database to confirm data integrity:

```sql
-- 1. Verify schema tables exist
SELECT table_name, table_type 
FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;

-- 2. Verify tenant counts match pre-incident records
SELECT status, count(*) 
FROM tenants 
GROUP BY status;

-- 3. Verify user seat allocations
SELECT count(*) AS total_users 
FROM app_users;

-- 4. Check database size parity
SELECT pg_size_pretty(pg_database_size('sentinel_dr_test')) AS restored_size;
```

---

## 5. Escalation Contacts & SLA Reporting
- **On-Call Lead:** SRE Tier 2 (`sre-oncall@cloudops-sentinel.io`)
- **Database Administrator:** CloudOps DBA Lead (`dba@cloudops-sentinel.io`)
- **Post-Mortem Requirement:** Mandatory within 24 hours of any P1 DR drill or failover event.

