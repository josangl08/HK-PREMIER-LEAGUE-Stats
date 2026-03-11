# ABOUTME: Base package for AI and Machine Learning models.
# ABOUTME: Exposes the ModelRegistry for centralized model management.

"""
AI Models package for HK Premier League Stats.
Provides predictors, clustering, similarity, and agentic AI capabilities.
"""

# Lazy import to avoid heavy dependency loading at the top level
def get_model_registry():
    """Returns the ModelRegistry class."""
    from ai_models.model_registry import ModelRegistry
    return ModelRegistry
