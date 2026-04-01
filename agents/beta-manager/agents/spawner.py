#!/usr/bin/env python3
"""
Agent Spawner - Dynamic agent registration and management for ai_final orchestrator.

This module provides functionality to:
- Spawn new agent processes with automatic port assignment
- Register agents with the orchestrator (port 18830)
- Monitor agent health and restart failed agents
- Manage agent lifecycle (start, stop, restart, list)

Usage:
    python spawner.py spawn --agent-type coding --name my-worker
    python spawner.py list
    python spawner.py stop --name my-worker
    python spawner.py health-check
"""

import argparse
import json
import logging
import os
import random
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.error import URLError
from urllib.request import Request, urlopen

# Configuration defaults
DEFAULT_ORCHESTRATOR_PORT = 18830
DEFAULT_MANAGER_PORT_START = 18801
DEFAULT_MANAGER_PORT_END = 18802
DEFAULT_WORKER_PORT_START = 18803
DEFAULT_WORKER_PORT_END = 18806
HEALTH_CHECK_INTERVAL = 30  # seconds
HEALTH_CHECK_TIMEOUT = 5  # seconds
MAX_HEALTH_FAILURES = 3

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class PortError(Exception):
    """Raised when port allocation fails."""
    pass


class RegistrationError(Exception):
    """Raised when orchestrator registration fails."""
    pass


@dataclass
class AgentConfig:
    """Configuration for an agent instance."""
    name: str
    agent_type: str  # e.g., 'coding', 'manager', 'specialist'
    port: int
    command: str
    env: Dict[str, str] = field(default_factory=dict)
    health_endpoint: str = "/health"
    max_restarts: int = 3
    restart_delay: int = 5  # seconds


@dataclass
class AgentInstance:
    """Represents a running agent instance."""
    config: AgentConfig
    process: Optional[subprocess.Popen] = None
    pid: Optional[int] = None
    status: str = "pending"  # pending, running, stopping, stopped, failed
    health_failures: int = 0
    registered: bool = False
    registration_id: Optional[str] = None
    started_at: Optional[datetime] = None
    last_health_check: Optional[datetime] = None
    restart_count: int = 0


class JSONFormatter(logging.Formatter):
    """JSON log formatter for observability."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if hasattr(record, "extra"):
            log_data.update(record.extra)
        return json.dumps(log_data)


class PortManager:
    """Manages automatic port assignment for agents."""
    
    def __init__(
        self,
        manager_range: tuple[int, int] = (DEFAULT_MANAGER_PORT_START, DEFAULT_MANAGER_PORT_END),
        worker_range: tuple[int, int] = (DEFAULT_WORKER_PORT_START, DEFAULT_WORKER_PORT_END),
    ):
        self.manager_range = manager_range
        self.worker_range = worker_range
        self._allocated_ports: Set[int] = set()
        self._load_existing_agents()
    
    def _load_existing_agents(self) -> None:
        """Load already allocated ports from the registry."""
        registry_path = Path.home() / ".openclaw" / "agent_registry.json"
        if registry_path.exists():
            try:
                with open(registry_path) as f:
                    registry = json.load(f)
                    for agent in registry.get("agents", []):
                        if "port" in agent:
                            self._allocated_ports.add(agent["port"])
            except (json.JSONDecodeError, IOError):
                pass
    
    def _save_registry(self, agents: Dict[str, AgentInstance]) -> None:
        """Save current agent registry to disk."""
        registry_path = Path.home() / ".openclaw" / "agent_registry.json"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        
        registry = {
            "updated_at": datetime.utcnow().isoformat(),
            "agents": [
                {
                    "name": name,
                    "type": inst.config.agent_type,
                    "port": inst.config.port,
                    "pid": inst.pid,
                    "status": inst.status,
                    "registered": inst.registered,
                }
                for name, inst in agents.items()
            ]
        }
        
        with open(registry_path, "w") as f:
            json.dump(registry, f, indent=2)
    
    def allocate_port(self, agent_type: str) -> int:
        """Allocate an available port for an agent.
        
        Args:
            agent_type: Either 'manager' or 'worker'
            
        Returns:
            Available port number
            
        Raises:
            PortError: If no ports are available
        """
        port_range = self.manager_range if agent_type == "manager" else self.worker_range
        available = set(range(port_range[0], port_range[1] + 1)) - self._allocated_ports
        
        if not available:
            raise PortError(f"No available ports in range {port_range}")
        
        port = random.choice(list(available))
        self._allocated_ports.add(port)
        return port
    
    def release_port(self, port: int) -> None:
        """Release a port back to the pool."""
        self._allocated_ports.discard(port)
    
    def is_port_available(self, port: int) -> bool:
        """Check if a port is available."""
        return port not in self._allocated_ports


class HealthMonitor:
    """Monitors agent health via HTTP health checks."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self._stop_event = False
    
    def check_health(self, instance: AgentInstance) -> bool:
        """Perform a health check on an agent.
        
        Args:
            instance: The agent instance to check
            
        Returns:
            True if healthy, False otherwise
        """
        if not instance.config.port:
            return False
        
        url = f"http://localhost:{instance.config.port}{instance.config.health_endpoint}"
        
        try:
            req = Request(url, method="GET")
            req.add_header("Accept", "application/json")
            
            with urlopen(req, timeout=HEALTH_CHECK_TIMEOUT) as response:
                instance.last_health_check = datetime.utcnow()
                if response.status == 200:
                    instance.health_failures = 0
                    return True
                else:
                    instance.health_failures += 1
                    return False
                    
        except URLError as e:
            self.logger.debug(f"Health check failed for {instance.config.name}: {e}")
            instance.health_failures += 1
            return False
        except Exception as e:
            self.logger.error(f"Health check error for {instance.config.name}: {e}")
            instance.health_failures += 1
            return False
    
    def is_agent_healthy(self, instance: AgentInstance) -> bool:
        """Check if agent is considered healthy based on failure count."""
        return instance.health_failures < MAX_HEALTH_FAILURES
    
    def should_restart(self, instance: AgentInstance) -> bool:
        """Determine if agent
class AgentSpawner:
    """Main agent spawning and management class."""
    
    def __init__(self, orchestrator_port: int = DEFAULT_ORCHESTRATOR_PORT):
        self.orchestrator_port = orchestrator_port
        self.port_manager = PortManager()
        self.health_monitor = HealthMonitor(self._setup_logger())
        self.agents: Dict[str, AgentInstance] = {}
        self._load_registry()
        self.logger = self.health_monitor.logger
    
    def _setup_logger(self) -> logging.Logger:
        """Configure JSON logging."""
        logger = logging.getLogger("agent_spawner")
        logger.setLevel(logging.INFO)
        
        # Console handler with JSON formatting
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        
        return logger
    
    def _load_registry(self) -> None:
        """Load existing agent registry."""
        registry_path = Path.home() / ".openclaw" / "agent_registry.json"
        if registry_path.exists():
            try:
                with open(registry_path) as f:
                    data = json.load(f)
                    for agent_data in data.get("agents", []):
                        name = agent_data["name"]
                        # Create minimal config and instance
                        config = AgentConfig(
                            name=name,
                            agent_type=agent_data.get("type", "unknown"),
                            port=agent_data.get("port", 0),
                            command="",
                        )
                        instance = AgentInstance(config=config)
                        instance.status = agent_data.get("status", "unknown")
                        instance.registered = agent_data.get("registered", False)
                        instance.pid = agent_data.get("pid")
                        self.agents[name] = instance
                        self.logger.info(f"Loaded agent {name} from registry", extra={"agent": name})
            except Exception as e:
                self.logger.error(f"Failed to load registry: {e}")
    
    def _save_registry(self) -> None:
        """Save current agent registry."""
        self.port_manager._save_registry(self.agents)
    
    def _register_with_orchestrator(self, instance: AgentInstance) -> bool:
        """Register agent with the orchestrator.
        
        Args:
            instance: The agent instance to register
            
        Returns:
            True if registration succeeded
        """
        url = f"http://localhost:{self.orchestrator_port}/register"
        
        payload = {
            "name": instance.config.name,
            "type": instance.config.agent_type,
            "port": instance.config.port,
            "pid": instance.pid,
            "status": instance.status,
        }
        
        try:
            req = Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            with urlopen(req, timeout=HEALTH_CHECK_TIMEOUT) as response:
                if response.status == 200:
                    resp_data = json.loads(response.read().decode("utf-8"))
                    instance.registration_id = resp_data.get("id")
                    instance.registered = True
                    self.logger.info(
                        f"Registered {instance.config.name} with orchestrator",
                        extra={"registration_id": instance.registration_id}
                    )
                    return True
                else:
                    self.logger.error(
                        f"Registration failed with status {response.status}",
                        extra={"agent": instance.config.name}
                    )
                    return False
                    
        except Exception as e:
            self.logger.error(
                f"Registration error: {e}",
                extra={"agent": instance.config.name}
            )
            return False
    
    def _unregister_from_orchestrator(self, instance: AgentInstance) -> bool:
        """Unregister agent from the orchestrator."""
        if not instance.registration_id:
            return True
        
        url = f"http://localhost:{self.orchestrator_port}/unregister/{instance.registration_id}"
        
        try:
            req = Request(url, method="DELETE")
            with urlopen(req, timeout=HEALTH_CHECK_TIMEOUT) as response:
                if response.status in (200, 204):
                    instance.registered = False
                    instance.registration_id = None
                    self.logger.info(f"Unregistered {instance.config.name}")
                    return True
        except Exception as e:
            self.logger.error(f"Unregister error: {e}", extra={"agent": instance.config.name})
        
        return False
    
    def spawn(
        self,
        name: str,
        agent_type: str,
        command: str,
        env: Optional[Dict[str, str]] = None,
        auto_register: bool = True,
    ) -> AgentInstance:
        """Spawn a new agent process.
        
        Args:
            name: Unique agent name
            agent_type: Type of agent (manager, worker, etc.)
            command: Command to run
            env: Optional environment variables
            auto_register: Whether to auto-register with orchestrator
            
        Returns:
            AgentInstance for the spawned agent
            
        Raises:
            ValueError: If agent name already exists
            PortError: If no ports available
        """
        if name in self.agents:
            raise ValueError(f"Agent {name} already exists")
        
        port = self.port_manager.allocate_port(agent_type)
        config = AgentConfig(
            name=name,
            agent_type=agent_type,
            port=port,
            command=command,
            env=env or {},
        )
        
        instance = AgentInstance(config=config)
        
        # Setup environment
        run_env = os.environ.copy()
        run_env["AGENT_NAME"] = name
        run_env["AGENT_PORT"] = str(port)
        run_env["AGENT_TYPE"] = agent_type
        run_env.update(config.env)
        
        try:
            # Spawn process
            process = subprocess.Popen(
                command,
                shell=True,
                env=run_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if os.name != "nt" else None,
            )
            
            instance.process = process
            instance.pid = process.pid
            instance.status = "running"
            instance.started_at = datetime.utcnow()
            
            self.agents[name] = instance
            
            self.logger.info(
                f"Spawned agent {name}",
                extra={"pid": instance.pid, "port": port, "command": command}
            )
            
            # Register with orchestrator
            if auto_register:
                time.sleep(0.5)  # Brief delay for process startup
                self._register_with_orchestrator(instance)
            
            self._save_registry()
            return instance
            
        except Exception as e:
            self.port_manager.release_port(port)
            self.logger.error(f"Failed to spawn agent {name}: {e}")
            raise
    
    def stop(self, name: str, force: bool = False) -> bool