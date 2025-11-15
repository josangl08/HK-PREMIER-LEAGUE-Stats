# 📋 PLAN DE DESARROLLO COMPLETO
## Hong Kong Premier League Stats - Proyecto Académico y SaaS

**Última actualización:** 14 de noviembre de 2025
**Versión:** 1.1
**Autor:** Claude AI + josangl08

**⚠️ VERSIÓN 1.1 - DECISIONES FINALES DE MÉTRICAS APLICADAS:**
- ✅ 99 columnas totales (83 comunes + 16 físicas GPS)
- ✅ TODAS las 16 métricas físicas mantenidas (Opción B)
- ✅ Info personal completa: Birth country, Passport, Foot, Height, Weight (sin Market value)
- ✅ PAdj metrics incluidas (Pressure Adjusted)
- ✅ Aerial duels as GK per 90 incluida (no era duplicado)
- ✅ Ver detalles en: `docs/METRICAS_MANTENER_ELIMINAR.md`

---

## 🎯 OBJETIVOS DEL PROYECTO

### **Doble Propósito:**
1. **Académico**: Proyecto de máster en IA aplicada al deporte
   - Implementar modelos de Machine Learning aplicados a datos deportivos
   - Generar memoria técnica completa con documentación del proceso
   - Demostrar valor práctico de IA en análisis deportivo

2. **Profesional/SaaS**: Plataforma de estadísticas para jugadores
   - Análisis multinivel (Liga, Equipos, Jugadores)
   - Generación automática de contenido para redes sociales
   - Futuro: Monetización mediante suscripción/pago

### **Contenido Instagram:**
- Cuenta dedicada a estadísticas de la Hong Kong Premier League
- Publicación automática de insights, gráficas y análisis
- Formatos: Stories, Carousels, Posts estáticos

---

## 📊 CONTEXTO TÉCNICO ACTUAL

### **Tecnologías:**
- **Framework**: Dash 3.2.0 (Python web framework)
- **Visualización**: Plotly 5.22.0
- **Backend**: Flask 3.0.3 + Gunicorn
- **Datos**: Pandas, NumPy
- **UI**: Dash Bootstrap Components

### **Datos Disponibles:**
- **Fuente**: CSV manuales desde GitHub (josangl08/Hong-Kong-Data)
- **Temporadas**: 8 temporadas (2018-19 a 2025-26)
- **Granularidad**: Totales por temporada (NO por jornada actualmente)
- **Actualización**: Manual semanal (lunes post-jornada)

### **Estructura de Datos:**
- **99 columnas totales** confirmadas (ver `docs/METRICAS_MANTENER_ELIMINAR.md`)
  - 83 columnas comunes a todas las temporadas
  - 16 columnas físicas GPS (solo 2023-26): distancias, velocidad, aceleraciones, sprints
  - 28 columnas descartadas (metadata, duplicados, redundantes)
- **5 posiciones** definidas: Goalkeeper (GK), Defender (DEF), Midfielder (MID), Winger (WING), Forward (FWD)
- **xG/xA incluidos** en CSV (no calculados localmente)
- **Métrica especial GK**: Aerial duels as GK per 90 (renombrada de "Aerial duels per 90.1")

### **Funcionalidades Actuales:**
- Dashboard de rendimiento con 3 niveles (Liga, Equipo, Jugador)
- Filtros: Temporada, Equipo, Jugador, Posición, Edad
- Visualizaciones: Radar charts, bar charts, scatter plots, heatmaps
- Exportación a PDF
- Sistema de caché inteligente
- Métricas de eficiencia (Goals/xG, Assists/xA)
- Análisis táctico (tempo, pressing, transiciones)

### **NO implementado (oportunidades):**
- ❌ Machine Learning / IA real
- ❌ API REST para acceso externo
- ❌ Multi-usuario/suscripciones
- ❌ Generación automática de contenido Instagram
- ❌ Datos por jornada (solo totales de temporada)

---

## 📐 MÉTRICAS DISPONIBLES - DECISIÓN FINAL

**⚠️ IMPORTANTE:** Para el listado completo y detallado de las 99 métricas finales, consultar:
- **`docs/METRICAS_MANTENER_ELIMINAR.md`** - Documento maestro con todas las métricas
- **`docs/ANALISIS_COLUMNAS_CSV.md`** - Análisis exhaustivo de columnas disponibles

### **RESUMEN DE MÉTRICAS (99 COLUMNAS TOTALES)**

#### **Distribución por Categoría:**

| Categoría | # Columnas | Disponibilidad | Prioridad |
|-----------|------------|----------------|-----------|
| **Identificación** | 4 | Todas | Obligatorio |
| **Info Personal** | 5 | Todas | Alta |
| **Tiempo de Juego** | 2 | Todas | Obligatorio |
| **Goles** | 8 | Todas | Alta (FWD/WING/MID) |
| **Asistencias** | 4 | Todas | Alta (WING/MID) |
| **Tiros** | 6 | Todas | Alta (FWD/WING) |
| **Duelos** | 8 | Todas | Alta (todas posiciones) |
| **Defensa (incl. PAdj)** | 7 | Todas | Alta (DEF/MID-DM) |
| **Regates/Movilidad** | 5 | Todas | Alta (WING/MID-AM) |
| **Pases Generales** | 8 | 6 todas, 2 solo 2023+ | Alta (MID/DEF) |
| **Pases Cortos/Largos** | 6 | Todas | Media (MID/DEF/GK) |
| **Pases Avanzados** | 10 | Todas | Alta (MID/WING) |
| **Pases al Área** | 4 | Todas | Alta (MID-AM/WING) |
| **Centros** | 7 | Todas | Alta (WING) |
| **Recepción** | 3 | Todas | Media (todas) |
| **Faltas/Disciplina** | 7 | Todas | Media (todas) |
| **Portero** | 13 | Todas | Alta (GK solo) |
| **Set Pieces** | 7 | Todas | Media (MID/FWD) |
| **Acciones Atacantes** | 1 | Todas | Media (FWD/WING/MID) |
| **🏃 Datos Físicos GPS** | **16** | **Solo 2023-26** ⚠️ | **Alta (todas)** |
| **Otros** | 1 | Todas | Baja |

**Total: 83 comunes + 16 físicas = 99 columnas**

---

### **MÉTRICAS DESTACADAS POR POSICIÓN**

#### **GOALKEEPER (GK)** - 32 métricas relevantes

**13 Críticas (⭐⭐⭐):**
- Save rate, %, Clean sheets, Conceded goals per 90
- Shots against per 90, xG against per 90, Prevented goals per 90
- Exits per 90, **Aerial duels as GK per 90** ⭐ (específica de porteros)
- Passes per 90, Accurate passes, %, Long passes per 90, Accurate long passes, %
- Back passes received as GK per 90

**8 Importantes (⭐⭐):**
- Height, Aerial duels won, %, Forward passes per 90, Average long pass length
- Fouls per 90, Yellow cards, Total Distance per 90, Accelerations per 90

**11 Secundarias (⭐):**
- Age, Team, Birth country, Foot, Weight, Matches/Minutes played
- Back passes per 90, Free kicks per 90, On loan, Max Speed

#### **DEFENDER (DEF)** - 48 métricas relevantes
- **18 Críticas:** Defensive actions, Tackles, Interceptions, PAdj metrics, Duelos, Pases progresivos
- **15 Importantes:** Long passes, Goals (balón parado), Crosses (full-backs), Métricas físicas
- **Subtipos:** CB (central), Full-Back (ofensivo), Ball-Playing Defender

#### **MIDFIELDER (MID)** - 68 métricas relevantes
- **30 Críticas:** Passes/90, Forward passes, Through passes, Tackles (DM), Assists, Goals (AM)
- **23 Importantes:** Regates, Progressive runs, Métricas físicas
- **Arquetipos:** Defensive MID (DM), Central MID (CM), Attacking MID (AM)

#### **WINGER (WING)** - 61 métricas relevantes
- **28 Críticas:** Crosses, Assists, xA, Goals, Dribbles, Duels 1v1, Sprints, Max Speed
- **20 Importantes:** Progressive runs, Touches in box, HSR Distance
- **Especial:** Foot (crítico), Métricas físicas esenciales

#### **FORWARD (FWD)** - 52 métricas relevantes
- **23 Críticas:** Goals, xG, Shots on target, Touches in box, Penalties, Aerial duels (Target Man)
- **18 Importantes:** Assists (Complete Forward), Dribbles, Métricas físicas
- **Subtipos:** Target Man, Poacher, Complete Forward

**📖 Ver detalles completos:** `docs/METRICAS_MANTENER_ELIMINAR.md` (todas las métricas, benchmarks y prioridades)

---

## 🗂️ ROADMAP DE 3 FASES

---

## 🎨 FASE 1: MEJORA DE UI/UX Y MÉTRICAS
**Prioridad:** MÁXIMA
**Duración estimada:** 3-4 semanas
**Objetivo:** Solidificar la base de la aplicación con métricas correctas y diseño atractivo

### **1.1 Revisión y Mejora de Métricas**

#### **Tarea 1.1.1: Implementar métricas calculadas generales**
**Archivos a modificar:**
- `data/processors/hong_kong_processor.py`
- `metrics/advanced_metrics.py` (NUEVO archivo)

**Métricas a añadir:**
```python
# En hong_kong_processor.py
df['Participation_Pct'] = (df['Minutes played'] / team_total_minutes) * 100
df['Consistency_Index'] = 1 - (df['Goals'].std() / df['Goals'].mean())  # Por jugador multi-temporada
df['All_Round_Score'] = normalize(df['Goals'] + df['Assists'] + df['Tackles per 90'])
```

**Documentación:** ✅ Ya creado `docs/METRICAS_MANTENER_ELIMINAR.md` con 99 columnas finales

---

#### **Tarea 1.1.2: Implementar métricas específicas por posición**
**Archivos a crear:**
- `metrics/goalkeeper_metrics.py`
- `metrics/defender_metrics.py`
- `metrics/midfielder_metrics.py`
- `metrics/winger_metrics.py`
- `metrics/forward_metrics.py`

**Estructura de cada archivo:**
```python
class GoalkeeperMetrics:
    @staticmethod
    def goals_conceded_per_90(df):
        return df['Conceded goals'] / (df['Minutes played'] / 90)

    @staticmethod
    def clean_sheet_rate(df):
        return df['Clean sheets'] / df['Matches played'] * 100

    @staticmethod
    def distribution_quality_score(df):
        # Combina Pass Accuracy + Long Passes
        return (df['Accurate passes, %'] * 0.7) + (df['Long passes per 90'] * 3)
```

**Criterios de aceptación:**
- [ ] Todas las métricas prioritarias (⭐⭐⭐) implementadas
- [ ] Benchmarks documentados por posición
- [ ] Tests unitarios para cada métrica
- [ ] Validación de datos (no NaN, no negativos)

---

#### **Tarea 1.1.3: Sistema de identificación de arquetipos**
**Archivos a crear:**
- `metrics/archetype_detector.py`

**Funcionalidad:**
```python
def detect_midfielder_archetype(player_stats):
    """
    Detecta si es DM, CM o AM basándose en ratios de métricas

    Returns:
        {
            'archetype': 'Defensive Midfielder',
            'confidence': 0.85,
            'reasoning': 'Alto tackles/90, bajo through passes/90'
        }
    """
    if player_stats['Tackles per 90'] > 3 and player_stats['Through passes per 90'] < 1:
        return {'archetype': 'Defensive Midfielder', 'confidence': 0.9}
    # ... más reglas
```

**Arquetipos a detectar:**
- Midfielder: DM, CM, AM
- Defender: CB, Full-Back, Ball-Playing Defender
- Forward: Target Man, Poacher, Complete Forward

---

### **1.2 Mejora de Visualizaciones**

#### **Tarea 1.2.1: Rediseñar Player View con métricas por posición**
**Archivo:** `layouts/performance_views/player_view.py`

**Cambios:**
1. **Chart 1 (Radar)**: Mostrar solo métricas relevantes según posición
   - GK: 5 métricas (Save Rate, Clean Sheets, Distribution, etc.)
   - DEF: 6 métricas (Tackles, Interceptions, Pass Accuracy, etc.)
   - MID: 8 métricas (Passes, Through passes, Tackles, etc.)
   - WING: 6 métricas (Crosses, xA, Shots, etc.)
   - FWD: 6 métricas (Goals, xG, Shots on Target, etc.)

2. **Chart 2 (Percentiles)**: Top 6-8 métricas del jugador
   - Mostrar percentil vs posición (no vs toda la liga)
   - Destacar top 10% en verde, bottom 10% en rojo

3. **Chart 3 (Efficiency)**: Específico por posición
   - GK: Save Rate vs Goals Conceded
   - DEF: Defensive Actions vs Pass Accuracy
   - MID: Passes per 90 vs Through Passes
   - WING: Crosses vs xA
   - FWD: xG vs Goals (con línea de overperformance)

4. **Chart 4 (Heatmap)**: Matriz de rendimiento
   - Filas: Categorías (Attacking, Passing, Defending)
   - Columnas: Métricas específicas de posición
   - Colores: Percentil (0-100)

5. **Chart 5 (Timeline)**: Evolución multi-temporada
   - Métricas clave (Goals, Assists, Tackles según posición)
   - Línea de tendencia
   - Comparar con promedio de posición

**Criterios de aceptación:**
- [ ] Visualizaciones dinámicas según posición detectada
- [ ] Colores consistentes con tema HKFA (rojo #ED1C24)
- [ ] Responsive en móvil/tablet/desktop
- [ ] Carga < 2 segundos

---

#### **Tarea 1.2.2: Mejorar Team View**
**Archivo:** `layouts/performance_views/team_view.py`

**Nuevas secciones:**
1. **Squad Composition**: Distribución por posición con arquetipos
2. **Team Style Profile**: Radar de estilo táctico (posesión, presión, directo)
3. **Top Performers by Position**: Top 3 en cada posición
4. **Balance Analysis**: Ataque vs Defensa del equipo

---

#### **Tarea 1.2.3: Mejorar League View**
**Archivo:** `layouts/performance_views/league_view.py`

**Nuevas secciones:**
1. **Top 10 por posición**: Tablas separadas (Top GK, Top DEF, etc.)
2. **Comparativa de equipos por estilo**: Clustering visual
3. **Liga Insights**:
   - Equipo más ofensivo (Goals per 90)
   - Equipo más defensivo (Goals Conceded per 90)
   - Mejor ataque (xG total)
   - Mejor defensa (xGA total)

---

### **1.3 Mejoras de UI/UX**

#### **Tarea 1.3.1: Actualizar diseño visual**
**Archivo:** `assets/style.css`

**Cambios:**
1. **Paleta de colores extendida**:
   ```css
   --background-primary: #18181A
   --background-secondary: #232326
   --accent-primary: #ED1C24 (HKFA Red)
   --accent-gold: #FFB81C
   --accent-blue: #00A3E0
   --success: #10B981 (Verde para métricas positivas)
   --warning: #F59E0B (Naranja para métricas medias)
   --danger: #EF4444 (Rojo para métricas bajas)
   ```

2. **Tipografía mejorada**:
   - Headings: Montserrat Bold
   - Body: Inter Regular
   - Números: Roboto Mono (monospace para stats)

3. **Animaciones sutiles**:
   ```css
   .fadeIn { animation: fadeIn 0.5s ease-in; }
   .chart-container { transition: transform 0.3s ease; }
   .chart-container:hover { transform: scale(1.02); }
   ```

4. **Tarjetas de métricas (KPI Cards)**:
   - Bordes redondeados
   - Sombras sutiles
   - Iconos relevantes (⚽ Goals, 🎯 Assists, 🛡️ Tackles)

---

#### **Tarea 1.3.2: Mejorar filtros y controles**
**Archivo:** `layouts/performance_views/shared_components.py`

**Mejoras:**
1. **Selector de temporada con contexto**:
   ```
   [2024-25] (Actual) ▼
   ```

2. **Búsqueda de jugadores con autocompletado**:
   - Dropdown → Search bar con sugerencias
   - Mostrar equipo y posición en resultados

3. **Filtro de posición con iconos**:
   ```
   [🧤 GK] [🛡️ DEF] [⚙️ MID] [⚡ WING] [⚽ FWD] [Todos]
   ```

4. **Comparador de jugadores** (2-3 jugadores):
   - Selector múltiple
   - Radar comparativo side-by-side

---

### **1.4 Performance y Optimización**

#### **Tarea 1.4.1: Optimizar carga de datos**
**Archivo:** `data/hong_kong_data_manager.py`

**Optimizaciones:**
1. **Lazy loading de métricas**: Solo calcular métricas específicas cuando se selecciona esa vista
2. **Cache por posición**: Pre-calcular percentiles por posición al inicio
3. **Compresión de datos**: Usar dtypes eficientes (int8, float32 en lugar de int64, float64)

---

#### **Tarea 1.4.2: Implementar loading skeletons**
**Archivo:** `layouts/performance_views/shared_components.py`

**Añadir:**
```python
def create_skeleton_loader():
    return html.Div([
        html.Div(className='skeleton skeleton-title'),
        html.Div(className='skeleton skeleton-chart'),
    ])
```

Con CSS:
```css
.skeleton {
    background: linear-gradient(90deg, #232326 25%, #2A2A2D 50%, #232326 75%);
    background-size: 200% 100%;
    animation: loading 1.5s infinite;
}
```

---

### **1.5 Documentación Técnica**

#### **Tarea 1.5.1: Crear documentación de métricas**
**Archivo:** `docs/METRICAS.md`

**Contenido:**
- Listado completo de métricas (generales + por posición)
- Fórmulas matemáticas
- Benchmarks (malo/bueno/excelente)
- Fuente de datos (CSV directo vs calculado)
- Ejemplos de interpretación

---

#### **Tarea 1.5.2: Crear guía de estilo visual**
**Archivo:** `docs/DESIGN_SYSTEM.md`

**Contenido:**
- Paleta de colores con códigos HEX
- Tipografía y tamaños
- Espaciado y grid system
- Componentes reutilizables (KPI cards, charts)
- Ejemplos de uso

---

### **CHECKLIST FASE 1**

**Métricas:**
- [ ] Métricas generales implementadas
- [ ] Métricas específicas por posición (5 posiciones)
- [ ] Sistema de arquetipos (3 arquetipos MID, 3 DEF, 3 FWD)
- [ ] Benchmarks documentados
- [ ] Tests unitarios (>80% cobertura)

**Visualizaciones:**
- [ ] Player View rediseñado (5 charts dinámicos por posición)
- [ ] Team View mejorado (4 nuevas secciones)
- [ ] League View mejorado (tops por posición)
- [ ] Responsive (mobile/tablet/desktop)

**UI/UX:**
- [ ] Paleta de colores actualizada
- [ ] Tipografía mejorada
- [ ] Animaciones implementadas
- [ ] KPI Cards rediseñadas
- [ ] Filtros mejorados con iconos
- [ ] Comparador de jugadores (2-3)

**Performance:**
- [ ] Carga < 2s en todas las vistas
- [ ] Lazy loading implementado
- [ ] Cache optimizado
- [ ] Skeletons loaders añadidos

**Documentación:**
- [ ] docs/METRICAS.md completo
- [ ] docs/DESIGN_SYSTEM.md completo
- [ ] Comentarios en código (>70% funciones)

---

## 📸 FASE 2: GENERACIÓN DE CONTENIDO INSTAGRAM
**Prioridad:** ALTA
**Duración estimada:** 2-3 semanas
**Objetivo:** Automatizar creación de imágenes para redes sociales

### **2.1 Arquitectura de Generación**

#### **Tarea 2.1.1: Crear sistema de templates**
**Archivos a crear:**
- `content_generation/templates/base_template.py`
- `content_generation/templates/pre_match_template.py`
- `content_generation/templates/post_match_template.py`
- `content_generation/templates/monthly_summary_template.py`
- `content_generation/templates/league_insights_template.py`

**Tecnologías:**
- Pillow (PIL) para composición de imágenes
- Matplotlib/Plotly para gráficos → PNG
- Python-pptx (opcional) para templates más complejos

---

#### **Tarea 2.1.2: Sistema de detección de cambios (match by match)**
**Archivo:** `content_generation/match_detector.py`

**Funcionalidad:**
```python
class MatchDetector:
    def detect_new_matches(self, current_csv, previous_csv):
        """
        Compara CSV actual con anterior para detectar partidos nuevos

        Returns:
            {
                'match_date': '2024-11-13',
                'players_updated': [
                    {
                        'player': 'Juan Pérez',
                        'team': 'Kitchee',
                        'stats_delta': {
                            'goals': +1,
                            'assists': +0,
                            'shots': +4,
                            # ...
                        }
                    }
                ]
            }
        """
```

**Proceso:**
1. Guardar snapshot del CSV cada semana (antes de actualizar)
2. Al actualizar, comparar con snapshot anterior
3. Calcular delta (diferencia) por jugador
4. Inferir stats del partido: `stats_partido = csv_nuevo - csv_anterior`

**Edge Cases a manejar:**
- **Semanas sin actualizar**: Comparar con último snapshot válido
- **Múltiples jornadas en una semana**: Suma de deltas (no podemos separar)
- **Nuevo jugador**: Todas sus stats son del partido (o múltiples partidos)

---

### **2.2 Tipos de Contenido**

#### **Tarea 2.2.1: POST PRE-PARTIDO (Stories 1080x1920)**
**Archivo:** `content_generation/generators/pre_match_generator.py`

**Input requerido del jugador:**
```json
{
    "player_name": "Juan Pérez",
    "player_photo": "url_or_path",
    "match_date": "2024-11-15",
    "match_time": "20:00",
    "opponent": "Eastern FC",
    "venue": "Mong Kok Stadium",
    "tv_channel": "Now Sports"
}
```

**Output:** Imagen 1080x1920 con:
- Fondo: Color del equipo + logo HKPL
- Foto del jugador (recortada circular)
- Texto: Fecha, hora, rival, estadio, TV
- Stats previas del jugador (goles, asistencias de la temporada)

**Diseño:**
```
┌─────────────────────┐
│   [LOGO HKPL]      │
│                     │
│   [FOTO JUGADOR]   │  <- Circular, centrado
│                     │
│   JUAN PÉREZ        │
│   #10 - Midfielder  │
│                     │
│  🗓️ 15 NOV 20:00   │
│  🏟️ Mong Kok       │
│  📺 Now Sports     │
│  ⚽ vs Eastern FC   │
│                     │
│  ESTA TEMPORADA:    │
│  ⚽ 8 Goles         │
│  🎯 4 Asistencias  │
└─────────────────────┘
```

---

#### **Tarea 2.2.2: POST POST-PARTIDO (Carousel 1080x1080, 3-4 slides)**
**Archivo:** `content_generation/generators/post_match_generator.py`

**Input:** Delta de stats del partido (calculado por MatchDetector)

**Slide 1: Portada**
```
┌─────────────────────┐
│   [LOGO EQUIPO]    │
│                     │
│   RENDIMIENTO       │
│   DEL PARTIDO       │
│                     │
│   JUAN PÉREZ        │
│   vs Eastern FC     │
│   15/11/2024        │
└─────────────────────┘
```

**Slide 2: Stats del partido**
```
┌─────────────────────┐
│  ESTADÍSTICAS       │
│                     │
│  ⚽ Goles: 1        │
│  🎯 Asistencias: 0 │
│  🔫 Tiros: 4       │
│  🎯 A puerta: 2    │
│  ✅ Pases: 45/52   │
│  🛡️ Duelos: 8/12  │
│                     │
│  ⭐ Rating: 7.8/10 │
└─────────────────────┘
```

**Slide 3: Gráfica de rendimiento**
- Radar chart con métricas del partido
- Comparado con promedio de la temporada

**Slide 4: Acumulado de temporada**
```
┌─────────────────────┐
│  TEMPORADA 2024-25  │
│                     │
│  ⚽ 9 Goles (+1)    │
│  🎯 4 Asistencias  │
│  📊 Partidos: 12   │
│                     │
│  [MINI BAR CHART]   │  <- Evolución goles
└─────────────────────┘
```

---

#### **Tarea 2.2.3: RESUMEN MENSUAL (Carousel 1080x1080, 5 slides)**
**Archivo:** `content_generation/generators/monthly_generator.py`

**Contenido:**
- Slide 1: Portada ("Noviembre 2024")
- Slide 2: Top stats del mes (goles, asistencias, minutos)
- Slide 3: Radar chart de rendimiento mensual
- Slide 4: Comparación vs mes anterior
- Slide 5: Recomendaciones IA (Fase 3)

---

#### **Tarea 2.2.4: CONTENIDO LIGA (para cuenta general)**
**Archivo:** `content_generation/generators/league_insights_generator.py`

**Tipos:**
1. **Top 5 Semanal**: Goleadores, asistentes, MVP
2. **Comparativa de equipos**: Radar de 2-3 equipos
3. **Estadística curiosa**: "Sabías que..."
4. **Spotlight de jugador**: Destacar un jugador aleatorio

---

### **2.3 Automatización**

#### **Tarea 2.3.1: Sistema de triggers**
**Archivo:** `content_generation/scheduler.py`

**Opciones:**
1. **Manual**: Botón en dashboard "Generar contenido post-partido"
2. **Semi-automático**: Script Python ejecutado manualmente cada lunes
3. **Automático (futuro)**: Cron job semanal

**Proceso:**
```python
# Cada lunes a las 10:00
1. Comparar CSV actual con snapshot anterior
2. Detectar partidos nuevos (deltas)
3. Para cada jugador con delta > 0:
   - Generar post post-partido (carousel)
4. Guardar en carpeta generated_content/{player_name}/
5. Dashboard: "Tienes 15 posts listos para publicar"
```

---

#### **Tarea 2.3.2: Dashboard de gestión de contenido**
**Archivo:** `layouts/content_manager.py`

**Funcionalidades:**
1. **Ver contenido generado**: Galería de imágenes
2. **Selector**: Elegir cuál publicar
3. **Preview**: Ver imagen antes de publicar
4. **Editar texto**: Modificar caption si es necesario
5. **Descargar**: Botón para descargar PNG

**Futuro (Fase 2.5):**
- Integración con Instagram API para publicar directamente
- Calendario de publicaciones
- Analytics de engagement

---

### **2.4 Calidad de Imágenes**

#### **Tarea 2.4.1: Sistema de assets**
**Estructura de carpetas:**
```
content_generation/
├── assets/
│   ├── logos/
│   │   ├── hkpl_logo.png
│   │   ├── team_logos/
│   │   │   ├── kitchee.png
│   │   │   ├── eastern.png
│   │   │   └── ...
│   ├── fonts/
│   │   ├── Montserrat-Bold.ttf
│   │   ├── Inter-Regular.ttf
│   │   └── RobotoMono-Regular.ttf
│   ├── backgrounds/
│   │   ├── pre_match_bg.png
│   │   ├── post_match_bg.png
│   │   └── monthly_bg.png
│   └── player_photos/
│       └── {player_name}.png
```

**Tarea:**
- [ ] Descargar/crear logos de equipos
- [ ] Preparar backgrounds con colores HKFA
- [ ] Conseguir fotos de jugadores (o usar placeholders)

---

#### **Tarea 2.4.2: Optimización de calidad**
**Archivo:** `content_generation/image_optimizer.py`

**Funcionalidades:**
1. **Resize con alta calidad**: Usar LANCZOS resampling
2. **Compresión inteligente**: PNG optimizado (pngquant)
3. **Añadir watermark**: Logo pequeño en esquina
4. **Validación de tamaño**: Stories (1080x1920), Posts (1080x1080)

---

### **CHECKLIST FASE 2**

**Sistema:**
- [ ] MatchDetector implementado y testeado
- [ ] Comparación CSV funcionando
- [ ] Manejo de edge cases (semanas sin actualizar)

**Templates:**
- [ ] Pre-match template (Stories)
- [ ] Post-match template (Carousel 4 slides)
- [ ] Monthly summary template (Carousel 5 slides)
- [ ] League insights template (Posts variados)

**Assets:**
- [ ] Logos de equipos (12 equipos mínimo)
- [ ] Logo HKPL
- [ ] Fonts instaladas
- [ ] Backgrounds diseñados
- [ ] Placeholders de fotos

**Automatización:**
- [ ] Scheduler implementado (manual/semi-auto)
- [ ] Dashboard de gestión creado
- [ ] Preview de imágenes funcional
- [ ] Descarga masiva (ZIP)

**Calidad:**
- [ ] Imágenes en resolución correcta (1080x1920, 1080x1080)
- [ ] Textos legibles (tamaño mínimo 24px)
- [ ] Colores consistentes con HKFA
- [ ] Watermark añadido

**Documentación:**
- [ ] docs/CONTENIDO_INSTAGRAM.md
- [ ] Tutorial de uso del sistema
- [ ] Ejemplos de posts generados

---

## 🤖 FASE 3: INTEGRACIÓN DE INTELIGENCIA ARTIFICIAL
**Prioridad:** MEDIA (después de Fase 1 y 2)
**Duración estimada:** 4-5 semanas
**Objetivo:** Implementar ML/IA para análisis avanzado y cumplir requisitos académicos

### **3.1 Clustering y Arquetipos Tácticos**

#### **Tarea 3.1.1: Implementar K-Means Clustering**
**Archivo:** `ai_models/clustering/player_archetypes.py`

**Objetivo:** Agrupar jugadores por estilo de juego usando ML

**Features para clustering:**
```python
features = [
    'Passes per 90',           # Volumen de juego
    'Tackles per 90',          # Intensidad defensiva
    'xG per 90',               # Peligro ofensivo
    'Shots per 90',            # Agresividad atacante
    'Duels won %',             # Presencia física
    'Forward passes %',        # Estilo progresivo
    'Crosses per 90',          # Juego de banda
    'Through passes per 90',   # Creatividad
]
```

**Proceso:**
```python
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

# 1. Preparar datos
scaler = StandardScaler()
X = scaler.fit_transform(df[features])

# 2. Determinar número óptimo de clusters (Elbow method)
inertias = []
for k in range(2, 12):
    kmeans = KMeans(n_clusters=k, random_state=42)
    kmeans.fit(X)
    inertias.append(kmeans.inertia_)

# 3. Entrenar con k óptimo (ej: 8 arquetipos)
kmeans = KMeans(n_clusters=8, random_state=42, n_init=50)
df['cluster'] = kmeans.fit_predict(X)

# 4. Etiquetar arquetipos
archetype_labels = {
    0: "Deep-lying Playmaker",
    1: "Box-to-box Midfielder",
    2: "Ball-Winning Midfielder",
    3: "Attacking Midfielder",
    4: "Target Man",
    5: "Poacher",
    6: "Complete Forward",
    7: "Defensive Full-back"
}

# 5. Guardar modelo
import joblib
joblib.dump(kmeans, 'ai_models/clustering/trained_kmeans.pkl')
joblib.dump(scaler, 'ai_models/clustering/scaler.pkl')
```

**Interpretación de clusters:**
```python
def interpret_cluster(cluster_id, centroids, feature_names):
    """
    Analiza el centroide para entender el arquetipo

    Returns:
        {
            'label': 'Box-to-box Midfielder',
            'characteristics': [
                'Alto volumen de pases (>50/90)',
                'Balance ataque-defensa',
                'Presencia física alta'
            ],
            'example_players': ['Player A', 'Player B']
        }
    """
```

---

#### **Tarea 3.1.2: Visualización de clustering**
**Archivo:** `layouts/ai_insights/archetypes_view.py`

**Vista "Arquetipos Tácticos":**
1. **Scatter plot 2D** (PCA para reducir a 2 dimensiones):
   - Eje X: PC1 (probablemente ataque vs defensa)
   - Eje Y: PC2 (probablemente volumen vs intensidad)
   - Puntos coloreados por cluster
   - Etiquetas de nombre en hover

2. **Tarjetas de arquetipos**:
   ```
   ┌──────────────────────────────┐
   │ Box-to-box Midfielder        │
   │ 15 jugadores en la liga      │
   │                              │
   │ Características:             │
   │ • Pases: 52 ± 8 per 90      │
   │ • Tackles: 2.8 ± 0.5        │
   │ • xG: 0.15 ± 0.08           │
   │                              │
   │ Ejemplos: Juan Pérez, ...    │
   └──────────────────────────────┘
   ```

3. **Radar del centroide**: Perfil promedio del arquetipo

4. **Buscador**: "¿A qué arquetipo pertenezco?"
   - Input: Nombre del jugador
   - Output: Arquetipo + similitud % + jugadores parecidos

---

#### **Tarea 3.1.3: Documentación académica del clustering**
**Archivo:** `docs/ML_CLUSTERING.md`

**Contenido para la memoria:**
- Justificación de features seleccionadas
- Proceso de normalización (StandardScaler)
- Elbow method para selección de k
- Métricas de evaluación:
  - Silhouette Score
  - Davies-Bouldin Index
  - Inertia
- Interpretación de cada cluster
- Comparación con arquetipos tradicionales del fútbol
- Limitaciones del modelo

---

### **3.2 Sistema de Recomendación: Jugadores Similares**

#### **Tarea 3.2.1: Implementar K-Nearest Neighbors**
**Archivo:** `ai_models/recommendation/similar_players.py`

**Objetivo:** Encontrar los 5-10 jugadores más similares a uno dado

**Proceso:**
```python
from sklearn.neighbors import NearestNeighbors
from sklearn.metrics.pairwise import cosine_similarity

# Features para similitud
similarity_features = [
    'Goals', 'Assists', 'xG', 'xA',
    'Passes per 90', 'Accurate passes %',
    'Tackles per 90', 'Duels won %',
    'Shots per 90', 'Shots on target %'
]

# Opción 1: KNN con cosine similarity
knn = NearestNeighbors(n_neighbors=10, metric='cosine')
player_matrix = scaler.fit_transform(df[similarity_features])
knn.fit(player_matrix)

# Buscar similares a "Juan Pérez"
player_idx = df[df['Player'] == 'Juan Pérez'].index[0]
distances, indices = knn.kneighbors([player_matrix[player_idx]])

# Similares (excluyendo el mismo jugador)
similar_players = df.iloc[indices[0][1:]]
similar_players['similarity_score'] = 1 - distances[0][1:]  # 0-1 (1=idéntico)
```

**Filtros opcionales:**
```python
def find_similar_players(player_name, filters=None):
    """
    Args:
        player_name: Nombre del jugador
        filters: {
            'same_position': True,   # Solo misma posición
            'age_range': (25, 30),   # Rango de edad
            'min_matches': 10,       # Mínimo partidos jugados
            'local_only': False      # Solo jugadores locales
        }
    """
```

---

#### **Tarea 3.2.2: Explicabilidad del sistema**
**Archivo:** `ai_models/recommendation/explainer.py`

**Funcionalidad:**
```python
def explain_similarity(player_a, player_b):
    """
    Explica POR QUÉ dos jugadores son similares

    Returns:
        {
            'similarity_score': 0.89,
            'main_factors': [
                {
                    'metric': 'Goals per 90',
                    'player_a_value': 0.52,
                    'player_b_value': 0.48,
                    'difference': 8%,
                    'weight': 0.15  # Contribución a la similitud
                },
                # ... más métricas
            ],
            'summary': 'Ambos son delanteros goleadores con alto xG y bajo aporte defensivo'
        }
    """
```

---

#### **Tarea 3.2.3: Vista de jugadores similares**
**Archivo:** `layouts/ai_insights/similar_players_view.py`

**Integración en Player View:**
1. **Sección nueva**: "Jugadores Similares"
2. **Tarjetas comparativas**:
   ```
   ┌──────────────────────────────┐
   │ Pedro García                 │
   │ Eastern FC - Forward         │
   │ Similitud: 87%               │
   │                              │
   │ [MINI RADAR CHART]           │  <- Comparación visual
   │                              │
   │ Similar en:                  │
   │ ✅ Goals per 90 (±5%)       │
   │ ✅ xG (±8%)                 │
   │ ⚠️  Assists (-15%)          │
   └──────────────────────────────┘
   ```

3. **Radar comparativo**: Player actual vs jugador similar
4. **Tabla de diferencias**: Métrica por métrica

---

### **3.3 Identificación de Jugadores Infravalorados**

#### **Tarea 3.3.1: Modelo de regresión lineal**
**Archivo:** `ai_models/undervalued/undervalued_detector.py`

**Objetivo:** Detectar jugadores con alto rendimiento pero pocos minutos

**Proceso:**
```python
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor

# Features de rendimiento
X = df[['Goals', 'Assists', 'xG', 'xA', 'Tackles per 90', 'Duels won %']]
y = df['Minutes played']

# Entrenar modelo
model = LinearRegression()
model.fit(X, y)

# Predecir minutos esperados
df['expected_minutes'] = model.predict(X)

# Score de infravaloración
df['undervalued_score'] = df['expected_minutes'] - df['Minutes played']

# Top 10 infravalorados (deberían jugar más)
undervalued = df[df['undervalued_score'] > 500].sort_values('undervalued_score', ascending=False)
```

**Categorías:**
- `undervalued_score > 1000`: Muy infravalorado (debería jugar 11+ partidos más)
- `500-1000`: Infravalorado
- `-500 a 500`: Apropiadamente valorado
- `< -500`: Sobrevalorado (juega más de lo que rinde)

---

#### **Tarea 3.3.2: Vista "Hidden Gems"**
**Archivo:** `layouts/ai_insights/undervalued_view.py`

**Contenido:**
1. **Tabla de infravalorados**:
   | Jugador | Equipo | Posición | Minutos Jugados | Minutos Esperados | Score |
   |---------|--------|----------|-----------------|-------------------|-------|
   | Juan P. | Kitchee | MID     | 800             | 1500              | +700  |

2. **Scatter plot**:
   - Eje X: Rendimiento (Goals + Assists + Tackles normalizado)
   - Eje Y: Minutos jugados
   - Línea diagonal: Expectativa
   - Puntos por encima de la línea: Sobrevalorados
   - Puntos por debajo: Infravalorados

3. **Explicación por jugador**:
   ```
   Juan Pérez debería jugar 700 minutos más basándose en:
   - 8 goles (top 15% de MID)
   - 4 asistencias (top 20%)
   - 3.2 tackles/90 (top 25%)
   ```

---

### **3.4 Recomendador de Áreas de Mejora**

#### **Tarea 3.4.1: Sistema de análisis de gaps**
**Archivo:** `ai_models/improvement/recommendations_engine.py`

**Proceso:**
```python
def get_improvement_areas(player_name):
    """
    Compara jugador con promedio de su arquetipo/posición

    Returns:
        {
            'player': 'Juan Pérez',
            'archetype': 'Box-to-box Midfielder',
            'weaknesses': [
                {
                    'metric': 'Through passes per 90',
                    'player_value': 0.8,
                    'archetype_avg': 1.5,
                    'percentile': 25,  # Está en el 25% más bajo
                    'gap': -0.7,
                    'priority': 'HIGH',
                    'recommendation': 'Mejorar visión de juego y timing de pases verticales'
                },
                # ... más áreas
            ],
            'strengths': [...],
            'balanced': [...]
        }
    """
```

**Criterios de prioridad:**
- `percentile < 20`: HIGH (muy por debajo)
- `20-40`: MEDIUM
- `40-60`: LOW (casi en promedio)

**Mapeo de métricas a recomendaciones:**
```python
improvement_suggestions = {
    'Passes per 90': {
        'LOW': 'Buscar más el balón, exigir pases de compañeros',
        'MEDIUM': 'Aumentar movilidad sin balón para recibir'
    },
    'Tackles per 90': {
        'LOW': 'Mejorar timing de entradas, trabajar 1v1 defensivo',
        'MEDIUM': 'Incrementar intensidad en presión'
    },
    'Shots on target %': {
        'LOW': 'Practicar definición, mejorar técnica de tiro',
        'MEDIUM': 'Ser más selectivo con los tiros, mejor selección de momento'
    },
    # ... más métricas
}
```

---

#### **Tarea 3.4.2: Vista "Tu Hoja de Ruta"**
**Archivo:** `layouts/ai_insights/improvement_view.py`

**Integración en Player View:**
1. **Sección "Áreas de Mejora"** (3-5 tarjetas):
   ```
   ┌──────────────────────────────┐
   │ 🎯 Prioridad ALTA            │
   │                              │
   │ Through Passes per 90        │
   │ Tú: 0.8 | Promedio: 1.5     │
   │ Percentil: 25%               │
   │                              │
   │ 💡 Recomendación:            │
   │ Mejorar visión de juego y    │
   │ timing de pases verticales.  │
   │ Ejercicios: ...              │
   └──────────────────────────────┘
   ```

2. **Radar de comparación**:
   - Player actual (línea roja)
   - Promedio del arquetipo (línea verde)
   - Destacar gaps más grandes

3. **Seguimiento mensual** (timeline):
   - Mostrar evolución de la métrica mes a mes
   - "En octubre mejoró de 0.6 a 0.8 (+33%)"

---

### **3.5 Integración con Contenido Instagram (Fase 2 + 3)**

#### **Tarea 3.5.1: Posts con insights de IA**
**Archivo:** `content_generation/generators/ai_insights_posts.py`

**Nuevos tipos de posts:**
1. **"Tu Arquetipo"**:
   - Imagen con nombre del arquetipo
   - Características principales
   - Jugadores famosos del mismo arquetipo

2. **"Jugadores Similares"**:
   - Comparación visual (2 radars side-by-side)
   - "¿Sabías que juegas como Pedro García?"

3. **"Área de Mejora del Mes"**:
   - Destacar 1 métrica a mejorar
   - Gráfica de evolución mensual
   - Recomendación personalizada

4. **"Hidden Gem de la Semana"**:
   - Destacar un jugador infravalorado
   - Stats comparativas
   - "Debería jugar 800 minutos más"

---

### **3.6 Documentación Académica Completa**

#### **Tarea 3.6.1: Memoria técnica de ML**
**Archivo:** `docs/MEMORIA_TECNICA_ML.md`

**Estructura:**
1. **Introducción**:
   - Contexto del proyecto
   - Objetivos de IA
   - Fuentes de datos

2. **Metodología**:
   - Features seleccionadas y justificación
   - Preprocesamiento (normalización, manejo de NaN)
   - Algoritmos elegidos y por qué

3. **Modelos Implementados**:
   - **Clustering**: K-Means para arquetipos
     - Proceso de entrenamiento
     - Elbow method y selección de k
     - Métricas de evaluación (Silhouette, Davies-Bouldin)
     - Interpretación de clusters

   - **Recomendación**: KNN para jugadores similares
     - Selección de features
     - Métrica de distancia (cosine similarity)
     - Validación de resultados

   - **Regresión**: LinearRegression para infravalorados
     - Variables independientes y dependiente
     - Métricas de evaluación (R², RMSE, MAE)
     - Análisis de residuos

4. **Resultados**:
   - Arquetipos identificados (8 clusters)
   - Ejemplos de jugadores similares
   - Top 10 jugadores infravalorados

5. **Discusión**:
   - Limitaciones de los modelos
   - Datos por jornada vs totales de temporada
   - Futuras mejoras (Deep Learning, NLP)

6. **Conclusiones**:
   - Valor aportado por IA
   - Aplicabilidad en contexto real (SaaS)

---

#### **Tarea 3.6.2: Notebook Jupyter de análisis exploratorio**
**Archivo:** `notebooks/EDA_and_ML.ipynb`

**Contenido:**
1. **Carga y exploración de datos**:
   - Distribuciones de métricas
   - Correlaciones
   - Outliers

2. **Visualizaciones**:
   - Histogramas por posición
   - Scatter plots multivariados
   - Heatmap de correlación

3. **Entrenamiento de modelos** (paso a paso):
   - Código comentado
   - Gráficas de evaluación
   - Comparación de hiperparámetros

4. **Interpretación de resultados**:
   - Análisis de clusters
   - Ejemplos de recomendaciones
   - Casos de estudio (3-4 jugadores)

---

### **3.7 Testing y Validación de Modelos**

#### **Tarea 3.7.1: Tests unitarios de ML**
**Archivo:** `tests/test_ml_models.py`

**Tests:**
```python
def test_clustering_reproducibility():
    # Verificar que con mismo random_state produce mismo resultado

def test_knn_recommendations_valid():
    # Verificar que jugadores similares son de misma posición (o cercana)

def test_undervalued_logic():
    # Verificar que jugadores con alto rendimiento y pocos minutos tienen score alto

def test_improvement_areas_reasonable():
    # Verificar que las recomendaciones tienen sentido (ej: GK no debe mejorar en 'Goals')
```

---

#### **Tarea 3.7.2: Validación manual de resultados**
**Archivo:** `docs/VALIDACION_ML.md`

**Proceso:**
1. Revisar arquetipos manualmente:
   - ¿Tiene sentido que "Juan Pérez" sea "Box-to-box"?
   - Comparar con posición oficial

2. Verificar jugadores similares:
   - ¿Los 5 similares son realmente parecidos?
   - Pedir feedback a expertos en la liga

3. Validar infravalorados:
   - Cruzar con datos de alineaciones (si disponible)
   - ¿Hay razones no estadísticas? (lesiones, indisciplina)

---

### **CHECKLIST FASE 3**

**Modelos ML:**
- [ ] K-Means clustering implementado y entrenado
- [ ] 8 arquetipos identificados y etiquetados
- [ ] KNN para jugadores similares implementado
- [ ] Regresión lineal para infravalorados implementada
- [ ] Motor de recomendaciones de mejora creado

**Visualizaciones IA:**
- [ ] Vista "Arquetipos Tácticos" (scatter 2D + tarjetas)
- [ ] Vista "Jugadores Similares" (integrada en Player View)
- [ ] Vista "Hidden Gems" (tabla + scatter)
- [ ] Vista "Áreas de Mejora" (tarjetas + radar + timeline)

**Integración Instagram:**
- [ ] Post "Tu Arquetipo" template
- [ ] Post "Jugadores Similares" template
- [ ] Post "Área de Mejora del Mes" template
- [ ] Post "Hidden Gem Semanal" template

**Documentación Académica:**
- [ ] MEMORIA_TECNICA_ML.md completa (>15 páginas)
- [ ] Notebook EDA_and_ML.ipynb con análisis
- [ ] VALIDACION_ML.md con casos de estudio
- [ ] Bibliografía y referencias

**Testing:**
- [ ] Tests unitarios de modelos ML
- [ ] Validación manual de 10+ jugadores
- [ ] Métricas de evaluación documentadas:
  - Silhouette Score > 0.3
  - R² de regresión > 0.6
  - Precisión de KNN > 75% (validación experta)

**Modelos guardados:**
- [ ] trained_kmeans.pkl
- [ ] scaler.pkl
- [ ] knn_model.pkl
- [ ] linear_regression_undervalued.pkl

---

## 📅 CRONOGRAMA ESTIMADO

### **Fase 1: UI/UX y Métricas** (3-4 semanas)
- Semana 1: Métricas generales + por posición
- Semana 2: Rediseño de vistas (Player, Team, League)
- Semana 3: Mejoras UI/UX (colores, filtros, animaciones)
- Semana 4: Testing, optimización, documentación

### **Fase 2: Contenido Instagram** (2-3 semanas)
- Semana 1: Sistema de detección de partidos + templates base
- Semana 2: Generadores de contenido (pre-match, post-match, monthly)
- Semana 3: Dashboard de gestión + assets + testing

### **Fase 3: Inteligencia Artificial** (4-5 semanas)
- Semana 1: Clustering (K-Means) + visualización
- Semana 2: KNN jugadores similares + explicabilidad
- Semana 3: Regresión infravalorados + recomendaciones de mejora
- Semana 4: Integración con Instagram + posts IA
- Semana 5: Documentación académica completa + notebook

**TOTAL: 9-12 semanas (2.5-3 meses)**

---

## 🎯 CRITERIOS DE ÉXITO

### **Fase 1 (UI/UX):**
✅ App carga en < 2 segundos
✅ Visualizaciones responsive (mobile/tablet/desktop)
✅ 100% de métricas prioritarias (⭐⭐⭐) implementadas
✅ Documentación completa de métricas
✅ Tests unitarios >80% cobertura

### **Fase 2 (Instagram):**
✅ Generación automática de 4 tipos de posts
✅ Calidad de imagen profesional (1080x1920, 1080x1080)
✅ Dashboard de gestión funcional
✅ Manejo de edge cases (semanas sin actualizar)
✅ 20+ posts de ejemplo generados

### **Fase 3 (IA):**
✅ 3 modelos ML entrenados y validados
✅ Silhouette Score > 0.3 (clustering)
✅ R² > 0.6 (regresión)
✅ Memoria técnica >15 páginas
✅ Notebook Jupyter completo
✅ Validación manual por expertos

---

## 🚀 PRÓXIMOS PASOS INMEDIATOS

### **Semana 1 (Inicio de Fase 1):**
1. **Día 1-2**: Crear estructura de carpetas nuevas (`metrics/`, `docs/`)
2. **Día 3-4**: Implementar métricas calculadas generales
3. **Día 5**: Crear `goalkeeper_metrics.py` con métricas específicas de GK
4. **Día 6-7**: Testing de métricas + documentación inicial

### **Para empezar YA:**
```bash
# Crear estructura de carpetas
mkdir -p metrics/{position_specific}
mkdir -p ai_models/{clustering,recommendation,undervalued,improvement}
mkdir -p content_generation/{templates,generators,assets/{logos,fonts,backgrounds}}
mkdir -p docs
mkdir -p notebooks

# Crear archivos base
touch metrics/advanced_metrics.py
touch metrics/position_specific/goalkeeper_metrics.py
touch docs/METRICAS.md
touch docs/DESIGN_SYSTEM.md
```

---

## 📚 RECURSOS Y REFERENCIAS

### **Librerías a instalar:**
```bash
# Para Fase 3 (ML)
pip install scikit-learn==1.3.0
pip install joblib
pip install jupyter
pip install seaborn  # Para visualizaciones en notebook

# Para Fase 2 (Imágenes)
pip install Pillow
pip install python-pptx  # Opcional
```

### **Referencias académicas para la memoria:**
- Scikit-learn documentation: https://scikit-learn.org/stable/
- "A Survey on Player Performance Analysis in Soccer" (2021)
- "Machine Learning Applications in Football: A Review" (2022)
- xG methodology: https://fbref.com/en/expected-goals-model-explained/

### **Recursos de diseño:**
- Coolors (paletas): https://coolors.co/
- Canva (inspiración para posts Instagram)
- Figma (mockups de UI)

---

## 📞 CONTACTO Y SOPORTE

**Desarrollador:** josangl08
**Repositorio:** https://github.com/josangl08/HK-PREMIER-LEAGUE-Stats
**Documentación:** Ver carpeta `docs/`

---

**ÚLTIMA ACTUALIZACIÓN:** 14 de noviembre de 2025
**VERSIÓN DEL PLAN:** 1.0
**ESTADO:** ✅ Aprobado para implementación
