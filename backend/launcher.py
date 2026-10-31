"""Launch the bundled Langhar API and open its local web interface."""
import logging
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import uvicorn

from config.settings import settings

PORT_SCAN_LIMIT = 10
SERVER_SHUTDOWN_TIMEOUT = 2
SERVER_STARTUP_TIMEOUT = 20
logger = logging.getLogger("langhar.launcher")


def _is_port_available(host: str, port: int) -> bool:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


def _resolve_port(host: str, preferred: int) -> int:
    last_port = min(preferred + PORT_SCAN_LIMIT, 65535)
    for port in range(preferred, last_port + 1):
        if _is_port_available(host, port):
            if port != preferred:
                logger.warning("Port %s is already in use; using %s instead.", preferred, port)
            return port
    raise RuntimeError(
        f"Langhar could not find a free port between {preferred} and {last_port}. "
        "Close the application using that port or set APP_PORT in the configuration."
    )


def _browser_url(host: str, port: int) -> str:
    if host == "0.0.0.0" or not host:
        display_host = "127.0.0.1"
    elif host == "::":
        display_host = "::1"
    else:
        display_host = host
    if ":" in display_host and not display_host.startswith("["):
        display_host = f"[{display_host}]"
    return f"http://{display_host}:{port}"


def _initialize_company_profile() -> None:
    profile_path = settings.base_dir / "config" / "company_profile.json"
    if profile_path.exists():
        return

    if getattr(sys, "frozen", False):
        bundled_profile = Path(getattr(sys, "_MEIPASS")) / "data" / "company_profile.json"
    else:
        bundled_profile = settings.base_dir / "config" / "company_profile.json"

    if not bundled_profile.is_file():
        raise FileNotFoundError(f"Bundled company profile is missing: {bundled_profile}")

    profile_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(bundled_profile, profile_path)


def _configure_logging() -> None:
    log_path = settings.base_dir / "logs" / "langhar.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )


def _start_server_process(host: str, port: int) -> subprocess.Popen:
    command = [sys.executable]
    if not getattr(sys, "frozen", False):
        command.append(str(Path(__file__).resolve()))
    command.extend(("--server-worker", host, str(port)))

    return subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _wait_for_server(process: subprocess.Popen, host: str, port: int) -> None:
    connect_host = {"": "127.0.0.1", "0.0.0.0": "127.0.0.1", "::": "::1"}.get(host, host)
    deadline = time.monotonic() + SERVER_STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(
                f"Langhar API server exited during startup with code {return_code}."
            )

        try:
            with socket.create_connection((connect_host, port), timeout=0.25):
                return
        except OSError:
            time.sleep(0.1)

    raise RuntimeError(
        f"Langhar API server did not start listening within {SERVER_STARTUP_TIMEOUT} seconds."
    )


def _stop_server_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=SERVER_SHUTDOWN_TIMEOUT)
    except subprocess.TimeoutExpired:
        logger.warning("API server did not stop; killing its process.")
        process.kill()
        process.wait()


def _show_startup_error(message: str) -> None:
    import ctypes

    ctypes.windll.user32.MessageBoxW(None, message, "Langhar", 0x10)


def _configure_webview(webview_module) -> None:
    # pywebview disables WebView2 downloads by default. Enable its native
    # Save As handler so the PDF download links work in the packaged app.
    webview_module.settings['ALLOW_DOWNLOADS'] = True


def _run_app() -> None:
    import webview

    _configure_webview(webview)
    logging.getLogger("tally_sync").handlers.clear()
    _initialize_company_profile()

    host = settings.server.host
    port = _resolve_port(host, settings.server.port)
    url = _browser_url(host, port)

    server_process = _start_server_process(host, port)

    try:
        _wait_for_server(server_process, host, port)
        logger.info("Langhar is running at %s.", url)
        webview.create_window("Langhar", url, min_size=(1024, 700))
        webview.start(gui="edgechromium")
    finally:
        _stop_server_process(server_process)


def _run_server_worker(host: str, port: int) -> None:
    from api import app

    server = uvicorn.Server(
        uvicorn.Config(app, host=host, port=port, log_level="info", log_config=None)
    )

    server.run()


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--server-worker":
        if len(sys.argv) != 4:
            raise ValueError("The server worker requires a host and port.")
        _configure_logging()
        _run_server_worker(sys.argv[2], int(sys.argv[3]))
        return

    try:
        _configure_logging()
        _run_app()
    except Exception:
        logging.exception("Langhar failed to start.")
        _show_startup_error(
            "Langhar could not start. Check the log file for details:\n"
            f"{settings.base_dir / 'logs' / 'langhar.log'}"
        )


if __name__ == "__main__":
    main()
