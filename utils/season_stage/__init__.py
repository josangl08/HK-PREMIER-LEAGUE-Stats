# ABOUTME: Public entrypoints for the season-stage surface subsystem.
# ABOUTME: Exposes the renderer and context builders while keeping stage-specific logic modular.

__all__ = ["render_season_stage"]


def render_season_stage(*args, **kwargs):
    """Lazily import the renderer to avoid package-level circular imports."""
    from utils.season_stage.season_stage_renderer import render_season_stage as _render

    return _render(*args, **kwargs)
