"""字段配置加载器 — 从 field_config.yaml 读取，生成 ALLOWED_FIELDS 和字段元数据。

用法:
    from app.core.field_config import load_field_config

    config = load_field_config()
    allowed = config.allowed_keys   # set[str]
    groups  = config.groups         # list[FieldGroupDef]
    fields  = config.fields         # list[FieldDef]
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent / "field_config.yaml"


@dataclass
class FieldGroupDef:
    id: str
    name: str


@dataclass
class FieldDef:
    key: str       # API 字段名（如 ownerId, caseSource__c）
    name: str      # 中文显示名
    group: str     # 分组 ID
    type: str      # text | select | textarea | number | phone | datetime
    required: bool = False
    readonly: bool = False
    is_key: bool = False
    ui_visible: bool = True
    options: list[dict[str, str]] = field(default_factory=list)


@dataclass
class FieldConfig:
    groups: list[FieldGroupDef]
    fields: list[FieldDef]

    @property
    def allowed_keys(self) -> set[str]:
        """返回 ALLOWED_FIELDS 集合（所有字段的 key，含 hidden）。"""
        return {f.key for f in self.fields}

    @property
    def visible_keys(self) -> set[str]:
        """返回 UI 可见字段的 key 集合。"""
        return {f.key for f in self.fields if f.ui_visible}

    @property
    def required_keys(self) -> set[str]:
        """返回必填字段的 key 集合。"""
        return {f.key for f in self.fields if f.required}

    def get_field(self, key: str) -> FieldDef | None:
        """按 key 查找字段定义。"""
        for f in self.fields:
            if f.key == key:
                return f
        return None


def _parse_config(raw: dict[str, Any]) -> FieldConfig:
    """将 YAML 原始数据解析为 FieldConfig。"""
    groups = [
        FieldGroupDef(id=g["id"], name=g["name"])
        for g in raw.get("groups", [])
    ]

    fields = []
    for item in raw.get("fields", []):
        fields.append(FieldDef(
            key=item["key"],
            name=item.get("name", item["key"]),
            group=item.get("group", ""),
            type=item.get("type", "text"),
            required=item.get("required", False),
            readonly=item.get("readonly", False),
            is_key=item.get("is_key", False),
            ui_visible=item.get("ui_visible", True),
            options=item.get("options", []),
        ))

    return FieldConfig(groups=groups, fields=fields)


@lru_cache(maxsize=1)
def load_field_config() -> FieldConfig:
    """加载字段配置（结果缓存，进程内只加载一次）。"""
    if not _CONFIG_PATH.exists():
        logger.error("字段配置文件不存在: %s", _CONFIG_PATH)
        raise FileNotFoundError(f"字段配置文件不存在: {_CONFIG_PATH}")

    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not raw or "fields" not in raw:
        raise ValueError("field_config.yaml 格式错误：缺少顶层 'fields' 键")

    config = _parse_config(raw)
    logger.info(
        "字段配置加载完成: %d 个分组, %d 个字段 (可见 %d, 必填 %d)",
        len(config.groups), len(config.fields),
        len(config.visible_keys), len(config.required_keys),
    )
    return config
