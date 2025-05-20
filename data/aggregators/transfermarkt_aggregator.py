"""
Agregador de estadísticas para datos de lesiones de Transfermarkt.
Organiza y transforma los datos para su uso en el dashboard.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime

class TransfermarktStatsAggregator:
    """
    Agregador de estadísticas para datos de lesiones de Transfermarkt.
    Proporciona métodos para calcular estadísticas y preparar datos para visualizaciones.
    """
    
    def __init__(self, processed_data: List[Dict]):
        """
        Inicializa el agregador con datos procesados.
        
        Args:
            processed_data: Lista de diccionarios con datos de lesiones procesados
        """
        self.injuries_data = processed_data
        self.df = pd.DataFrame(processed_data) if processed_data else pd.DataFrame()
        
        # Cache para optimizar consultas repetidas
        self._cache = {}
    
    def get_statistics_summary(self) -> Dict:
        """
        Obtiene resumen estadístico de las lesiones.
        
        Returns:
            Diccionario con estadísticas resumidas
        """
        cache_key = 'statistics_summary'
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        if not self.injuries_data:
            summary = {
                'total_injuries': 0,
                'active_injuries': 0,
                'avg_recovery_days': 0,
                'most_common_injury': 'N/A',
                'most_affected_part': 'N/A'
            }
            self._cache[cache_key] = summary
            return summary
        
        # Estadísticas globales
        total_injuries = len(self.injuries_data)
        
        # Lesiones activas
        active_injuries = len([injury for injury in self.injuries_data 
                              if injury.get('status') == 'En tratamiento'])
        
        # Días de recuperación promedio
        recovery_days = [injury.get('recovery_days', 0) for injury in self.injuries_data 
                        if injury.get('recovery_days', 0) > 0]
        avg_recovery_days = sum(recovery_days) / len(recovery_days) if recovery_days else 0
        
        # Lesión más común
        injury_types = [injury.get('injury_type', 'Desconocida') for injury in self.injuries_data]
        injury_counts = {}
        for injury_type in injury_types:
            if injury_type in injury_counts:
                injury_counts[injury_type] += 1
            else:
                injury_counts[injury_type] = 1
        
        most_common_injury = max(injury_counts.items(), key=lambda x: x[1])[0] if injury_counts else 'N/A'
        
        # Parte del cuerpo más afectada
        body_parts = [injury.get('body_part', 'Otros') for injury in self.injuries_data]
        body_part_counts = {}
        for body_part in body_parts:
            if body_part in body_part_counts:
                body_part_counts[body_part] += 1
            else:
                body_part_counts[body_part] = 1
        
        most_affected_part = max(body_part_counts.items(), key=lambda x: x[1])[0] if body_part_counts else 'N/A'
        
        # Crear resumen
        summary = {
            'total_injuries': total_injuries,
            'active_injuries': active_injuries,
            'avg_recovery_days': round(avg_recovery_days, 1),
            'most_common_injury': most_common_injury,
            'most_affected_part': most_affected_part,
            'teams_with_injuries': len(set(injury.get('team', '') for injury in self.injuries_data)),
            'recovered_injuries': len([injury for injury in self.injuries_data 
                                     if injury.get('status') == 'Recuperado']),
            'chronic_injuries': len([injury for injury in self.injuries_data 
                                    if injury.get('status') == 'Crónico'])
        }
        
        self._cache[cache_key] = summary
        return summary
    
    def get_injury_distribution(self) -> Dict:
        """
        Obtiene distribución de lesiones por tipo.
        
        Returns:
            Diccionario con datos de distribución
        """
        cache_key = 'injury_distribution'
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        if not self.injuries_data:
            return {'types': [], 'counts': []}
        
        # Contar tipos de lesiones
        injury_types = [injury.get('injury_type', 'Desconocida') for injury in self.injuries_data]
        injury_counts = {}
        for injury_type in injury_types:
            if injury_type in injury_counts:
                injury_counts[injury_type] += 1
            else:
                injury_counts[injury_type] = 1
        
        # Ordenar por frecuencia
        sorted_injuries = sorted(injury_counts.items(), key=lambda x: x[1], reverse=True)
        
        # Tomar top 10
        if len(sorted_injuries) > 10:
            sorted_injuries = sorted_injuries[:10]
        
        distribution = {
            'types': [item[0] for item in sorted_injuries],
            'counts': [item[1] for item in sorted_injuries]
        }
        
        self._cache[cache_key] = distribution
        return distribution
    
    def get_monthly_trends(self) -> Dict:
        """
        Obtiene tendencias mensuales de lesiones.
        
        Returns:
            Diccionario con datos de tendencias
        """
        cache_key = 'monthly_trends'
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        if not self.injuries_data:
            return {'months': [], 'counts': []}
        
        # Agrupar por mes
        monthly_counts = {}
        
        for injury in self.injuries_data:
            injury_date_str = injury.get('injury_date')
            if injury_date_str:
                try:
                    injury_date = datetime.strptime(injury_date_str, '%Y-%m-%d')
                    month_key = injury_date.strftime('%Y-%m')
                    
                    if month_key in monthly_counts:
                        monthly_counts[month_key] += 1
                    else:
                        monthly_counts[month_key] = 1
                except:
                    continue
        
        # Ordenar por fecha
        sorted_months = sorted(monthly_counts.items())
        
        trends = {
            'months': [item[0] for item in sorted_months],
            'counts': [item[1] for item in sorted_months]
        }
        
        self._cache[cache_key] = trends
        return trends
    
    def get_body_parts_analysis(self) -> Dict:
        """
        Obtiene análisis de lesiones por partes del cuerpo.
        
        Returns:
            Diccionario con datos de análisis
        """
        cache_key = 'body_parts_analysis'
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        if not self.injuries_data:
            return {'parts': [], 'counts': [], 'percentages': []}
        
        # Contar lesiones por parte del cuerpo
        body_parts = [injury.get('body_part', 'Otros') for injury in self.injuries_data]
        body_part_counts = {}
        
        for part in body_parts:
            if part in body_part_counts:
                body_part_counts[part] += 1
            else:
                body_part_counts[part] = 1
        
        # Ordenar por frecuencia
        sorted_parts = sorted(body_part_counts.items(), key=lambda x: x[1], reverse=True)
        
        # Calcular porcentajes
        total_injuries = len(self.injuries_data)
        percentages = [round((count / total_injuries) * 100, 1) for _, count in sorted_parts]
        
        # Tomar top 8
        if len(sorted_parts) > 8:
            sorted_parts = sorted_parts[:8]
            percentages = percentages[:8]
        
        analysis = {
            'parts': [item[0] for item in sorted_parts],
            'counts': [item[1] for item in sorted_parts],
            'percentages': percentages
        }
        
        self._cache[cache_key] = analysis
        return analysis
    
    def get_team_risk_analysis(self) -> Dict:
        """
        Obtiene análisis de riesgo por equipo.
        
        Returns:
            Diccionario con datos de análisis de riesgo
        """
        cache_key = 'team_risk_analysis'
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        if not self.injuries_data:
            return {'teams': [], 'risk_scores': [], 'details': {}}
        
        # Análisis de riesgo por equipo
        team_stats = {}
        
        for injury in self.injuries_data:
            team = injury.get('team', 'Desconocido')
            
            if team not in team_stats:
                team_stats[team] = {
                    'total_injuries': 0,
                    'severe_injuries': 0,
                    'recovery_days': [],
                    'active_injuries': 0
                }
            
            # Incrementar contadores
            team_stats[team]['total_injuries'] += 1
            
            # Verificar severidad
            if injury.get('severity') == 'Grave':
                team_stats[team]['severe_injuries'] += 1
            
            # Agregar días de recuperación
            if injury.get('recovery_days'):
                team_stats[team]['recovery_days'].append(injury.get('recovery_days', 0))
            
            # Verificar lesiones activas
            if injury.get('status') == 'En tratamiento':
                team_stats[team]['active_injuries'] += 1
        
        # Calcular índice de riesgo
        team_risk = []
        
        for team, stats in team_stats.items():
            # Calcular promedio de días de recuperación
            avg_recovery = (sum(stats['recovery_days']) / len(stats['recovery_days']) 
                           if stats['recovery_days'] else 0)
            
            # Fórmula de riesgo: considera múltiples factores con diferentes pesos
            risk_score = (
                stats['total_injuries'] * 0.4 +
                stats['severe_injuries'] * 2 +
                stats['active_injuries'] * 1.5 +
                avg_recovery * 0.01
            )
            
            team_risk.append({
                'team': team,
                'risk_score': risk_score,
                'total_injuries': stats['total_injuries'],
                'severe_injuries': stats['severe_injuries'],
                'active_injuries': stats['active_injuries']
            })
        
        # Ordenar por riesgo
        team_risk.sort(key=lambda x: x['risk_score'], reverse=True)
        
        # Tomar top 8
        if len(team_risk) > 8:
            team_risk = team_risk[:8]
        
        analysis = {
            'teams': [item['team'] for item in team_risk],
            'risk_scores': [item['risk_score'] for item in team_risk],
            'details': {item['team']: item for item in team_risk}
        }
        
        self._cache[cache_key] = analysis
        return analysis
    
    def get_filtered_injuries(self, team: Optional[str] = None, status: Optional[str] = None) -> List[Dict]:
        """
        Obtiene lesiones filtradas por equipo y/o estado.
        
        Args:
            team: Filtrar por equipo específico
            status: Filtrar por estado ('En tratamiento', 'Recuperado', 'Crónico')
            
        Returns:
            Lista de lesiones filtradas
        """
        cache_key = f'filtered_injuries_{team}_{status}'
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        if not self.injuries_data:
            return []
        
        filtered_data = self.injuries_data.copy()
        
        # Filtrar por equipo
        if team and team != 'all':
            filtered_data = [injury for injury in filtered_data 
                            if injury.get('team') == team]
        
        # Filtrar por estado
        if status:
            filtered_data = [injury for injury in filtered_data 
                            if injury.get('status') == status]
        
        self._cache[cache_key] = filtered_data
        return filtered_data
    
    def get_chart_data(self, chart_type: str, team: Optional[str] = None) -> Dict:
        """
        Prepara datos específicamente para gráficos.
        
        Args:
            chart_type: Tipo de gráfico ('distribution', 'trends', 'body_parts', 'risk')
            team: Equipo específico para filtrar
            
        Returns:
            Diccionario con datos formateados para gráficos
        """
        cache_key = f'chart_data_{chart_type}_{team}'
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Filtrar por equipo si es necesario
        filtered_data = self.injuries_data
        if team and team != 'all':
            filtered_data = [injury for injury in filtered_data 
                            if injury.get('team') == team]
        
        # Preparar datos según el tipo de gráfico
        if chart_type == 'distribution':
            data = self.get_injury_distribution()
        elif chart_type == 'trends':
            data = self.get_monthly_trends()
        elif chart_type == 'body_parts':
            data = self.get_body_parts_analysis()
        elif chart_type == 'risk':
            data = self.get_team_risk_analysis()
        else:
            data = {}
        
        self._cache[cache_key] = data
        return data
    
    def clear_cache(self):
        """Limpia el cache del agregador."""
        self._cache.clear()
    
    def get_available_teams(self) -> List[str]:
        """Retorna lista de equipos disponibles."""
        if not self.injuries_data:
            return []
        
        teams = set(injury.get('team', '') for injury in self.injuries_data 
                   if injury.get('team'))
        return sorted(list(teams))