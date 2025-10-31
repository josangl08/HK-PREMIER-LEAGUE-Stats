import pytest
import pandas as pd
from unittest.mock import Mock

# Assuming these imports exist from your project structure
from data.processors.hong_kong_processor import HongKongDataProcessor
from data.aggregators.tactical_analyzer import TacticalAnalyzer
from data.hong_kong_data_manager import HongKongDataManager


@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    """Raw player data with 100+ columns (simplified for fixture)."""
    shots_data = [5 + (i % 10) for i in range(1, 51)]
    xa_data = [round(float(i % 2) + 0.3, 2) for i in range(1, 51)]
    data = {
        'Player': [f'Player {i}' for i in range(1, 51)],
        'Team': [f'Team {i % 10 + 1}' for i in range(1, 51)],
        'Primary position': ['ST', 'GK', 'CB', 'CM', 'RW'] * 10,
        'Age': [20 + (i % 15) for i in range(1, 51)],
        'Matches played': [5 + (i % 15) for i in range(1, 51)],
        'Minutes played': [450 + (i * 10) for i in range(1, 51)],
        'Goals': [min(s, i % 5) for i, s in enumerate(shots_data, 1)],
        'Assists': [min(round(x * 0.5), 2) for x in xa_data],
        'xG': [round(float(i % 4) + 0.5, 2) for i in range(1, 51)],
        'xA': xa_data,
        'Passes per 90': [50 + (i % 20) for i in range(1, 51)],
        'Accurate passes, %': [70 + (i % 25) for i in range(1, 51)],
        'Forward passes per 90': [10 + (i % 5) for i in range(1, 51)],
        'Backward passes per 90': [5 + (i % 3) for i in range(1, 51)],
        'Long passes per 90': [3 + (i % 3) for i in range(1, 51)],
        'Through passes per 90': [1 + (i % 2) for i in range(1, 51)],
        'Tackles per 90': [2 + (i % 3) for i in range(1, 51)],
        'Interceptions per 90': [1 + (i % 2) for i in range(1, 51)],
        'Defensive duels won, %': [60 + (i % 35) for i in range(1, 51)],
        'Duels won, %': [50 + (i % 45) for i in range(1, 51)],
        'Crosses per 90': [1 + (i % 4) for i in range(1, 51)],
        'Shots': shots_data,
        'Shots on target, %': [30 + (i % 40) for i in range(1, 51)],
        'Dribbles per 90': [2 + (i % 3) for i in range(1, 51)],
        'Successful dribbles, %': [40 + (i % 55) for i in range(1, 51)],
    }
    return pd.DataFrame(data)


@pytest.fixture
def processed_dataframe(sample_dataframe: pd.DataFrame) -> pd.DataFrame:
    """Processed data via HongKongDataProcessor."""
    processor = HongKongDataProcessor()
    return processor.process_season_data(sample_dataframe, season='2024-2025')


@pytest.fixture
def tactical_analyzer(processed_dataframe: pd.DataFrame) -> TacticalAnalyzer:
    """TacticalAnalyzer instance with test data."""
    return TacticalAnalyzer(processed_dataframe)


@pytest.fixture
def mock_data_manager(processed_dataframe: pd.DataFrame) -> Mock:
    """Mocked HongKongDataManager for callback tests."""
    manager = Mock(spec=HongKongDataManager)
    manager.get_processed_data.return_value = processed_dataframe
    return manager
