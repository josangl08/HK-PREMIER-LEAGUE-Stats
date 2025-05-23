import pandas as pd
from typing import Dict, List, Optional, Tuple
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

    def _count_and_sort(self, field_name: str, max_items: int = 10) -> Tuple[List[str], List[int]]:
        """
        Método auxiliar para contar ocurrencias de un campo y ordenar por frecuencia.
        
        Args:
            field_name: Nombre del campo a contar
            max_items: Número máximo de elementos a retornar
            
        Returns:
            Tupla con (etiquetas, conteos)
        """
        if not self.injuries_data:
            return [], []
        
        # Contar ocurrencias
        field_values = [injury.get(field_name, 'Desconocido') for injury in self.injuries_data]
        counts = {}
        for value in field_values:
            counts[value] = counts.get(value, 0) + 1
        
        # Ordenar por frecuencia y limitar
        sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_items) > max_items:
            sorted_items = sorted_items[:max_items]
        
        return [item[0] for item in sorted_items], [item[1] for item in sorted_items]
    
    def _get_base_statistics(self) -> Dict:
        """Calcula estadísticas base reutilizables."""
        if not self.injuries_data:
            return {
                'total_injuries': 0,
                'active_injuries': 0,
                'recovery_days': [],
                'injury_types': [],
                'body_parts': []
            }
        
        # Calcular una vez y reutilizar
        recovery_days = [injury.get('recovery_days', 0) for injury in self.injuries_data 
                        if injury.get('recovery_days', 0) > 0]
        
        injury_types = [injury.get('injury_type', 'Desconocida') for injury in self.injuries_data]
        body_parts = [injury.get('body_part', 'Otros') for injury in self.injuries_data]
        
        active_injuries = len([injury for injury in self.injuries_data 
                            if injury.get('status') == 'En tratamiento'])
        
        return {
            'total_injuries': len(self.injuries_data),
            'active_injuries': active_injuries,
            'recovery_days': recovery_days,
            'injury_types': injury_types,
            'body_parts': body_parts
        }

    def get_statistics_summary(self) -> Dict:
        """Obtiene resumen estadístico usando estadísticas base."""
        cache_key = 'statistics_summary'
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        base_stats = self._get_base_statistics()
        
        if base_stats['total_injuries'] == 0:
            summary = {
                'total_injuries': 0,
                'active_injuries': 0,
                'avg_recovery_days': 0,
                'most_common_injury': 'N/A',
                'most_affected_part': 'N/A'
            }
            self._cache[cache_key] = summary
            return summary
        
        # Calcular estadísticas usando los datos base
        avg_recovery_days = (sum(base_stats['recovery_days']) / len(base_stats['recovery_days']) 
                            if base_stats['recovery_days'] else 0)
        
        # Encontrar el más común
        most_common_injury = self._find_most_common(base_stats['injury_types'])
        most_affected_part = self._find_most_common(base_stats['body_parts'])
        
        summary = {
            'total_injuries': base_stats['total_injuries'],
            'active_injuries': base_stats['active_injuries'],
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

    def _find_most_common(self, items: List[str]) -> str:
        """Encuentra el elemento más común en una lista."""
        if not items:
            return 'N/A'
        
        counts = {}
        for item in items:
            counts[item] = counts.get(item, 0) + 1
        
        return max(counts.items(), key=lambda x: x[1])[0]
    
    def get_injury_distribution(self) -> Dict:
        """Obtiene distribución de lesiones por tipo."""
        cache_key = 'injury_distribution'
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        types, counts = self._count_and_sort('injury_type', 10)
        
        distribution = {'types': types, 'counts': counts}
        self._cache[cache_key] = distribution
        return distribution

    def get_body_parts_analysis(self) -> Dict:
        """Obtiene análisis de lesiones por partes del cuerpo."""
        cache_key = 'body_parts_analysis'
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        if not self.injuries_data:
            return {'parts': [], 'counts': [], 'percentages': []}
        
        parts, counts = self._count_and_sort('body_part', 8)
        
        # Calcular porcentajes
        total_injuries = len(self.injuries_data)
        percentages = [round((count / total_injuries) * 100, 1) for count in counts] if total_injuries > 0 else []
        
        analysis = {
            'parts': parts,
            'counts': counts,
            'percentages': percentages
        }
        
        self._cache[cache_key] = analysis
        return analysis
    
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
    
    def get_team_risk_analysis(self, risk_weights: Optional[Dict] = None) -> Dict:
        """
        Obtiene análisis de riesgo por equipo con pesos configurables.
        
        Args:
            risk_weights: Diccionario con pesos para diferentes factores de riesgo
        """
        cache_key = f'team_risk_analysis_{hash(str(risk_weights))}'
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        if not self.injuries_data:
            return {'teams': [], 'risk_scores': [], 'details': {}}
        
        # Pesos por defecto para el cálculo de riesgo
        default_weights = {
            'total_injuries': 0.4,
            'severe_injuries': 2.0,
            'active_injuries': 1.5,
            'avg_recovery_days': 0.01
        }
        
        weights = risk_weights or default_weights
        
        # Análisis de riesgo por equipo
        team_stats = self._calculate_team_stats()
        team_risk = self._calculate_risk_scores(team_stats, weights)
        
        # Ordenar por riesgo y tomar top 8
        team_risk.sort(key=lambda x: x['risk_score'], reverse=True)
        if len(team_risk) > 8:
            team_risk = team_risk[:8]
        
        analysis = {
            'teams': [item['team'] for item in team_risk],
            'risk_scores': [item['risk_score'] for item in team_risk],
            'details': {item['team']: item for item in team_risk}
        }
        
        self._cache[cache_key] = analysis
        return analysis

    def _calculate_team_stats(self) -> Dict:
        """Calcula estadísticas por equipo."""
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
            
            if injury.get('severity') == 'Grave':
                team_stats[team]['severe_injuries'] += 1
            
            if injury.get('recovery_days'):
                team_stats[team]['recovery_days'].append(injury.get('recovery_days', 0))
            
            if injury.get('status') == 'En tratamiento':
                team_stats[team]['active_injuries'] += 1
        
        return team_stats

    def _calculate_risk_scores(self, team_stats: Dict, weights: Dict) -> List[Dict]:
        """Calcula puntuaciones de riesgo para cada equipo."""
        team_risk = []
        
        for team, stats in team_stats.items():
            avg_recovery = (sum(stats['recovery_days']) / len(stats['recovery_days']) 
                        if stats['recovery_days'] else 0)
            
            # Fórmula de riesgo configurable
            risk_score = (
                stats['total_injuries'] * weights['total_injuries'] +
                stats['severe_injuries'] * weights['severe_injuries'] +
                stats['active_injuries'] * weights['active_injuries'] +
                avg_recovery * weights['avg_recovery_days']
            )
            
            team_risk.append({
                'team': team,
                'risk_score': risk_score,
                'total_injuries': stats['total_injuries'],
                'severe_injuries': stats['severe_injuries'],
                'active_injuries': stats['active_injuries'],
                'avg_recovery_days': round(avg_recovery, 1)
            })
        
        return team_risk
    
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
        """Prepara datos específicamente para gráficos."""
        cache_key = f'chart_data_{chart_type}_{team}'
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Mapeo de tipos de gráfico a métodos
        chart_methods = {
            'distribution': self.get_injury_distribution,
            'trends': self.get_monthly_trends,
            'body_parts': self.get_body_parts_analysis,
            'risk': self.get_team_risk_analysis
        }
        
        if chart_type in chart_methods:
            # Filtrar por equipo si es necesario (solo para ciertos tipos)
            if team and team != 'all' and chart_type in ['distribution', 'body_parts']:
                # Crear una instancia temporal con datos filtrados
                filtered_data = [injury for injury in self.injuries_data 
                            if injury.get('team') == team]
                if filtered_data:
                    temp_aggregator = TransfermarktStatsAggregator(filtered_data)
                    data = getattr(temp_aggregator, chart_methods[chart_type].__name__)()
                else:
                    data = {}
            else:
                data = chart_methods[chart_type]()
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