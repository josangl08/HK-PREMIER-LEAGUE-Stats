
import pandas as pd
import numpy as np
from utils.app_context import get_hong_kong_data_manager
from ai_models.model_registry import ModelRegistry
from ai_models.clustering import apply_quality_filters, label_archetypes
from data.processors.ml_preprocessor import MLPreprocessor

def debug():
    from data.hong_kong_data_manager import HongKongDataManager
    dm = HongKongDataManager(auto_load=True)
    df = dm.processed_data
    if df is None:
        print("No data found")
        return

    players_to_check = ["Daniel Almazan", "Felipe Sa", "Manuel Bleda", "Everton Camargo", "Jose Angel"]
    print(f"--- Data Check ---")
    for p in players_to_check:
        p_row = df[df["Player"].str.contains(p, case=False, na=False)]
        if p_row.empty:
            print(f"{p}: NOT FOUND in processed data")
        else:
            mins = p_row["Minutes played"].iloc[0]
            pos = p_row["Position"].iloc[0]
            print(f"{p}: {mins} mins, Position: {pos}")

    # Load Model
    registry = ModelRegistry()
    km = registry.load("kmeans_overall_k5")
    reg_data = registry._load_registry()
    expected_features = reg_data.get("kmeans_overall_k5", {}).get("latest", {}).get("features")

    if not km or not expected_features:
        print("Model or features not found in registry")
        return

    print(f"\n--- Cluster Labeling Debug ---")
    labels = label_archetypes(km, expected_features)
    for i, l in enumerate(labels):
        print(f"Cluster {i}: {l}")

    # Apply feature engineering
    pp = MLPreprocessor()
    meta_cols = {"Player", "Season", "Team", "Position"}
    numeric_cols_raw = [c for c in df.columns if c not in meta_cols and pd.api.types.is_numeric_dtype(df[c])]
    
    df_eng = pp.compute_temporal_features(df, numeric_cols_raw)
    df_eng = pp.compute_positional_zscores(df_eng, numeric_cols_raw)
    df_eng = pp.compute_benchmark_deltas(df_eng, numeric_cols_raw)
    df_eng = pp.inject_composite_metrics(df_eng)

    # Check distribution
    df_filtered = apply_quality_filters(df_eng, min_minutes=1) # Use 1 min to see everyone
    
    # Fill missing expected features with 0
    for f in expected_features:
        if f not in df_filtered.columns:
            df_filtered[f] = 0.0
            
    X = df_filtered[expected_features].fillna(0).values
    
    from sklearn.preprocessing import StandardScaler
    X_scaled = StandardScaler().fit_transform(X)
    preds = km.predict(X_scaled)
    df_filtered["cluster"] = preds
    
    print(f"\n--- Distribution ---")
    print(df_filtered["cluster"].value_counts().sort_index())

    print(f"\n--- Target Players Result ---")
    for p in players_to_check:
        p_row = df_filtered[df_filtered["Player"].str.contains(p, case=False, na=False)]
        if not p_row.empty:
            cid = p_row["cluster"].iloc[0]
            print(f"{p}: Cluster {cid} ({labels[cid]})")

if __name__ == "__main__":
    debug()
