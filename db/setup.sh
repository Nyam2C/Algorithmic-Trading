#!/bin/bash
# =============================================================================
# Database Setup Script
# =============================================================================
# Initializes PostgreSQL database for trading bot
# Creates schema, tables, indexes, and initial data
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo ""
    echo "======================================================================"
    echo "  $1"
    echo "======================================================================"
    echo ""
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Load environment variables
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    print_error ".env file not found. Run setup.sh first."
    exit 1
fi

# Parse DATABASE_URL
# Format: postgresql://user:password@host:port/database
DB_URL=${DATABASE_URL:-"postgresql://postgres:postgres@localhost:5432/trading"}

# Extract components
DB_USER=$(echo $DB_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
DB_PASS=$(echo $DB_URL | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
DB_HOST=$(echo $DB_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
DB_PORT=$(echo $DB_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
DB_NAME=$(echo $DB_URL | sed -n 's/.*\/\(.*\)/\1/p')

print_header "Database Setup"

echo "Database Configuration:"
echo "  Host: $DB_HOST"
echo "  Port: $DB_PORT"
echo "  Database: $DB_NAME"
echo "  User: $DB_USER"
echo ""

# Check if running in Docker
if [ "$DB_HOST" == "db" ] || [ "$DB_HOST" == "localhost" ] && docker ps | grep -q postgres; then
    print_info "Detected Docker environment"
    USE_DOCKER=true
else
    USE_DOCKER=false
fi

# Function to run SQL
run_sql() {
    local sql="$1"
    if [ "$USE_DOCKER" = true ]; then
        # Use Docker exec
        docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME" -c "$sql"
    else
        # Use local psql
        PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "$sql"
    fi
}

# Function to run SQL file
run_sql_file() {
    local file="$1"
    if [ "$USE_DOCKER" = true ]; then
        # Copy file to container and execute
        docker cp "$file" trading-db:/tmp/init.sql
        docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME" -f /tmp/init.sql
    else
        # Use local psql
        PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$file"
    fi
}

# Wait for database to be ready
print_info "Waiting for database to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if run_sql "SELECT 1;" &> /dev/null; then
        print_success "Database is ready"
        break
    fi

    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -n "."
    sleep 1
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    print_error "Database connection timeout"
    exit 1
fi

echo ""

# Create database if not exists
print_info "Checking database existence..."
if [ "$USE_DOCKER" = true ]; then
    docker compose exec -T db psql -U "$DB_USER" -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME" || {
        print_info "Creating database $DB_NAME..."
        docker compose exec -T db psql -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;"
    }
else
    PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME" || {
        print_info "Creating database $DB_NAME..."
        PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;"
    }
fi

# Run initialization script
print_info "Running database initialization script..."
run_sql_file "$SCRIPT_DIR/db/init.sql"

print_success "Database schema created"

# Verify tables
print_info "Verifying tables..."
TABLE_COUNT=$(run_sql "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';" | grep -o '[0-9]\+' | head -1)

echo ""
echo "Tables created: $TABLE_COUNT"
echo ""

# Show created tables
print_info "Created tables:"
if [ "$USE_DOCKER" = true ]; then
    docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME" -c "\dt"
else
    PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "\dt"
fi

echo ""

# Insert test data (optional)
read -p "$(echo -e ${YELLOW}Insert test data? \(y/N\): ${NC})" -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Inserting test data..."

    run_sql "INSERT INTO bot_status (bot_name, is_running, current_position) VALUES ('test-bot', FALSE, 'NONE') ON CONFLICT (bot_name) DO NOTHING;"

    print_success "Test data inserted"
fi

print_header "Database Setup Complete!"

echo -e "${GREEN}Database is ready for use!${NC}"
echo ""
echo "Connection info:"
echo "  postgresql://$DB_USER:****@$DB_HOST:$DB_PORT/$DB_NAME"
echo ""
echo "Connect manually:"
if [ "$USE_DOCKER" = true ]; then
    echo "  docker compose exec db psql -U $DB_USER -d $DB_NAME"
else
    echo "  psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME"
fi
echo ""
