"""
Utilidades para validación y verificación de datos.
Funciones auxiliares para verificar la integridad de los datos de la liga.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
from config import DataConfig

# Configurar logging
logger = logging.getLogger(__name__)

class DataValidator:
    """
    Validador de datos para verificar la integridad y consistencia
    de los datos de la Liga de Hong Kong.
    """
    
    def __init__(self):
        self.expected_teams = DataConfig.EXPECTED_HK_TEAMS
        self.min_teams = DataConfig.MIN_TEAMS_EXPECTED
        self.max_teams = DataConfig.MAX_TEAMS_EXPECTED
        self.max_players_per_team = DataConfig.MAX_PLAYERS_PER_TEAM
    
    def validate_basic_structure(self, df: pd.DataFrame) -> Dict:
        """
        Valida la estructura básica del DataFrame.
        
        Args:
            df: DataFrame a validar
            
        Returns:
            Diccionario con resultados de validación
        """
        validation_results = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'stats': {}
        }
        
        # Verificar que no esté vacío
        if df.empty:
            validation_results['is_valid'] = False
            validation_results['errors'].append("DataFrame está vacío")
            return validation_results
        
        # Verificar columnas críticas
        required_columns = ['Player', 'Team', 'Age', 'Goals', 'Assists']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            validation_results['is_valid'] = False
            validation_results['errors'].append(f"Columnas faltantes: {missing_columns}")
        
        # Estadísticas básicas
        validation_results['stats'] = {
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'columns': list(df.columns)
        }
        
        return validation_results
    
    def validate_teams(self, df: pd.DataFrame) -> Dict:
        """
        Valida información de equipos.
        
        Args:
            df: DataFrame con datos de jugadores
            
        Returns:
            Diccionario con resultados de validación de equipos
        """
        validation_results = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'teams_info': {}
        }
        
        if 'Team' not in df.columns:
            validation_results['is_valid'] = False
            validation_results['errors'].append("Columna 'Team' no encontrada")
            return validation_results
        
        # Analizar equipos
        teams = df['Team'].unique()
        teams_count = len(teams)
        
        # Verificar número de equipos
        if teams_count < self.min_teams:
            validation_results['warnings'].append(
                f"Pocos equipos encontrados: {teams_count} (esperado: {self.min_teams}-{self.max_teams})"
            )
        elif teams_count > self.max_teams:
            validation_results['warnings'].append(
                f"Demasiados equipos encontrados: {teams_count} (esperado: {self.min_teams}-{self.max_teams})"
            )
        
        # Analizar cada equipo
        teams_info = {}
        for team in teams:
            team_data = df[df['Team'] == team]
            players_count = len(team_data)
            
            team_info = {
                'players_count': players_count,
                'avg_age': team_data['Age'].mean() if 'Age' in df.columns else None,
                'total_goals': team_data['Goals'].sum() if 'Goals' in df.columns else None,
                'is_expected': team in self.expected_teams
            }
            
            # Verificar número de jugadores por equipo
            if players_count > self.max_players_per_team:
                validation_results['warnings'].append(
                    f"Equipo {team} tiene muchos jugadores: {players_count} (máximo esperado: {self.max_players_per_team})"
                )
            elif players_count < 15:
                validation_results['warnings'].append(
                    f"Equipo {team} tiene pocos jugadores: {players_count}"
                )
            
            teams_info[team] = team_info
        
        # Verificar equipos esperados
        missing_expected_teams = [team for team in self.expected_teams if team not in teams]
        if missing_expected_teams:
            validation_results['warnings'].append(
                f"Equipos esperados no encontrados: {missing_expected_teams}"
            )
        
        # Equipos no esperados
        unexpected_teams = [team for team in teams if team not in self.expected_teams]
        if unexpected_teams:
            validation_results['warnings'].append(
                f"Equipos no esperados encontrados: {unexpected_teams}"
            )
        
        validation_results['teams_info'] = teams_info
        
        return validation_results
    
    def validate_players(self, df: pd.DataFrame) -> Dict:
        """
        Valida información de jugadores.
        
        Args:
            df: DataFrame con datos de jugadores
            
        Returns:
            Diccionario con resultados de validación de jugadores
        """
        validation_results = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'players_stats': {}
        }
        
        # Verificar duplicados
        if 'Player' in df.columns and 'Team' in df.columns:
            duplicates = df[df.duplicated(subset=['Player', 'Team'], keep=False)]
            if not duplicates.empty:
                validation_results['warnings'].append(
                    f"Jugadores duplicados encontrados: {len(duplicates)}"
                )
        
        # Verificar edades
        if 'Age' in df.columns:
            age_issues = []
            
            # Edades extremas
            too_young = df[df['Age'] < 16]
            too_old = df[df['Age'] > 45]
            
            if not too_young.empty:
                age_issues.append(f"{len(too_young)} jugadores menores de 16 años")
            
            if not too_old.empty:
                age_issues.append(f"{len(too_old)} jugadores mayores de 45 años")
            
            # Edades faltantes
            missing_ages = df[df['Age'].isna()]
            if not missing_ages.empty:
                age_issues.append(f"{len(missing_ages)} jugadores sin edad")
            
            if age_issues:
                validation_results['warnings'].extend(age_issues)
        
        # Verificar posiciones
        if 'Position_Group' in df.columns:
            missing_positions = df[df['Position_Group'].isna() | (df['Position_Group'] == 'Unknown')]
            if not missing_positions.empty:
                validation_results['warnings'].append(
                    f"{len(missing_positions)} jugadores sin posición definida"
                )
        
        # Estadísticas de jugadores
        players_stats = {
            'total_players': len(df),
            'unique_players': df['Player'].nunique() if 'Player' in df.columns else 0,
            'avg_age': df['Age'].mean() if 'Age' in df.columns else None,
            'age_range': [df['Age'].min(), df['Age'].max()] if 'Age' in df.columns else None
        }
        
        validation_results['players_stats'] = players_stats
        
        return validation_results
    
    def validate_statistics(self, df: pd.DataFrame) -> Dict:
        """
        Valida estadísticas de performance.
        
        Args:
            df: DataFrame con datos de jugadores
            
        Returns:
            Diccionario con resultados de validación de estadísticas
        """
        validation_results = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'stats_summary': {}
        }
        
        stats_columns = ['Goals', 'Assists', 'Minutes played', 'Matches played']
        
        for col in stats_columns:
            if col in df.columns:
                # Verificar valores negativos
                negative_values = df[df[col] < 0]
                if not negative_values.empty:
                    validation_results['warnings'].append(
                        f"Valores negativos en {col}: {len(negative_values)} casos"
                    )
                
                # Verificar valores extremos
                if col == 'Goals':
                    extreme_goals = df[df[col] > 50]  # Más de 50 goles parece excesivo
                    if not extreme_goals.empty:
                        validation_results['warnings'].append(
                            f"Valores extremos de goles: {len(extreme_goals)} jugadores con más de 50 goles"
                        )
                
                elif col == 'Minutes played':
                    # No puede haber más minutos que matches * 90
                    if 'Matches played' in df.columns:
                        max_possible = df['Matches played'] * 90
                        excessive_minutes = df[df[col] > max_possible]
                        if not excessive_minutes.empty:
                            validation_results['warnings'].append(
                                f"Minutos excesivos: {len(excessive_minutes)} jugadores"
                            )
        
        # Verificar consistencia de porcentajes
        percentage_columns = [col for col in df.columns if '%' in col]
        for col in percentage_columns:
            if col in df.columns:
                out_of_range = df[(df[col] < 0) | (df[col] > 100)]
                if not out_of_range.empty:
                    validation_results['warnings'].append(
                        f"Porcentajes fuera de rango en {col}: {len(out_of_range)} casos"
                    )
        
        return validation_results
    
    def validate_positions(self, df: pd.DataFrame) -> Dict:
        """
        Valida información de posiciones.
        
        Args:
            df: DataFrame con datos de jugadores
            
        Returns:
            Diccionario con resultados de validación de posiciones
        """
        validation_results = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'position_stats': {}
        }
        
        position_columns = [
            'Position_Primary', 'Position_Secondary', 'Position_Third',
            'Position_Group', 'Position_Primary_Group'
        ]
        
        available_position_cols = [col for col in position_columns if col in df.columns]
        
        if not available_position_cols:
            validation_results['errors'].append("No se encontraron columnas de posición")
            validation_results['is_valid'] = False
            return validation_results
        
        # Analizar distribución por posición
        position_stats = {}
        
        for col in available_position_cols:
            if col in df.columns:
                position_counts = df[col].value_counts()
                position_stats[col] = position_counts.to_dict()
                
                # Verificar si alguna posición está muy desbalanceada
                if len(position_counts) > 0:
                    max_count = position_counts.max()
                    min_count = position_counts.min()
                    
                    if max_count / min_count > 10:  # Ratio muy alto
                        validation_results['warnings'].append(
                            f"Distribución desbalanceada en {col}: ratio {max_count}/{min_count}"
                        )
        
        validation_results['position_stats'] = position_stats
        
        return validation_results
    
    def run_full_validation(self, df: pd.DataFrame, season: Optional[str] = None) -> Dict:
        """
        Ejecuta validación completa del DataFrame.
        
        Args:
            df: DataFrame a validar
            season: Temporada (opcional)
            
        Returns:
            Diccionario con todos los resultados de validación
        """
        full_results = {
            'season': season,
            'timestamp': pd.Timestamp.now().isoformat(),
            'overall_status': 'valid',
            'summary': {
                'total_errors': 0,
                'total_warnings': 0
            },
            'validations': {}
        }
        
        # Ejecutar todas las validaciones
        validations = {
            'basic_structure': self.validate_basic_structure(df),
            'teams': self.validate_teams(df),
            'players': self.validate_players(df),
            'statistics': self.validate_statistics(df),
            'positions': self.validate_positions(df)
        }
        
        # Compilar resultados
        total_errors = 0
        total_warnings = 0
        
        for validation_name, result in validations.items():
            full_results['validations'][validation_name] = result
            
            total_errors += len(result.get('errors', []))
            total_warnings += len(result.get('warnings', []))
            
            if not result.get('is_valid', True):
                full_results['overall_status'] = 'invalid'
        
        # Si hay errores críticos, marcar como inválido
        if total_errors > 0:
            full_results['overall_status'] = 'invalid'
        elif total_warnings > 5:
            full_results['overall_status'] = 'warning'
        
        full_results['summary']['total_errors'] = total_errors
        full_results['summary']['total_warnings'] = total_warnings
        
        # Log de resultados
        logger.info(f"Validation completed for season {season}: {full_results['overall_status']}")
        logger.info(f"Errors: {total_errors}, Warnings: {total_warnings}")
        
        return full_results
    
    def get_validation_report(self, validation_results: Dict) -> str:
        """
        Genera un reporte de texto de los resultados de validación.
        
        Args:
            validation_results: Resultados de validación completa
            
        Returns:
            Reporte de texto formateado
        """
        report = []
        report.append("=" * 50)
        report.append("REPORTE DE VALIDACIÓN DE DATOS")
        report.append("=" * 50)
        report.append(f"Temporada: {validation_results.get('season', 'N/A')}")
        report.append(f"Fecha: {validation_results.get('timestamp', 'N/A')}")
        report.append(f"Estado General: {validation_results.get('overall_status', 'unknown').upper()}")
        report.append("")
        
        # Resumen
        summary = validation_results.get('summary', {})
        report.append(f"RESUMEN:")
        report.append(f"  Errores: {summary.get('total_errors', 0)}")
        report.append(f"  Advertencias: {summary.get('total_warnings', 0)}")
        report.append("")
        
        # Detalles por validación
        validations = validation_results.get('validations', {})
        
        for validation_name, result in validations.items():
            report.append(f"{validation_name.upper().replace('_', ' ')}:")
            
            errors = result.get('errors', [])
            warnings = result.get('warnings', [])
            
            if errors:
                report.append("  Errores:")
                for error in errors:
                    report.append(f"    - {error}")
            
            if warnings:
                report.append("  Advertencias:")
                for warning in warnings:
                    report.append(f"    - {warning}")
            
            if not errors and not warnings:
                report.append("  ✓ OK")
            
            report.append("")
        
        return "\n".join(report)

# Instancia global del validador
data_validator = DataValidator()