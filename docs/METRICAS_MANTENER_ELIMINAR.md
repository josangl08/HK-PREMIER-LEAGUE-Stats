# 📊 MÉTRICAS FINALES: MANTENER vs ELIMINAR

**Fecha:** 14 de noviembre de 2025
**Decisiones del usuario aplicadas:**
- ✅ Opción B: TODAS las 16 métricas físicas
- ✅ Info personal: Birth country, Passport country, Foot, Height, Weight (❌ Market value)
- ✅ Pases laterales mantenidos
- ✅ PAdj metrics mantenidas (análisis ajustado por presión)
- ✅ Todas las métricas de recepción mantenidas

---

## ✅ MÉTRICAS A MANTENER (98 columnas totales)

### **CATEGORÍA 1: IDENTIFICACIÓN DEL JUGADOR** (4 columnas)
**Todas las posiciones**

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `Player` | Texto | Nombre del jugador |
| `Team` | Texto | Equipo actual |
| `Position` | Texto | Posición principal |
| `Age` | Numérico | Edad del jugador |

**Uso por posición:** GK, DEF, MID, WING, FWD (todas)

---

### **CATEGORÍA 2: INFORMACIÓN PERSONAL** (5 columnas)
**Todas las posiciones**

| Columna | Tipo | Descripción | Uso |
|---------|------|-------------|-----|
| `Birth country` | Texto | País de nacimiento | Distinguir local vs extranjero |
| `Passport country` | Texto | País del pasaporte | Contexto nacionalidad |
| `Foot` | Texto | Pie dominante (Left/Right/Both) | Análisis de estilo |
| `Height` | Numérico | Altura en cm | Correlación duelos aéreos |
| `Weight` | Numérico | Peso en kg | Contexto físico |

**Uso por posición:**
- GK: Todas (especialmente Height para alcance)
- DEF: Todas (Height para duelos aéreos)
- MID: Todas (contexto general)
- WING: Todas (Foot especialmente importante)
- FWD: Todas (Height para Target Man, Foot para finalizadores)

---

### **CATEGORÍA 3: TIEMPO DE JUEGO** (2 columnas)
**Todas las posiciones**

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `Matches played` | Numérico | Partidos jugados |
| `Minutes played` | Numérico | Minutos totales |

**Uso por posición:** GK, DEF, MID, WING, FWD (todas)

---

### **CATEGORÍA 4: GOLES** (8 columnas)
**Principalmente: FWD, WING, MID | Secundario: DEF**

| Columna | Tipo | Posiciones Principales | Posiciones Secundarias |
|---------|------|----------------------|----------------------|
| `Goals` | Numérico | FWD, WING, MID | DEF (balón parado) |
| `Goals per 90` | Numérico | FWD, WING, MID | DEF |
| `xG` | Numérico | FWD, WING, MID | - |
| `xG per 90` | Numérico | FWD, WING, MID | - |
| `Non-penalty goals` | Numérico | FWD, WING, MID | - |
| `Non-penalty goals per 90` | Numérico | FWD, WING, MID | - |
| `Head goals` | Numérico | FWD (Target Man), DEF | - |
| `Head goals per 90` | Numérico | FWD, DEF | - |

**Justificación:**
- **FWD:** Todas las métricas de goles son críticas (⭐⭐⭐)
- **WING:** Goles cada vez más importantes en wingers modernos (⭐⭐⭐)
- **MID:** Especialmente AM, goles de segunda línea (⭐⭐)
- **DEF:** Goles de balón parado, Head goals relevante (⭐)
- **GK:** No aplica

---

### **CATEGORÍA 5: ASISTENCIAS** (4 columnas)
**Principalmente: WING, MID | Secundario: FWD, DEF**

| Columna | Tipo | Posiciones Principales | Posiciones Secundarias |
|---------|------|----------------------|----------------------|
| `Assists` | Numérico | WING, MID | FWD |
| `Assists per 90` | Numérico | WING, MID | FWD |
| `xA` | Numérico | WING, MID | - |
| `xA per 90` | Numérico | WING, MID | - |

**Justificación:**
- **WING:** Creación principal, centros al área (⭐⭐⭐)
- **MID:** Pases clave, through balls (⭐⭐⭐)
- **FWD:** Jugadores asociativos, Complete Forward (⭐⭐)
- **DEF:** Pases largos a delanteros (⭐)
- **GK:** No aplica

---

### **CATEGORÍA 6: TIROS** (6 columnas)
**Principalmente: FWD, WING | Secundario: MID**

| Columna | Tipo | Posiciones Principales | Posiciones Secundarias |
|---------|------|----------------------|----------------------|
| `Shots` | Numérico | FWD, WING | MID (AM) |
| `Shots per 90` | Numérico | FWD, WING | MID (AM) |
| `Shots on target, %` | Porcentaje | FWD, WING | MID |
| `Goal conversion, %` | Porcentaje | FWD, WING | MID |

**Justificación:**
- **FWD:** Esencial para medir eficiencia de definición (⭐⭐⭐)
- **WING:** Cada vez más rematadores desde banda (⭐⭐⭐)
- **MID:** AM con llegada al área (⭐⭐)
- **DEF, GK:** No relevante

---

### **CATEGORÍA 7: DUELOS GENERALES** (8 columnas)
**Todas las posiciones**

| Columna | Tipo | Posiciones Críticas | Posiciones Secundarias |
|---------|------|-------------------|----------------------|
| `Duels per 90` | Numérico | DEF, MID, WING | FWD |
| `Duels won, %` | Porcentaje | Todas | - |
| `Offensive duels per 90` | Numérico | FWD, WING | MID |
| `Offensive duels won, %` | Porcentaje | FWD, WING | MID |
| `Defensive duels per 90` | Numérico | DEF, MID | - |
| `Defensive duels won, %` | Porcentaje | DEF, MID | - |
| `Aerial duels per 90` | Numérico | DEF, FWD (Target Man) | - |
| `Aerial duels won, %` | Porcentaje | DEF, FWD | - |

**Justificación:**
- **DEF:** Duelos defensivos y aéreos críticos (⭐⭐⭐)
- **FWD:** Duelos ofensivos, Target Man para aéreos (⭐⭐⭐)
- **WING:** Duelos 1v1 para regates (⭐⭐⭐)
- **MID:** Balance ofensivo-defensivo (⭐⭐)
- **GK:** Solo duelos aéreos en saques de esquina

---

### **CATEGORÍA 8: DEFENSA** (7 columnas)
**Principalmente: DEF, MID (DM) | Secundario: WING**

| Columna | Tipo | Posiciones Principales | Posiciones Secundarias |
|---------|------|----------------------|----------------------|
| `Successful defensive actions per 90` | Numérico | DEF, MID (DM) | WING |
| `Sliding tackles per 90` | Numérico | DEF, MID (DM) | - |
| `PAdj Sliding tackles` | Ajustado | DEF, MID (DM) | - |
| `Interceptions per 90` | Numérico | DEF, MID (DM) | - |
| `PAdj Interceptions` | Ajustado | DEF, MID (DM) | - |
| `Shots blocked per 90` | Numérico | DEF | - |

**Justificación:**
- **DEF:** Todas las métricas defensivas son core (⭐⭐⭐)
- **MID (DM):** Tackles e interceptions críticas (⭐⭐⭐)
- **MID (CM):** Interceptions moderadas (⭐⭐)
- **WING:** Algunas acciones defensivas al replegarse (⭐)
- **FWD, GK:** No relevante

**Nota sobre PAdj:** Métricas ajustadas por presión del rival, útil para comparar en diferentes contextos tácticos

---

### **CATEGORÍA 9: REGATES Y MOVILIDAD** (5 columnas)
**Principalmente: WING, MID (AM) | Secundario: FWD**

| Columna | Tipo | Posiciones Principales | Posiciones Secundarias |
|---------|------|----------------------|----------------------|
| `Dribbles per 90` | Numérico | WING, MID (AM) | FWD |
| `Successful dribbles, %` | Porcentaje | WING, MID (AM) | FWD |
| `Progressive runs per 90` | Numérico | WING, MID | FWD |
| `Accelerations per 90` | Numérico | WING, FWD | MID |
| `Touches in box per 90` | Numérico | FWD, WING | MID (AM) |

**Justificación:**
- **WING:** Regates 1v1 esenciales (⭐⭐⭐)
- **MID (AM):** Creatividad, progresión con balón (⭐⭐⭐)
- **FWD:** Regates en área, touches in box (⭐⭐)
- **DEF:** No relevante (salvo full-backs ofensivos)

---

### **CATEGORÍA 10: PASES GENERALES** (8 columnas)
**Todas las posiciones (especialmente MID, DEF)**

| Columna | Tipo | Posiciones Críticas | Posiciones Secundarias |
|---------|------|-------------------|----------------------|
| `Passes per 90` | Numérico | MID, DEF | WING, GK |
| `Accurate passes, %` | Porcentaje | Todas | - |
| `Forward passes per 90` | Numérico | MID, DEF | - |
| `Accurate forward passes, %` | Porcentaje | MID, DEF | - |
| `Back passes per 90` | Numérico | DEF, MID (DM) | - |
| `Accurate back passes, %` | Porcentaje | DEF, MID (DM) | - |
| `Lateral passes per 90` | Numérico | MID, DEF | - |
| `Accurate lateral passes, %` | Porcentaje | MID, DEF | - |

**Nota:** `Lateral passes` solo disponible en temporadas 2023-26

**Justificación:**
- **MID:** Volumen de pases es core (⭐⭐⭐)
- **DEF:** Construcción desde atrás, ball-playing (⭐⭐⭐)
- **GK:** Distribución con pies (⭐⭐)
- **WING, FWD:** Menos volumen pero accuracy importante (⭐)

---

### **CATEGORÍA 11: PASES CORTOS Y LARGOS** (6 columnas)
**Todas las posiciones**

| Columna | Tipo | Posiciones Principales | Posiciones Secundarias |
|---------|------|----------------------|----------------------|
| `Short / medium passes per 90` | Numérico | MID, DEF | - |
| `Accurate short / medium passes, %` | Porcentaje | Todas | - |
| `Long passes per 90` | Numérico | DEF, MID, GK | - |
| `Accurate long passes, %` | Porcentaje | DEF, MID, GK | - |
| `Average pass length, m` | Numérico | Todas | - |
| `Average long pass length, m` | Numérico | DEF, GK | - |

**Justificación:**
- **DEF:** Long passes para cambio de juego (⭐⭐⭐)
- **GK:** Distribución larga (⭐⭐⭐)
- **MID:** Balance corto-largo según arquetipo (⭐⭐⭐)
- **WING, FWD:** Menos crítico (⭐)

---

### **CATEGORÍA 12: PASES AVANZADOS / CREATIVIDAD** (10 columnas)
**Principalmente: MID (AM, CM), WING**

| Columna | Tipo | Posiciones Principales | Posiciones Secundarias |
|---------|------|----------------------|----------------------|
| `Through passes per 90` | Numérico | MID (AM), WING | - |
| `Accurate through passes, %` | Porcentaje | MID (AM), WING | - |
| `Progressive passes per 90` | Numérico | MID, DEF | - |
| `Accurate progressive passes, %` | Porcentaje | MID, DEF | - |
| `Smart passes per 90` | Numérico | MID (AM), WING | - |
| `Accurate smart passes, %` | Porcentaje | MID (AM), WING | - |
| `Key passes per 90` | Numérico | MID, WING | FWD |
| `Shot assists per 90` | Numérico | MID, WING | - |
| `Passes to final third per 90` | Numérico | MID, DEF | - |
| `Accurate passes to final third, %` | Porcentaje | MID, DEF | - |

**Justificación:**
- **MID (AM):** Creatividad, through balls esencial (⭐⭐⭐)
- **WING:** Pases al área, key passes (⭐⭐⭐)
- **MID (CM):** Progressive passes (⭐⭐)
- **DEF:** Progressive passes desde atrás (⭐⭐)

---

### **CATEGORÍA 13: PASES AL ÁREA** (4 columnas)
**Principalmente: MID, WING**

| Columna | Tipo | Posiciones Principales | Posiciones Secundarias |
|---------|------|----------------------|----------------------|
| `Passes to penalty area per 90` | Numérico | MID (AM), WING | - |
| `Accurate passes to penalty area, %` | Porcentaje | MID (AM), WING | - |
| `Deep completions per 90` | Numérico | MID, WING | - |
| `Deep completed crosses per 90` | Numérico | WING | - |

**Justificación:**
- **WING:** Centros y pases al área (⭐⭐⭐)
- **MID (AM):** Pases filtrados al área (⭐⭐⭐)

---

### **CATEGORÍA 14: CENTROS** (7 columnas)
**Principalmente: WING | Secundario: DEF (full-backs)**

| Columna | Tipo | Posiciones Principales | Posiciones Secundarias |
|---------|------|----------------------|----------------------|
| `Crosses per 90` | Numérico | WING | DEF (RB, LB) |
| `Accurate crosses, %` | Porcentaje | WING | DEF (RB, LB) |
| `Crosses from left flank per 90` | Numérico | WING (LW), DEF (LB) | - |
| `Accurate crosses from left flank, %` | Porcentaje | WING (LW), DEF (LB) | - |
| `Crosses from right flank per 90` | Numérico | WING (RW), DEF (RB) | - |
| `Accurate crosses from right flank, %` | Porcentaje | WING (RW), DEF (RB) | - |
| `Crosses to goalie box per 90` | Numérico | WING | DEF (RB, LB) |

**Justificación:**
- **WING:** Core de su juego, centros al área (⭐⭐⭐)
- **DEF (Full-backs):** Laterales ofensivos (⭐⭐)
- Crosses por flanco útil para detectar jugadores que cambian de banda

---

### **CATEGORÍA 15: RECEPCIÓN DE PASES** (3 columnas)
**Todas las posiciones**

| Columna | Tipo | Posiciones Principales | Posiciones Secundarias |
|---------|------|----------------------|----------------------|
| `Received passes per 90` | Numérico | MID, FWD | DEF, WING |
| `Received long passes per 90` | Numérico | FWD, WING | - |

**Justificación:**
- **MID:** Participación en juego, volumen de recepción (⭐⭐⭐)
- **FWD:** Recepción de pases largos, Target Man (⭐⭐)
- **WING:** Recepción en carrera (⭐⭐)

---

### **CATEGORÍA 16: FALTAS Y DISCIPLINA** (7 columnas)
**Todas las posiciones**

| Columna | Tipo | Posiciones Críticas | Posiciones Secundarias |
|---------|------|-------------------|----------------------|
| `Fouls per 90` | Numérico | DEF, MID (DM) | - |
| `Fouls suffered per 90` | Numérico | WING, FWD | - |
| `Yellow cards` | Numérico | Todas | - |
| `Yellow cards per 90` | Numérico | DEF, MID (DM) | - |
| `Red cards` | Numérico | Todas | - |
| `Red cards per 90` | Numérico | DEF | - |

**Justificación:**
- **DEF:** Alta frecuencia de faltas defensivas (⭐⭐)
- **WING/FWD:** Fouls suffered indica regates con contacto (⭐⭐)
- Todas las posiciones: Disciplina general

---

### **CATEGORÍA 17: PORTERO ESPECÍFICO** (12 columnas)
**Solo: GK**

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `Save rate, %` | Porcentaje | % de paradas efectivas |
| `Clean sheets` | Numérico | Partidos sin goles encajados |
| `Conceded goals` | Numérico | Goles encajados totales |
| `Conceded goals per 90` | Numérico | Goles encajados por partido |
| `Shots against` | Numérico | Tiros recibidos |
| `Shots against per 90` | Numérico | Tiros recibidos por partido |
| `xG against` | Numérico | Goles esperados en contra |
| `xG against per 90` | Numérico | xG en contra por partido |
| `Prevented goals` | Numérico | Goles evitados vs xG |
| `Prevented goals per 90` | Numérico | Goles evitados por partido |
| `Back passes received as GK per 90` | Numérico | Pases recibidos de defensores |
| `Exits per 90` | Numérico | Salidas del área (sweeper keeper) |

**Justificación:**
- Todas esenciales para análisis de porteros (⭐⭐⭐)
- `Prevented goals` especialmente valioso (rendimiento vs esperado)

---

### **CATEGORÍA 18: SET PIECES / BALÓN PARADO** (7 columnas)
**Principalmente: MID (AM), FWD | Secundario: DEF**

| Columna | Tipo | Posiciones Principales | Posiciones Secundarias |
|---------|------|----------------------|----------------------|
| `Free kicks per 90` | Numérico | MID (AM), FWD | - |
| `Direct free kicks per 90` | Numérico | MID (AM), FWD | DEF |
| `Direct free kicks on target, %` | Porcentaje | MID (AM), FWD | DEF |
| `Corners per 90` | Numérico | WING, MID (AM) | - |
| `Penalties taken` | Numérico | FWD | MID |
| `Penalty conversion, %` | Porcentaje | FWD | MID |

**Justificación:**
- Identifica especialistas en set pieces
- Penalties esencial para delanteros

---

### **CATEGORÍA 19: ACCIONES ATACANTES** (1 columna)
**Todas las posiciones ofensivas**

| Columna | Tipo | Posiciones Principales | Posiciones Secundarias |
|---------|------|----------------------|----------------------|
| `Successful attacking actions per 90` | Numérico | FWD, WING, MID (AM) | MID (CM) |

**Justificación:**
- Métrica agregada de todas las acciones ofensivas exitosas

---

### **CATEGORÍA 20: DATOS FÍSICOS / GPS** (16 columnas) ⭐
**Todas las posiciones**
**⚠️ SOLO DISPONIBLE EN TEMPORADAS 2023-26**

#### **Distancias recorridas (5 columnas)**

| Columna | Tipo | Descripción | Posiciones Críticas |
|---------|------|-------------|-------------------|
| `Total Distance per 90` | Numérico (km) | Distancia total recorrida | Todas (especialmente MID) |
| `Running Distance per 90 (15-20 km/h)` | Numérico (km) | Distancia a velocidad media | MID, WING |
| `HSR Distance per 90 (20-25 km/h)` | Numérico (km) | High Speed Running | WING, FWD |
| `Sprinting Distance per 90 (+25 km/h)` | Numérico (km) | Distancia en sprint máximo | WING, FWD |
| `HI Distance per 90 (+20 km/h)` | Numérico (km) | High Intensity total | WING, FWD, MID |

#### **Velocidad (2 columnas)**

| Columna | Tipo | Descripción | Posiciones Críticas |
|---------|------|-------------|-------------------|
| `Max Speed (km/h)` | Numérico | Velocidad pico alcanzada | WING, FWD |
| `Meter/Min` | Numérico | Intensidad promedio (m/min) | Todas |

#### **Aceleraciones y Desaceleraciones (4 columnas)**

| Columna | Tipo | Descripción | Posiciones Críticas |
|---------|------|-------------|-------------------|
| `Count Medium Acceleration per 90 (1.5 m/s² to 3 m/s²)` | Numérico | Aceleraciones medias | WING, MID |
| `Count High Acceleration per 90 (+3 m/s²)` | Numérico | Aceleraciones explosivas | WING, FWD |
| `Count Medium Deceleration per 90 (-1.5 m/s² to -3 m/s²)` | Numérico | Frenadas medias | Todas |
| `Count High Deceleration per 90 (-3 m/s²)` | Numérico | Frenadas bruscas | Todas |

#### **Contadores de intensidad (3 columnas)**

| Columna | Tipo | Descripción | Posiciones Críticas |
|---------|------|-------------|-------------------|
| `Count HSR per 90 (20-25 km/h)` | Numérico | Frecuencia de carreras rápidas | WING, FWD |
| `Count Sprint per 90 (+25 km/h)` | Numérico | Frecuencia de sprints | WING, FWD |
| `Count HI per 90 (+20 km/h)` | Numérico | Frecuencia alta intensidad | WING, FWD, MID |

**Justificación:**
- **WING/FWD:** Sprints y velocidad máxima críticas (⭐⭐⭐)
- **MID:** Distancia total y trabajo físico (⭐⭐⭐)
- **DEF:** Distancia total, menos sprints (⭐⭐)
- **GK:** Menos relevante, pero exits rápidos (⭐)

**Métricas más valiosas:**
1. Total Distance → Trabajo físico
2. HSR Distance → Intensidad
3. Max Speed → Velocidad pura
4. Count Sprint → Frecuencia de esfuerzos máximos

---

### **CATEGORÍA 21: OTROS** (1 columna)

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `On loan` | Booleano | ¿Jugador cedido? |

**Justificación:** Contexto sobre situación contractual

---

## ❌ MÉTRICAS A ELIMINAR (29 columnas)

### **GRUPO 1: METADATA DE WYSCOUT** (4 columnas)

| Columna | Razón para eliminar |
|---------|-------------------|
| `Wyscout id` | ID interno de Wyscout, no útil para usuario final |
| `Full name` | Redundante con `Player` |
| `Team logo` | URL, podemos obtenerlo de otra forma |
| `Competition` | Siempre es "Hong Kong Premier League" |

---

### **GRUPO 2: INFORMACIÓN ADMINISTRATIVA NO RELEVANTE** (2 columnas)

| Columna | Razón para eliminar |
|---------|-------------------|
| `Market value` | No es métrica de rendimiento, cambia constantemente, datos poco fiables |
| `Contract expires` | Administrativo, no refleja rendimiento en campo |

---

### **GRUPO 3: POSICIONES CON PORCENTAJES (ya no disponibles)** (6 columnas)

| Columna | Razón para eliminar |
|---------|-------------------|
| `Primary position` | Redundante con `Position` |
| `Primary position, %` | Solo en temporadas antiguas, ya no existe |
| `Secondary position` | Menos relevante que posición principal |
| `Secondary position, %` | Solo en temporadas antiguas, ya no existe |
| `Third position` | Poco relevante |
| `Third position, %` | Solo en temporadas antiguas, ya no existe |

**Nota:** Mantenemos solo `Position` como posición principal

---

### **GRUPO 4: INFORMACIÓN PERSONAL DETALLADA** (1 columna)

| Columna | Razón para eliminar |
|---------|-------------------|
| `Birthday` | Redundante, ya tenemos `Age` |

**Nota:** Mantenemos `Age` que es más útil y actualizado

---

### **GRUPO 5: ASISTENCIAS INDIRECTAS (poco relevantes)** (2 columnas)

| Columna | Razón para eliminar |
|---------|-------------------|
| `Second assists per 90` | Demasiado indirecto, pase antes del asistidor |
| `Third assists per 90` | Extremadamente indirecto, 3 pases antes del gol |

**Nota:** Mantenemos `Assists` y `Shot assists` que son más directas

---

### **GRUPO 6: PASES VERTICALES (ya no disponibles)** (2 columnas)

| Columna | Razón para eliminar |
|---------|-------------------|
| `Vertical passes per 90` | Solo en temporadas 2018-23, ya no existe en 2023+ |
| `Accurate vertical passes, %` | Solo en temporadas 2018-23, ya no existe en 2023+ |

**Nota:** No podemos usarla porque crea inconsistencia temporal

---

### **GRUPO 7: DUPLICADO TÉCNICO** (1 columna)

| Columna | Razón para eliminar |
|---------|-------------------|
| `Aerial duels per 90.1` | Columna duplicada de `Aerial duels per 90` |

---

## 📊 RESUMEN NUMÉRICO

### **TOTAL DE COLUMNAS POR CONJUNTO:**

- **Temporadas 2018-23:** 127 columnas
- **Temporadas 2023-26:** 136 columnas

### **DECISIÓN FINAL:**

| Categoría | Cantidad |
|-----------|----------|
| ✅ **Columnas a MANTENER** | **98 columnas** |
| ❌ **Columnas a ELIMINAR** | **29 columnas** |
| ⚠️ **Columnas solo 2023+** | **18 columnas** (16 físicas + 2 laterales) |

### **DISTRIBUCIÓN DE COLUMNAS MANTENIDAS:**

| Categoría | # Columnas | Temporadas |
|-----------|------------|------------|
| Identificación | 4 | Todas |
| Info Personal | 5 | Todas |
| Tiempo de Juego | 2 | Todas |
| Goles | 8 | Todas |
| Asistencias | 4 | Todas |
| Tiros | 6 | Todas |
| Duelos | 8 | Todas |
| Defensa | 7 | Todas |
| Regates/Movilidad | 5 | Todas |
| Pases Generales | 8 | Todas (Lateral solo 2023+) |
| Pases Cortos/Largos | 6 | Todas |
| Pases Avanzados | 10 | Todas |
| Pases al Área | 4 | Todas |
| Centros | 7 | Todas |
| Recepción | 3 | Todas |
| Faltas/Disciplina | 7 | Todas |
| Portero | 12 | Todas |
| Set Pieces | 7 | Todas |
| Acciones Atacantes | 1 | Todas |
| **Datos Físicos GPS** | **16** | **Solo 2023-26** ⚠️ |
| Otros | 1 | Todas |

---

## 🎯 MÉTRICAS POR POSICIÓN (MAPA DE RELEVANCIA)

### **GOALKEEPER (GK)** - 31 métricas relevantes

**⭐⭐⭐ Críticas (12):**
- Save rate, %
- Clean sheets
- Conceded goals per 90
- Shots against per 90
- xG against per 90
- Prevented goals per 90
- Exits per 90
- Passes per 90
- Accurate passes, %
- Long passes per 90
- Accurate long passes, %
- Back passes received as GK per 90

**⭐⭐ Importantes (8):**
- Height (alcance)
- Aerial duels won, %
- Forward passes per 90
- Average long pass length
- Fouls per 90
- Yellow cards
- Total Distance per 90 (físico)
- Accelerations per 90

**⭐ Secundarias (11):**
- Age, Team, Birth country, Foot, Weight
- Matches played, Minutes played
- Back passes per 90
- Free kicks per 90
- On loan
- Max Speed

---

### **DEFENDER (DEF)** - 48 métricas relevantes

**⭐⭐⭐ Críticas (18):**
- Successful defensive actions per 90
- Sliding tackles per 90
- PAdj Sliding tackles
- Interceptions per 90
- PAdj Interceptions
- Shots blocked per 90
- Defensive duels won, %
- Aerial duels per 90
- Aerial duels won, %
- Passes per 90
- Accurate passes, %
- Forward passes per 90
- Accurate forward passes, %
- Long passes per 90
- Progressive passes per 90
- Passes to final third per 90
- Duels won, %
- Height (duelos aéreos)

**⭐⭐ Importantes (15):**
- Back passes per 90
- Lateral passes per 90 (2023+)
- Short/medium passes per 90
- Goals (balón parado)
- Head goals
- Assists (pases largos)
- Crosses per 90 (full-backs)
- Fouls per 90
- Yellow cards per 90
- Red cards
- Total Distance per 90
- HSR Distance per 90
- Sprinting Distance per 90
- Foot
- Weight

**⭐ Secundarias (15):**
- Age, Team, Birth country
- Matches played, Minutes played
- Received passes per 90
- Dribbles per 90 (full-backs ofensivos)
- Progressive runs per 90 (full-backs)
- Key passes per 90 (full-backs)
- Free kicks per 90
- On loan
- Max Speed
- Count Sprint per 90
- Meter/Min
- Count High Acceleration per 90
- Accelerations per 90

---

### **MIDFIELDER (MID)** - 68 métricas relevantes

**⭐⭐⭐ Críticas (30):**
- Passes per 90
- Accurate passes, %
- Forward passes per 90
- Accurate forward passes, %
- Through passes per 90
- Progressive passes per 90
- Key passes per 90
- Smart passes per 90
- Passes to final third per 90
- Passes to penalty area per 90
- Assists
- xA
- Assists per 90
- xA per 90
- Goals (AM especialmente)
- xG (AM)
- Duels won, %
- Defensive duels won, % (DM)
- Successful defensive actions per 90 (DM)
- Sliding tackles per 90 (DM)
- Interceptions per 90 (DM)
- Received passes per 90
- Dribbles per 90 (AM)
- Successful dribbles, % (AM)
- Total Distance per 90
- HSR Distance per 90
- Shot assists per 90
- Long passes per 90 (DM)
- Back passes per 90 (DM)
- Lateral passes per 90 (2023+)

**⭐⭐ Importantes (23):**
- Goals per 90
- Non-penalty goals
- Shots per 90 (AM)
- Shots on target, % (AM)
- Accurate through passes, %
- Accurate progressive passes, %
- Deep completions per 90
- Offensive duels won, %
- Aerial duels won, %
- PAdj Sliding tackles (DM)
- PAdj Interceptions (DM)
- Progressive runs per 90
- Touches in box per 90 (AM)
- Fouls per 90
- Fouls suffered per 90
- Yellow cards
- Free kicks per 90
- Corners per 90 (AM)
- Sprinting Distance per 90
- Max Speed
- Count Sprint per 90
- Count High Acceleration per 90
- Meter/Min

**⭐ Secundarias (15):**
- Age, Team, Birth country, Foot, Height, Weight
- Matches played, Minutes played
- Head goals
- Crosses per 90
- Received long passes per 90
- Penalties taken
- Red cards
- HI Distance per 90
- On loan

---

### **WINGER (WING)** - 61 métricas relevantes

**⭐⭐⭐ Críticas (28):**
- Crosses per 90
- Accurate crosses, %
- Crosses from left/right flank per 90
- Accurate crosses from left/right flank, %
- Deep completed crosses per 90
- Assists
- xA
- Assists per 90
- xA per 90
- Goals
- xG
- Goals per 90
- Shots per 90
- Shots on target, %
- Dribbles per 90
- Successful dribbles, %
- Offensive duels won, %
- Duels won, %
- Key passes per 90
- Through passes per 90
- Progressive runs per 90
- Accelerations per 90
- Total Distance per 90
- HSR Distance per 90
- Sprinting Distance per 90
- Max Speed
- Count Sprint per 90
- Foot (crítico para wingers)

**⭐⭐ Importantes (20):**
- Passes to penalty area per 90
- Smart passes per 90
- Shot assists per 90
- Touches in box per 90
- Received long passes per 90
- Fouls suffered per 90
- Goal conversion, %
- Non-penalty goals
- Progressive passes per 90
- Passes to final third per 90
- Successful defensive actions per 90
- Defensive duels won, %
- Free kicks per 90
- Corners per 90
- HI Distance per 90
- Count High Acceleration per 90
- Count Medium Acceleration per 90
- Meter/Min
- Height
- Weight

**⭐ Secundarias (13):**
- Age, Team, Birth country
- Matches played, Minutes played
- Passes per 90
- Accurate passes, %
- Forward passes per 90
- Head goals
- Aerial duels won, %
- Yellow cards
- Penalties taken
- On loan
- Running Distance per 90

---

### **FORWARD (FWD)** - 52 métricas relevantes

**⭐⭐⭐ Críticas (23):**
- Goals
- Goals per 90
- xG
- xG per 90
- Non-penalty goals
- Non-penalty goals per 90
- Shots
- Shots per 90
- Shots on target, %
- Goal conversion, %
- Touches in box per 90
- Offensive duels won, %
- Duels won, %
- Aerial duels per 90 (Target Man)
- Aerial duels won, % (Target Man)
- Head goals (Target Man)
- Assists (Complete Forward)
- xA (Complete Forward)
- Received passes per 90
- Received long passes per 90
- Penalties taken
- Penalty conversion, %
- Height (Target Man)

**⭐⭐ Importantes (18):**
- Dribbles per 90
- Successful dribbles, %
- Progressive runs per 90
- Accelerations per 90
- Key passes per 90
- Shot assists per 90
- Fouls suffered per 90
- Free kicks per 90
- Direct free kicks per 90
- Direct free kicks on target, %
- HSR Distance per 90
- Sprinting Distance per 90
- Max Speed
- Count Sprint per 90
- Count High Acceleration per 90
- Total Distance per 90
- Foot
- Weight

**⭐ Secundarias (11):**
- Age, Team, Birth country
- Matches played, Minutes played
- Passes per 90
- Through passes per 90 (False 9)
- Crosses per 90
- Yellow cards
- HI Distance per 90
- Meter/Min
- On loan

---

## 📋 SIGUIENTES PASOS

### **1. Actualizar `hong_kong_processor.py`:**
- Validar que las 98 columnas mantenidas existan
- Eliminar las 29 columnas descartadas
- Manejar las 18 columnas solo disponibles en 2023+ (marcar como NULL en temporadas antiguas)
- Eliminar duplicado `Aerial duels per 90.1`

### **2. Crear mapeo de columnas:**
```python
COLUMNS_TO_KEEP = [
    # CATEGORÍA 1: IDENTIFICACIÓN
    'Player', 'Team', 'Position', 'Age',
    # CATEGORÍA 2: INFO PERSONAL
    'Birth country', 'Passport country', 'Foot', 'Height', 'Weight',
    # ... (las 98 columnas)
]

COLUMNS_TO_DROP = [
    'Wyscout id', 'Full name', 'Team logo', 'Competition',
    'Market value', 'Contract expires',
    # ... (las 29 columnas)
]

COLUMNS_2023_ONLY = [
    'Lateral passes per 90', 'Accurate lateral passes, %',
    'Total Distance per 90', 'Running Distance per 90 (15-20 km/h)',
    # ... (las 18 columnas físicas)
]
```

### **3. Documentar métricas por posición:**
- Crear `docs/METRICAS_POR_POSICION.md`
- Listar qué métricas son críticas/importantes/secundarias para cada posición
- Incluir benchmarks (qué es bueno/malo/excelente)

### **4. Actualizar visualizaciones:**
- Player View: Mostrar solo métricas relevantes según posición
- Radar charts: Usar solo métricas críticas (⭐⭐⭐)
- Añadir disclaimer: "Datos físicos disponibles desde 2023-24"

---

## ✅ CONFIRMACIÓN FINAL

**Total columnas a procesar: 98 (82 comunes + 16 físicas solo 2023+)**

¿Procedo con la implementación en el código?
