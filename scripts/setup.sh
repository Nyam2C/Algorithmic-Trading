#!/bin/bash
# =============================================================================
# Environment Setup Script - High-Win Survival System
# =============================================================================
# Complete environment setup for development and deployment.
# Supports both trading bot and future backend (FastAPI) implementation.
#
# Usage:
#     ./setup.sh              # Interactive setup
#     ./setup.sh --all        # Setup everything
#     ./setup.sh --dev        # Development environment only
#     ./setup.sh --docker     # Docker environment only
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Functions
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

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

check_python() {
    print_info "Checking Python installation..."

    if check_command python3; then
        PYTHON_CMD="python3"
    elif check_command python; then
        PYTHON_CMD="python"
    else
        print_error "Python not found. Please install Python 3.11+"
        exit 1
    fi

    # Check version
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
        print_error "Python 3.11+ required, found $PYTHON_VERSION"
        exit 1
    fi

    print_success "Python $PYTHON_VERSION"
}

check_docker() {
    print_info "Checking Docker installation..."

    if ! check_command docker; then
        print_warning "Docker not found"
        return 1
    fi

    if ! docker ps &> /dev/null; then
        print_warning "Docker is installed but not running"
        return 1
    fi

    print_success "Docker is installed and running"
    return 0
}

check_docker_compose() {
    print_info "Checking Docker Compose..."

    # Check for docker compose (plugin)
    if docker compose version &> /dev/null; then
        print_success "Docker Compose (plugin) available"
        return 0
    fi

    # Check for docker-compose (standalone)
    if check_command docker-compose; then
        print_success "Docker Compose (standalone) available"
        return 0
    fi

    print_warning "Docker Compose not found"
    return 1
}

install_dependencies() {
    print_info "Installing Python dependencies..."

    if [ ! -f "requirements.txt" ]; then
        print_error "requirements.txt not found"
        exit 1
    fi

    # Upgrade pip
    $PYTHON_CMD -m pip install --upgrade pip

    # Install requirements
    $PYTHON_CMD -m pip install -r requirements.txt

    print_success "Python dependencies installed"
}

setup_env_file() {
    print_info "Setting up .env file..."

    if [ -f ".env" ]; then
        echo -e "${YELLOW}.env file already exists. Overwrite? (y/N): ${NC}\c"
        read -r response
        if [ "$response" != "y" ] && [ "$response" != "Y" ]; then
            print_info "Skipping .env setup"
            return
        fi
    fi

    if [ ! -f ".env.example" ]; then
        print_error ".env.example not found"
        exit 1
    fi

    echo ""
    echo "Please provide the following configuration values:"
    echo "(Press Enter to use default values where applicable)"
    echo ""

    # Bot Name
    echo -e "${BLUE}Bot Name [high-win-bot]:${NC} \c"
    read -r BOT_NAME
    BOT_NAME=${BOT_NAME:-high-win-bot}

    # Binance API
    echo ""
    echo -e "${BLUE}Binance Testnet API Keys${NC}"
    echo "Get your keys from: https://testnet.binancefuture.com"
    echo -e "Binance API Key: \c"
    read -r BINANCE_API_KEY
    echo -e "Binance Secret Key: \c"
    read -r BINANCE_SECRET_KEY

    # Gemini API
    echo ""
    echo -e "${BLUE}Gemini AI API Key${NC}"
    echo "Get your key from: https://aistudio.google.com/apikey"
    echo -e "Gemini API Key: \c"
    read -r GEMINI_API_KEY

    # Discord Webhook
    echo ""
    echo -e "${BLUE}Discord Webhook URL${NC}"
    echo -e "Discord Webhook URL: \c"
    read -r DISCORD_WEBHOOK_URL

    # Trading Parameters
    echo ""
    echo -e "${BLUE}Trading Parameters${NC}"
    echo -e "Symbol [BTCUSDT]: \c"
    read -r SYMBOL
    SYMBOL=${SYMBOL:-BTCUSDT}

    echo -e "Leverage [15]: \c"
    read -r LEVERAGE
    LEVERAGE=${LEVERAGE:-15}

    echo -e "Position Size % [0.05]: \c"
    read -r POSITION_SIZE_PCT
    POSITION_SIZE_PCT=${POSITION_SIZE_PCT:-0.05}

    echo -e "Take Profit % [0.004]: \c"
    read -r TAKE_PROFIT_PCT
    TAKE_PROFIT_PCT=${TAKE_PROFIT_PCT:-0.004}

    echo -e "Stop Loss % [0.004]: \c"
    read -r STOP_LOSS_PCT
    STOP_LOSS_PCT=${STOP_LOSS_PCT:-0.004}

    # Database
    echo ""
    echo -e "${BLUE}Database Configuration${NC}"
    echo -e "Database URL [postgresql://postgres:postgres@db:5432/trading]: \c"
    read -r DATABASE_URL
    DATABASE_URL=${DATABASE_URL:-postgresql://postgres:postgres@db:5432/trading}

    # Write .env file
    cp .env.example .env

    # Replace values using sed
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s|BOT_NAME=.*|BOT_NAME=$BOT_NAME|" .env
        sed -i '' "s|BINANCE_API_KEY=.*|BINANCE_API_KEY=$BINANCE_API_KEY|" .env
        sed -i '' "s|BINANCE_SECRET_KEY=.*|BINANCE_SECRET_KEY=$BINANCE_SECRET_KEY|" .env
        sed -i '' "s|GEMINI_API_KEY=.*|GEMINI_API_KEY=$GEMINI_API_KEY|" .env
        sed -i '' "s|DISCORD_WEBHOOK_URL=.*|DISCORD_WEBHOOK_URL=$DISCORD_WEBHOOK_URL|" .env
        sed -i '' "s|SYMBOL=.*|SYMBOL=$SYMBOL|" .env
        sed -i '' "s|LEVERAGE=.*|LEVERAGE=$LEVERAGE|" .env
        sed -i '' "s|POSITION_SIZE_PCT=.*|POSITION_SIZE_PCT=$POSITION_SIZE_PCT|" .env
        sed -i '' "s|TAKE_PROFIT_PCT=.*|TAKE_PROFIT_PCT=$TAKE_PROFIT_PCT|" .env
        sed -i '' "s|STOP_LOSS_PCT=.*|STOP_LOSS_PCT=$STOP_LOSS_PCT|" .env
        sed -i '' "s|DATABASE_URL=.*|DATABASE_URL=$DATABASE_URL|" .env
    else
        # Linux
        sed -i "s|BOT_NAME=.*|BOT_NAME=$BOT_NAME|" .env
        sed -i "s|BINANCE_API_KEY=.*|BINANCE_API_KEY=$BINANCE_API_KEY|" .env
        sed -i "s|BINANCE_SECRET_KEY=.*|BINANCE_SECRET_KEY=$BINANCE_SECRET_KEY|" .env
        sed -i "s|GEMINI_API_KEY=.*|GEMINI_API_KEY=$GEMINI_API_KEY|" .env
        sed -i "s|DISCORD_WEBHOOK_URL=.*|DISCORD_WEBHOOK_URL=$DISCORD_WEBHOOK_URL|" .env
        sed -i "s|SYMBOL=.*|SYMBOL=$SYMBOL|" .env
        sed -i "s|LEVERAGE=.*|LEVERAGE=$LEVERAGE|" .env
        sed -i "s|POSITION_SIZE_PCT=.*|POSITION_SIZE_PCT=$POSITION_SIZE_PCT|" .env
        sed -i "s|TAKE_PROFIT_PCT=.*|TAKE_PROFIT_PCT=$TAKE_PROFIT_PCT|" .env
        sed -i "s|STOP_LOSS_PCT=.*|STOP_LOSS_PCT=$STOP_LOSS_PCT|" .env
        sed -i "s|DATABASE_URL=.*|DATABASE_URL=$DATABASE_URL|" .env
    fi

    print_success ".env file created"
}

create_directories() {
    print_info "Creating project directories..."

    mkdir -p logs
    mkdir -p data
    mkdir -p configs
    mkdir -p scripts
    mkdir -p tests/data
    mkdir -p src/ai/prompts

    print_success "Directories created"
}

init_git() {
    print_info "Checking git repository..."

    if [ -d ".git" ]; then
        print_success "Git repository already initialized"
        return
    fi

    echo -e "${YELLOW}Initialize git repository? (y/N): ${NC}\c"
    read -r response
    if [ "$response" != "y" ] && [ "$response" != "Y" ]; then
        return
    fi

    git init
    git add .
    git commit -m "Initial commit"

    print_success "Git repository initialized"
}

setup_docker() {
    print_info "Setting up Docker environment..."

    if ! check_docker; then
        print_error "Docker is not available. Please install Docker first."
        print_info "Visit: https://docs.docker.com/get-docker/"
        return 1
    fi

    if ! check_docker_compose; then
        print_error "Docker Compose is not available."
        return 1
    fi

    # Build Docker image
    print_info "Building Docker image..."
    docker compose build

    print_success "Docker environment ready"
    return 0
}

run_tests() {
    print_info "Running test suite..."

    if ! check_command pytest; then
        print_warning "pytest not found, installing..."
        $PYTHON_CMD -m pip install pytest pytest-asyncio pytest-mock pytest-cov
    fi

    $PYTHON_CMD -m pytest -v

    print_success "All tests passed"
}

print_summary() {
    print_header "Setup Complete!"

    echo -e "${GREEN}Environment is ready!${NC}\n"

    echo "Next steps:"
    echo ""
    echo -e "  ${BLUE}1. Review your .env file:${NC}"
    echo "     cat .env"
    echo ""
    echo -e "  ${BLUE}2. Run tests:${NC}"
    echo "     ./run-tests.sh"
    echo ""
    echo -e "  ${BLUE}3. Start the bot:${NC}"
    echo -e "     ${YELLOW}Docker (Recommended):${NC}"
    echo "     ./start-docker.sh"
    echo -e "     ${YELLOW}Local:${NC}"
    echo "     ./run.sh"
    echo ""
    echo -e "  ${BLUE}4. Monitor logs:${NC}"
    echo "     docker compose logs -f bot"
    echo "     # or"
    echo "     tail -f logs/bot.log"
    echo ""
    echo -e "${YELLOW}Documentation:${NC}"
    echo "  - README.md - Project overview"
    echo "  - TEST_GUIDE.md - Testing guide"
    echo "  - .claude/ - Development plans"
    echo ""
}

# Main
main() {
    print_header "High-Win Survival System - Environment Setup"

    # Parse arguments
    MODE=""
    SKIP_TESTS=false

    while [[ "$#" -gt 0 ]]; do
        case $1 in
            --all) MODE="all" ;;
            --dev) MODE="dev" ;;
            --docker) MODE="docker" ;;
            --skip-tests) SKIP_TESTS=true ;;
            *) print_error "Unknown parameter: $1"; exit 1 ;;
        esac
        shift
    done

    # Check Python
    check_python

    # Create directories
    create_directories

    if [ "$MODE" == "docker" ]; then
        # Docker setup only
        setup_docker

    elif [ "$MODE" == "dev" ]; then
        # Development setup only
        install_dependencies
        setup_env_file
        [ "$SKIP_TESTS" = false ] && run_tests

    elif [ "$MODE" == "all" ]; then
        # Full setup
        install_dependencies
        setup_env_file
        init_git
        check_docker && setup_docker
        [ "$SKIP_TESTS" = false ] && run_tests

    else
        # Interactive mode
        echo ""
        echo "Select setup mode:"
        echo "1. Full setup (dependencies + .env + Docker)"
        echo "2. Development only (dependencies + .env)"
        echo "3. Docker only"
        echo "4. Exit"
        echo ""
        echo -e "${BLUE}Enter choice (1-4):${NC} \c"
        read -r choice

        case $choice in
            1)
                install_dependencies
                setup_env_file
                init_git
                check_docker && setup_docker
                [ "$SKIP_TESTS" = false ] && run_tests
                ;;
            2)
                install_dependencies
                setup_env_file
                [ "$SKIP_TESTS" = false ] && run_tests
                ;;
            3)
                setup_docker
                ;;
            4)
                print_info "Setup cancelled"
                exit 0
                ;;
            *)
                print_error "Invalid choice"
                exit 1
                ;;
        esac
    fi

    print_summary
}

# Run main
main "$@"
