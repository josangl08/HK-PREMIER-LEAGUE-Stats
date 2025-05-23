"""
Utilidades para generar reportes en PDF para los dashboards deportivos.
Utiliza reportlab para crear PDFs personalizados con gráficos y datos.
Versión simplificada con mejor manejo de errores y menos redundancia.
"""

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from io import BytesIO
from datetime import datetime
import logging
from typing import Dict, List, Optional, Any

# Configurar logging
logger = logging.getLogger(__name__)

class SportsPDFGenerator:
    """
    Generador de reportes PDF para dashboards deportivos.
    Versión simplificada con mejor manejo de errores.
    """
    
    def __init__(self):
        """Inicializa el generador con estilos básicos."""
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
        try:
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            story = []
            
            # Título principal
            title = Paragraph("PERFORMANCE REPORT", self.title_style)
            story.append(title)
            story.append(Spacer(1, 20))
            
            # Información de generación
            timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
            info_text = f"Completed on: {timestamp}"
            story.append(Paragraph(info_text, self.normal_style))
            story.append(Spacer(1, 10))
            
            # Secciones principales - Usando try/except para mayor robustez
            try:
                # Información de filtros
                filter_info = self._create_filter_section(filters)
                story.extend(filter_info)
                story.append(Spacer(1, 20))
            except Exception as e:
                logger.warning(f"Error generando sección de filtros: {e}")
                story.append(Paragraph("Error when generating filter information", self.normal_style))
            
            # Determinar nivel de análisis y agregar secciones apropiadas
            analysis_level = filters.get('analysis_level', 'league')
            
            # Métricas principales (KPIs)
            if 'overview' in data:
                try:
                    kpi_section = self._create_kpi_section(data['overview'], analysis_level)
                    story.extend(kpi_section)
                    story.append(Spacer(1, 20))
                except Exception as e:
                    logger.warning(f"Error generando KPIs: {e}")
                    story.append(Paragraph("Failure to generate key metrics", self.normal_style))
            
            # Secciones específicas según el nivel de análisis
            if analysis_level == 'league':
                # Top performers y análisis por posición
                if 'top_performers' in data:
                    try:
                        top_section = self._create_top_performers_section(data['top_performers'])
                        story.extend(top_section)
                        story.append(Spacer(1, 20))
                    except Exception as e:
                        logger.warning(f"Error generando sección top performers: {e}")
                
                if 'position_analysis' in data:
                    try:
                        position_section = self._create_position_analysis_section(data['position_analysis'])
                        story.extend(position_section)
                    except Exception as e:
                        logger.warning(f"Error generando análisis por posición: {e}")
            
            elif analysis_level == 'team' and 'top_players' in data:
                try:
                    team_section = self._create_team_analysis_section(data['top_players'])
                    story.extend(team_section)
                except Exception as e:
                    logger.warning(f"Error generando análisis de equipo: {e}")
            
            elif analysis_level == 'player' and 'basic_info' in data:
                try:
                    player_section = self._create_player_analysis_section(data)
                    story.extend(player_section)
                except Exception as e:
                    logger.warning(f"Error generando análisis de jugador: {e}")
            
            # Pie de página
            story.append(Spacer(1, 30))
            footer = Paragraph(
                "Report generated by the Hong Kong Premier League Dashboard - Performance Management",
                ParagraphStyle('Footer', fontSize=8, alignment=1, textColor=colors.grey)
            )
            story.append(footer)
            
            # Construir PDF
            doc.build(story)
            buffer.seek(0)
            return buffer
            
        except Exception as e:
            logger.error(f"Error generando reporte PDF de performance: {e}")
            # Crear un PDF de error básico
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            story = [
                Paragraph("ERROR IN REPORT GENERATION", self.title_style),
                Spacer(1, 20),
                Paragraph(f"An error occurred while generating the report: {str(e)}", self.normal_style)
            ]
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
        try:
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            story = []
            
            # Título principal
            title = Paragraph("INJURIES REPORT", self.title_style)
            story.append(title)
            story.append(Spacer(1, 20))
            
            # Información de generación
            timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
            info_text = f"Completed on: {timestamp}"
            story.append(Paragraph(info_text, self.normal_style))
            story.append(Spacer(1, 10))
            
            # Información de filtros
            filter_text = f"<b>Filters applied:</b><br/>"
            filter_text += f"Type of analysis: {filters.get('analysis_type', 'N/A')}<br/>"
            filter_text += f"Team: {filters.get('team', 'Todos')}<br/>"
            filter_text += f"Period: {filters.get('period', 'N/A')}<br/>"
            story.append(Paragraph(filter_text, self.normal_style))
            story.append(Spacer(1, 20))
            
            # Resumen estadístico
            try:
                summary_section = self._create_injury_summary_section(summary_stats, len(data))
                story.extend(summary_section)
                story.append(Spacer(1, 20))
            except Exception as e:
                logger.warning(f"Error generando resumen de lesiones: {e}")
                story.append(Paragraph("Error when generating summary statistics", self.normal_style))
            
            # Tabla de lesiones
            if data:
                try:
                    table_section = self._create_injury_table_section(data)
                    story.extend(table_section)
                except Exception as e:
                    logger.warning(f"Error generando tabla de lesiones: {e}")
                    story.append(Paragraph("Error when generating injury table", self.normal_style))
            
            # Pie de página
            footer = Paragraph(
                "Report generated by the Hong Kong Premier League Dashboard - Injury Management",
                ParagraphStyle('Footer', fontSize=8, alignment=1, textColor=colors.grey)
            )
            story.append(Spacer(1, 30))
            story.append(footer)
            
            # Construir PDF
            doc.build(story)
            buffer.seek(0)
            return buffer
            
        except Exception as e:
            logger.error(f"Error generando reporte PDF de lesiones: {e}")
            # Crear un PDF de error básico
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            story = [
                Paragraph("ERROR IN REPORT GENERATION", self.title_style),
                Spacer(1, 20),
                Paragraph(f"An error occurred while generating the report: {str(e)}", self.normal_style)
            ]
            doc.build(story)
            buffer.seek(0)
            return buffer
    
    # ----- Métodos privados auxiliares (simplificados) -----
    
    def _create_filter_section(self, filters: Dict) -> List:
        """Crea la sección de filtros aplicados."""
        elements = []
        
        subtitle = Paragraph("Applied Filters", self.subtitle_style)
        elements.append(subtitle)
        
        filter_text = ""
        if filters.get('analysis_level'):
            level_names = {'league': 'Full League', 'team': 'Team', 'player': 'Player'}
            filter_text += f"<b>Analysis Level:</b> {level_names.get(filters['analysis_level'], filters['analysis_level'])}<br/>"
        
        if filters.get('team'):
            filter_text += f"<b>Team:</b> {filters['team']}<br/>"
        
        if filters.get('player'):
            filter_text += f"<b>Player:</b> {filters['player']}<br/>"
        
        if filters.get('position_filter') and filters.get('position_filter') != 'all':
            filter_text += f"<b>Position:</b> {filters['position_filter']}<br/>"
        
        if filters.get('age_range'):
            age_range = filters['age_range']
            filter_text += f"<b>Age Range:</b> {age_range[0]} - {age_range[1]} años<br/>"
        
        elements.append(Paragraph(filter_text, self.normal_style))
        
        return elements
    
    def _create_kpi_section(self, overview: Dict, level: str) -> List:
        """Crea la sección de métricas principales."""
        elements = []
        
        subtitle = Paragraph("Main Metrics", self.subtitle_style)
        elements.append(subtitle)
        
        # Datos KPI según nivel
        if level == 'league':
            kpi_data = [
                ['Métrica', 'Valor'],
                ['Total Players', str(overview.get('total_players', 0))],
                ['Total Teams', str(overview.get('total_teams', 0))],
                ['Total Goals', str(overview.get('total_goals', 0))],
                ['Total Assists', str(overview.get('total_assists', 0))],
                ['Avg. Age', f"{overview.get('average_age', 0)} años"],
                ['Goals per Player', str(overview.get('avg_goals_per_player', 0))]
            ]
        elif level == 'team':
            kpi_data = [
                ['Métrica', 'Valor'],
                ['Team', overview.get('team_name', 'N/A')],
                ['Total Players', str(overview.get('total_players', 0))],
                ['Total Goals', str(overview.get('total_goals', 0))],
                ['Total Assists', str(overview.get('total_assists', 0))],
                ['Avg. Age', f"{overview.get('avg_age', 0)} años"]
            ]
        else:  # player
            kpi_data = [
                ['Métrica', 'Valor'],
                ['Player', overview.get('name', 'N/A')],
                ['Team', overview.get('team', 'N/A')],
                ['Age', f"{overview.get('age', 0)} años"],
                ['Position', overview.get('position_group', 'N/A')],
                ['Matches Played', str(overview.get('matches_played', 0))]
            ]
        
        # Crear tabla de KPIs
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
        if 'top_scorers' in top_performers and top_performers['top_scorers']:
            elements.append(Paragraph("Top Goleadores", 
                ParagraphStyle('SubSubtitle', fontSize=12, spaceAfter=10, textColor=colors.darkred)))
            
            scorer_data = [['Pos.', 'Player', 'Team', 'Goals']]
            for i, scorer in enumerate(top_performers['top_scorers'][:5], 1):
                scorer_data.append([
                    str(i),
                    scorer.get('Player', 'N/A'),
                    scorer.get('Team', 'N/A'),
                    str(scorer.get('Goals', 0))
                ])
            
            table = self._create_table(scorer_data, colors.darkred)
            elements.append(table)
            elements.append(Spacer(1, 15))
        
        # Top asistentes
        if 'top_assisters' in top_performers and top_performers['top_assisters']:
            elements.append(Paragraph("Top Asisters", 
                ParagraphStyle('SubSubtitle', fontSize=12, spaceAfter=10, textColor=colors.darkgreen)))
            
            assister_data = [['Pos.', 'Player', 'Team', 'Assists']]
            for i, assister in enumerate(top_performers['top_assisters'][:5], 1):
                assister_data.append([
                    str(i),
                    assister.get('Player', 'N/A'),
                    assister.get('Team', 'N/A'),
                    str(assister.get('Assists', 0))
                ])
            
            table = self._create_table(assister_data, colors.darkgreen)
            elements.append(table)
        
        return elements
    
    def _create_table(self, data: List[List[str]], header_color=colors.grey) -> Table:
        """Método auxiliar para crear tablas con formato estándar."""
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), header_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        return table
    
    def _create_position_analysis_section(self, position_analysis: Dict) -> List:
        """Crea la sección de análisis por posición."""
        elements = []
        
        subtitle = Paragraph("Position Analysis", self.subtitle_style)
        elements.append(subtitle)
        
        # Crear tabla con estadísticas por posición
        position_data = [['Pos.', 'Players', 'Goals', 'Avg. Age']]
        
        for position, stats in position_analysis.items():
            position_data.append([
                position,
                str(stats.get('player_count', 0)),
                str(stats.get('total_goals', 0)),
                f"{stats.get('avg_age', 0)} años"
            ])
        
        table = self._create_table(position_data, colors.darkblue)
        elements.append(table)
        return elements
    
    def _create_team_analysis_section(self, top_players: Dict) -> List:
        """Crea la sección de análisis del equipo."""
        elements = []
        
        subtitle = Paragraph("Team Analysis", self.subtitle_style)
        elements.append(subtitle)
        
        team_text = ""
        if 'top_scorer' in top_players:
            top_scorer = top_players['top_scorer']
            team_text += f"<b>Top Scorer:</b> {top_scorer.get('name', 'N/A')} ({top_scorer.get('goals', 0)} goles)<br/>"
        
        if 'top_assister' in top_players:
            top_assister = top_players['top_assister']
            team_text += f"<b>Top Asister:</b> {top_assister.get('name', 'N/A')} ({top_assister.get('assists', 0)} asistencias)<br/>"
        
        if 'most_played' in top_players:
            most_played = top_players['most_played']
            team_text += f"<b>Most Minutes:</b> {most_played.get('name', 'N/A')} ({most_played.get('minutes', 0)} minutos)<br/>"
        
        elements.append(Paragraph(team_text, self.normal_style))
        return elements
    
    def _create_player_analysis_section(self, data: Dict) -> List:
        """Crea la sección de análisis del jugador."""
        elements = []
        
        subtitle = Paragraph("Player Analysis", self.subtitle_style)
        elements.append(subtitle)
        
        basic_info = data.get('basic_info', {})
        performance = data.get('performance_stats', {})
        
        player_text = f"<b>Basic Info:</b><br/>"
        player_text += f"Name: {basic_info.get('name', 'N/A')}<br/>"
        player_text += f"Team: {basic_info.get('team', 'N/A')}<br/>"
        player_text += f"Age: {basic_info.get('age', 'N/A')} años<br/>"
        player_text += f"Position: {basic_info.get('position_group', 'N/A')}<br/><br/>"
        
        player_text += f"<b>Performance Stats:</b><br/>"
        player_text += f"Goals: {performance.get('goals', 0)}<br/>"
        player_text += f"Assists: {performance.get('assists', 0)}<br/>"
        player_text += f"Minutes per Game: {performance.get('minutes_per_match', 0):.1f}<br/>"
        
        elements.append(Paragraph(player_text, self.normal_style))
        return elements
    
    def _create_injury_summary_section(self, summary_stats: Dict, total_records: int) -> List:
        """Crea la sección de resumen de lesiones."""
        elements = []
        
        subtitle = Paragraph("Injury summary", self.subtitle_style)
        elements.append(subtitle)
        
        summary_data = [
            ['Métrica', 'Valor'],
            ['Total Injuries', str(total_records)],
            ['Injuries in Treatment', str(summary_stats.get('active_injuries', 0))],
            ['Average Recovery Days', f"{summary_stats.get('avg_recovery_days', 0):.0f}"],
            ['Most Common Injury', summary_stats.get('most_common_injury', 'N/A')],
            ['Most Affected Area', summary_stats.get('most_affected_part', 'N/A')]
        ]
        
        table = Table(summary_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkred),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightpink),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
        return elements
    
    def _create_injury_table_section(self, data: List[Dict]) -> List:
        """Crea la sección de tabla de lesiones."""
        elements = []
        
        subtitle = Paragraph("Injury register", self.subtitle_style)
        elements.append(subtitle)
        
        # Limitar a 20 registros para el PDF
        display_data = data[:20] if len(data) > 20 else data
        
        # Crear tabla de lesiones
        table_data = [['Player', 'Team', 'Type', 'Zone', 'Severity', 'Date', 'State']]
        
        for injury in display_data:
            table_data.append([
                injury.get('player_name', 'N/A'),
                injury.get('team', 'N/A'),
                injury.get('injury_type', 'N/A'),
                injury.get('body_part', 'N/A'),
                injury.get('severity', 'N/A'),
                injury.get('injury_date', 'N/A'),
                injury.get('status', 'N/A')
            ])
        
        table = Table(table_data)
        table.setStyle(TableStyle([
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
        
        elements.append(table)
        
        if len(data) > 20:
            note = Paragraph(f"Note: The first 20 records of {len(data)} total.", 
                ParagraphStyle('Note', fontSize=8, textColor=colors.grey))
            elements.append(Spacer(1, 10))
            elements.append(note)
        
        return elements