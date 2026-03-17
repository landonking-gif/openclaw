# 101 Tools Reference

Complete inventory of the Meta-Orchestrator's internal tools, organized by category.

## System Tools (15)

| Tool | Purpose |
|------|---------|
| `run_shell_command` | Execute shell commands |
| `spawn_process` | Launch background processes |
| `manage_process` | Monitor/kill processes |
| `system_info` | Runtime metrics |
| `resource_monitor` | CPU/memory/disk monitoring |
| `port_manager` | Check/kill ports |
| `network_probe` | DNS, ping, traceroute |
| `read_file` | Read any file |
| `write_file` | Write/create files |
| `list_files` | Directory listing |
| `search_files` | Grep-like search |
| `compress_archive` | ZIP, tar.gz, tar.bz2 |
| `diff_files` | Compare files |
| `file_watch` | Directory watching |
| `eval_python` | Execute Python code |

## Data Tools (12)

| Tool | Purpose |
|------|---------|
| `query_database` | PostgreSQL queries |
| `sqlite_query` | SQLite operations |
| `redis_command` | Redis operations |
| `data_transform` | CSV/JSON/YAML/TOML conversion |
| `hash_encode` | SHA256, base64, tokens |
| `text_process` | Regex, stats, case, lines |
| `regex_builder` | Pattern testing |
| `date_calc` | Date/time calculations |
| `math_compute` | SymPy + NumPy |
| `json_schema` | Schema validation |
| `cache_manager` | Redis caching |
| `metrics_collect` | Time-series metrics |

## Network Tools (8)

| Tool | Purpose |
|------|---------|
| `http_fetch` | HTTP requests (all methods) |
| `webhook_register` | Dynamic endpoints |
| `web_scrape` | HTML parsing |
| `ssh_remote` | Remote execution |
| `cert_check` | SSL inspection |
| `url_tools` | URL parsing/building |
| `api_client` | REST/GraphQL client |
| `service_mesh` | Redis pub/sub |

## Media Tools (10)

| Tool | Purpose |
|------|---------|
| `image_process` | Resize, crop, convert |
| `screenshot` | macOS capture |
| `video_process` | ffmpeg operations |
| `audio_process` | ffmpeg + TTS |
| `pdf_tools` | Create/parse PDFs |
| `qr_code` | Generate/decode QR |
| `browser_automate` | Playwright automation |
| `desktop_control` | GUI automation |
| `screen_share` | Live monitoring |
| `visionclaw` | Meta glasses integration |

## Dev Tools (14)

| Tool | Purpose |
|------|---------|
| `git_ops` | Git + GitHub API |
| `docker_manage` | Container lifecycle |
| `code_analyze` | AST, lint, security |
| `test_runner` | pytest/unittest |
| `dependency_analysis` | Import analysis |
| `project_replace` | Find/replace across files |
| `render_template` | Jinja2 templating |
| `markdown_render` | MD ↔ HTML |
| `sql_schema` | PostgreSQL schema |
| `secret_vault` | Encrypted secrets |
| `full_backup` | System backup |
| `manage_config` | JSON/YAML configs |
| `cron_advanced` | Task chains |
| `process_watchdog` | Auto-restart |

## AI/LLM Tools (6)

| Tool | Purpose |
|------|---------|
| `embeddings` | Vector search |
| `llm_fallback` | Multi-provider routing |
| `github_copilot` | Copilot CLI |
| `analyze_sentiment` | Sentiment analysis |
| `word_counter` | Text statistics |
| `reverse_words` | Text transformation |

## Automation Tools (12)

| Tool | Purpose |
|------|---------|
| `browser_automate` | Headless browser |
| `desktop_control` | Mouse/keyboard |
| `accessibility` | macOS AX API |
| `screen_share` | Continuous capture |
| `osascript` | AppleScript |
| `clipboard` | macOS pasteboard |
| `schedule_task` | Recurring tasks |
| `cron_schedule` | Time-based tasks |
| `workflow_manifest` | YAML workflows |
| `batch_delegate` | Parallel delegation |
| `agent_message` | Direct agent comms |
| `notify_send` | Multi-channel alerts |

## Communication Tools (6)

| Tool | Purpose |
|------|---------|
| `send_notification` | Email via SMTP |
| `notify_send` | macOS/Slack/Discord/Pushover |
| `email_parse` | IMAP + .eml parsing |
| `clipboard` | Read/write clipboard |
| `broadcast_event` | WebSocket events |
| `knowledge_query` | Obsidian vault |

## Memory Tools (8)

| Tool | Purpose |
|------|---------|
| `memory_store` | Store memories |
| `memory_search` | Vector search |
| `knowledge_query` | Obsidian operations |
| `manage_sessions` | Chat sessions |
| `sql_schema` | Database schema |
| `redis_command` | Cache operations |
| `sqlite_query` | Local database |
| `cache_manager` | Smart caching |

## Self-Modification Tools (8)

| Tool | Purpose |
|------|---------|
| `modify_own_code` | Edit main.py |
| `read_own_code` | Inspect source |
| `rollback_code_change` | Undo edits |
| `view_modification_history` | Change log |
| `register_new_tool` | Runtime tools |
| `unregister_tool` | Remove tools |
| `update_system_prompt` | Learn behaviors |
| `remove_prompt_section` | Unlearn |

## Self-Healing Tools (4)

| Tool | Purpose |
|------|---------|
| `run_self_heal` | Clear locks, restart |
| `run_diagnostic` | Health report |
| `query_failure_patterns` | Error analysis |
| `restart_self` | Process restart |

## Delegation Tools (6)

| Tool | Purpose |
|------|---------|
| `delegate_to_alpha` | General tasks |
| `delegate_to_beta` | Coding tasks |
| `delegate_to_gamma` | Research tasks |
| `batch_delegate` | Parallel delegation |
| `agent_message` | Direct messaging |
| `check_quality` | Output scoring |

## Infrastructure Tools (6)

| Tool | Purpose |
|------|---------|
| `install_package` | pip install |
| `manage_env` | Environment variables |
| `create_backup` | Timestamped backups |
| `setup_launchd` | Auto-start |
| `git_command` | Version control |
| `http_server` | Ephemeral file server |

## Usage Examples

### Shell + File + Transform
```python
run_shell_command("ls -la")
read_file("~/config.json")
data_transform(action="convert", data=csv, from_format="csv", to_format="json")
```

### Database + Memory + Knowledge
```python
query_database("SELECT * FROM memories")
memory_store(content="Fact", category="knowledge")
knowledge_query(action="write", path="notes/fact.md", content="...")
```

### Self-Modification
```python
read_own_code(search="def delegate_to_alpha")
modify_own_code(old_text="...", new_text="...")
restart_self()
```

## Related Notes

- [[Meta-Orchestrator]] — Tool user
- [[Self-Modification]] — Evolution
- [[Self-Healing System]] — Recovery
- [[Delegation Patterns]] — Work routing

---

**Tags:** #tools #reference #capabilities #inventory #meta-orchestrator
