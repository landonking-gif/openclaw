"""Dual-stack (IPv4 + IPv6) launcher for orchestrator-api via uvicorn."""
import socket
import sys
import uvicorn

port = int(sys.argv[1]) if len(sys.argv) > 1 else 18830

# Create a dual-stack IPv6 socket that also accepts IPv4
sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
sock.bind(("::", port))

uvicorn.run("main:app", fd=sock.fileno(), log_level="info")
