import argparse
import socket
from pathlib import Path

import uvicorn


PREFERRED_PORTS = [8000, 8001, 8002, 8003, 8004, 8005, 8006, 8007, 8008, 8010]
FALLBACK_PORT_RANGE = range(8011, 8101)


def is_port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) != 0


def choose_port(host: str, explicit_port: int | None) -> int:
    if explicit_port is not None:
        if not is_port_free(host, explicit_port):
            raise RuntimeError(f"Requested port {explicit_port} is already in use.")
        return explicit_port

    for port in PREFERRED_PORTS:
        if is_port_free(host, port):
            return port
    for port in FALLBACK_PORT_RANGE:
        if is_port_free(host, port):
            return port
    raise RuntimeError("No free port found in 8000-8100.")


def write_frontend_env(frontend_dir: Path, host: str, port: int) -> Path:
    env_file = frontend_dir / ".env.local"
    env_file.write_text(f"VITE_API_BASE_URL=http://{host}:{port}\n", encoding="utf-8")
    return env_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start backend on a free local port and sync frontend API URL."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind backend server.")
    parser.add_argument("--port", type=int, default=None, help="Optional explicit backend port.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only resolve port and write frontend env; do not start server.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parent
    frontend_dir = project_root / "frontend"

    if not frontend_dir.exists():
        raise RuntimeError("Could not find frontend directory.")

    selected_port = choose_port(args.host, args.port)
    env_path = write_frontend_env(frontend_dir, args.host, selected_port)
    print(f"Synced frontend API base URL in {env_path} -> http://{args.host}:{selected_port}")

    if args.dry_run:
        print("Dry run complete. Backend not started.")
        return

    print(f"Starting FastAPI backend on http://{args.host}:{selected_port}")
    uvicorn.run("main:app", host=args.host, port=selected_port, reload=False)


if __name__ == "__main__":
    main()
