import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile


def state_dir():
    home = Path.home()
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or home / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = home / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
    return base / "wstack" / "wayne-mode"


def read_bool(path, key, fallback):
    try:
        with path.open(encoding="utf-8") as stream:
            value = json.load(stream)
    except FileNotFoundError:
        return fallback
    if not isinstance(value, dict) or set(value) != {key} or type(value[key]) is not bool:
        raise ValueError("invalid state")
    return value[key]


def write_bool(path, key, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".wayne-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({key: value}, stream)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main():
    data = json.load(sys.stdin)
    if not isinstance(data, dict):
        raise ValueError("invalid input")
    client = sys.argv[1]
    if client not in ("claude", "codex"):
        raise ValueError("invalid client")
    event = data.get("hook_event_name")
    if event not in ("SessionStart", "UserPromptSubmit"):
        raise ValueError("invalid event")
    sid = data.get("session_id")
    if not isinstance(sid, str) or not sid:
        print(json.dumps({"systemMessage": "wayne-mode：缺少会话标识，未加载规则。"}, ensure_ascii=False))
        return
    root = state_dir()
    config = root / "config.json"
    digest = hashlib.sha256(sid.encode("utf-8")).hexdigest()
    session = root / "sessions" / (client + "-" + digest + ".json")
    default = read_bool(config, "default", True)
    enabled = read_bool(session, "enabled", default)
    if not session.exists():
        write_bool(session, "enabled", enabled)
    prompt = data.get("prompt", "")
    if not isinstance(prompt, str):
        raise ValueError("invalid prompt")
    command = None
    if event == "UserPromptSubmit" and "\n" not in prompt and "\r" not in prompt:
        command = re.fullmatch(r"[ \t]*/(?:wstack:)?wayne-mode(?:[ \t]+([^ \t]+))?(?:[ \t]+([^ \t]+))?[ \t]*", prompt)
    control = False
    if command:
        action, arg = command.groups()
        if action in ("on", "off", "status") and arg is None:
            control = True
            if action != "status":
                enabled = action == "on"
                write_bool(session, "enabled", enabled)
        elif action == "default" and arg in ("on", "off"):
            control = True
            default = arg == "on"
            write_bool(config, "default", default)
        elif action is None or (action not in ("on", "off", "status") and arg is None) or (action == "default" and arg not in ("on", "off")):
            control = True
            action = "invalid"
    status = "开启" if enabled else "关闭"
    if control:
        context = "这是 wayne-mode 控制命令，只需简短确认，不要加载或执行同名技能。当前会话：" + status + "；新会话默认：" + ("开启" if default else "关闭") + "。"
        if action == "invalid":
            context += " 用法：/wayne-mode on|off|status|default on|default off。"
    else:
        context = ""
    if enabled and (not control or action == "on"):
        skill = Path(__file__).resolve().parent.parent / "skills" / "wayne-mode"
        context += "\nwayne-mode 技能目录（相对 Playbook 路径以此为基准）：" + str(skill) + "\n" + (skill / "SKILL.md").read_text(encoding="utf-8")
    elif not enabled:
        context += "\nwayne-mode 已关闭：停用此前 hook 注入的 wayne-mode；用户和项目原有规范仍然有效，不要重新启用该技能。"
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"systemMessage": "wayne-mode：读取或保存失败，未加载规则，请检查配置。"}, ensure_ascii=False))
