# 🚀 Instalación Rápida - Sports Dashboard

## Prerequisitos
- Python 3.8 o superior
- pip (gestor de paquetes de Python)

## 🔧 Instalación en 3 pasos

### 1. Clonar y configurar
```bash
# Clonar repositorio
git clone 
cd sports-dashboard

# Crear entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Ejecutar configuración automática
python setup.py
```

### 2. Configurar variables de entorno
El script de setup creará un archivo `.env`. Revísalo y ajusta si es necesario:

```env
ADMIN_USER=admin
ADMIN_PASSWORD=admin
SECRET_KEY=tu_clave_secreta
DEBUG=True
```

### 3. Ejecutar la aplicación
```bash
python app.py
```

🎉 **¡Listo!** Abre http://localhost:8050 en tu navegador

## 🔐 Credenciales por defecto
- **Usuario**: admin
- **Contraseña**: admin

## ⚙️ Instalación manual (alternativa)

Si prefieres instalar manualmente:

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Crear directorios necesarios
mkdir -p cache logs data/cache data/exports

# 3. Copiar configuración
cp .env.example .env

# 4. Ejecutar
python app.py
```

## 🐳 Instalación con Docker (próximamente)

```bash
# Construir imagen
docker build -t sports-dashboard .

# Ejecutar contenedor
docker run -p 8050:8050 sports-dashboard
```

## 🆘 Solución de problemas

### Error: Módulo no encontrado
```bash
pip install -r requirements.txt
```

### Error: Puerto en uso
Cambia el puerto en `.env`:
```env
PORT=8051
```

### Problemas con permisos
En Linux/Mac, es posible que necesites:
```bash
sudo chmod +x setup.py
```

## 📚 Siguientes pasos

1. Explora el dashboard de performance
2. Revisa el dashboard de injuries
3. Prueba la exportación de reportes
4. Consulta la documentación completa en README.md

---

**¿Necesitas ayuda?** Consulta la documentación completa o crea un issue en GitHub.