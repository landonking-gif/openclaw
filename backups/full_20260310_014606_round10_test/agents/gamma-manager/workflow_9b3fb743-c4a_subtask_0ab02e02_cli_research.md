# Research: What Makes a Good CLI Tool

**Workflow ID:** 9b3fb743-c4a  
**Subtask ID:** 0ab02e02  
**Completed by:** gamma-manager  
**Priority:** 1  

---

## 1. Best Practices and Design Principles

### Core Philosophy: Human-First Design
Modern CLI tools should be **human-first** (machine-second), designed as text-based user interfaces rather than just programmatic interfaces.

### Unix Philosophy Modernized
| Principle | Implementation |
|-----------|---------------|
| **Do one thing well** | Small, focused tools that compose together via pipes |
| **Text as universal interface** | Easy to pipe between commands; JSON for structured data |
| **Simple parts, clean interfaces** | Program composability over monolithic tools |

### UX Guidelines

**Command Naming:**
- Use actionable verbs: `get`, `list`, `create`, `delete`, `update`
- Follow established patterns: `git push`, `docker run`, `kubectl get`

**Options/Flags:**
- Short flags: `-v`, `-f`, `-o`
- Long flags: `--verbose`, `--file`, `--output`
- Use `--no-` prefix for negative booleans: `--no-color`

### Help System Requirements
1. **Every command must support `--help`** — auto-generated, accurate, current
2. **Include working examples** in help text
3. **Show expected output** format explicitly
4. **Document exit codes** and common error scenarios

Example well-structured help:
```
Usage: mytool [OPTIONS] COMMAND [ARGS]...

Options:
  --verbose, -v          Enable verbose output
  --output, -o FORMAT    Output format (json|yaml|table)
  --help                 Show this message and exit

Commands:
  list      List all items
  create    Create a new item
  delete    Delete an item
```

### Error Handling Standards

**Exit Codes:**
- `0`: Success
- `1`: General error
- `2`: Usage error (missing args, invalid flags)
- `3-255`: Application-specific errors

**Best Practice Error Messages:**
```python
# Good: Clear, actionable, with suggestion
click.echo(f"Error: File '{path}' not found", err=True)
click.echo("Run 'mytool init' to create a default configuration.")
```

---

## 2. Python CLI Frameworks Comparison

### Framework Decision Matrix

| Feature | Typer | Click | argparse | docopt |
|---------|-------|-------|----------|--------|
| Min code required | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐ |
| Type safety | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐ |
| Auto-help | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ |
| Shell completion | ⭐⭐⭐ | ⭐⭐ | ❌ | ❌ |
| Flexibility | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| Learning curve | Low | Medium | High | Medium |
| Maintenance | ✅ Active | ✅ Active | Stdlib | ⚠️ Stale |

### Detailed Framework Analysis

#### **Typer** ⭐ RECOMMENDED FOR NEW PROJECTS
- **Philosophy:** "FastAPI of CLIs" — type hints drive the interface
- **Pros:** Minimal boilerplate, automatic help generation, excellent IDE support, built on Click (proven), includes Rich, automatic shell completion
- **Cons:** Requires Python 3.8+, newer framework (fewer third-party examples)
- **When to use:** New projects, teams familiar with FastAPI, type safety required

```python
import typer
app = typer.Typer()

@app.command()
def hello(name: str, count: int = 1, formal: bool = False):
    for _ in range(count):
        typer.echo(f"Hello {name}!")

if __name__ == "__main__":
    app()
```

#### **Click** — Legacy/Mature Projects
- **Philosophy:** "Command Line Interface Creation Kit" — composable, highly configurable
- **Pros:** Battle-tested (Flask ecosystem), extensive ecosystem, highly customizable, rich plugin ecosystem
- **Cons:** More verbose than Typer, steeper learning curve
- **When to use:** Large applications needing customization, existing Click codebase

#### **argparse** — Stdlib, No Dependencies
- **Pros:** No dependencies, always available, good for simple scripts
- **Cons:** Verbose syntax, no automatic shell completion, manual help formatting
- **When to use:** Single-file scripts, strict dependency constraints

#### **docopt** — Not Recommended
- **Philosophy:** Documentation drives interface
- **Status:** ⚠️ Limited maintenance, largely unmaintained
- **Not recommended for new projects**

#### **Fire** (Google) — Quick Prototyping
- **Pros:** Zero-code for simple cases, automatic from existing Python
- **Cons:** Less control, limited customization, smaller community
- **When to use:** Quick prototypes, wrapping existing scripts

---

## 3. Examples of Excellent CLI Tools

| Tool | Excellence Factor |
|------|-------------------|
| **git** | Rich subcommand structure, discoverable help, pluggable hooks, consistent UX |
| **gh** (GitHub CLI) | Modern UX, color output, good defaults, JSON output support, clear error messages |
| **jq** | Standard for JSON processing, simple interface, powerful, composable |
| **fzf** | Interactive fuzzy finder, integrates with everything, TUI excellence |
| **ripgrep** (`rg`) | Faster grep alternative, respects .gitignore, colored output, clear flags |
| **restic** | Well-documented, clear progress indicators, multiple backends, exit codes |
| **docker** | Intuitive command structure, good defaults, compose integration |

**Common patterns these tools share:**
- Clear error messages with suggestions
- Support for `--format json` (machine-readable output)
- TTY detection (disable colors when piped)
- Consistent global flags across subcommands
- Sensible defaults with overrides available

---

## 4. Configuration and Output Patterns

### Configuration Hierarchy

**Precedence (highest to lowest):**
```
1. CLI arguments
2. Environment variables
3. Project config file (e.g., .myapprc.toml)
4. User config file (~/.config/myapp/config.toml)
5. Built-in defaults
```

### Config File Format Recommendation

| Format | Best For | Recommendation |
|--------|----------|----------------|
| **TOML** | Python projects | ✅ Recommended |
| **YAML** | Complex nested data | Good |
| **JSON** | API integration | Good |
| **INI** | Simple key-value | Legacy |

### Implementation Pattern
```python
import os
import tomllib
from pathlib import Path

def get_config(cli_args):
    # 1. Start with defaults
    config = DEFAULTS.copy()
    
    # 2. Load user config
    user_conf = Path.home() / ".config/myapp/config.toml"
    if user_conf.exists():
        config.update(tomllib.loads(user_conf.read_text()))
    
    # 3. Load project config
    project_conf = find_project_config()
    if project_conf:
        config.update(tomllib.loads(project_conf.read_text()))
    
    # 4. Environment overrides
    if "MYAPP_API_KEY" in os.environ:
        config["api_key"] = os.environ["MYAPP_API_KEY"]
    
    # 5. CLI args override everything
    config.update(cli_args)
    return config
```

### Output Formatting Best Practices

**Multiple Output Formats:**
```python
@app.command()
def list(format: str = typer.Option("table", "--format", "-f")):
    results = get_data()
    if format == "json":
        typer.echo(json.dumps(results, indent=2))
    elif format == "yaml":
        typer.echo(yaml.dump(results))
    elif format == "csv":
        writer = csv.writer(sys.stdout)
        writer.writerows(results)
    else:  # table
        console.print(table)
```

**Rich Terminal Output (Recommended):**
```python
from rich.console import Console
from rich.table import Table
from rich.progress import track

console = Console()

# Tables with colors
console.print("[bold red]Error:[/] Something went wrong")
console.print(table)  # Rich auto-renders tables beautifully

# Progress bars
for item in track(items, description="Processing..."):
    process(item)
```

---

## 5. Testing Strategies for CLI Applications

### Testing with CliRunner

**Click Testing:**
```python
from click.testing import CliRunner
import pytest

runner = CliRunner()

def test_hello():
    result = runner.invoke(cli, ['