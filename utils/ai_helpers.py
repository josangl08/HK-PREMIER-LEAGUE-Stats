# ABOUTME: Helper functions for AI/LLM operations, including gcloud token extraction.
# ABOUTME: Provides get_gcloud_auth_token for Subscription Bridging and umap_scatter_chart for UMAP visualizations.

import subprocess
import logging
import os

import plotly.graph_objects as go

logger = logging.getLogger(__name__)

def get_session_cookie():
    """Returns the Gemini Session Cookie from .env for subscription bridging."""
    return os.getenv("GEMINI_SESSION_COOKIE")

def get_gcloud_auth_token():
    """
    Extracts the current gcloud access token from the system.
    This token carries the identity and subscription benefits of the logged-in user.
    """
    try:
        # Ejecutar el comando oficial de gcloud para imprimir el token
        result = subprocess.run(
            ['gcloud', 'auth', 'print-access-token'],
            capture_output=True,
            text=True,
            check=True
        )
        token = result.stdout.strip()
        if token:
            logger.info("✅ GCLOUD TOKEN: Successfully extracted Pro subscription token.")
            return token
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ GCLOUD ERROR: Failed to get token. Are you logged in? ({e.stderr.strip()})")
    except FileNotFoundError:
        logger.error("❌ GCLOUD NOT FOUND: Please install Google Cloud SDK.")
    
    return None

def umap_scatter_chart(umap_df) -> go.Figure:
    """
    Creates a Plotly scatter chart from a UMAP DataFrame.
    Expected columns: x, y, player_name, and optionally team, season.
    """
    hover_text = umap_df.get("player_name", umap_df.index).astype(str)
    if "team" in umap_df.columns:
        hover_text = hover_text + "<br>" + umap_df["team"].astype(str)
    if "season" in umap_df.columns:
        hover_text = hover_text + "<br>" + umap_df["season"].astype(str)

    fig = go.Figure(go.Scatter(
        x=umap_df["x"],
        y=umap_df["y"],
        mode="markers",
        marker=dict(size=8, color="rgba(0,242,255,0.7)", line=dict(width=1, color="#1a1a2e")),
        text=hover_text,
        hovertemplate="%{text}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=20, b=20),
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    )
    return fig


def is_gcloud_available():
    """Checks if gcloud CLI is installed and accessible."""
    try:
        subprocess.run(['gcloud', '--version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
