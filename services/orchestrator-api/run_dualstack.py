"""Dual-stack (IPv4 + IPv6) launcher for orchestrator-api via uvicorn."""
import socket
import sys
import os

# Load .env from ARMY_HOME so NVAPI_KIMI_KEY_* and other vars are available
_army_home = os.environ.get("ARMY_HOME", os.path.expanduser("~/openclaw-army"))
_env_file = os.path.join(_army_home, ".env")
if os.path.exists(_env_file):
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _val = _line.partition("=")
                _key = _key.strip()
                _val = _val.strip().strip('"').strip("'")
                # Expand ${VAR} references using already-set env
                import re as _re
                _val = _re.sub(r'\$\{(\w+)(?::-[^}]*)?\}', lambda m: os.environ.get(m.group(1), ""), _val)
                if _key and _key not in os.environ:
                    os.environ[_key] = _val

import uvicorn

port = int(sys.argv[1]) if len(sys.argv) > 1 else 18830

# Create a dual-stack IPv6 socket that also accepts IPv4
sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
sock.bind(("::", port))

uvicorn.run("main:app", fd=sock.fileno(), log_level="info")
