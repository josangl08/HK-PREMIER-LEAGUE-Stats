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
from utils.ai_helpers import shap_bar_chart, umap_scatter_chart, constellation_chart, _build_knn_edges, similarity_table, trend_chart
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
    Output("ai-predictor-player-dropdown", "value"),
    Output("ai-similarity-player-dropdown", "value"),
    Input("ai-insights-role-store", "data"),
    prevent_initial_call=False,
)
def populate_dropdowns(role):
    """Populates player and season dropdowns from the DataManager on page load."""
    players = _player_options()
    seasons = _season_options()

    # For player role, restrict both predictor and similarity to own player
    if role == "player":
        try:
            own_player = getattr(current_user, "player_name", None)
            if own_player:
                own_opts = [{"label": own_player, "value": own_player}]
                return own_opts, own_opts, seasons, own_player, own_player
        except Exception:
            pass

    return players, players, seasons, None, None


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
        from ai_models.clustering import fit_kmeans, fit_umap, label_archetypes, FEATURE_LENSES, apply_quality_filters

        # Apply quality filters: min minutes and Bayesian smoothing for rates
        df_filtered = apply_quality_filters(df, min_minutes=180, smooth_rates=True)
        if df_filtered.empty:
            return {}, _error_card("No players match the quality filters (min 180 mins).")

        # Select numeric features
        meta_cols = {"Player", "Season", "Team", "Position", "player_name"}
        feature_cols = [
            c for c in df_filtered.columns
            if c not in meta_cols and pd.api.types.is_numeric_dtype(df_filtered[c])
        ]

        # Apply feature lens filter
        lens_keywords = FEATURE_LENSES.get(feature_lens, [])
        if lens_keywords:
            feature_cols = [
                c for c in feature_cols
                if any(kw in c.lower() for kw in lens_keywords)
            ] or feature_cols  # fallback to all if no match

        X_raw = df_filtered[feature_cols].fillna(0).values
        scaler = StandardScaler()
        X = scaler.fit_transform(X_raw)

        player_names = df_filtered["Player"].values if "Player" in df_filtered.columns else [str(i) for i in range(len(df_filtered))]

        labels, kmeans_model = fit_kmeans(X, k=int(k), feature_lens=feature_lens, feature_names=feature_cols)
        umap_df, _ = fit_umap(X, player_names=list(player_names))

        # Add extra columns for hover
        for col in ["team", "Team", "season", "Season"]:
            if col in df_filtered.columns:
                umap_df[col.lower()] = df_filtered[col].values

        archetype_labels = label_archetypes(kmeans_model, feature_cols)
        knn_edges = _build_knn_edges(umap_df, k=4)
        fig = constellation_chart(umap_df, cluster_labels=labels, archetype_labels=archetype_labels, knn_edges=knn_edges)

        status = f"Clustered {len(df_filtered)} players into {k} archetypes using '{feature_lens}' lens (Min 180 mins + Smoothed Rates)."
        return fig, html.Span(status, style={"color": HKFATheme.TEXT_SECONDARY})

    except Exception as e:
        logger.error(f"Clustering error: {e}", exc_info=True)
        return {}, _error_card(f"Clustering failed: {str(e)}")


# ──────────────────────────────────────────────────────────────────────────────
# 8.2 — Predictor callback: player + metric + model → prediction + SHAP
# ──────────────────────────────────────────────────────────────────────────────

@callback(
    Output("ai-predictor-result", "children"),
    Output("ai-predictor-trend-graph", "figure"),
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
    the predicted value, career trend chart, and SHAP feature importance bar chart.
    """
    if not n_clicks:
        raise PreventUpdate

    if not player_name or not target_metric:
        return _info_card("Select a player and target metric."), {}, {}

    df = _get_player_df()
    if df is None or df.empty:
        return _error_card("No player data available."), {}, {}

    try:
        from data.processors.ml_preprocessor import MLPreprocessor
        from ai_models.predictor import predict, compute_shap, predict_with_interval

        # Load pre-trained model + scaler from registry
        registry = ModelRegistry()
        model_id = f"{model_type}_{target_metric}"
        scaler_id = f"scaler_{target_metric}"

        try:
            model = registry.load(model_id)
        except ModelNotFoundError:
            return _error_card(
                f"Model '{model_id}' not found. Run: python scripts/train_models.py"
            ), {}, {}

        # Retrieve saved feature names from registry metadata
        reg_data = registry._load_registry()
        feature_cols = reg_data.get(scaler_id, {}).get("latest", {}).get("features") or \
                       reg_data.get(model_id, {}).get("latest", {}).get("features")

        if not feature_cols or not isinstance(feature_cols[0], str):
            return _error_card(
                "Feature metadata missing. Re-run: python scripts/train_models.py"
            ), {}, {}

        # Apply the same feature engineering pipeline that was used during training
        pp = MLPreprocessor()
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
            return _error_card(f"No data found for player '{player_name}'."), {}, {}

        # Load persisted scaler or fit a fresh one
        try:
            scaler = registry.load(scaler_id)
        except ModelNotFoundError:
            from sklearn.preprocessing import StandardScaler
            scaler = StandardScaler()
            scaler.fit(df_eng[available_cols].fillna(0).values)

        X_player = player_df[available_cols].fillna(0).values
        X_player_scaled = scaler.transform(X_player)

        # Predict with confidence interval
        interval = predict_with_interval(model, X_player_scaled, model_id)
        prediction = interval["prediction"]
        lower = interval["lower"]
        upper = interval["upper"]
        rmse = interval["rmse"]

        shap_vals = compute_shap(model, X_player_scaled)

        # ── Archetype context (best-effort, silent on failure) ────────────────
        archetype_line = None
        try:
            from ai_models.clustering import label_archetypes, FEATURE_LENSES
            from sklearn.preprocessing import StandardScaler as _SS

            kmeans_model = registry.load("kmeans_overall_k5")
            # LOAD metadata to sync features and avoid warning
            reg_data = registry._load_registry()
            cluster_cols = reg_data.get("kmeans_overall_k5", {}).get("latest", {}).get("features")
            
            if not cluster_cols:
                lens_keywords = FEATURE_LENSES.get("overall", [])
                meta_cols_set = {"Player", "Season", "Team", "Position", "player_name"}
                all_num_cols = [
                    c for c in df_eng.columns
                    if c not in meta_cols_set and pd.api.types.is_numeric_dtype(df_eng[c])
                ]
                cluster_cols = (
                    [c for c in all_num_cols if any(kw in c.lower() for kw in lens_keywords)]
                    or all_num_cols
                )
            
            # Align df_eng with expected features
            X_all_df = df_eng[[c for c in cluster_cols if c in df_eng.columns]].fillna(0).copy()
            for mc in cluster_cols:
                if mc not in X_all_df.columns: X_all_df[mc] = 0.0
            
            X_all = X_all_df[cluster_cols].values
            X_all_scaled = _SS().fit_transform(X_all)
            all_clusters = kmeans_model.predict(X_all_scaled)

            player_pos_in_df = df_eng[df_eng["Player"] == player_name].index
            if len(player_pos_in_df):
                player_cluster = all_clusters[df_eng.index.get_loc(player_pos_in_df[-1])]
            else:
                player_cluster = all_clusters[df_eng.reset_index(drop=True)[df_eng["Player"] == player_name].index[-1]]

            arch_labels = label_archetypes(kmeans_model, cluster_cols)
            arch_name = arch_labels[player_cluster] if player_cluster < len(arch_labels) else f"Cluster {player_cluster}"

            cluster_mask = all_clusters == player_cluster
            cluster_df = df_eng[cluster_mask]
            if target_metric in cluster_df.columns:
                cluster_avg = cluster_df[target_metric].dropna().mean()
                archetype_line = f"Plays like a '{arch_name}' — avg {target_metric} for this archetype: {cluster_avg:.1f}"
        except Exception as e:
            logger.debug(f"Predictor archetype context skipped: {e}")
            pass  # Silently skip if kmeans model not in registry

        # ── Build result card ─────────────────────────────────────────────────
        confidence_pct = max(0, min(100, round(100 - (rmse / max(prediction, 1)) * 100))) if prediction else 0
        result_card_children = [
            html.H5(f"Predicted {target_metric}", className="card-title text-muted"),
            html.H2(
                f"{prediction:.2f}",
                style={"color": HKFATheme.ACCENT_GOLD, "fontWeight": "700"},
            ),
            html.P(
                f"Range: {lower:.1f} – {upper:.1f}",
                className="text-muted mb-1",
                style={"fontSize": "0.9rem"},
            ),
        ]
        if rmse > 0:
            result_card_children.append(
                dbc.Progress(
                    value=confidence_pct,
                    label=f"Confidence {confidence_pct}%",
                    color="warning",
                    style={"height": "16px", "marginBottom": "8px"},
                )
            )
        result_card_children.append(
            html.Small(f"{player_name} — {model_type.upper()} model", className="text-muted")
        )
        if archetype_line:
            result_card_children.append(
                html.P(archetype_line, className="text-muted mt-2 mb-0", style={"fontSize": "0.85rem"})
            )

        result_card = dbc.Card(
            dbc.CardBody(result_card_children),
            style={
                "backgroundColor": HKFATheme.BG_TERTIARY,
                "border": f"1px solid {HKFATheme.BORDER_COLOR}",
                "maxWidth": "360px",
            },
        )

        # ── Trend chart ───────────────────────────────────────────────────────
        trend_fig = {}
        try:
            player_history = df[df["Player"] == player_name].copy()
            if "Season" in player_history.columns and target_metric in player_history.columns:
                player_history = player_history.sort_values("Season")
                seasons_hist = player_history["Season"].tolist()
                actuals_hist = player_history[target_metric].fillna(0).tolist()

                # Infer next season label
                last_season = seasons_hist[-1] if seasons_hist else ""
                try:
                    parts = last_season.split("-")
                    next_season = f"{int(parts[0]) + 1}-{int(parts[1]) + 1:02d}" if len(parts) == 2 else "Next"
                except Exception:
                    next_season = "Next"

                trend_fig = trend_chart(
                    seasons=seasons_hist,
                    actuals=actuals_hist,
                    predicted_next_season=next_season,
                    predicted_value=prediction,
                    lower=lower,
                    upper=upper,
                    metric_name=target_metric,
                )
        except Exception as e:
            logger.warning(f"Could not build trend chart: {e}")

        shap_fig = shap_bar_chart(shap_vals, feature_names=available_cols, top_k=10)
        return result_card, trend_fig, shap_fig

    except Exception as e:
        logger.error(f"Predictor error: {e}", exc_info=True)
        return _error_card(f"Prediction failed: {str(e)}"), {}, {}


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

        # Derive query player's position for position-aware filtering
        query_position = None
        pos_col = next((c for c in ["Position_Group", "Position"] if c in df_reset.columns), None)
        if pos_col:
            pos_rows = df_reset[df_reset["Player"] == player_name]
            if not pos_rows.empty:
                query_position = str(pos_rows.iloc[-1][pos_col])

        season_filter = list(seasons) if seasons else None
        results = find_similar(
            query_embedding=query_embedding,
            corpus_embeddings=embeddings,
            player_meta=player_meta,
            k=10,
            seasons=season_filter,
            query_index=query_pos,
            position=query_position,
        )

        if results.empty:
            return _info_card("No similar players found with current filters.")

        position_tag = (
            html.P(
                [html.I(className="bi bi-funnel me-1"), f"Searching within: {query_position}"],
                className="text-muted small mb-2",
            )
            if query_position else None
        )
        return html.Div([position_tag, similarity_table(results)] if position_tag else [similarity_table(results)])

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
