import json
import time
import urllib.request
from datetime import datetime

API = "http://localhost:18830"
SESSION = f"recovery-check-{int(time.time())}"


def iso_to_epoch(raw: str):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def post_chat(msg: str, sid: str, timeout: int = 95):
    payload = json.dumps({"message": msg, "session_id": sid}).encode("utf-8")
    req = urllib.request.Request(
        API + "/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def get_activity(sid: str, limit: int = 260, timeout: int = 18):
    with urllib.request.urlopen(
        API + f"/activity/session/{sid}?limit={limit}", timeout=timeout
    ) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_response(sid: str, started_epoch: float, max_wait: int = 260):
    end = time.time() + max_wait
    saw_thinking = False

    while time.time() < end:
        try:
            entries = get_activity(sid).get("entries", [])
        except Exception:
            time.sleep(1.5)
            continue

        response_entries = []
        thinking_like = 0

        for entry in entries:
            ts_epoch = iso_to_epoch(entry.get("ts"))
            if ts_epoch is None or ts_epoch + 1 < started_epoch:
                continue

            event_type = str(entry.get("type", "")).lower()
            if event_type in {
                "llm_thinking",
                "llm_call",
                "llm_tool_calls",
                "delegation",
                "chat_pending",
            }:
                thinking_like += 1

            if event_type == "response" and str(entry.get("content", "")).strip():
                response_entries.append(entry)

        if thinking_like > 0 and not saw_thinking:
            saw_thinking = True
            print("thinking_seen_after_watermark", thinking_like)

        if response_entries:
            return response_entries[-1]

        time.sleep(2.0)

    return None


def run():
    print("session", SESSION)

    start1 = time.time()
    immediate1 = post_chat("Reply with ONLY FIRST-CHECK", SESSION)
    print(
        "turn1_immediate",
        {"pending": immediate1.get("pending"), "status": immediate1.get("status")},
    )
    final1 = wait_response(SESSION, start1)
    print("turn1_final_found", bool(final1))
    print("turn1_final", (final1.get("content", "")[:120] if final1 else ""))

    start2 = time.time()
    immediate2 = post_chat("Reply with ONLY SECOND-CHECK", SESSION)
    print(
        "turn2_immediate",
        {"pending": immediate2.get("pending"), "status": immediate2.get("status")},
    )
    final2 = wait_response(SESSION, start2)
    print("turn2_final_found", bool(final2))
    print("turn2_final", (final2.get("content", "")[:120] if final2 else ""))

    ok = bool(final1) and bool(final2)
    print("PASS" if ok else "FAIL")


if __name__ == "__main__":
    run()
