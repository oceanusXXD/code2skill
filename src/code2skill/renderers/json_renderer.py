from __future__ import annotations

import json

from ..models import SkillBlueprint


def render_skill_blueprint(blueprint: SkillBlueprint) -> str:
    """把 blueprint 渲染为稳定、可供后续程序消费的 JSON。"""

    return json.dumps(blueprint.to_dict(), indent=2, ensure_ascii=False)
