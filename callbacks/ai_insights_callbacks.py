# ABOUTME: Interactive callbacks for the AI Insights dashboard.
# ABOUTME: Handles clustering, predictor, and similarity search interactions.

# Standard Library
import logging
from typing import List, Optional

# Third-party
import numpy as np
import pandas as pd
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dcc, html, no_update
from dash.exceptions import PreventUpdate
from flask_login import current_user

# Project
from ai_models.model_registry import ModelRegistry, ModelNotFoundError
from utils.app_context import get_hong_kong_data_manager
from utils.ai_helpers import shap_bar_chart, umap_scatter_chart, similarity_table
from utils.chart_helpers import HKFATheme

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Helper: load processed player DataFrame from DataManager
# ──────────────────────────────────────────────────────────────────────────────

def _get_player_df() -> Optional[pd.DataFrame]:
    """Returns processed_data DataFrame from the registered DataManager, or None."""
    try:
        dm = get_hong_kong_data_manager()
        return dm.processed_data
    except Exception as e:
        logger.warning(f"Could not retrieve player data: {e}")
        return None


def _player_options() -> List[dict]:
    df = _get_player_df()
    if df is None or "Player" not in df.columns:
        return []
    return [{"label": p, "value": p} for p in sorted(df["Player"].dropna().unique())]


def _season_options() -> List[dict]:
    df = _get_player_df()
    if df is None or "Season" not in df.columns:
        return []
    return [{"label": s, "value": s} for s in sorted(df["Season"].dropna().unique())]


def _error_card(msg: str) -> dbc.Alert:
    return dbc.Alert(msg, color="danger", className="mt-2")


def _info_card(msg: str) -> dbc.Alert:
    return dbc.Alert(msg, color="secondary", className="mt-2")


# ──────────────────────────────────────────────────────────────────────────────
# Populate player / season dropdowns on page load
# ──────────────────────────────────────────────────────────────────────────────

@callback(
    Output("ai-predictor-player-dropdown", "options"),
    Output("ai-similarity-player-dropdown", "options"),
    Output("ai-similarity-season-dropdown", "options"),
    Input("ai-insights-role-store", "data"),
    prevent_initial_call=False,
)
def populate_dropdowns(role):
    """Populates player and season dropdowns from the DataManager on page load."""
    players = _player_options()
    seasons = _season_options()

    # For player role, restrict predictor to own player profile
    if role == "player":
        try:
            own_player = getattr(current_user, "player_name", None)
            if own_player:
                players_predictor = [{"label": own_player, "value": own_player}]
                return players_predictor, players, seasons
        except Exception:
            pass

    return players, players, seasons


# ──────────────────────────────────────────────────────────────────────────────
# 8.1 — Clustering callback: lens + k → UMAP scatter
# ──────────────────────────────────────────────────────────────────────────────

@callback(
    Output("ai-clustering-umap-graph", "figure"),
    Output("ai-clustering-status", "children"),
    Input("ai-clustering-btn", "n_clicks"),
    State("ai-clustering-lens-dropdown", "value"),
    State("ai-clustering-k-dropdown", "value"),
    prevent_initial_call=True,
)
def update_clustering_panel(n_clicks, feature_lens, k):
    """
    Runs KMeans + UMAP on the current player data and renders the scatter plot.
    Models are trained on-the-fly from processed_data if no pre-trained model exists.
    """
    if not n_clicks:
        raise PreventUpdate

    df = _get_player_df()
    if df is None or df.empty:
        return {}, _error_card("No player data available. Run the ETL pipeline first.")

    try:
        from sklearn.preprocessing import StandardScaler
        from ai_models.clustering import fit_kmeans, fit_umap, label_archetypes, FEATURE_LENSES

        # Select numeric features
        meta_cols = {"Player", "Season", "Team", "Position", "player_name"}
        feature_cols = [
            c for c in df.columns
            if c not in meta_cols and pd.api.types.is_numeric_dtype(df[c])
        ]

        # Apply feature lens filter
        lens_keywords = FEATURE_LENSES.get(feature_lens, [])
        if lens_keywords:
            feature_cols = [
                c for c in feature_cols
                if any(kw in c.lower() for kw in lens_keywords)
            ] or feature_cols  # fallback to all if no match

        X_raw = df[feature_cols].fillna(0).values
        scaler = StandardScaler()
        X = scaler.fit_transform(X_raw)

        player_names = df["Player"].values if "Player" in df.columns else [str(i) for i in range(len(df))]

        labels, kmeans_model = fit_kmeans(X, k=int(k), feature_lens=feature_lens, feature_names=feature_cols)
        umap_df, _ = fit_umap(X, player_names=list(player_names))

        # Add extra columns for hover
        for col in ["team", "Team", "season", "Season"]:
            if col in df.columns:
                umap_df[col.lower()] = df[col].values

        archetype_labels = label_archetypes(kmeans_model, feature_cols)
        fig = umap_scatter_chart(umap_df, cluster_labels=labels, archetype_labels=archetype_labels)

        status = f"Clustered {len(df)} players into {k} archetypes using '{feature_lens}' lens."
        return fig, html.Span(status, style={"color": HKFATheme.TEXT_SECONDARY})

    except Exception as e:
        logger.error(f"Clustering error: {e}", exc_info=True)
        return {}, _error_card(f"Clustering failed: {str(e)}")


# ──────────────────────────────────────────────────────────────────────────────
# 8.2 — Predictor callback: player + metric + model → prediction + SHAP
# ──────────────────────────────────────────────────────────────────────────────

@callback(
    Output("ai-predictor-result", "children"),
    Output("ai-predictor-shap-graph", "figure"),
    Input("ai-predictor-btn", "n_clicks"),
    State("ai-predictor-player-dropdown", "value"),
    State("ai-predictor-metric-dropdown", "value"),
    State("ai-predictor-model-dropdown", "value"),
    prevent_initial_call=True,
)
def update_predictor_panel(n_clicks, player_name, target_metric, model_type):
    """
    Runs inference for the selected player using a pre-trained model and renders
    the predicted value and SHAP feature importance bar chart.
    """
    if not n_clicks:
        raise PreventUpdate

    if not player_name or not target_metric:
        return _info_card("Select a player and target metric."), {}

    df = _get_player_df()
    if df is None or df.empty:
        return _error_card("No player data available."), {}

    try:
        from data.processors.ml_preprocessor import MLPreprocessor
        from ai_models.predictor import predict, compute_shap

        # Load pre-trained model + scaler from registry
        registry = ModelRegistry()
        model_id = f"{model_type}_{target_metric}"
        scaler_id = f"scaler_{target_metric}"

        try:
            model = registry.load(model_id)
        except ModelNotFoundError:
            return _error_card(
                f"Model '{model_id}' not found. Run: python scripts/train_models.py"
            ), {}

        # Retrieve saved feature names from registry metadata
        reg_data = registry._load_registry()
        feature_cols = reg_data.get(scaler_id, {}).get("latest", {}).get("features") or \
                       reg_data.get(model_id, {}).get("latest", {}).get("features")

        if not feature_cols or not isinstance(feature_cols[0], str):
            return _error_card(
                "Feature metadata missing. Re-run: python scripts/train_models.py"
            ), {}

        # Apply the same feature engineering pipeline that was used during training
        pp = MLPreprocessor()
        numeric_raw = [c for c in df.columns if c in feature_cols or
                       pd.api.types.is_numeric_dtype(df.get(c, pd.Series(dtype=float)))]
        df_eng = pp.compute_temporal_features(df, [c for c in df.columns
                                                    if pd.api.types.is_numeric_dtype(df[c])])
        df_eng = pp.compute_positional_zscores(df_eng, [c for c in df.columns
                                                         if pd.api.types.is_numeric_dtype(df[c])])
        df_eng = pp.compute_benchmark_deltas(df_eng, [c for c in df.columns
                                                       if pd.api.types.is_numeric_dtype(df[c])])
        df_eng = pp.inject_composite_metrics(df_eng)

        # Only keep columns the model knows about
        available_cols = [c for c in feature_cols if c in df_eng.columns]
        missing_cols = [c for c in feature_cols if c not in df_eng.columns]
        if missing_cols:
            logger.warning(f"Predictor: {len(missing_cols)} feature cols missing after engineering.")

        # Filter to player's latest row
        player_df = df_eng[df_eng["Player"] == player_name].sort_values("Season").tail(1)
        if player_df.empty:
            return _error_card(f"No data found for player '{player_name}'."), {}

        # Load persisted scaler or fit a fresh one
        try:
            scaler = registry.load(scaler_id)
        except ModelNotFoundError:
            from sklearn.preprocessing import StandardScaler
            scaler = StandardScaler()
            scaler.fit(df_eng[available_cols].fillna(0).values)

        X_player = player_df[available_cols].fillna(0).values
        X_player_scaled = scaler.transform(X_player)

        # Predict
        prediction = predict(model, X_player_scaled)[0]
        shap_vals = compute_shap(model, X_player_scaled)

        result_card = dbc.Card(
            dbc.CardBody([
                html.H5(f"Predicted {target_metric}", className="card-title text-muted"),
                html.H2(
                    f"{prediction:.2f}",
                    style={"color": HKFATheme.ACCENT_GOLD, "fontWeight": "700"},
                ),
                html.Small(
                    f"{player_name} — {model_type.upper()} model",
                    className="text-muted",
                ),
            ]),
            style={
                "backgroundColor": HKFATheme.BG_TERTIARY,
                "border": f"1px solid {HKFATheme.BORDER_COLOR}",
                "maxWidth": "300px",
            },
        )

        fig = shap_bar_chart(shap_vals, feature_names=available_cols, top_k=10)
        return result_card, fig

    except Exception as e:
        logger.error(f"Predictor error: {e}", exc_info=True)
        return _error_card(f"Prediction failed: {str(e)}"), {}


# ──────────────────────────────────────────────────────────────────────────────
# 8.3 — Similarity callback: player + season → similarity table
# ──────────────────────────────────────────────────────────────────────────────

@callback(
    Output("ai-similarity-result", "children"),
    Input("ai-similarity-btn", "n_clicks"),
    State("ai-similarity-player-dropdown", "value"),
    State("ai-similarity-season-dropdown", "value"),
    prevent_initial_call=True,
)
def update_similarity_panel(n_clicks, player_name, seasons):
    """
    Builds or loads player embeddings, then finds top-10 similar players.
    """
    if not n_clicks:
        raise PreventUpdate

    if not player_name:
        return _info_card("Select a player to find similar profiles.")

    df = _get_player_df()
    if df is None or df.empty:
        return _error_card("No player data available.")

    try:
        from ai_models.similarity import build_embeddings, find_similar

        embeddings = build_embeddings(df)

        # Find query player index (latest season by default)
        player_rows = df[df["Player"] == player_name]
        if player_rows.empty:
            return _error_card(f"Player '{player_name}' not found in data.")

        query_idx = player_rows.index[-1]
        # Align with reset-index position in build_embeddings output
        df_reset = df.reset_index(drop=True)
        query_pos = df_reset[df_reset["Player"] == player_name].index[-1]

        query_embedding = embeddings[query_pos]

        # Build metadata aligned with embeddings
        meta_cols = [c for c in ["Player", "Season", "Team"] if c in df_reset.columns]
        player_meta = df_reset[meta_cols].copy()

        season_filter = list(seasons) if seasons else None
        results = find_similar(
            query_embedding=query_embedding,
            corpus_embeddings=embeddings,
            player_meta=player_meta,
            k=10,
            seasons=season_filter,
            query_index=query_pos,
        )

        if results.empty:
            return _info_card("No similar players found with current filters.")

        return similarity_table(results)

    except Exception as e:
        logger.error(f"Similarity error: {e}", exc_info=True)
        return _error_card(f"Similarity search failed: {str(e)}")


# ──────────────────────────────────────────────────────────────────────────────
# 8.4 — Click-through: similarity table row → navigate to /performance
# ──────────────────────────────────────────────────────────────────────────────

@callback(
    Output("url", "pathname", allow_duplicate=True),
    Output("url", "search", allow_duplicate=True),
    Input({"type": "similarity-player-link", "index": "ALL"}, "n_clicks"),
    prevent_initial_call=True,
)
def navigate_to_player_profile(n_clicks_list):
    """
    Navigates to /performance when a player name in the similarity table is clicked.
    The player name is passed as a URL query parameter so the performance page can
    pre-select the correct player.
    """
    if not any(n for n in (n_clicks_list or []) if n):
        raise PreventUpdate

    from dash import ctx
    triggered = ctx.triggered_id
    if triggered and isinstance(triggered, dict):
        player_name = triggered.get("index", "")
        if player_name:
            import urllib.parse
            query = "?" + urllib.parse.urlencode({"player": player_name})
            return "/performance", query

    raise PreventUpdate
