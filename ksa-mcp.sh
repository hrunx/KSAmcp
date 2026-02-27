#!/usr/bin/env bash
set -euo pipefail

GREEN="\033[1;32m"
WHITE="\033[1;37m"
SOFT_GREEN="\033[38;5;42m"
RESET="\033[0m"
BOLD="\033[1m"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_BASE_URL="http://ksa-opendata-mcp.localhost:8000"
DEFAULT_FASTAPI_KEY='$$hrn&ali4KSA$$'
LOCAL_FALLBACK_BASE_URL="http://127.0.0.1:8000"
BASE_URL="${DEFAULT_BASE_URL}"
HEALTH_URL="${BASE_URL}/health"
MCP_URL="${BASE_URL}/mcp/"
API_DOCS_URL="${BASE_URL}/docs"
API_TOOLS_URL="${BASE_URL}/api/tools"
FLAG_IMAGE="${PROJECT_ROOT}/assets/ksa-flag.png"
CONTAINER_NAME="ksa-opendata-mcp"
FASTAPI_API_KEY_VALUE=""
PUBLIC_BASE_URL_VALUE=""
MCP_API_KEY_REQUIRED_VALUE="false"
LAN_IP=""
CURSOR_MCP_CONFIG_FILE="${PROJECT_ROOT}/.cursor/mcp.json"
CHATGPT_SETUP_FILE="${PROJECT_ROOT}/reports/chatgpt_mcp_setup.json"

COMPOSE_CMD=()

msg() {
  echo -e "${SOFT_GREEN}$*${RESET}"
}

ok() {
  echo -e "${GREEN}${BOLD}[OK]${RESET} $*"
}

warn() {
  echo -e "${WHITE}${BOLD}[INFO]${RESET} $*"
}

fail() {
  echo -e "${WHITE}${BOLD}[ERROR]${RESET} $*"
  exit 1
}

detect_compose() {
  if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD=("docker" "compose")
    return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD=("docker-compose")
    return
  fi
  fail "Docker Compose not found. Install Docker Desktop or docker-compose."
}

compose() {
  "${COMPOSE_CMD[@]}" "$@"
}

ensure_env_file() {
  if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    return 0
  fi
  warn ".env not found. Creating a ready-to-run .env with defaults."
  cat > "${PROJECT_ROOT}/.env" <<'EOF'
# Local runtime secrets/config for docker-compose and ksa-mcp.sh
# Keep this file local (ignored by git).

FASTAPI_API_KEY=$$hrn&ali4KSA$$
MCP_API_KEY_REQUIRED=false
MCP_PUBLIC_BASE_URL=http://ksa-opendata-mcp.localhost:8000
MCP_SERVER_NAME=KSA Open Data MCP
MCP_SERVER_DESCRIPTION=National Saudi Open Data MCP with FastAPI and vector memory.
MCP_ICON_URL=http://ksa-opendata-mcp.localhost:8000/assets/ksa-mcp-icon-128.jpg
MCIT_API_KEY=
KSA_MCP_SOURCES=sources.yaml
POSTGRES_DB=ksa_mcp
POSTGRES_USER=ksa_mcp
POSTGRES_PASSWORD=ksa_mcp
DATABASE_URL=postgresql://ksa_mcp:ksa_mcp@ksa-mcp-postgres:5432/ksa_mcp
VECTOR_MEMORY_ENABLED=true
VECTOR_MEMORY_TTL_SECONDS=604800
VECTOR_MEMORY_MAX_TEXT_CHARS=6000
EMBEDDING_MODEL_NAME=arabic-hash-ngram-v1
EMBEDDING_DIM=256
EOF
}

apply_url_config() {
  if [[ -z "${PUBLIC_BASE_URL_VALUE}" ]]; then
    BASE_URL="${DEFAULT_BASE_URL}"
  else
    BASE_URL="${PUBLIC_BASE_URL_VALUE}"
  fi
  BASE_URL="${BASE_URL%/}"
  HEALTH_URL="${BASE_URL}/health"
  MCP_URL="${BASE_URL}/mcp/"
  API_DOCS_URL="${BASE_URL}/docs"
  API_TOOLS_URL="${BASE_URL}/api/tools"
}

load_env_config() {
  local env_dump
  env_dump="$(
    PROJECT_ROOT="${PROJECT_ROOT}" python3 - <<'PY'
import os
from pathlib import Path

env_path = Path(os.environ["PROJECT_ROOT"]) / ".env"
if not env_path.exists():
    print("")
    raise SystemExit

for line in env_path.read_text(encoding="utf-8").splitlines():
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        continue
    key, value = stripped.split("=", 1)
    print(f"{key.strip()}={value.strip()}")
PY
  )"

  while IFS= read -r line; do
    [[ -z "${line}" ]] && continue
    case "${line}" in
      FASTAPI_API_KEY=*)
        FASTAPI_API_KEY_VALUE="${line#FASTAPI_API_KEY=}"
        ;;
      MCP_PUBLIC_BASE_URL=*)
        PUBLIC_BASE_URL_VALUE="${line#MCP_PUBLIC_BASE_URL=}"
        ;;
      MCP_API_KEY_REQUIRED=*)
        MCP_API_KEY_REQUIRED_VALUE="${line#MCP_API_KEY_REQUIRED=}"
        ;;
    esac
  done <<< "${env_dump}"

  if [[ -z "${FASTAPI_API_KEY_VALUE}" ]]; then
    FASTAPI_API_KEY_VALUE="${DEFAULT_FASTAPI_KEY}"
  fi
  if [[ -z "${PUBLIC_BASE_URL_VALUE}" ]]; then
    PUBLIC_BASE_URL_VALUE="${DEFAULT_BASE_URL}"
  fi
}

detect_lan_ip() {
  LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || true)"
  if [[ -z "${LAN_IP}" ]]; then
    LAN_IP="$(ipconfig getifaddr en1 2>/dev/null || true)"
  fi
}

check_prerequisites() {
  command -v docker >/dev/null 2>&1 || fail "Docker is not installed."
  command -v curl >/dev/null 2>&1 || fail "curl is required."
  detect_compose
  docker info >/dev/null 2>&1 || fail "Docker daemon is not running."
  ensure_env_file
  load_env_config
  apply_url_config
  detect_lan_ip
}

is_api_key_required() {
  local lowered
  lowered="$(printf '%s' "${MCP_API_KEY_REQUIRED_VALUE}" | tr '[:upper:]' '[:lower:]')"
  case "${lowered}" in
    true|1|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

print_banner() {
  echo -e "${GREEN}${BOLD}"
  cat <<'EOF'
====================================================================
                     KSA OPEN DATA MCP STARTUP
                  -----------<|>-----------
====================================================================
EOF
  echo -e "${RESET}"
  printf "\033[42m\033[97m  KINGDOM OF SAUDI ARABIA                                      \033[0m\n"
  printf "\033[42m\033[97m  -----------------------------------------------------------  \033[0m\n"
  printf "\033[42m\033[97m                    ==========<|>==========                    \033[0m\n"
  printf "\033[42m\033[97m                                                               \033[0m\n"
  warn "KSA flag asset: ${FLAG_IMAGE}"
}

write_local_connection_files() {
  mkdir -p "${PROJECT_ROOT}/.cursor" "${PROJECT_ROOT}/reports"
  PROJECT_ROOT="${PROJECT_ROOT}" \
  MCP_URL="${MCP_URL}" \
  BASE_URL="${BASE_URL}" \
  API_DOCS_URL="${API_DOCS_URL}" \
  API_TOOLS_URL="${API_TOOLS_URL}" \
  API_KEY="${FASTAPI_API_KEY_VALUE}" \
  API_KEY_REQUIRED="${MCP_API_KEY_REQUIRED_VALUE}" \
  CURSOR_FILE="${CURSOR_MCP_CONFIG_FILE}" \
  CHATGPT_FILE="${CHATGPT_SETUP_FILE}" \
  python3 - <<'PY'
import json
import os
from pathlib import Path

api_key_required = os.environ.get("API_KEY_REQUIRED", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
mcp_url = os.environ["MCP_URL"]
cursor_file = Path(os.environ["CURSOR_FILE"])
chatgpt_file = Path(os.environ["CHATGPT_FILE"])

server_cfg = {
    "transport": "streamable-http",
    "url": mcp_url,
}
if api_key_required:
    server_cfg["headers"] = {"X-API-Key": os.environ.get("API_KEY", "")}

cursor_payload = {
    "mcpServers": {
        "ksa-opendata-mcp": server_cfg,
    }
}
cursor_file.write_text(
    json.dumps(cursor_payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

chatgpt_payload = {
    "name": "KSA Open Data MCP",
    "description": "National Saudi Open Data MCP with FastAPI and vector memory.",
    "icon": f"{os.environ['BASE_URL']}/assets/ksa-mcp-icon-128.jpg",
    "mcp_server_url": mcp_url,
    "authentication": "X-API-Key header" if api_key_required else "No auth (public mode)",
    "oauth": "Not required",
    "fastapi_docs_url": os.environ["API_DOCS_URL"],
    "fastapi_tools_url": os.environ["API_TOOLS_URL"],
}
chatgpt_file.write_text(
    json.dumps(chatgpt_payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY
  ok "Generated Cursor MCP config: ${CURSOR_MCP_CONFIG_FILE}"
  ok "Generated ChatGPT MCP setup file: ${CHATGPT_SETUP_FILE}"
}

print_welcome() {
  echo -e "${GREEN}${BOLD}"
  cat <<'EOF'
--------------------------------------------------------------------
MCP SERVER IS LIVE
--------------------------------------------------------------------
EOF
  echo -e "${RESET}"
  warn "MCP URL: ${MCP_URL}"
  warn "FastAPI docs: ${API_DOCS_URL}"
  warn "FastAPI tool gateway: ${API_TOOLS_URL}"
  warn "Health endpoint: ${HEALTH_URL}"
  warn "Container-network URL: http://ksa-opendata-mcp:8000/mcp/"
  warn "Container: ${CONTAINER_NAME}"
  if [[ -n "${LAN_IP}" ]]; then
    warn "LAN access URL: http://${LAN_IP}:8000/mcp/"
  fi
  if is_api_key_required; then
    warn "Auth mode: API key required (X-API-Key)"
    warn "FASTAPI_API_KEY value: ${FASTAPI_API_KEY_VALUE}"
  else
    warn "Auth mode: public (no API key required)"
  fi
  warn "Cursor config: ${CURSOR_MCP_CONFIG_FILE}"
  warn "ChatGPT setup json: ${CHATGPT_SETUP_FILE}"
  echo
  msg "Available MCP tools:"
  cat <<'EOF'
  - list_sources
  - list_publishers
  - search_datasets
  - get_dataset
  - get_resource
  - preview_resource
  - publisher_summary
  - datastore_search
  - call_source_endpoint
  - memory_search
EOF
  echo
  msg "Tool briefs:"
  cat <<'EOF'
  - list_sources: show configured connectors
  - list_publishers: list government publishers
  - search_datasets: ranked dataset discovery
  - get_dataset/get_resource: metadata detail retrieval
  - preview_resource: safe row-limited previews
  - publisher_summary: publisher-level data profile
  - datastore_search: CKAN datastore queries
  - call_source_endpoint: allowlisted ministry API calls
  - memory_search: semantic search over stored memory vectors
EOF
  echo
  msg "Useful commands:"
  cat <<'EOF'
  ./ksa-mcp.sh status   # show container and endpoint status
  ./ksa-mcp.sh logs     # stream container logs
  ./ksa-mcp.sh stop     # stop and remove container
  ./ksa-mcp.sh rebuild  # force clean rebuild and restart
  ./ksa-mcp.sh configure # regenerate MCP connection files only
EOF
}

wait_for_server() {
  local code="000"
  local fallback_code="000"
  local retries=60
  for ((i=1; i<=retries; i++)); do
    code="$(curl -sS -o /dev/null -w '%{http_code}' "${HEALTH_URL}" || true)"
    fallback_code="$(curl -sS -o /dev/null -w '%{http_code}' "${LOCAL_FALLBACK_BASE_URL}/health" || true)"
    if [[ "${code}" == "200" ]]; then
      ok "Health check passed (HTTP ${code})"
      return 0
    fi
    if [[ "${fallback_code}" == "200" ]]; then
      warn "Service is healthy on ${LOCAL_FALLBACK_BASE_URL}; configured base URL currently unresolved."
      return 0
    fi
    sleep 1
  done
  fail "Server did not become healthy at ${HEALTH_URL} or ${LOCAL_FALLBACK_BASE_URL}/health."
}

smoke_test_api() {
  local code
  local probe_base_url="${BASE_URL}"
  local base_code
  base_code="$(curl -sS -o /dev/null -w '%{http_code}' "${BASE_URL}/health" || true)"
  if [[ "${base_code}" != "200" ]]; then
    probe_base_url="${LOCAL_FALLBACK_BASE_URL}"
  fi
  if is_api_key_required; then
    code="$(
      curl -sS -o /dev/null -w '%{http_code}' \
        -H "X-API-Key: ${FASTAPI_API_KEY_VALUE}" \
        "${probe_base_url}/api/welcome" || true
    )"
    if [[ "${code}" == "200" ]]; then
      ok "FastAPI auth smoke test passed (HTTP 200 at ${probe_base_url}/api/welcome)"
    else
      fail "FastAPI auth smoke test failed (HTTP ${code} at ${probe_base_url}/api/welcome)"
    fi
  else
    code="$(
      curl -sS -o /dev/null -w '%{http_code}' "${probe_base_url}/api/welcome" || true
    )"
    if [[ "${code}" == "200" ]]; then
      ok "FastAPI public-mode smoke test passed (HTTP 200 at ${probe_base_url}/api/welcome)"
    else
      fail "FastAPI public-mode smoke test failed (HTTP ${code} at ${probe_base_url}/api/welcome)"
    fi
  fi
}

compose_up() {
  compose -f "${PROJECT_ROOT}/docker-compose.yml" up -d --remove-orphans
}

cmd_start() {
  check_prerequisites
  print_banner
  write_local_connection_files
  msg "Building Docker image (installs Python + dependencies inside image)..."
  compose -f "${PROJECT_ROOT}/docker-compose.yml" build --pull
  msg "Starting MCP container..."
  compose_up
  wait_for_server
  smoke_test_api
  print_welcome
}

cmd_stop() {
  check_prerequisites
  msg "Stopping MCP container..."
  compose -f "${PROJECT_ROOT}/docker-compose.yml" down --remove-orphans
  ok "Stopped."
}

cmd_status() {
  check_prerequisites
  compose -f "${PROJECT_ROOT}/docker-compose.yml" ps
  local code
  code="$(curl -sS -o /dev/null -w '%{http_code}' "${HEALTH_URL}" || true)"
  if [[ "${code}" == "000" ]]; then
    warn "Endpoint status: unreachable (${HEALTH_URL})"
  else
    ok "Endpoint status: HTTP ${code} (${HEALTH_URL})"
  fi
}

cmd_logs() {
  check_prerequisites
  compose -f "${PROJECT_ROOT}/docker-compose.yml" logs -f
}

cmd_rebuild() {
  check_prerequisites
  print_banner
  write_local_connection_files
  msg "Rebuilding from scratch..."
  compose -f "${PROJECT_ROOT}/docker-compose.yml" down --remove-orphans
  compose -f "${PROJECT_ROOT}/docker-compose.yml" build --no-cache
  compose_up
  wait_for_server
  smoke_test_api
  print_welcome
}

cmd_configure() {
  check_prerequisites
  print_banner
  write_local_connection_files
  ok "Configuration files generated. You can now run ./ksa-mcp.sh start"
}

usage() {
  cat <<'EOF'
Usage: ./ksa-mcp.sh [start|stop|status|logs|rebuild|configure|help]

Default command: start
Use configure to regenerate local Cursor + ChatGPT setup files.
EOF
}

main() {
  local cmd="${1:-start}"
  case "${cmd}" in
    start) cmd_start ;;
    stop) cmd_stop ;;
    status) cmd_status ;;
    logs) cmd_logs ;;
    rebuild) cmd_rebuild ;;
    configure) cmd_configure ;;
    help|-h|--help) usage ;;
    *)
      usage
      fail "Unknown command: ${cmd}"
      ;;
  esac
}

main "$@"
