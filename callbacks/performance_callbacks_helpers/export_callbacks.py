# ABOUTME: Export functionality callbacks
# ABOUTME: PDF and data export operations

"""
Export callbacks for performance dashboard.

This module contains callbacks for exporting performance data
to various formats (PDF, CSV, etc.).
"""

from dash import Input, Output, State, callback
from dash.exceptions import PreventUpdate
from dash.dcc import send_bytes, send_string
from datetime import datetime


@callback(
    Output('download-performance-pdf', 'data'),
    [Input('export-pdf-button', 'n_clicks')],
    [State('performance-data-store', 'data'),
     State('current-filters-store', 'data')],
    prevent_initial_call=True
)
def export_performance_pdf(n_clicks, performance_data, filters):
    """
    Exporta el reporte de performance a PDF.

    DESIGN NOTES:
    - Only triggers on explicit button click
    - Uses State for data (not Input to avoid re-triggering)
    - Generates dynamic filename based on analysis level
    - Returns error log file if PDF generation fails
    """
    if n_clicks is None:
        raise PreventUpdate

    # Variables para debugging
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    try:
        # Verificar datos básicos
        if not performance_data:
            raise ValueError("No hay datos de performance disponibles")

        if not filters:
            filters = {"analysis_level": "league"}  # Valor por defecto

        # Importar generador
        from utils.pdf_generator import SportsPDFGenerator

        # Determinar análisis level y filename
        analysis_level = filters.get('analysis_level', 'league')
        season = filters.get('season', 'unknown')

        if analysis_level == 'team':
            filename = (
                f"reporte_performance_{filters.get('team', 'equipo')}_"
                f"{season}_{timestamp}.pdf"
            )
        elif analysis_level == 'player':
            filename = (
                f"reporte_performance_{filters.get('player', 'jugador')}_"
                f"{season}_{timestamp}.pdf"
            )
        else:
            filename = f"reporte_performance_liga_{season}_{timestamp}.pdf"

        # Generar PDF
        pdf_generator = SportsPDFGenerator()
        pdf_buffer = pdf_generator.create_performance_report(
            performance_data, filters
        )

        # Usar send_bytes para manejar automáticamente los bytes
        return send_bytes(pdf_buffer.getvalue(), filename)

    except Exception as e:
        # En caso de error, crear un archivo de texto con información de debug
        error_content = f"""ERROR GENERANDO PDF
========================

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Error: {str(e)}
Tipo de error: {type(e).__name__}

Información de debug:
- Performance data disponible: {performance_data is not None}
- Performance data type: {type(performance_data)}
- Filters: {filters}
- Analysis level: {filters.get('analysis_level') if filters else 'No filters'}

Performance data keys: {list(performance_data.keys()) if isinstance(performance_data, dict) else 'No es dict'}

Traceback completo:
{str(e)}
"""

        # Crear archivo de error usando send_string
        return send_string(error_content, f"error_export_{timestamp}.txt")
