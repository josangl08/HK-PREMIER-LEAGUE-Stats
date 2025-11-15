# 📊 ANÁLISIS EXHAUSTIVO DE COLUMNAS CSV

**Fecha:** 14 de noviembre de 2025
**Objetivo:** Identificar diferencias entre temporadas y decidir qué columnas usar

---

## 📋 RESUMEN

### **Temporadas 2018-19 a 2022-23** (Primeras 5 temporadas)
- **Total columnas:** 127 columnas

### **Temporadas 2023-24 a 2025-26** (Últimas 3 temporadas)
- **Total columnas:** 136 columnas

---

## 🔍 DIFERENCIAS ENTRE CONJUNTOS DE DATOS

### ❌ **COLUMNAS SOLO EN TEMPORADAS ANTIGUAS (2018-23)** - 9 columnas

Estas columnas **desaparecieron** en las temporadas recientes:

1. **`Full name`** - Nombre completo del jugador
2. **`Wyscout id`** - ID único de Wyscout
3. **`Team logo`** - URL del logo del equipo
4. **`Competition`** - Nombre de la competición
5. **`Primary position, %`** - Porcentaje de partidos en posición primaria
6. **`Secondary position, %`** - Porcentaje de partidos en posición secundaria
7. **`Third position, %`** - Porcentaje de partidos en posición terciaria
8. **`Birthday`** - Fecha de nacimiento completa
9. **`Vertical passes per 90`** - Pases verticales por 90 minutos
10. **`Accurate vertical passes, %`** - Precisión de pases verticales

---

### ✅ **COLUMNAS SOLO EN TEMPORADAS RECIENTES (2023-26)** - 18 columnas

Estas columnas **nuevas** aparecen solo en las últimas 3 temporadas:

#### **A) Datos de Pases Laterales (2 columnas)**
11. **`Lateral passes per 90`** - Pases laterales por 90 minutos
12. **`Accurate lateral passes, %`** - Precisión de pases laterales

#### **B) Datos Físicos / GPS (16 columnas)** ⭐ **MUY VALIOSAS**
13. **`Total Distance per 90`** - Distancia total recorrida por 90 min
14. **`Running Distance per 90 (15-20 km/h)`** - Distancia corriendo (velocidad media)
15. **`HSR Distance per 90 (20-25 km/h)`** - High Speed Running (carrera rápida)
16. **`Sprinting Distance per 90 (+25 km/h)`** - Distancia en sprint (velocidad alta)
17. **`HI Distance per 90 (+20 km/h)`** - High Intensity (alta intensidad total)
18. **`Meter/Min`** - Metros por minuto (intensidad promedio)
19. **`Max Speed (km/h)`** - Velocidad máxima alcanzada
20. **`Count Medium Acceleration per 90 (1.5 m/s² to 3 m/s²)`** - Aceleraciones medias
21. **`Count High Acceleration per 90 (+3 m/s²)`** - Aceleraciones altas
22. **`Count Medium Deceleration per 90 (-1.5 m/s² to -3 m/s²)`** - Desaceleraciones medias
23. **`Count High Deceleration per 90 (-3 m/s²)`** - Desaceleraciones altas
24. **`Count HSR per 90 (20-25 km/h)`** - Cuenta de carreras rápidas
25. **`Count Sprint per 90 (+25 km/h)`** - Cuenta de sprints
26. **`Count HI per 90 (+20 km/h)`** - Cuenta de acciones alta intensidad

---

## 📊 COLUMNAS COMUNES (109 columnas)

Estas columnas están en **AMBOS** conjuntos de datos:

### **Identificación del Jugador (6)**
- Player
- Team
- Team within selected timeframe
- Position
- Age
- Birth country
- Passport country

### **Información Personal (5)**
- Foot
- Height
- Weight
- Market value
- Contract expires
- On loan

### **Minutos y Partidos (2)**
- Matches played
- Minutes played

### **Goles y Asistencias (6)**
- Goals
- xG
- Assists
- xA
- Non-penalty goals
- Head goals

### **Tiros (6)**
- Shots
- Shots per 90
- Shots on target, %
- Goal conversion, %
- Goals per 90
- Non-penalty goals per 90
- xG per 90
- Head goals per 90

### **Duelos (7)**
- Duels per 90
- Duels won, %
- Offensive duels per 90
- Offensive duels won, %
- Defensive duels per 90
- Defensive duels won, %
- Aerial duels per 90
- Aerial duels won, %
- Aerial duels per 90.1 (duplicado?)

### **Defensa (8)**
- Successful defensive actions per 90
- Sliding tackles per 90
- PAdj Sliding tackles
- Shots blocked per 90
- Interceptions per 90
- PAdj Interceptions

### **Pases Generales (8)**
- Passes per 90
- Accurate passes, %
- Forward passes per 90
- Accurate forward passes, %
- Back passes per 90
- Accurate back passes, %
- Short / medium passes per 90
- Accurate short / medium passes, %
- Long passes per 90
- Accurate long passes, %
- Average pass length, m
- Average long pass length, m

### **Pases Avanzados (14)**
- xA per 90
- Shot assists per 90
- Second assists per 90
- Third assists per 90
- Smart passes per 90
- Accurate smart passes, %
- Key passes per 90
- Passes to final third per 90
- Accurate passes to final third, %
- Passes to penalty area per 90
- Accurate passes to penalty area, %
- Through passes per 90
- Accurate through passes, %
- Progressive passes per 90
- Accurate progressive passes, %

### **Centros (7)**
- Crosses per 90
- Accurate crosses, %
- Crosses from left flank per 90
- Accurate crosses from left flank, %
- Crosses from right flank per 90
- Accurate crosses from right flank, %
- Crosses to goalie box per 90
- Deep completed crosses per 90

### **Regates y Movilidad (6)**
- Dribbles per 90
- Successful dribbles, %
- Touches in box per 90
- Progressive runs per 90
- Accelerations per 90

### **Recepción de Pases (3)**
- Received passes per 90
- Received long passes per 90

### **Faltas y Tarjetas (7)**
- Fouls per 90
- Fouls suffered per 90
- Yellow cards
- Yellow cards per 90
- Red cards
- Red cards per 90

### **Portero Específico (11)**
- Conceded goals
- Conceded goals per 90
- Shots against
- Shots against per 90
- Clean sheets
- Save rate, %
- xG against
- xG against per 90
- Prevented goals
- Prevented goals per 90
- Back passes received as GK per 90
- Exits per 90

### **Set Pieces (5)**
- Free kicks per 90
- Direct free kicks per 90
- Direct free kicks on target, %
- Corners per 90
- Penalties taken
- Penalty conversion, %

### **Otros (4)**
- Successful attacking actions per 90
- Deep completions per 90

---

## 🎯 DECISIONES Y RECOMENDACIONES

### ✅ **COLUMNAS A MANTENER** (Esenciales)

#### **1. Identificación (OBLIGATORIAS)**
- ✅ `Player`
- ✅ `Team`
- ✅ `Position`
- ✅ `Age`

#### **2. Minutos y Disponibilidad**
- ✅ `Matches played`
- ✅ `Minutes played`
- ⚠️ `On loan` - Útil para contexto, pero secundario

#### **3. Goles y Asistencias (CORE)**
- ✅ `Goals`
- ✅ `xG`
- ✅ `Assists`
- ✅ `xA`
- ✅ `Non-penalty goals` - Importante para analizar penalties
- ⚠️ `Head goals` - Interesante para delanteros altos

#### **4. Tiros (CORE)**
- ✅ `Shots`
- ✅ `Shots per 90`
- ✅ `Shots on target, %`
- ✅ `Goal conversion, %`

#### **5. Pases (CORE)**
- ✅ `Passes per 90`
- ✅ `Accurate passes, %`
- ✅ `Forward passes per 90`
- ✅ `Accurate forward passes, %`
- ✅ `Long passes per 90`
- ✅ `Through passes per 90`
- ✅ `Progressive passes per 90`
- ✅ `Key passes per 90`
- ⚠️ `Back passes per 90` - Útil para detectar estilo conservador
- ⚠️ `Lateral passes per 90` - Solo en temporadas recientes

#### **6. Defensa (CORE)**
- ✅ `Tackles per 90` - NO APARECE COMO TAL, usar `Sliding tackles per 90`?
- ✅ `Interceptions per 90`
- ✅ `Defensive duels won, %`
- ✅ `Aerial duels won, %`
- ✅ `Successful defensive actions per 90`

#### **7. Regates y 1v1**
- ✅ `Dribbles per 90`
- ✅ `Successful dribbles, %`
- ✅ `Offensive duels won, %`
- ✅ `Duels won, %`

#### **8. Centros (para Wingers)**
- ✅ `Crosses per 90`
- ✅ `Accurate crosses, %`

#### **9. Portero Específico**
- ✅ `Save rate, %`
- ✅ `Clean sheets`
- ✅ `Conceded goals`
- ✅ `Conceded goals per 90`
- ✅ `Prevented goals per 90` - Muy valioso (save vs xG)

#### **10. Físico (SOLO TEMPORADAS RECIENTES)** ⭐ **AÑADIR**
- ✅ `Total Distance per 90` - Trabajo físico total
- ✅ `HSR Distance per 90 (20-25 km/h)` - Intensidad alta
- ✅ `Sprinting Distance per 90 (+25 km/h)` - Velocidad máxima
- ✅ `Max Speed (km/h)` - Pico de velocidad
- ✅ `Count Sprint per 90 (+25 km/h)` - Frecuencia de sprints
- ⚠️ `Meter/Min` - Promedio de intensidad
- ⚠️ Aceleraciones/Desaceleraciones - Útiles pero secundarias

---

### ❌ **COLUMNAS A DESCARTAR** (No esenciales o redundantes)

#### **1. Metadata de Wyscout (no útil para usuario final)**
- ❌ `Wyscout id`
- ❌ `Team logo` - Podemos obtenerlo de otra forma
- ❌ `Competition` - Siempre es Hong Kong Premier League
- ❌ `Full name` - `Player` es suficiente

#### **2. Información Personal Detallada (privacidad/irrelevante)**
- ❌ `Birthday` - `Age` es suficiente
- ⚠️ `Birth country` - Podría ser útil para distinguir local/extranjero
- ⚠️ `Passport country` - Redundante con Birth country
- ❌ `Height` - Útil solo para análisis muy específicos (ej: duelos aéreos)
- ❌ `Weight` - Poco relevante sin contexto físico completo
- ⚠️ `Foot` - Interesante para análisis de estilo, pero secundario

#### **3. Posiciones con Porcentajes (ya no disponible)**
- ❌ `Primary position, %`
- ❌ `Secondary position, %`
- ❌ `Third position, %`

#### **4. Métricas Redundantes o Demasiado Granulares**
- ❌ `Crosses from left flank per 90` - Demasiado específico
- ❌ `Accurate crosses from left flank, %` - Demasiado específico
- ❌ `Crosses from right flank per 90` - Demasiado específico
- ❌ `Accurate crosses from right flank, %` - Demasiado específico
- ❌ `Crosses to goalie box per 90` - `Crosses per 90` es suficiente
- ❌ `Short / medium passes per 90` - Redundante con `Passes per 90`
- ❌ `Accurate short / medium passes, %` - `Accurate passes, %` es suficiente
- ❌ `Average pass length, m` - Interesante pero no crítico
- ❌ `Average long pass length, m` - Demasiado específico

#### **5. Pases Verticales (solo en temporadas antiguas)**
- ⚠️ `Vertical passes per 90` - Útil, pero ya no disponible
- ⚠️ `Accurate vertical passes, %` - Ya no disponible

#### **6. Asistencias de 2º y 3º nivel (poco relevantes)**
- ❌ `Second assists per 90` - Demasiado indirecto
- ❌ `Third assists per 90` - Demasiado indirecto

#### **7. Métricas de Pases Avanzadas (redundantes)**
- ⚠️ `Smart passes per 90` - Solapamiento con Key passes
- ❌ `Accurate smart passes, %` - Redundante
- ⚠️ `Shot assists per 90` - Similar a xA
- ❌ `Deep completions per 90` - Poco claro
- ❌ `Deep completed crosses per 90` - Redundante con Crosses

#### **8. PAdj Metrics (ajustadas por presión - útiles pero complejas)**
- ⚠️ `PAdj Sliding tackles` - Útil para análisis avanzado
- ⚠️ `PAdj Interceptions` - Útil para análisis avanzado

#### **9. Métricas Físicas Secundarias (solo si tenemos espacio)**
- ⚠️ `Running Distance per 90 (15-20 km/h)` - Secundaria
- ⚠️ `HI Distance per 90 (+20 km/h)` - Redundante con HSR + Sprint
- ⚠️ `Count Medium Acceleration per 90` - Demasiado granular
- ⚠️ `Count High Acceleration per 90` - Secundaria
- ⚠️ `Count Medium Deceleration per 90` - Demasiado granular
- ⚠️ `Count High Deceleration per 90` - Secundaria
- ⚠️ `Count HSR per 90` - Redundante con HSR Distance
- ⚠️ `Count HI per 90` - Redundante

#### **10. Otras**
- ❌ `Aerial duels per 90.1` - Duplicado de `Aerial duels per 90`
- ❌ `Market value` - Puede cambiar, no es métrica de rendimiento
- ❌ `Contract expires` - Administrativo, no rendimiento
- ⚠️ `Received passes per 90` - Interesante para medir participación
- ⚠️ `Received long passes per 90` - Secundaria
- ⚠️ `Fouls suffered per 90` - Indica regates con contacto
- ⚠️ `Touches in box per 90` - Útil para delanteros

---

## 🎯 LISTADO FINAL PROPUESTO (60-70 COLUMNAS CORE)

### **CATEGORÍA A: OBLIGATORIAS** (4 columnas)
1. Player
2. Team
3. Position
4. Age

### **CATEGORÍA B: TIEMPO DE JUEGO** (2 columnas)
5. Matches played
6. Minutes played

### **CATEGORÍA C: GOLES** (5 columnas)
7. Goals
8. xG
9. Non-penalty goals
10. Goals per 90
11. xG per 90

### **CATEGORÍA D: ASISTENCIAS** (4 columnas)
12. Assists
13. xA
14. Assists per 90
15. xA per 90

### **CATEGORÍA E: TIROS** (5 columnas)
16. Shots
17. Shots per 90
18. Shots on target, %
19. Goal conversion, %
20. Head goals (opcional)

### **CATEGORÍA F: PASES GENERALES** (6 columnas)
21. Passes per 90
22. Accurate passes, %
23. Forward passes per 90
24. Accurate forward passes, %
25. Back passes per 90 (opcional)
26. Accurate back passes, % (opcional)

### **CATEGORÍA G: PASES AVANZADOS** (6 columnas)
27. Long passes per 90
28. Accurate long passes, %
29. Through passes per 90
30. Accurate through passes, %
31. Progressive passes per 90
32. Accurate progressive passes, %

### **CATEGORÍA H: CREACIÓN** (3 columnas)
33. Key passes per 90
34. Passes to final third per 90
35. Passes to penalty area per 90

### **CATEGORÍA I: CENTROS** (2 columnas)
36. Crosses per 90
37. Accurate crosses, %

### **CATEGORÍA J: REGATES Y DUELOS** (6 columnas)
38. Dribbles per 90
39. Successful dribbles, %
40. Duels won, %
41. Offensive duels won, %
42. Defensive duels won, %
43. Aerial duels won, %

### **CATEGORÍA K: DEFENSA** (5 columnas)
44. Successful defensive actions per 90
45. Sliding tackles per 90
46. Interceptions per 90
47. Shots blocked per 90
48. Aerial duels per 90

### **CATEGORÍA L: DISCIPLINA** (4 columnas)
49. Fouls per 90
50. Yellow cards
51. Yellow cards per 90
52. Red cards

### **CATEGORÍA M: PORTERO** (8 columnas)
53. Save rate, %
54. Clean sheets
55. Conceded goals
56. Conceded goals per 90
57. Shots against per 90
58. xG against per 90
59. Prevented goals per 90
60. Exits per 90

### **CATEGORÍA N: SET PIECES** (4 columnas)
61. Free kicks per 90
62. Direct free kicks on target, %
63. Corners per 90
64. Penalties taken
65. Penalty conversion, %

### **CATEGORÍA O: FÍSICO (SOLO TEMPORADAS RECIENTES)** (5 columnas)
66. Total Distance per 90
67. HSR Distance per 90 (20-25 km/h)
68. Sprinting Distance per 90 (+25 km/h)
69. Max Speed (km/h)
70. Count Sprint per 90

### **CATEGORÍA P: CONTEXTO** (3 columnas - opcional)
71. Birth country (para distinguir local/extranjero)
72. Touches in box per 90
73. Progressive runs per 90

---

## ⚠️ PROBLEMAS DETECTADOS

### **1. INCONSISTENCIA ENTRE TEMPORADAS**
- Las temporadas 2023-26 tienen **16 métricas físicas nuevas**
- Esto crea un problema: jugadores de temporadas antiguas no tendrán estos datos
- **Solución:**
  - Marcar estas columnas como `NULL` para temporadas 2018-23
  - Solo mostrar gráficas físicas para jugadores de 2023+
  - En comparativas multi-temporada, excluir métricas físicas

### **2. COLUMNAS DUPLICADAS**
- `Aerial duels per 90` aparece 2 veces (`Aerial duels per 90.1`)
- **Solución:** Eliminar el duplicado en procesamiento

### **3. MÉTRICAS QUE DESAPARECEN**
- `Vertical passes per 90` estaba en 2018-23 pero ya no en 2023-26
- **Solución:** No usar esta métrica en análisis generales

### **4. FALTA "TACKLES PER 90"**
- No hay una columna simple "Tackles per 90"
- Solo existe `Sliding tackles per 90`
- **Solución:** Usar `Sliding tackles per 90` como proxy de tackles totales

---

## 📋 SIGUIENTES PASOS

1. **Actualizar `hong_kong_processor.py`:**
   - Validar que todas las columnas del listado final existan
   - Manejar columnas faltantes (especialmente físicas en temporadas antiguas)
   - Eliminar duplicados (`Aerial duels per 90.1`)

2. **Crear archivo de mapeo:**
   - Mapear columnas antiguas a nuevas (si hay renombramientos)
   - Documentar qué columnas están disponibles por temporada

3. **Actualizar documentación:**
   - Documentar en `docs/METRICAS.md` qué métricas están disponibles
   - Indicar qué temporadas tienen datos físicos

4. **Ajustar visualizaciones:**
   - Solo mostrar métricas físicas si el jugador tiene datos (temporada 2023+)
   - Añadir disclaimer: "Datos físicos disponibles desde 2023-24"

---

## 🎯 RESUMEN EJECUTIVO

### **Columnas a mantener:** ~70 columnas
### **Columnas a descartar:** ~57 columnas
### **Nuevas métricas físicas (2023+):** 16 columnas

### **Distribución por categoría:**
- Identificación: 4
- Goles/Asistencias: 9
- Tiros: 5
- Pases: 17
- Duelos/Regates: 6
- Defensa: 5
- Portero: 8
- Set Pieces: 5
- Físico: 5 (solo 2023+)
- Contexto: 3

**Total Core:** ~67 columnas + físicas opcionales
