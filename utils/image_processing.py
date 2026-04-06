# ABOUTME: Image utility for background removal and player photo album management.
# ABOUTME: Uses rembg for offline U2-Net processing and enforces a max-5 album constraint.
# ABOUTME: Indexes jersey and stadium assets for the elite design agency.

import os
import io
import shutil
import logging
from pathlib import Path
from typing import Optional, Dict

# Safeguard for Numba threading layer on macOS (Silicon)
if "NUMBA_THREADING_LAYER" not in os.environ:
    os.environ["NUMBA_THREADING_LAYER"] = "workqueue"

from rembg import remove
from PIL import Image

logger = logging.getLogger(__name__)

# --- Constants ---
MAX_PHOTOS = 5
ALBUM_ROOT = "data/player_cards"
ASSETS_ROOT = "assets"

# Mapping for team assets (prefix matches for filenames)
TEAM_PREFIX_MAPPING = {
    "eastern": "eastern",
    "kitchee": "kitchee",
    "lee_man": "leeman",
    "tai_po": "taipo",
    "hong_kong_football_club": "hkfc",
    "kowloon_city": "kowloon",
    "north_district": "northdt",
    "southern_district": "southern",
    "eastern_district": "easterndt",
    "rangers": "rangers",
    "bc_rangers": "rangers",
    "hkfc": "hkfc"
}

# --- Asset Indexing Functions ---

def get_team_assets(team_id: str) -> Dict[str, Optional[str]]:
    """
    Retrieves indexed assets for a specific team.
    Returns paths to home/away jerseys and stadium thumbnail.
    """
    prefix = TEAM_PREFIX_MAPPING.get(team_id, team_id)
    
    # 1. Jerseys
    jersey_dir = Path(ASSETS_ROOT) / "team_jersey"
    home_j = jersey_dir / f"{prefix}_home.png"
    away_j = jersey_dir / f"{prefix}_away.png"
    
    # Fallback for typos like kitche_home.png
    if not home_j.exists() and prefix == "kitchee":
        home_j = jersey_dir / "kitche_home.png"
    if not away_j.exists() and prefix == "kitchee":
        away_j = jersey_dir / "kitche_away.png"

    # 2. Stadium
    # Check assets/team_media/{team_id}/stadium_thumb.jpg
    # and also try with prefix
    stadium_path = Path(ASSETS_ROOT) / "team_media" / team_id / "stadium_thumb.jpg"
    if not stadium_path.exists():
        stadium_path = Path(ASSETS_ROOT) / "team_media" / prefix / "stadium_thumb.jpg"

    return {
        "home_jersey": str(home_j) if home_j.exists() else None,
        "away_jersey": str(away_j) if away_j.exists() else None,
        "stadium": str(stadium_path) if stadium_path.exists() else None
    }

# --- Core Functions ---

def remove_background(image_bytes: bytes) -> bytes:
    """
    Removes background from image bytes using rembg (U2-Net).
    Returns RGBA PNG bytes.
    Handles potential onnxruntime/OpenMP crashes gracefully by falling back to original.
    """
    try:
        output_bytes = remove(image_bytes)
        return output_bytes
    except Exception as exc:
        logger.warning(f"Background removal failed (likely OpenMP/ONNX issue): {exc}")
        # Return original bytes if rembg fails
        return image_bytes

def save_player_photo(player_id, image_bytes: bytes, filename: str) -> dict:
    """
    Saves original and background-removed photo to the player's album.
    Enforces MAX_PHOTOS constraint.
    """
    album_dir = Path(ALBUM_ROOT) / str(player_id) / "photos"
    album_dir.mkdir(parents=True, exist_ok=True)
    
    # Check current count
    existing = get_player_album(player_id)
    if len(existing) >= MAX_PHOTOS:
        raise ValueError(f"Max photos limit reached ({MAX_PHOTOS})")
    
    # Generate index-based name to avoid collisions and simplify deletion
    idx = len(existing)
    orig_path = album_dir / f"photo_{idx}_orig.png"
    bgrm_path = album_dir / f"photo_{idx}_bgrm.png"
    
    # Save original (convert to RGBA for consistency)
    with Image.open(io.BytesIO(image_bytes)) as img:
        img.convert("RGBA").save(orig_path, "PNG")
    
    # Remove background and save
    bgrm_bytes = remove_background(image_bytes)
    with open(bgrm_path, "wb") as f:
        f.write(bgrm_bytes)
        
    return {
        "idx": idx,
        "filename": filename,
        "original": str(orig_path),
        "bg_removed": str(bgrm_path)
    }

def get_player_album(player_id) -> list[dict]:
    """
    Reads the player's photo album from disk.
    """
    album_dir = Path(ALBUM_ROOT) / str(player_id) / "photos"
    if not album_dir.exists():
        return []
    
    album = []
    # Find all original photos and assume their bgrm counterpart exists
    for orig_file in sorted(album_dir.glob("photo_*_orig.png")):
        idx_str = orig_file.name.split("_")[1]
        idx = int(idx_str)
        bgrm_file = album_dir / f"photo_{idx}_bgrm.png"
        
        album.append({
            "idx": idx,
            "original": str(orig_file),
            "bg_removed": str(bgrm_file) if bgrm_file.exists() else None
        })
    return album

def delete_player_photo(player_id, idx: int) -> bool:
    """
    Deletes original and bgrm files for a specific photo index.
    Re-indexes remaining photos to keep them sequential 0..N.
    """
    album_dir = Path(ALBUM_ROOT) / str(player_id) / "photos"
    if not album_dir.exists():
        return False
    
    orig_path = album_dir / f"photo_{idx}_orig.png"
    bgrm_path = album_dir / f"photo_{idx}_bgrm.png"
    
    deleted = False
    if orig_path.exists():
        orig_path.unlink()
        deleted = True
    if bgrm_path.exists():
        bgrm_path.unlink()
        deleted = True
        
    if deleted:
        # Re-index remaining to avoid gaps
        photos = sorted(album_dir.glob("photo_*_orig.png"))
        for i, p in enumerate(photos):
            old_idx = p.name.split("_")[1]
            if int(old_idx) != i:
                # Rename orig
                new_orig = album_dir / f"photo_{i}_orig.png"
                p.rename(new_orig)
                # Rename bgrm if exists
                old_bgrm = album_dir / f"photo_{old_idx}_bgrm.png"
                if old_bgrm.exists():
                    new_bgrm = album_dir / f"photo_{i}_bgrm.png"
                    old_bgrm.rename(new_bgrm)
    
    return deleted
