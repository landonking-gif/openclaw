from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .commands import PORTED_COMMANDS
from .tools import PORTED_TOOLS

CURRENT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_ROOT.parent

RUST_TOOLS_PATH = REPO_ROOT / 'rust' / 'crates' / 'tools' / 'src' / 'lib.rs'
RUST_COMMANDS_PATH = REPO_ROOT / 'rust' / 'crates' / 'commands' / 'src' / 'lib.rs'
RUST_CONVERSATION_PATH = REPO_ROOT / 'rust' / 'crates' / 'runtime' / 'src' / 'conversation.rs'
PARITY_PATH = REPO_ROOT / 'PARITY.md'

LEAK_PUBLIC_TOOL_TARGET = 40
LEAK_PUBLIC_COMMAND_TARGET = 80
LEAK_MISSING_INTERNAL_MODULE_TARGET = 108

PARITY_FAMILY_MARKERS = {
    'plugins': '## plugins/',
    'hooks': '## hooks/',
    'skills': '## skills/ and CLAUDE.md discovery',
    'cli-breadth': '## cli/',
    'assistant-orchestration': '## assistant/ (agentic loop, streaming, tool calling)',
    'services-ecosystem': '## services/ (API client, auth, models, MCP)',
}


@dataclass(frozen=True)
class CapabilityGap:
    label: str
    current: int
    target: int

    @property
    def remaining(self) -> int:
        return max(self.target - self.current, 0)

    @property
    def completion_percent(self) -> float:
        if self.target <= 0:
            return 100.0
        return min(100.0, (self.current / self.target) * 100.0)


@dataclass(frozen=True)
class CapabilityMatrix:
    rust_tool_count: int
    rust_command_count: int
    mirrored_tool_entries: int
    mirrored_command_entries: int
    leak_public_tool_target: int
    leak_public_command_target: int
    leak_missing_internal_module_target: int
    missing_parity_families: tuple[str, ...]

    @property
    def runtime_tool_gap(self) -> CapabilityGap:
        return CapabilityGap(
            label='Runtime tools',
            current=self.rust_tool_count,
            target=self.leak_public_tool_target,
        )

    @property
    def runtime_command_gap(self) -> CapabilityGap:
        return CapabilityGap(
            label='Runtime slash commands',
            current=self.rust_command_count,
            target=self.leak_public_command_target,
        )

    def to_markdown(self) -> str:
        tool_gap = self.runtime_tool_gap
        command_gap = self.runtime_command_gap
        lines = [
            '# Capability Matrix',
            '',
            '## Leak Targets vs Rewrite Runtime',
            f'- Rust runtime tools: **{self.rust_tool_count}** / leak public target **{self.leak_public_tool_target}+** ({tool_gap.completion_percent:.1f}%)',
            f'- Rust runtime slash commands: **{self.rust_command_count}** / leak public target **{self.leak_public_command_target}+** ({command_gap.completion_percent:.1f}%)',
            f'- Mirrored tool snapshot entries (Python metadata): **{self.mirrored_tool_entries}**',
            f'- Mirrored command snapshot entries (Python metadata): **{self.mirrored_command_entries}**',
            f'- Leak internal feature-gated modules (unpublished): **{self.leak_missing_internal_module_target}**',
            '',
            '## Prioritized Runtime Gaps',
            f'- Tools remaining to reach leak public baseline: **{tool_gap.remaining}**',
            f'- Commands remaining to reach leak public baseline: **{command_gap.remaining}**',
            '',
            '## Missing Parity Families (From PARITY.md)',
        ]
        if self.missing_parity_families:
            lines.extend(f'- {family}' for family in self.missing_parity_families)
        else:
            lines.append('- none detected')
        return '\n'.join(lines)


def _read_text(path: Path) -> str:
    if not path.exists():
        return ''
    return path.read_text()


def _slice_braced_block(text: str, marker: str) -> str:
    start = text.find(marker)
    if start == -1:
        return ''
    brace_start = text.find('{', start)
    if brace_start == -1:
        return ''
    depth = 0
    for idx in range(brace_start, len(text)):
        char = text[idx]
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return text[brace_start:idx + 1]
    return ''


def _count_rust_tool_specs() -> int:
    text = _read_text(RUST_TOOLS_PATH)
    fn_block = _slice_braced_block(text, 'pub fn mvp_tool_specs() -> Vec<ToolSpec>')
    return len(re.findall(r'name:\s*"([^"]+)"', fn_block))


def _count_rust_command_specs() -> int:
    text = _read_text(RUST_COMMANDS_PATH)
    marker = 'const SLASH_COMMAND_SPECS: &[SlashCommandSpec] = &['
    start = text.find(marker)
    if start == -1:
        return 0
    end = text.find('];', start)
    if end == -1:
        return 0
    block = text[start:end]
    return len(re.findall(r'name:\s*"([^"]+)"', block))


def _missing_parity_families() -> tuple[str, ...]:
    text = _read_text(PARITY_PATH)
    missing = [name for name, marker in PARITY_FAMILY_MARKERS.items() if marker in text]

    # Promote completed slices based on live runtime capabilities, not only static docs.
    if 'hooks' in missing and _rust_has_command('hooks') and _hook_runtime_enabled():
        missing.remove('hooks')
    if 'skills' in missing and _rust_has_command('skills'):
        missing.remove('skills')
    if 'cli-breadth' in missing and _count_rust_command_specs() >= LEAK_PUBLIC_COMMAND_TARGET:
        missing.remove('cli-breadth')

    return tuple(missing)


def _rust_has_command(name: str) -> bool:
    text = _read_text(RUST_COMMANDS_PATH)
    return f'name: "{name}"' in text


def _hook_runtime_enabled() -> bool:
    text = _read_text(RUST_CONVERSATION_PATH)
    return 'run_pre_tool_use' in text and 'run_post_tool_use' in text


def run_capability_matrix() -> CapabilityMatrix:
    return CapabilityMatrix(
        rust_tool_count=_count_rust_tool_specs(),
        rust_command_count=_count_rust_command_specs(),
        mirrored_tool_entries=len(PORTED_TOOLS),
        mirrored_command_entries=len(PORTED_COMMANDS),
        leak_public_tool_target=LEAK_PUBLIC_TOOL_TARGET,
        leak_public_command_target=LEAK_PUBLIC_COMMAND_TARGET,
        leak_missing_internal_module_target=LEAK_MISSING_INTERNAL_MODULE_TARGET,
        missing_parity_families=_missing_parity_families(),
    )