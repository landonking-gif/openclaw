#!/bin/bash
#
# PostgreSQL Database Backup Script
# Filename: postgresql_backup.sh
# Description: Automates daily PostgreSQL backups with compression and rotation
# Author: Beta Manager (coding-3)
# Date: 2026-03-08
#

# ============================================================================
# CONFIGURATION - Can be overridden via environment variables
# ============================================================================

# Database connection settings
DB_NAME="${DB_NAME:-mydatabase}"          # Database name to backup
DB_USER="${DB_USER:-postgres}"            # PostgreSQL user
DB_HOST="${DB_HOST:-localhost}"           # Database host
DB_PORT="${DB_PORT:-5432}"                # Database port
DB_PASSWORD="${DB_PASSWORD:-}"            # PostgreSQL password (optional)

# Backup settings
BACKUP_DIR="${BACKUP_DIR:-/var/backups/postgresql}"  # Backup directory
RETENTION_DAYS="${RETENTION_DAYS:-30}"               # Days to keep backups

# Logging
LOG_FILE="${BACKUP_DIR}/backup.log"       # Log file location

# ============================================================================
# SCRIPT CONSTANTS
# ============================================================================

# Exit codes
EXIT_SUCCESS=0
EXIT_INVALID_ARGS=1
EXIT_MISSING_DEPS=2
EXIT_BACKUP_DIR_ERROR=3
EXIT_DB_CONNECTION_ERROR=4
EXIT_BACKUP_FAILED=5
EXIT_CLEANUP_FAILED=6

# ============================================================================
# FUNCTIONS
# ============================================================================

# Print usage information
usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

PostgreSQL Database Backup Script

This script creates compressed backups of a PostgreSQL database and manages
backup retention by deleting old backups.

OPTIONS:
    -h, --help          Show this help message and exit
    -c, --config        Show current configuration and exit
    --dry-run          Show what would be done without executing

ENVIRONMENT VARIABLES:
    DB_NAME            Database name (default: mydatabase)
    DB_USER            PostgreSQL username (default: postgres)
    DB_HOST            Database host (default: localhost)
    DB_PORT            Database port (default: 5432)
    DB_PASSWORD        PostgreSQL password (optional)
    BACKUP_DIR         Backup directory (default: /var/backups/postgresql)
    RETENTION_DAYS     Days to keep backups (default: 30)

EXAMPLES:
    # Run with defaults
    ./postgresql_backup.sh

    # Run with environment variables
    DB_NAME=production DB_USER=admin ./postgresql_backup.sh

    # Dry run to preview actions
    ./postgresql_backup.sh --dry-run

EXIT CODES:
    0   Success
    1   Invalid arguments
    2   Missing dependencies
    3   Backup directory error
    4   Database connection error
    5   Backup failed
    6   Cleanup failed

EOF
}

# Print current configuration
print_config() {
    echo "Current Configuration:"
    echo "======================"
    echo "Database Name:    $DB_NAME"
    echo "Database User:    $DB_USER"
    echo "Database Host:    $DB_HOST"
    echo "Database Port:    $DB_PORT"
    echo "Backup Directory: $BACKUP_DIR"
    echo "Retention Days:   $RETENTION_DAYS"
    echo "Log File:         $LOG_FILE"
}

# Logging function
log() {
    local level="$1"
    local message="$2"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Log to console
    echo "[$timestamp] [$level] $message"
    
    # Log to file (append)
    if [[ -d "$BACKUP_DIR" ]]; then
        echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
    fi
}

# Check if required dependencies exist
check_dependencies() {
    local missing_deps=()
    
    if ! command -v pg_dump &> /dev/null; then
        missing_deps+=("pg_dump")
    fi
    
    if ! command -v psql &> /dev/null; then
        missing_deps+=("psql")
    fi
    
    if ! command -v gzip &> /dev/null; then
        missing_deps+=("gzip")
    fi
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log "ERROR" "Missing dependencies: ${missing_deps[*]}"
        log "INFO" "Please install PostgreSQL client tools and gzip"
        exit $EXIT_MISSING_DEPS
    fi
    
    log "INFO" "All dependencies found"
}

# Create backup directory if it doesn't exist
setup_backup_dir() {
    if [[ "$DRY_RUN" == "true" ]]; then
        log "INFO" "[DRY RUN] Would create directory: $BACKUP_DIR"
        return 0
    fi
    
    if [[ ! -d "$BACKUP_DIR" ]]; then
        log "INFO" "Creating backup directory: $BACKUP_DIR"
        if ! mkdir -p "$BACKUP_DIR"; then
            log "ERROR" "Failed to create backup directory: $BACKUP_DIR"
            exit $EXIT_BACKUP_DIR_ERROR
        fi
    fi
    
    # Ensure we have write permissions
    if [[ ! -w "$BACKUP_DIR" ]]; then
        log "ERROR" "Backup directory is not writable: $BACKUP_DIR"
        exit $EXIT_BACKUP_DIR_ERROR
    fi
    
    log "INFO" "Backup directory ready: $BACKUP_DIR"
}

# Test database connection
test_connection() {
    log "INFO" "Testing database connection to $DB_HOST:$DB_PORT..."
    
    local conn_opts="-h $DB_HOST -p $DB_PORT -U $DB_USER"
    
    if [[ -n "$DB_PASSWORD" ]]; then
        export PGPASSWORD="$DB_PASSWORD"
    fi
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "INFO" "[DRY RUN] Would test connection to $DB_NAME"
        return 0
    fi
    
    if ! psql $conn_opts -d "$DB_NAME" -c "SELECT 1;" &> /dev/null; then
        log "ERROR" "Failed to connect to database '$DB_NAME'"
        log "ERROR" "Please check: host, port, credentials, and database existence"
        exit $EXIT_DB_CONNECTION_ERROR
    fi
    
    log "INFO" "Database connection successful"
}

# Create database backup
create_backup() {
    local timestamp
    timestamp=$(date '+%Y-%m-%d_%H-%M')
    local backup_file="${BACKUP_DIR}/backup_${DB_NAME}_${timestamp}.sql"
    local compressed_file="${backup_file}.gz"
    
    log "INFO" "Starting backup of database: $DB_NAME"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "INFO" "[DRY RUN] Would create backup: $compressed_file"
        return 0
    fi
    
    # Export password if provided
    if [[ -n "$DB_PASSWORD" ]]; then
        export PGPASSWORD="$DB_PASSWORD"
    fi
    
    local pgdump_opts="-h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME"
    pgdump_opts="$pgdump_opts --clean --if-exists --create"
    
    # Create backup with compression
    if ! pg_dump $pgdump_opts | gzip > "$compressed_file"; then
        log "ERROR" "Backup creation failed for database: $DB_NAME"
        # Clean up partial file if it exists
        [[ -f "$compressed_file" ]] && rm -f "$compressed_file"
        exit $EXIT_BACKUP_FAILED
    fi
    
    # Get file size
    local file_size
    file_size=$(du -h "$compressed_file" | cut -f1)
    
    log "INFO" "Backup created successfully: $compressed_file ($file_size)"
}

# Clean up old backups
cleanup_old_backups() {
    log "INFO" "Cleaning up backups older than $RETENTION_DAYS days..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "INFO" "[DRY RUN] Would delete backups older than $RETENTION_DAYS days"
        return 0
    fi
    
    local deleted_count=0
    
    # Find and remove backups older than RETENTION_DAYS
    while IFS= read -r file; do
        if [[ -f "$file" ]]; then
            log "INFO" "Deleting old backup: $file"
            rm -f "$file"
            ((deleted_count++))
        fi
    done < <(find "$BACKUP_DIR" -name "backup_*.sql.gz" -type f -mtime +$RETENTION_DAYS 2>/dev/null)
    
    log "INFO" "