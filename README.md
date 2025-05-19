# Sports Dashboard - Liga de Hong Kong

Una aplicación web interactiva para el análisis de performance deportiva y gestión de lesiones, desarrollada con Dash y Python.

## 📋 Descripción

Este dashboard deportivo proporciona análisis completos de datos de la Liga de Hong Kong, incluyendo:

- **Dashboard de Performance**: Análisis de estadísticas de jugadores y equipos
- **Dashboard de Injuries**: Gestión y análisis de lesiones
- **Sistema de Autenticación**: Login seguro con Flask-Login
- **Exportación de Reportes**: Generación de PDFs personalizados

## 🚀 Características Principales

### Autenticación y Seguridad
- Sistema de login con Flask-Login
- Protección de rutas
- Gestión de sesiones
- Logout seguro

### Dashboard de Performance
- Análisis a nivel de liga, equipo y jugador
- Visualizaciones interactivas con Plotly
- Filtros avanzados (posición, edad, equipo)
- Métricas clave (KPIs)
- Exportación a PDF

### Dashboard de Injuries
- Gestión de lesiones simuladas
- Análisis por tipo y región corporal
- Tendencias temporales
- Tabla interactiva con DataTable
- Reportes médicos

### Diseño y UX
- Interfaz responsiva con Bootstrap
- CSS personalizado
- Animaciones y transiciones
- Diseño moderno y profesional

## 🛠️ Tecnologías Utilizadas

- **Dash**: Framework principal para la aplicación web
- **Plotly**: Visualizaciones interactivas
- **Flask-Login**: Autenticación y gestión de sesiones
- **Pandas**: Manipulación de datos
- **NumPy**: Cálculos numéricos
- **ReportLab**: Generación de PDFs
- **Dash Bootstrap Components**: Componentes de interfaz
- **Python-dotenv**: Gestión de variables de entorno

## 📁 Estructura del Proyecto

```
sports_dashboard/
├── app.py                      # Aplicación principal
├── requirements.txt            # Dependencias
├── .env                        # Variables de entorno
├── .gitignore                 # Archivos ignorados por git
├── README.md                  # Este archivo
├── assets/
│   ├── style.css              # Estilos personalizados
│   └── logo.png               # Logo de la aplicación
├── callbacks/
│   ├── __init__.py            # Importaciones de callbacks
│   ├── auth_callbacks.py      # Callbacks de autenticación
│   ├── navigation_callbacks.py # Callbacks de navegación
│   ├── home_callbacks.py      # Callbacks del home
│   ├── performance_callbacks.py # Callbacks de performance
│   └── injuries_callbacks.py  # Callbacks de injuries
├── components/
│   └── navbar.py              # Componente del navbar
├── data/
│   ├── __init__.py            # Gestión de datos
│   ├── hong_kong_data_manager.py # Gestor principal
│   ├── extractors/            # Extractores de datos
│   ├── processors/            # Procesadores de datos
│   └── aggregators/           # Agregadores de estadísticas
├── layouts/
│   ├── home.py                # Layout del home
│   ├── login.py               # Layout del login
│   ├── performance.py         # Layout de performance
│   ├── injuries.py            # Layout de injuries
│   └── not_found.py           # Layout de error 404
└── utils/
    ├── auth.py                # Utilidades de autenticación
    ├── cache.py               # Gestión de caché
    └── pdf_generator.py       # Generador de PDFs
```

## ⚙️ Instalación y Configuración

### 1. Requisitos Previos

- Python 3.8 o superior
- pip (gestor de paquetes de Python)

### 2. Clonación del Repositorio

```bash
git clone 
cd sports_dashboard
```

### 3. Instalación de Dependencias

```bash
pip install -r requirements.txt
```

### 4. Configuración de Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
# Configuración de autenticación
ADMIN_USER=admin
ADMIN_PASSWORD=admin
SECRET_KEY=tu_clave_secreta_aqui

# Configuración de cache
CACHE_TYPE=filesystem
CACHE_DIR=./cache

# Configuración de desarrollo
DEBUG=True
```

### 5. Ejecutar la Aplicación

```bash
python app.py
```

La aplicación estará disponible en: http://localhost:8050

## 🔐 Credenciales de Acceso

- **Usuario**: admin
- **Contraseña**: admin

## 📊 Uso de la Aplicación

### 1. Login
- Accede a la aplicación con las credenciales proporcionadas
- El sistema redirigirá automáticamente al dashboard principal

### 2. Dashboard de Performance
- Selecciona el nivel de análisis (Liga, Equipo, Jugador)
- Aplica filtros según tus necesidades
- Explora las visualizaciones interactivas
- Exporta reportes en PDF

### 3. Dashboard de Injuries
- Analiza datos de lesiones simuladas
- Filtra por tipo, equipo o período
- Revisa tendencias y estadísticas
- Genera reportes médicos

## 📈 Características Técnicas

### Gestión de Datos
- Extractor automático desde GitHub
- Procesamiento y limpieza de datos
- Sistema de caché inteligente
- Agregadores de estadísticas

### Visualizaciones
- Gráficos de barras y líneas interactivos
- Gráficos de radar y dispersión
- Tablas dinámicas con filtros
- KPIs en tiempo real

### Performance
- Caché de consultas pesadas
- Loading states para mejor UX
- Optimización de callbacks
- Manejo de errores robusto

## 🔄 Actualizaciones y Mantenimiento

### Actualización de Datos
- Los datos se actualizan automáticamente desde GitHub
- Verificación de cambios en tiempo real
- Cache inteligente para optimizar performance

### Logs y Debugging
- Logging configurado para desarrollo
- Manejo de errores personalizado
- Debug mode para desarrollo

## 🚀 Despliegue en Producción

### Consideraciones
1. Cambiar `DEBUG=False` en variables de entorno
2. Usar una base de datos real para usuarios
3. Configurar HTTPS
4. Implementar rate limiting
5. Configurar logging para producción

### Heroku (Ejemplo)
```bash
# Crear Procfile
echo "web: gunicorn app:server" > Procfile

# Deploy
git add .
git commit -m "Deploy to production"
git push heroku main
```

## 📝 Notas de Desarrollo

### Decisiones de Diseño
1. **Arquitectura Modular**: Separación clara entre callbacks, layouts y componentes
2. **Datos Simulados**: Para injuries se usan datos simulados para demostración
3. **Sistema de Cache**: Implementado para optimizar consultas repetidas
4. **Responsive Design**: Compatible con móviles y tablets

### Desafíos Encontrados
1. **Gestión de Estado**: Uso de dcc.Store para mantener estado entre callbacks
2. **Performance**: Optimización con cache y prevent_initial_call
3. **PDF Generation**: Implementación personalizada con ReportLab
4. **Data Processing**: Pipeline completo de extracción y procesamiento

## 🤝 Contribución

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/nueva-caracteristica`)
3. Commit tus cambios (`git commit -am 'Agregar nueva característica'`)
4. Push a la rama (`git push origin feature/nueva-caracteristica`)
5. Crea un Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para más detalles.

## 🆘 Soporte

Para dudas o problemas:
1. Revisa la documentación
2. Consulta los logs de error
3. Crea un issue en GitHub

---

**Desarrollado para el Máster en Python Avanzado Aplicado al Deporte - Módulo 9: Dash con Plotly**