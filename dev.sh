#!/usr/bin/env bash
# dev.sh — Local development runner for the Autonomous IT Service Management Agent
#
# Automatically creates and activates a .venv, installs requirements on first
# run (or when requirements.txt changes), then manages the agent processes.
#
# Usage: ./dev.sh [command] [options]
#
# Commands:
#   start [url]      Start all agents (default AgentField URL: http://localhost:8080)
#   stop             Stop all running agents
#   restart [url]    Stop then start all agents
#   status           Show which agents are running
#   logs [agent]     Tail logs for all agents, or a specific one
#   check-env        Validate .env configuration without starting agents
#   help             Show this help

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"
REQUIREMENTS_HASH_FILE="$SCRIPT_DIR/.venv/.requirements_hash"
PID_DIR="$SCRIPT_DIR/.pids"
LOG_DIR="$SCRIPT_DIR/.logs"
ENV_FILE="$SCRIPT_DIR/.env"

DEFAULT_AGENTFIELD_URL="http://localhost:8080"

# Ordered list of agent module paths (module : node_id)
declare -A AGENTS=(
  [ingestion]="agents.ingestion_agent"
  [classification]="agents.classification_agent"
  [enrichment]="agents.enrichment_agent"
  [decision_planning]="agents.decision_planning_agent"
  [execution]="agents.execution_agent"
  [validation]="agents.validation_agent"
  [communication]="agents.communication_agent"
  [learning]="agents.learning_agent"
  [human_review]="agents.human_review_agent"
)

# Colour helpers (disabled when not a terminal)
if [ -t 1 ]; then
  RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'
  CYAN=$'\033[0;36m'; BOLD=$'\033[1m'; RESET=$'\033[0m'
else
  RED=''; GREEN=''; YELLOW=''; CYAN=''; BOLD=''; RESET=''
fi

info()    { echo -e "${CYAN}[dev]${RESET} $*"; }
success() { echo -e "${GREEN}[dev]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[dev]${RESET} $*"; }
error()   { echo -e "${RED}[dev]${RESET} $*" >&2; }
die()     { error "$*"; exit 1; }

# ── Virtual-env & dependency management ──────────────────────────────────────

ensure_venv() {
  if [ ! -d "$VENV_DIR" ]; then
    info "Creating virtual environment at .venv …"
    python3 -m venv "$VENV_DIR"
  fi
  # shellcheck source=/dev/null
  source "$VENV_DIR/bin/activate"
}

ensure_deps() {
  ensure_venv

  local current_hash
  current_hash=$(sha256sum "$REQUIREMENTS" 2>/dev/null | awk '{print $1}' || echo "none")
  local stored_hash=""
  [ -f "$REQUIREMENTS_HASH_FILE" ] && stored_hash=$(cat "$REQUIREMENTS_HASH_FILE")

  if [ "$current_hash" != "$stored_hash" ]; then
    info "requirements.txt changed — installing dependencies …"
    pip install --quiet --upgrade pip
    pip install --quiet -r "$REQUIREMENTS"
    echo "$current_hash" > "$REQUIREMENTS_HASH_FILE"
    success "Dependencies installed."
  fi
}

# ── .env helpers ──────────────────────────────────────────────────────────────

load_env() {
  if [ -f "$ENV_FILE" ]; then
    # Export non-comment, non-empty lines
    set -o allexport
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +o allexport
  fi
}

cmd_check_env() {
  load_env
  ensure_venv
  info "Validating .env configuration …"

  local ok=true

  _check_var() {
    local name="$1" required="${2:-false}"
    local val="${!name:-}"
    if [ -z "$val" ]; then
      if [ "$required" = "true" ]; then
        error "  MISSING (required): $name"
        ok=false
      else
        warn  "  not set (optional): $name"
      fi
    else
      # Mask secrets in output
      local display="$val"
      if [[ "$name" == *KEY* || "$name" == *SECRET* || "$name" == *PASSWORD* || "$name" == *TOKEN* ]]; then
        display="${val:0:4}****"
      fi
      success "  OK: $name = $display"
    fi
  }

  echo ""
  echo -e "${BOLD}Required variables:${RESET}"
  _check_var AGENTFIELD_SERVER true
  _check_var AI_MODEL          true

  echo ""
  echo -e "${BOLD}ServiceNow integration:${RESET}"
  _check_var SERVICENOW_INSTANCE false
  _check_var SERVICENOW_API_KEY  false
  _check_var SERVICENOW_TABLE    false

  echo ""
  echo -e "${BOLD}Optional integrations:${RESET}"
  _check_var KNOWLEDGE_BASE_URL      false
  _check_var NOTIFICATION_WEBHOOK_URL false
  _check_var HUMAN_REVIEW_QUEUE_URL  false

  echo ""
  echo -e "${BOLD}Execution settings:${RESET}"
  _check_var RETRY_ATTEMPTS  false
  _check_var TIMEOUT_SECONDS false

  echo ""
  if [ "$ok" = "true" ]; then
    success "All required variables are set."
  else
    error "One or more required variables are missing. Copy .env.example → .env and fill them in."
    exit 1
  fi
}

# ── Process management ────────────────────────────────────────────────────────

pid_file() { echo "$PID_DIR/$1.pid"; }
log_file()  { echo "$LOG_DIR/$1.log"; }

agent_is_running() {
  local name="$1"
  local pf; pf=$(pid_file "$name")
  [ -f "$pf" ] && kill -0 "$(cat "$pf")" 2>/dev/null
}

start_agent() {
  local name="$1" module="$2" agentfield_url="$3"
  local pf; pf=$(pid_file "$name")
  local lf; lf=$(log_file "$name")

  if agent_is_running "$name"; then
    warn "  $name is already running (PID $(cat "$pf"))"
    return
  fi

  AGENTFIELD_SERVER="$agentfield_url" \
    python -c "import asyncio; from $module import app; asyncio.run(app.start())" \
    >> "$lf" 2>&1 &

  echo $! > "$pf"
  success "  started $name (PID $!)"
}

stop_agent() {
  local name="$1"
  local pf; pf=$(pid_file "$name")

  if ! agent_is_running "$name"; then
    warn "  $name is not running"
    rm -f "$pf"
    return
  fi

  local pid; pid=$(cat "$pf")
  kill "$pid" 2>/dev/null && success "  stopped $name (PID $pid)" || warn "  could not stop $name"
  rm -f "$pf"
}

cmd_start() {
  local agentfield_url="${1:-}"
  load_env
  agentfield_url="${agentfield_url:-${AGENTFIELD_SERVER:-$DEFAULT_AGENTFIELD_URL}}"

  ensure_deps
  mkdir -p "$PID_DIR" "$LOG_DIR"

  info "Starting all agents → AgentField at $agentfield_url"
  echo ""

  for name in "${!AGENTS[@]}"; do
    start_agent "$name" "${AGENTS[$name]}" "$agentfield_url"
  done

  echo ""
  success "All agents started. Logs: .logs/  |  PIDs: .pids/"
  info "Run './dev.sh status' to check, './dev.sh logs' to follow output."
}

cmd_stop() {
  info "Stopping all agents …"
  echo ""

  for name in "${!AGENTS[@]}"; do
    stop_agent "$name"
  done

  echo ""
  success "All agents stopped."
}

cmd_restart() {
  local url="${1:-}"
  cmd_stop
  echo ""
  cmd_start "$url"
}

cmd_status() {
  info "Agent status:"
  echo ""
  printf "  %-25s %-10s %s\n" "AGENT" "STATUS" "PID"
  printf "  %-25s %-10s %s\n" "─────────────────────────" "──────────" "───"

  for name in "${!AGENTS[@]}"; do
    local pf; pf=$(pid_file "$name")
    if agent_is_running "$name"; then
      local pid; pid=$(cat "$pf")
      printf "  ${GREEN}%-25s %-10s %s${RESET}\n" "$name" "running" "$pid"
    else
      printf "  ${RED}%-25s %-10s${RESET}\n" "$name" "stopped"
    fi
  done
  echo ""
}

cmd_logs() {
  local target="${1:-}"
  mkdir -p "$LOG_DIR"

  if [ -n "$target" ]; then
    local lf; lf=$(log_file "$target")
    if [ ! -f "$lf" ]; then
      die "No log file found for agent '$target'. Available: ${!AGENTS[*]}"
    fi
    info "Tailing logs for $target (Ctrl-C to stop) …"
    tail -f "$lf"
  else
    # Tail all log files that exist
    local log_files=()
    for name in "${!AGENTS[@]}"; do
      local lf; lf=$(log_file "$name")
      [ -f "$lf" ] && log_files+=("$lf")
    done

    if [ ${#log_files[@]} -eq 0 ]; then
      warn "No log files found yet. Start agents first with: ./dev.sh start"
      exit 0
    fi

    info "Tailing all agent logs (Ctrl-C to stop) …"
    tail -f "${log_files[@]}"
  fi
}

cmd_help() {
  cat <<EOF

${BOLD}dev.sh${RESET} — Local development runner for the Autonomous IT Service Management Agent

${BOLD}USAGE${RESET}
  ./dev.sh <command> [options]

${BOLD}COMMANDS${RESET}
  ${CYAN}start [url]${RESET}      Start all 9 agents.
                   url defaults to \$AGENTFIELD_SERVER in .env, or $DEFAULT_AGENTFIELD_URL.

  ${CYAN}stop${RESET}             Stop all running agents.

  ${CYAN}restart [url]${RESET}    Stop then start all agents.

  ${CYAN}status${RESET}           Show which agents are running and their PIDs.

  ${CYAN}logs [agent]${RESET}     Tail logs for all agents, or a specific one.
                   Available agents: ${!AGENTS[*]}

  ${CYAN}check-env${RESET}        Validate .env configuration without starting agents.

  ${CYAN}help${RESET}             Show this help message.

${BOLD}FIRST-TIME SETUP${RESET}
  1. cp .env.example .env && edit .env
  2. ./dev.sh check-env          # verify config
  3. ./dev.sh start              # start AgentField control plane (Docker) first!
  4. ./dev.sh status             # confirm all agents are running
  5. ./dev.sh logs               # watch live output

${BOLD}FILES${RESET}
  .venv/       Python virtual environment (auto-created)
  .logs/       Per-agent log files
  .pids/       Per-agent PID files

EOF
}

# ── Entry point ───────────────────────────────────────────────────────────────

cd "$SCRIPT_DIR"

case "${1:-help}" in
  start)       cmd_start "${2:-}" ;;
  stop)        cmd_stop ;;
  restart)     cmd_restart "${2:-}" ;;
  status)      cmd_status ;;
  logs)        cmd_logs "${2:-}" ;;
  check-env)   cmd_check_env ;;
  help|--help|-h) cmd_help ;;
  *)           error "Unknown command: $1"; cmd_help; exit 1 ;;
esac
