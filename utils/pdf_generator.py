"""
Utilidades para generar reportes en PDF para los dashboards deportivos.
Utiliza reportlab para crear PDFs personalizados con gráficos y datos.
"""

from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from io import BytesIO
from datetime import datetime
import base64
import plotly.graph_objects as go
import plotly.io as pio
import pandas as pd
from typing import Dict, List, Optional, Any

class SportsPDFGenerator:
    """
    Generador de reportes PDF para dashboards deportivos.
    Incluye funcionalidades para crear reportes de performance e injuries.
    """
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        
        # Crear estilos personalizados
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=1,  # Center
            textColor=colors.darkblue
        )
        
        self.subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=20,
            textColor=colors.darkgreen
        )
        
        self.normal_style = ParagraphStyle(
            'CustomNormal',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=12
        )
    
    def create_performance_report(self, data: Dict, filters: Dict) -> BytesIO:
        """
        Crea un reporte PDF de performance.
        
        Args:
            data: Diccionario con datos de performance
            filters: Filtros aplicados al reporte
            
        Returns:
            BytesIO object con el PDF generado
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []
        
        # Título principal
        title = Paragraph("REPORTE DE PERFORMANCE", self.title_style)
        story.append(title)
        story.append(Spacer(1, 20))
        
        # Información de generación
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
        info_text = f"Generado el: {timestamp}"
        story.append(Paragraph(info_text, self.normal_style))
        story.append(Spacer(1, 10))
        
        # Información de filtros
        filter_info = self._create_filter_section(filters)
        story.extend(filter_info)
        story.append(Spacer(1, 20))
        
        # Métricas principales
        if 'overview' in data:
            kpi_section = self._create_kpi_section(data['overview'], filters.get('analysis_level', 'league'))
            story.extend(kpi_section)
            story.append(Spacer(1, 20))
        
        # Top performers
        if 'top_performers' in data:
            top_section = self._create_top_performers_section(data['top_performers'])
            story.extend(top_section)
            story.append(Spacer(1, 20))
        
        # Análisis por posición (solo para liga)
        if filters.get('analysis_level') == 'league' and 'position_analysis' in data:
            position_section = self._create_position_analysis_section(data['position_analysis'])
            story.extend(position_section)
        
        # Información del equipo (solo para equipo)
        if filters.get('analysis_level') == 'team' and 'top_players' in data:
            team_section = self._create_team_analysis_section(data['top_players'])
            story.extend(team_section)
        
        # Información del jugador (solo para jugador)
        if filters.get('analysis_level') == 'player' and 'basic_info' in data:
            player_section = self._create_player_analysis_section(data)
            story.extend(player_section)
        
        # Pie de página
        footer = Paragraph(
            "Reporte generado por Sports Dashboard - Liga de Hong Kong",
            ParagraphStyle('Footer', fontSize=8, alignment=1, textColor=colors.grey)
        )
        story.append(Spacer(1, 30))
        story.append(footer)
        
        # Construir PDF
        doc.build(story)
        buffer.seek(0)
        return buffer
    
    def create_injury_report(self, data: List[Dict], filters: Dict, summary_stats: Dict) -> BytesIO:
        """
        Crea un reporte PDF de lesiones.
        
        Args:
            data: Lista de diccionarios con datos de lesiones
            filters: Filtros aplicados al reporte
            summary_stats: Estadísticas resumidas
            
        Returns:
            BytesIO object con el PDF generado
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []
        
        # Título principal
        title = Paragraph("REPORTE DE LESIONES", self.title_style)
        story.append(title)
        story.append(Spacer(1, 20))
        
        # Información de generación
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
        info_text = f"Generado el: {timestamp}"
        story.append(Paragraph(info_text, self.normal_style))
        story.append(Spacer(1, 10))
        
        # Información de filtros
        filter_text = f"<b>Filtros aplicados:</b><br/>"
        filter_text += f"Tipo de análisis: {filters.get('analysis_type', 'N/A')}<br/>"
        filter_text += f"Equipo: {filters.get('team', 'Todos')}<br/>"
        filter_text += f"Período: {filters.get('period', 'N/A')}<br/>"
        story.append(Paragraph(filter_text, self.normal_style))
        story.append(Spacer(1, 20))
        
        # Resumen estadístico
        summary_section = self._create_injury_summary_section(summary_stats, len(data))
        story.extend(summary_section)
        story.append(Spacer(1, 20))
        
        # Tabla de lesiones
        if data:
            table_section = self._create_injury_table_section(data)
            story.extend(table_section)
        
        # Pie de página
        footer = Paragraph(
            "Reporte generado por Sports Dashboard - Gestión de Lesiones",
            ParagraphStyle('Footer', fontSize=8, alignment=1, textColor=colors.grey)
        )
        story.append(Spacer(1, 30))
        story.append(footer)
        
        # Construir PDF
        doc.build(story)
        buffer.seek(0)
        return buffer
    
    def _create_filter_section(self, filters: Dict) -> List:
        """Crea la sección de filtros aplicados."""
        elements = []
        
        subtitle = Paragraph("Filtros Aplicados", self.subtitle_style)
        elements.append(subtitle)
        
        filter_text = ""
        if filters.get('analysis_level'):
            level_names = {'league': 'Liga Completa', 'team': 'Equipo', 'player': 'Jugador'}
            filter_text += f"<b>Nivel de análisis:</b> {level_names.get(filters['analysis_level'], filters['analysis_level'])}<br/>"
        
        if filters.get('team'):
            filter_text += f"<b>Equipo:</b> {filters['team']}<br/>"
        
        if filters.get('player'):
            filter_text += f"<b>Jugador:</b> {filters['player']}<br/>"
        
        if filters.get('position_filter') and filters.get('position_filter') != 'all':
            filter_text += f"<b>Posición:</b> {filters['position_filter']}<br/>"
        
        if filters.get('age_range'):
            age_range = filters['age_range']
            filter_text += f"<b>Rango de edad:</b> {age_range[0]} - {age_range[1]} años<br/>"
        
        elements.append(Paragraph(filter_text, self.normal_style))
        
        return elements
    
    def _create_kpi_section(self, overview: Dict, level: str) -> List:
        """Crea la sección de métricas principales."""
        elements = []
        
        subtitle = Paragraph("Métricas Principales", self.subtitle_style)
        elements.append(subtitle)
        
        if level == 'league':
            kpi_data = [
                ['Métrica', 'Valor'],
                ['Total de Jugadores', str(overview.get('total_players', 0))],
                ['Total de Equipos', str(overview.get('total_teams', 0))],
                ['Total de Goles', str(overview.get('total_goals', 0))],
                ['Total de Asistencias', str(overview.get('total_assists', 0))],
                ['Edad Promedio', f"{overview.get('average_age', 0)} años"],
                ['Goles por Jugador', str(overview.get('avg_goals_per_player', 0))]
            ]
        elif level == 'team':
            kpi_data = [
                ['Métrica', 'Valor'],
                ['Equipo', overview.get('team_name', 'N/A')],
                ['Total de Jugadores', str(overview.get('total_players', 0))],
                ['Total de Goles', str(overview.get('total_goals', 0))],
                ['Total de Asistencias', str(overview.get('total_assists', 0))],
                ['Edad Promedio', f"{overview.get('avg_age', 0)} años"]
            ]
        else:  # player
            kpi_data = [
                ['Métrica', 'Valor'],
                ['Jugador', overview.get('name', 'N/A')],
                ['Equipo', overview.get('team', 'N/A')],
                ['Edad', f"{overview.get('age', 0)} años"],
                ['Posición', overview.get('position_group', 'N/A')],
                ['Partidos Jugados', str(overview.get('matches_played', 0))]
            ]
        
        table = Table(kpi_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
        return elements
    
    def _create_top_performers_section(self, top_performers: Dict) -> List:
        """Crea la sección de top performers."""
        elements = []
        
        subtitle = Paragraph("Top Performers", self.subtitle_style)
        elements.append(subtitle)
        
        # Top goleadores
        if 'top_scorers' in top_performers:
            scorer_subtitle = Paragraph("Top Goleadores", ParagraphStyle('SubSubtitle', fontSize=12, spaceAfter=10, textColor=colors.darkred))
            elements.append(scorer_subtitle)
            
            scorer_data = [['Pos.', 'Jugador', 'Equipo', 'Goles']]
            for i, scorer in enumerate(top_performers['top_scorers'][:5], 1):
                scorer_data.append([
                    str(i),
                    scorer['Player'],
                    scorer['Team'],
                    str(scorer['Goals'])
                ])
            
            scorer_table = Table(scorer_data)
            scorer_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkred),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(scorer_table)
            elements.append(Spacer(1, 15))
        
        # Top asistentes
        if 'top_assisters' in top_performers:
            assister_subtitle = Paragraph("Top Asistentes", ParagraphStyle('SubSubtitle', fontSize=12, spaceAfter=10, textColor=colors.darkgreen))
            elements.append(assister_subtitle)
            
            assister_data = [['Pos.', 'Jugador', 'Equipo', 'Asistencias']]
            for i, assister in enumerate(top_performers['top_assisters'][:5], 1):
                assister_data.append([
                    str(i),
                    assister['Player'],
                    assister['Team'],
                    str(assister['Assists'])
                ])
            
            assister_table = Table(assister_data)
            assister_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(assister_table)
        
        return elements
    
    def _create_position_analysis_section(self, position_analysis: Dict) -> List:
        """Crea la sección de análisis por posición."""
        elements = []
        
        subtitle = Paragraph("Análisis por Posición", self.subtitle_style)
        elements.append(subtitle)
        
        # Crear tabla con estadísticas por posición
        position_data = [['Posición', 'Jugadores', 'Goles', 'Edad Promedio']]
        
        for position, stats in position_analysis.items():
            position_data.append([
                position,
                str(stats.get('player_count', 0)),
                str(stats.get('total_goals', 0)),
                f"{stats.get('avg_age', 0)} años"
            ])
        
        position_table = Table(position_data)
        position_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(position_table)
        return elements
    
    def _create_team_analysis_section(self, top_players: Dict) -> List:
        """Crea la sección de análisis del equipo."""
        elements = []
        
        subtitle = Paragraph("Análisis del Equipo", self.subtitle_style)
        elements.append(subtitle)
        
        team_text = ""
        if 'top_scorer' in top_players:
            top_scorer = top_players['top_scorer']
            team_text += f"<b>Máximo Goleador:</b> {top_scorer['name']} ({top_scorer['goals']} goles)<br/>"
        
        if 'top_assister' in top_players:
            top_assister = top_players['top_assister']
            team_text += f"<b>Máximo Asistente:</b> {top_assister['name']} ({top_assister['assists']} asistencias)<br/>"
        
        if 'most_played' in top_players:
            most_played = top_players['most_played']
            team_text += f"<b>Más Minutos:</b> {most_played['name']} ({most_played['minutes']} minutos)<br/>"
        
        elements.append(Paragraph(team_text, self.normal_style))
        return elements
    
    def _create_player_analysis_section(self, data: Dict) -> List:
        """Crea la sección de análisis del jugador."""
        elements = []
        
        subtitle = Paragraph("Análisis del Jugador", self.subtitle_style)
        elements.append(subtitle)
        
        basic_info = data.get('basic_info', {})
        performance = data.get('performance_stats', {})
        
        player_text = f"<b>Información Básica:</b><br/>"
        player_text += f"Nombre: {basic_info.get('name', 'N/A')}<br/>"
        player_text += f"Equipo: {basic_info.get('team', 'N/A')}<br/>"
        player_text += f"Edad: {basic_info.get('age', 'N/A')} años<br/>"
        player_text += f"Posición: {basic_info.get('position_group', 'N/A')}<br/><br/>"
        
        player_text += f"<b>Estadísticas de Performance:</b><br/>"
        player_text += f"Goles: {performance.get('goals', 0)}<br/>"
        player_text += f"Asistencias: {performance.get('assists', 0)}<br/>"
        player_text += f"Minutos por partido: {performance.get('minutes_per_match', 0):.1f}<br/>"
        
        elements.append(Paragraph(player_text, self.normal_style))
        return elements
    
    def _create_injury_summary_section(self, summary_stats: Dict, total_records: int) -> List:
        """Crea la sección de resumen de lesiones."""
        elements = []
        
        subtitle = Paragraph("Resumen de Lesiones", self.subtitle_style)
        elements.append(subtitle)
        
        summary_data = [
            ['Métrica', 'Valor'],
            ['Total de Lesiones', str(total_records)],
            ['Lesiones en Tratamiento', str(summary_stats.get('active_injuries', 0))],
            ['Días Promedio de Recuperación', f"{summary_stats.get('avg_recovery_days', 0):.0f}"],
            ['Lesión Más Común', summary_stats.get('most_common_injury', 'N/A')],
            ['Zona Más Afectada', summary_stats.get('most_affected_part', 'N/A')]
        ]
        
        summary_table = Table(summary_data)
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkred),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightpink),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(summary_table)
        return elements
    
    def _create_injury_table_section(self, data: List[Dict]) -> List:
        """Crea la sección de tabla de lesiones."""
        elements = []
        
        subtitle = Paragraph("Registro de Lesiones", self.subtitle_style)
        elements.append(subtitle)
        
        # Crear tabla con los primeros 20 registros
        table_data = [['Jugador', 'Equipo', 'Tipo', 'Zona', 'Severidad', 'Fecha', 'Estado']]
        
        for injury in data[:20]:  # Máximo 20 registros para el PDF
            table_data.append([
                injury.get('player_name', 'N/A'),
                injury.get('team', 'N/A'),
                injury.get('injury_type', 'N/A'),
                injury.get('body_part', 'N/A'),
                injury.get('severity', 'N/A'),
                injury.get('injury_date', 'N/A'),
                injury.get('status', 'N/A')
            ])
        
        injury_table = Table(table_data)
        injury_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkred),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(injury_table)
        
        if len(data) > 20:
            note = Paragraph(f"Nota: Se muestran los primeros 20 registros de {len(data)} total.", 
                           ParagraphStyle('Note', fontSize=8, textColor=colors.grey))
            elements.append(Spacer(1, 10))
            elements.append(note)
        
        return elements