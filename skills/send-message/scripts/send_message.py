"""
Send-message skill runtime adapter.

This is the canonical runtime script for the send-message skill.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

SKILL_DIR = Path(__file__).resolve().parents[1]
SKILL_MD = SKILL_DIR / "SKILL.md"

DEFAULT_NAME = "send-message"
DEFAULT_DESCRIPTION = (
    "Use when user asks to send a message to a contact in Lark."
)

SEND_TRIGGER_PATTERN = r"(?:帮我)?给(?P<recipient>.+?)(?:发送|发消息说|发消息|发|说)(?P<message>.+)$"

STAGE_OPEN_SEARCH = 0
STAGE_INPUT_RECIPIENT = 1
STAGE_CLICK_RECIPIENT = 2
STAGE_INPUT_MESSAGE = 3
STAGE_SEND_ENTER = 4
STAGE_DONE = 5


@dataclass(frozen=True)
class SkillDoc:
    """Skill markdown data loaded from SKILL.md."""

    name: str
    description: str
    body: str


def _clean_text(value: str) -> str:
    return value.strip().strip(" ：:，,。！？!?")


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def load_skill_doc() -> SkillDoc:
    """Parse codex-style SKILL.md with optional frontmatter."""
    try:
        raw = SKILL_MD.read_text(encoding="utf-8")
    except OSError:
        return SkillDoc(name=DEFAULT_NAME, description=DEFAULT_DESCRIPTION, body="")

    text = raw.strip()
    if not text.startswith("---"):
        return SkillDoc(name=DEFAULT_NAME, description=DEFAULT_DESCRIPTION, body=text)

    lines = text.splitlines()
    if len(lines) < 3:
        return SkillDoc(name=DEFAULT_NAME, description=DEFAULT_DESCRIPTION, body=text)

    end_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break

    if end_index is None:
        return SkillDoc(name=DEFAULT_NAME, description=DEFAULT_DESCRIPTION, body=text)

    fields: dict[str, str] = {}
    for line in lines[1:end_index]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip().lower()] = _strip_quotes(value)

    body = "\n".join(lines[end_index + 1 :]).strip()
    name = fields.get("name") or DEFAULT_NAME
    description = fields.get("description") or DEFAULT_DESCRIPTION
    return SkillDoc(name=name, description=description, body=body)


def match_send_intent(user_command: str) -> dict[str, str] | None:
    """Extract recipient and message when command matches send-message pattern."""
    text = (user_command or "").strip()
    if not text:
        return None

    match = re.search(SEND_TRIGGER_PATTERN, text)
    if not match:
        return None

    recipient = _clean_text(match.group("recipient"))
    message = _clean_text(match.group("message"))
    if not recipient or not message:
        return None
    return {"recipient": recipient, "message": message}


@dataclass
class SendMessageSkill:
    """Prompt + gate hybrid skill to reduce wrong-contact sends."""

    recipient: str
    message: str
    doc: SkillDoc
    stage: int = STAGE_OPEN_SEARCH
    contact_click_retry: int = 0

    @property
    def name(self) -> str:
        return self.doc.name

    @property
    def description(self) -> str:
        return self.doc.description

    @property
    def trigger_condition(self) -> str:
        return SEND_TRIGGER_PATTERN

    @classmethod
    def try_create(cls, user_command: str) -> "SendMessageSkill | None":
        intent = match_send_intent(user_command)
        if not intent:
            return None
        return cls(
            recipient=intent["recipient"],
            message=intent["message"],
            doc=load_skill_doc(),
        )

    def _guidance_block(self) -> str:
        return (
            f"[Active Skill]\n"
            f"name: {self.name}\n"
            f"description: {self.description}\n"
            f"trigger_condition: {self.trigger_condition}\n"
            f"recipient: {self.recipient}\n"
            f"message: {self.message}\n\n"
            f"[Skill Main Content]\n{self.doc.body}"
        ).strip()

    def plan_guidance(self) -> str:
        return self._guidance_block()

    def react_guidance(self) -> str:
        stage_hint = {
            STAGE_OPEN_SEARCH: "下一步必须先打开搜索框（open_search 或 press_key(command+k/cmd+k/ctrl+k)）",
            STAGE_INPUT_RECIPIENT: f"下一步必须在搜索框输入联系人：{self.recipient}",
            STAGE_CLICK_RECIPIENT: "下一步必须点击搜索结果中的目标联系人（优先顶部精确匹配）",
            STAGE_INPUT_MESSAGE: f"已点击联系人，下一步必须直接输入消息内容：{self.message}",
            STAGE_SEND_ENTER: "下一步必须按回车发送",
            STAGE_DONE: "下一步必须 done",
        }.get(self.stage, "按目标继续")
        click_policy = (
            "[Click Policy]\n"
            f"- 目标联系人必须是“{self.recipient}”精确匹配。\n"
            "- 只能点击“联系人”结果行，不要点群聊/话题/文档结果。\n"
            "- 若出现与联系人无关条目（例如“论文重投”这类群聊），禁止点击。\n"
            "- 优先点击联系人结果第一条（通常位于搜索结果上方）。\n"
            "- 点击同一格时优先点上半区（offset_ratio≈0.22），不要点中下半区。\n"
            "- 不确定时先 wait 或重新搜索，不要盲点。"
        )
        return f"{self._guidance_block()}\n\n[Stage Constraint]\n{stage_hint}\n\n{click_policy}"

    @staticmethod
    def _is_open_search_action(action: dict[str, object]) -> bool:
        action_type = str(action.get("action", "")).lower()
        if action_type == "open_search":
            return True
        if action_type != "press_key":
            return False
        key = str(action.get("key", "")).lower().strip()
        return key in ("command+k", "cmd+k", "ctrl+k", "control+k")

    def enforce_action(self, action: dict[str, object]) -> dict[str, object]:
        """Enforce minimal reliable sequence for send-message."""
        action_type = str(action.get("action", "")).lower().strip()

        if self.stage == STAGE_OPEN_SEARCH:
            if not self._is_open_search_action(action):
                print("技能门控(send-message)：先打开搜索框。")
                return {"action": "open_search", "reason": "skill gate: 打开搜索框"}
            return action

        if self.stage == STAGE_INPUT_RECIPIENT:
            text = str(action.get("text", ""))
            if not (action_type == "input_text" and text == self.recipient):
                print("技能门控(send-message)：先在搜索框输入联系人。")
                return {
                    "action": "input_text",
                    "text": self.recipient,
                    "reason": "skill gate: 在搜索框输入联系人",
                }
            return action

        if self.stage == STAGE_CLICK_RECIPIENT:
            if action_type != "click_grid":
                print("技能门控(send-message)：先点击联系人搜索结果。")
                return {
                    "action": "wait",
                    "seconds": 0.8,
                    "reason": "skill gate: 等待并重新定位联系人结果",
                }
            try:
                grid = int(action.get("grid", 0))
            except (TypeError, ValueError):
                grid = 0
            if grid > 12 and self.contact_click_retry < 2:
                self.contact_click_retry += 1
                print("技能门控(send-message)：联系人点击位置偏低，优先点击搜索结果上方第一条精确联系人。")
                return {
                    "action": "wait",
                    "seconds": 0.8,
                    "reason": "skill gate: 重新定位上方联系人条目后再点击",
                }
            patched = dict(action)
            patched["offset_ratio"] = 0.22
            patched["reason"] = (
                f"{str(action.get('reason', '')).strip()} "
                "[skill gate: 联系人点击固定上半区，避免误点下方条目]"
            ).strip()
            return patched

        if self.stage == STAGE_INPUT_MESSAGE:
            if action_type == "click_grid":
                print("技能门控(send-message)：联系人已点击，禁止重复点击，直接输入消息。")
                return {
                    "action": "input_text",
                    "text": self.message,
                    "reason": "skill gate: 联系人已进入聊天，直接输入消息",
                }
            text = str(action.get("text", ""))
            if not (action_type == "input_text" and text == self.message):
                print("技能门控(send-message)：先输入消息内容。")
                return {
                    "action": "input_text",
                    "text": self.message,
                    "reason": "skill gate: 输入消息内容",
                }
            return action

        if self.stage == STAGE_SEND_ENTER:
            key = str(action.get("key", "")).lower().strip()
            if not (action_type == "press_key" and key in ("enter", "return")):
                print("技能门控(send-message)：按回车发送消息。")
                return {"action": "press_key", "key": "enter", "reason": "skill gate: 回车发送"}
            return action

        if action_type != "done":
            print("技能门控(send-message)：流程结束，仅允许 done。")
            return {"action": "done", "reason": "skill gate: 发送流程完成"}
        return action

    def on_action_result(self, action: dict[str, object], success: bool) -> None:
        if not success:
            return

        action_type = str(action.get("action", "")).lower().strip()
        if self.stage == STAGE_OPEN_SEARCH and self._is_open_search_action(action):
            self.stage = STAGE_INPUT_RECIPIENT
            return
        if self.stage == STAGE_INPUT_RECIPIENT and action_type == "input_text":
            self.stage = STAGE_CLICK_RECIPIENT
            self.contact_click_retry = 0
            return
        if self.stage == STAGE_CLICK_RECIPIENT and action_type == "click_grid":
            self.stage = STAGE_INPUT_MESSAGE
            return
        if self.stage == STAGE_INPUT_MESSAGE and action_type == "input_text":
            self.stage = STAGE_SEND_ENTER
            return
        if self.stage == STAGE_SEND_ENTER and action_type == "press_key":
            self.stage = STAGE_DONE

    def allow_done(self) -> bool:
        return self.stage >= STAGE_DONE


def describe_send_message_skill() -> dict[str, str]:
    """Static descriptor for catalog text and router prompt."""
    doc = load_skill_doc()
    return {
        "name": doc.name,
        "description": doc.description,
        "trigger_condition": SEND_TRIGGER_PATTERN,
    }


__all__ = [
    "SendMessageSkill",
    "describe_send_message_skill",
]

