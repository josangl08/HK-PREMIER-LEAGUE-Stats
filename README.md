# Sports Dashboard – Liga de Hong Kong

Una aplicación web interactiva para el análisis de rendimiento deportivo y gestión de lesiones desarrollada con **Dash** y **Python**.

---

## 📋 Índice

1. [Instalación rápida](#instalación-rápida)
2. [Descripción](#descripción)
3. [Características principales](#características-principales)
4. [Tecnologías](#tecnologías)
5. [Estructura del proyecto](#estructura-del-proyecto)
6. [Instalación y configuración detallada](#instalación-y-configuración-detallada)
7. [Uso](#uso)
8. [Características técnicas](#características-técnicas)
9. [Despliegue](#despliegue)
10. [Guía para desarrolladores](#guía-para-desarrolladores)
11. [Contribución](#contribución)
12. [Licencia](#licencia)
13. [Soporte](#soporte)

---

## 🚀 Instalación rápida

### Prerrequisitos

* Python ≥ 3.8
* `pip`

### Instalación en 3 pasos

```bash
# 1. Clonar y configurar
git clone <URL_DEL_REPOSITORIO>
cd sports-dashboard

# Crear entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Ejecutar la aplicación
python app.py
```

> Abre [http://localhost:8050](http://localhost:8050) en tu navegador

### Credenciales por defecto

| Usuario | Contraseña |
| ------- | ---------- |
| `admin` | `admin`    |

### Solución a problemas comunes

| Error                   | Solución                                  |
| ----------------------- | ----------------------------------------- |
| Module not found        | `bash\npip install -r requirements.txt\n` |
| Address already in use  | Ajusta el puerto en `.env` → `PORT=8051`  |
| Permisos en Linux/macOS | `bash\nsudo chmod +x setup.py\n`          |

---

## 📋 Descripción

Este dashboard deportivo proporciona análisis completos de datos de la **Liga de Hong Kong**, incluyendo:

* **Dashboard de Performance**: estadísticas de jugadores y equipos
* **Dashboard de Injuries**: gestión y análisis de lesiones
* **Sistema de autenticación** con *Flask‑Login*
* **Exportación de reportes** en PDF personalizados

---

## 🚀 Características principales

### Autenticación y seguridad

* Sistema de login con *Flask‑Login*
* Protección de rutas y gestión de sesiones
* Logout seguro

### Dashboard de Performance

* Análisis a nivel de liga, equipo y jugador
* Visualizaciones interactivas con Plotly
* Filtros avanzados (posición, edad, equipo)
* KPIs y exportación a PDF

### Dashboard de Injuries

* Gestión de lesiones simuladas
* Análisis por tipo y región corporal
* Tendencias temporales y tablas interactivas

### Diseño y UX

* Interfaz responsive con Bootstrap
* Animaciones y transiciones suaves
* Estilo moderno y profesional

---

## 🛠️ Tecnologías

| Herramienta               | Uso                             |
| ------------------------- | ------------------------------- |
| Dash                      | Framework web                   |
| Plotly                    | Gráficos interactivos           |
| Flask‑Login               | Autenticación                   |
| Pandas / NumPy            | Manipulación y cálculo de datos |
| ReportLab                 | Generación de PDFs              |
| Dash Bootstrap Components | UI                              |
| python‑dotenv             | Variables de entorno            |

---

## 🧭 Gobernanza del repositorio

Las reglas de estructura, runtime storage y clasificación de módulos están documentadas en `docs/repo_structure_governance.md`.

Puntos clave:

* Los assets generados en runtime escriben ahora en `storage/player_cards/`.
* `data/player_cards/` queda como ruta legada de lectura durante la migración.
* Artefactos generados como `htmlcov/`, `.pytest_cache/`, `__pycache__/`, `*.db-wal` y `*.db-shm` no forman parte de la estructura fuente.

---

## 📁 Estructura del proyecto

```text
sports_dashboard/
├── app.py                      # Aplicación principal
├── requirements.txt            # Dependencias
├── .env                        # Variables de entorno
├── assets/
│   ├── style.css               # Estilos
│   └── logo.png                # Logo
├── callbacks/
│   ├── auth_callbacks.py
│   ├── navigation_callbacks.py
│   ├── home_callbacks.py
│   ├── performance_callbacks.py
│   └── injuries_callbacks.py
├── components/
│   └── navbar.py
├── data/
│   ├── hong_kong_data_manager.py
│   ├── extractors/
│   ├── processors/
│   └── aggregators/
├── layouts/
│   ├── home.py
│   ├── login.py
│   ├── performance.py
│   └── injuries.py
└── utils/
    ├── auth.py
    ├── cache.py
    └── pdf_generator.py
```

---

## ⚙️ Instalación y configuración detallada

1. **Requisitos previos**
   Python ≥ 3.8 y `pip`

2. **Clonación del repositorio**

   ```bash
   git clone <URL_DEL_REPOSITORIO>
   cd sports_dashboard
   ```

3. **Instalación de dependencias**

   ```bash
   pip install -r requirements.txt
   ```

4. **Variables de entorno**
   Crea un archivo `.env`:

   ```env
   # Autenticación
   ADMIN_USER=admin
   ADMIN_PASSWORD=admin
   SECRET_KEY=tu_clave_secreta_aqui

   # Caché
   CACHE_TYPE=filesystem
   CACHE_DIR=./cache

   # Desarrollo
   DEBUG=True
   ```

5. **Ejecutar la aplicación**

   ```bash
   python app.py
   ```

   La aplicación estará en [http://localhost:8050](http://localhost:8050).

---

## 📊 Uso

### 1. Login

Accede con las credenciales por defecto para entrar al dashboard.

### 2. Dashboard de Performance

1. Selecciona el nivel de análisis (Liga | Equipo | Jugador)
2. Aplica filtros
3. Explora las visualizaciones
4. Exporta reportes en PDF

### 3. Dashboard de Injuries

1. Filtra por tipo, equipo o periodo
2. Analiza tendencias y métricas
3. Genera reportes médicos

---

## 📈 Características técnicas

### Gestión de datos

* Extracción automática desde GitHub
* Limpieza y procesamiento ETL
* Caché inteligente

### Visualizaciones

* Gráficos de barras, líneas, radar y dispersión
* Tablas dinámicas con filtros
* KPIs en tiempo real

### Performance

* Caché de consultas costosas
* Indicadores de carga (loading states)
* Manejo robusto de errores

---

## 🔄 Actualizaciones y mantenimiento

* **Datos**: actualización automática desde GitHub con verificación en tiempo real
* **Logs**: logging configurado y modo debug disponible

---

## 🚀 Despliegue

> **Nota:** establece `DEBUG=False` en producción.

### Ejemplo con Heroku

```bash
# Crear Procfile
echo 'web: gunicorn app:server' > Procfile

# Deploy
git add .
git commit -m 'Deploy to production'
git push heroku main
```
