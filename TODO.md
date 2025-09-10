# pytp Enhancement TODO List

## Session Summary & Critical Findings (2025-09-01)

### Current Deployment Status
- **Production System**: 50GB RAM server with LTO-9 (18TB) and LTO-6 (2.5TB) drives
- **Configuration**: Using `/data-extern/Backup/tmp/` for tar_dir and snapshots
- **Testing Results**: Successfully backing up large video files (300GB+) with minimal rewrites

### Key Issues Discovered

#### 1. Buffer Underrun Problem (CRITICAL)
- **Issue**: mbuffer lacks proper flow control - no "low water mark" feature
- **Symptom**: Buffer repeatedly hits 0% even with large buffers (24-48GB)
- **Root Cause**: Inconsistent disk I/O speeds (0-511 MB/s) vs steady tape write (250-380 MB/s)
- **Impact**: Causes tape shoe-shining, leading to rewrites and reduced tape life
- **Current Workaround**: Using larger buffers (24-32GB) with higher thresholds (35-40%)

#### 2. Memory Management Issues
- **Problem**: Requesting buffers larger than available RAM causes OOM killer
- **Example**: 48GB buffer on 50GB system triggered systemd-oomd
- **Solution**: Check available RAM before setting buffer size, use max 60% of available

#### 3. Strategy-Specific Limitations
- **Direct Strategy**: No log file generation (only console output)
- **Tar Strategy**: Requires full disk space for intermediate files
- **Both**: No automatic tape spanning when full

### Successful Configurations Tested

#### For 50GB RAM System:
```bash
# Conservative (most stable)
pytp backup --strategy direct --memory_buffer 20 --memory_buffer_percent 35 /data/Videos/

# Optimal (good balance)
pytp backup --strategy direct --memory_buffer 24 --memory_buffer_percent 40 /data/Videos/

# After stopping VMs (42GB available)
pytp backup --strategy direct --memory_buffer 30 --memory_buffer_percent 35 /data/Videos/
```

### Tape Error Monitoring Tools Developed
```bash
# Script created at /pgm/scripts/tape_diagnostics.sh
# Captures: mt status, sg_logs write/read errors, tape usage
# Key metric: "Total write retries" - indicates buffer underruns
```

### Metadata Management Insights
- **Current**: JSON files in snapshot_dir track all backed up files
- **Location**: `/data-extern/Backup/tmp/snapshots/_backup.json`
- **Contents**: Full file list with paths, sizes, mtimes, tape positions
- **Issue**: Naming inconsistent without --job parameter

### Recommended Two-Tier Backup Strategy
1. **Archiware**: Daily incrementals, complex scheduling (short-term, on-site)
2. **pytp**: Yearly archives with tar format (long-term, off-site, vendor-independent)

### Proposed Buffer Solutions

#### Immediate Fix - Double Buffering with Named Pipes:
```bash
mkfifo /tmp/tape_buffer
tar -cvf - -T filelist | mbuffer -m 12G -P 80 -o /tmp/tape_buffer &
mbuffer -i /tmp/tape_buffer -m 12G -P 20 -L -o /dev/nst0
```

#### Better Solution - Use 'buffer' with Watermarks:
```bash
tar -cvf - /data/Filme | buffer -S 24G -p 75 -l 90 -o /dev/nst0
# -p 75: Pause input at 75% full
# -l 90: Resume at 90% empty
```

### Database Schema Requirements
- Need SQLite with WAL mode for concurrent access (two drives simultaneously)
- Track backup chains (full + incrementals)
- Support pool-based tape management
- Enable quick file location queries across multiple tapes

### Critical Commands for Next Session
```bash
# Check available memory before backup
free -h

# Monitor backup performance
watch -n 2 'free -h; ps aux | grep -E "mbuffer|tar" | grep -v grep'

# Check tape errors after backup
sg_logs --page=0x02 /dev/nst0 | grep "Total write retries"

# View metadata
cat /data-extern/Backup/tmp/snapshots/_backup.json | jq '.[0].files | keys | length'
```

## Current Limitations & Immediate Fixes

### Tape Spanning / Out of Space Handling
- [ ] Currently no automatic handling when tape is full
- [ ] Need to detect EOT (End of Tape) conditions
- [ ] Implement tape spanning across multiple volumes
- [ ] Add prompts for manual tape changes when autoloader unavailable
- [ ] Handle write errors gracefully with retry logic

### Error Logging & Monitoring
- [ ] Capture tape hardware errors (SCSI sense data)
- [ ] Log rewrites and buffer underruns
- [ ] Add comprehensive logging for all strategies (not just tar/dd)
- [ ] Implement real-time monitoring dashboard
- [ ] Add email/webhook alerts for critical errors

## Architecture Improvements

### Database Migration (Priority: High)
- [ ] Replace JSON metadata with SQLite database
- [ ] Design schema:
  ```sql
  - pools (pool_id, pool_name, retention_policy, type)
  - volumes (volume_id, label, pool_id, capacity, used_space, status, location)
  - jobs (job_id, job_name, pool_id, schedule, strategy, directories)
  - backups (backup_id, job_id, volume_id, start_time, end_time, status, size)
  - files (file_id, backup_id, filepath, size, mtime, tape_position)
  - tape_errors (error_id, volume_id, timestamp, error_type, details)
  ```
- [ ] Create migration script from existing JSON files
- [ ] Add database backup to backup routine
- [ ] Implement database integrity checks

### Pool & Volume Management (Priority: High)
Following Archiware-like architecture:
- [ ] Implement Pool concept:
  - Pools contain multiple volumes (tapes)
  - Define retention policies per pool
  - Support different pool types (daily, weekly, monthly, archive)
- [ ] Volume management:
  - Track volume status (empty, appendable, full, error)
  - Automatic volume selection from pool
  - Volume expiration and recycling
  - Import/export slot management
- [ ] Multi-tape spanning:
  - Continue backup across volumes in same pool
  - Handle tape changes (automatic via library or manual)
  - Track file fragments across multiple tapes

### Job Management System
- [ ] Job definitions:
  - Source directories
  - Target pool
  - Backup strategy (direct/tar/dd)
  - Retention policy
  - Pre/post scripts
- [ ] Scheduling:
  - Integration with cron
  - Optional Airflow DAG generation
  - Job dependencies and chains
- [ ] Job history and reporting

## CLI Enhancements

### Query Commands
- [ ] `pytp find --file <path>` - Find which tape contains a file
- [ ] `pytp list --tape <label>` - List all files on a tape
- [ ] `pytp list --pool <name>` - List all tapes in a pool
- [ ] `pytp verify --tape <label>` - Verify tape contents against database
- [ ] `pytp status --job <name>` - Show job status and history
- [ ] `pytp inventory` - Full library inventory with tape locations

### Operational Commands
- [ ] `pytp pool create --name <name> --retention <days>`
- [ ] `pytp pool add-volume --pool <name> --tape <label>`
- [ ] `pytp job create --name <name> --pool <pool> --dirs <dirs>`
- [ ] `pytp job run --name <name>` - Manual job execution
- [ ] `pytp expire --pool <name>` - Mark expired tapes for recycling
- [ ] `pytp import --slot <n>` - Import tape from I/E slot

### Recovery Commands
- [ ] `pytp restore --file <path> --to <destination>`
- [ ] `pytp restore --tape <label> --to <destination>`
- [ ] `pytp restore --job <name> --date <date> --to <destination>`
- [ ] `pytp restore --verify` - Dry run showing what would be restored

## Configuration Enhancements

### Extended config.json
```json
{
  "database": "/var/lib/pytp/pytp.db",
  "pools": [
    {
      "name": "daily",
      "retention_days": 30,
      "strategy": "tar",
      "compression": true
    },
    {
      "name": "archive",
      "retention_days": 2555,
      "strategy": "direct",
      "compression": false
    }
  ],
  "alerts": {
    "email": "admin@example.com",
    "webhook": "https://hooks.slack.com/...",
    "on_error": true,
    "on_completion": true
  },
  "logging": {
    "level": "INFO",
    "file": "/var/log/pytp/pytp.log",
    "max_size": "100MB",
    "retain_days": 90
  }
}
```

## Performance Optimizations

- [ ] Parallel tar generation for multiple directories
- [ ] Configurable memory buffer sizing based on available RAM
- [ ] Automatic block size optimization per tape drive
- [ ] Compression options (gzip, lz4, zstd)
- [ ] Deduplication tracking (at file level)

## Testing & Documentation

- [ ] Unit tests for all major components
- [ ] Integration tests with mock tape device
- [ ] Stress testing for large datasets
- [ ] Performance benchmarking suite
- [ ] Complete API documentation
- [ ] Administrator guide
- [ ] Disaster recovery procedures

## Future Considerations

- [ ] Web UI for monitoring and management
- [ ] REST API for integration
- [ ] Cloud storage tier (AWS Glacier, Azure Archive)
- [ ] Encryption at rest support
- [ ] Multi-site replication
- [ ] Kubernetes operator for containerized deployments
- [ ] Prometheus metrics export
- [ ] Backup verification jobs (periodic restore tests)

## Current Bugs to Fix

- [ ] Direct strategy doesn't create log files
- [ ] Metadata file naming when no job/label specified
- [ ] tar strategy requires full space for intermediate files
- [ ] No graceful handling of keyboard interrupts during backup
- [ ] Memory buffer settings not validated against available RAM

## Notes on Tape Full Handling

Based on code analysis, current behavior when tape is full:
- **Direct strategy**: Would see mbuffer/tar errors but no automatic handling
- **Tar/DD strategy**: Write errors would occur, no continuation to next tape
- **README confirms**: "pytp isn't currently handling out of tape situations"

Proposed solution:
1. Monitor write operations for ENOSPC or tape full errors
2. If tape full detected:
   - Mark current tape as full in database
   - If library available: Load next tape from pool
   - If manual: Prompt user to change tape
   - Continue backup from point of interruption
3. Update metadata to track files spanning multiple tapes


# Last Status


```
  The Problem:

  mbuffer doesn't have a "low water mark" feature - it keeps draining even at 0% until input stops completely. This causes tape thrashing.

  Solutions:

  1. Use double-buffering with named pipes (immediate fix):

  # Create a named pipe
  mkfifo /tmp/tape_buffer

  # Terminal 1: First stage with aggressive buffering
  tar -cvf - -T /data-extern/Backup/tmp/tars/filelist -b 524288 | \
    mbuffer -m 12G -P 80 -o /tmp/tape_buffer &

  # Terminal 2: Second stage to tape
  mbuffer -i /tmp/tape_buffer -m 12G -P 20 -L -o /dev/nst0

  The -L flag makes second mbuffer wait when buffer is low!

  2. Modify pytp to use better buffering strategy:

  We need to add a low-water mark feature. Instead of current command:
  tar | mbuffer -P 40 -m 24G -o /dev/nst0

  Use:
  tar | mbuffer -P 40 -m 24G -l /var/log/mbuffer.log | \
    pv -L 250M | \
    mbuffer -m 12G -P 20 -o /dev/nst0

  The pv -L 250M rate-limits to prevent buffer drain.

  3. Switch to buffer with watermarks (best long-term):

  Use buffer command instead of mbuffer:
  tar -cvf - /data/Filme | \
    buffer -S 24G -p 75 -l 90 -o /dev/nst0
  - -p 75: Pause input at 75% full
  - -l 90: Resume at 90% empty

  4. For now, try the tar strategy:

  Since your disk I/O is inconsistent:
  pytp backup --strategy tar /data/Filme/
  This pre-creates tar files, eliminating the I/O variability.

  The fundamental issue is mbuffer lacks proper flow control. We need to update pytp to use a better buffering strategy with high/low watermarks.
```