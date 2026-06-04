"""
Dorothy OS v2.0 — Desktop Native Launcher
PyWebView-based native window that wraps the Command Center UI.
Falls back to browser launch if pywebview is not available.
"""

import os
import sys
import time
import threading
import webbrowser
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-25s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("Dorothy.Desktop")

# Server configuration
HOST = "127.0.0.1"
PORT = 8000
SERVER_URL = f"http://{HOST}:{PORT}"


def start_server():
    """Start the FastAPI server in a background thread."""
    import asyncio
    import uvicorn

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    logger.info(f"Starting Dorothy OS server on {SERVER_URL}...")
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        log_level="warning",
        access_log=False,
    )


def wait_for_server(timeout: int = 15) -> bool:
    """Wait for the server to become available."""
    import socket

    start = time.time()
    while time.time() - start < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            sock.connect((HOST, PORT))
            sock.close()
            return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            time.sleep(0.3)
    return False


def launch_native_window():
    """Launch Dorothy OS in a native PyWebView window."""
    try:
        import webview

        logger.info("Launching native desktop window...")
        window = webview.create_window(
            title="Dorothy OS v2.0 — Command Center",
            url=SERVER_URL,
            width=1440,
            height=900,
            min_size=(1024, 680),
            resizable=True,
            frameless=False,
            easy_drag=False,
            text_select=True,
        )
        webview.start(debug=False)
    except ImportError:
        logger.warning("pywebview not installed. Opening in default browser...")
        webbrowser.open(SERVER_URL)
        # Keep main thread alive while server runs
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Dorothy OS shutting down.")


def main():
    """Main entry point — starts server then opens desktop window."""
    logger.info("=" * 55)
    logger.info("  Dorothy OS v2.0 — Enterprise AI Operating System")
    logger.info("=" * 55)

    # Start server in background thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # Wait for server to boot
    logger.info("Waiting for server to initialize...")
    if wait_for_server():
        logger.info(f"✓ Server online at {SERVER_URL}")
        launch_native_window()
    else:
        logger.error("✗ Server failed to start within 15 seconds.")
        sys.exit(1)


if __name__ == "__main__":
    main()
