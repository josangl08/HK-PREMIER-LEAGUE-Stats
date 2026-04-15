# ABOUTME: Shared stage card shell component used by portal stages such as pre-match, season, and career.
# ABOUTME: Encapsulates the common glass-card wrapper so stage surfaces can share one visual container without duplicating classes.

from __future__ import annotations

from typing import Any, Dict, Optional

import dash_bootstrap_components as dbc


_PADDING_BY_SIZE = {
    "sm": "0.75rem",
    "md": "1rem",
    "lg": "1.25rem",
}


def create_stage_card_shell(
    children: Any,
    variant: str = "clean",
    padding: str = "md",
    class_name: str = "",
    style: Optional[Dict[str, Any]] = None,
) -> dbc.Card:
    shell_class = "border-0 prematch-float-card"
    if variant == "clean":
        shell_class = f"{shell_class} prematch-clean-card"
    if class_name:
        shell_class = f"{shell_class} {class_name}"

    shell_style: Dict[str, Any] = {
        "position": "relative",
        "marginBottom": "0",
    }
    if style:
        shell_style.update(style)

    body_style = {"padding": _PADDING_BY_SIZE.get(padding, _PADDING_BY_SIZE["md"])}
    return dbc.Card(
        dbc.CardBody(children, style=body_style),
        className=shell_class,
        style=shell_style,
    )
