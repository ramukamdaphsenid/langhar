#!/bin/bash
set -u

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required to start the backend."
  read -r -p "Install Python 3 now with Homebrew? [y/N] " install_python
  case "$install_python" in
    y|Y|yes|YES)
      if command -v brew >/dev/null 2>&1; then
        if ! brew install python; then
          echo "Python installation failed. Install Python 3 from https://www.python.org/downloads/macos/ and rerun this script."
          read -r -p "Press Return to close..."
          exit 1
        fi
      else
        open "https://www.python.org/downloads/macos/"
        echo "Install Python 3, then rerun this script."
        read -r -p "Press Return to close..."
        exit 1
      fi
      ;;
    *)
      echo "Install Python 3 from https://www.python.org/downloads/macos/ and rerun this script."
      read -r -p "Press Return to close..."
      exit 1
      ;;
  esac
  if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 is not available in this shell's PATH. Restart Terminal and rerun this script."
    read -r -p "Press Return to close..."
    exit 1
  fi
fi

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "Node.js and npm are required to start the Angular frontend."
  read -r -p "Install Node.js now with Homebrew? [y/N] " install_node
  case "$install_node" in
    y|Y|yes|YES)
      if command -v brew >/dev/null 2>&1; then
        if ! brew install node; then
          echo "Node.js installation failed. Install it from https://nodejs.org/ and rerun this script."
          read -r -p "Press Return to close..."
          exit 1
        fi
        if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
          echo "Node.js was installed, but node/npm are not available in this shell's PATH."
          echo "Restart Terminal or update PATH, then rerun this script."
          read -r -p "Press Return to close..."
          exit 1
        fi
      else
        open "https://nodejs.org/en/download"
        echo "Install Node.js LTS, then rerun this script."
        read -r -p "Press Return to close..."
        exit 1
      fi
      ;;
    *)
      echo "Install Node.js LTS from https://nodejs.org/ and rerun this script."
      read -r -p "Press Return to close..."
      exit 1
      ;;
  esac
fi

node_is_supported() {
  node -e 'const [major, minor, patch] = process.versions.node.split(".").map(Number); process.exit((major === 22 && (minor > 22 || (minor === 22 && patch >= 3))) || (major === 24 && (minor > 15 || (minor === 15 && patch >= 0))) || major >= 26 ? 0 : 1)'
}

if ! node_is_supported; then
  echo "Node.js $(node --version) is too old for this Angular frontend. Use Node.js 22.22.3+, 24.15.0+, or 26+."
  if command -v brew >/dev/null 2>&1; then
    read -r -p "Upgrade Node.js with Homebrew now? [y/N] " upgrade_node
    case "$upgrade_node" in
      y|Y|yes|YES)
        if ! brew upgrade node; then
          echo "Node.js upgrade failed. Run 'brew upgrade node' or install a supported version from https://nodejs.org/"
          read -r -p "Press Return to close..."
          exit 1
        fi
        hash -r
        if ! node_is_supported; then
          echo "The active Node.js on PATH is still unsupported. Update PATH or install Node.js 22.22.3+, 24.15.0+, or 26+."
          read -r -p "Press Return to close..."
          exit 1
        fi
        ;;
      *)
        echo "Upgrade Node.js with 'brew upgrade node' or install a supported version from https://nodejs.org/"
        read -r -p "Press Return to close..."
        exit 1
        ;;
    esac
  else
    open "https://nodejs.org/en/download"
    echo "Install Node.js 22.22.3+, 24.15.0+, or 26+, then rerun this script."
    read -r -p "Press Return to close..."
    exit 1
  fi
fi

BACKEND_PYTHON=""
if [ -x "$ROOT_DIR/backend/venv/bin/python" ]; then
  BACKEND_PYTHON="$ROOT_DIR/backend/venv/bin/python"
elif [ -x "$ROOT_DIR/backend/.venv/bin/python" ]; then
  BACKEND_PYTHON="$ROOT_DIR/backend/.venv/bin/python"
else
  if ! python3 -m venv "$ROOT_DIR/backend/venv"; then
    echo "Could not create the backend virtual environment."
    read -r -p "Press Return to close..."
    exit 1
  fi
  BACKEND_PYTHON="$ROOT_DIR/backend/venv/bin/python"
fi

if ! "$BACKEND_PYTHON" -c "import fastapi, uvicorn, requests, xmltodict, pydantic, dotenv, rich, pyodbc" >/dev/null 2>&1; then
  echo "Installing backend dependencies..."
  if ! "$BACKEND_PYTHON" -m pip install -r "$ROOT_DIR/backend/requirements.txt"; then
    echo "Backend dependency installation failed. Check your internet connection and try again."
    read -r -p "Press Return to close..."
    exit 1
  fi
fi

if [ ! -x "$ROOT_DIR/frontend/node_modules/.bin/ng" ]; then
  echo "Installing frontend dependencies..."
  if ! npm --prefix "$ROOT_DIR/frontend" ci; then
    echo "Frontend dependency installation failed. Check your internet connection and try again."
    read -r -p "Press Return to close..."
    exit 1
  fi
fi

cleanup() {
  kill "$backend_pid" "$frontend_pid" 2>/dev/null || true
  wait "$backend_pid" "$frontend_pid" 2>/dev/null || true
}

(
  cd "$ROOT_DIR/backend"
  exec "$BACKEND_PYTHON" -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload
) &
backend_pid=$!

(
  cd "$ROOT_DIR/frontend"
  exec npm start -- --host 127.0.0.1
) &
frontend_pid=$!

trap cleanup EXIT INT TERM

echo "Starting Langhar backend and frontend..."
backend_ready=0
frontend_ready=0
attempts=0
while [ "$attempts" -lt 30 ]; do
  if curl -fsS http://127.0.0.1:8000/openapi.json >/dev/null 2>&1; then
    backend_ready=1
  fi
  if curl -fsS http://127.0.0.1:4200/ >/dev/null 2>&1; then
    frontend_ready=1
  fi
  if [ "$backend_ready" -eq 1 ] && [ "$frontend_ready" -eq 1 ]; then
    break
  fi
  if ! kill -0 "$backend_pid" 2>/dev/null; then
    echo "Backend stopped before it became ready. Review the error above."
    exit 1
  fi
  if ! kill -0 "$frontend_pid" 2>/dev/null; then
    echo "Frontend stopped before it became ready. Review the error above."
    exit 1
  fi
  attempts=$((attempts + 1))
  sleep 1
done

if [ "$backend_ready" -ne 1 ] || [ "$frontend_ready" -ne 1 ]; then
  echo "Langhar did not start within 30 seconds. Review the errors above and try again."
  exit 1
fi

open "http://localhost:4200"
echo "Langhar is running at http://localhost:4200. Press Control-C to stop both services."
wait
