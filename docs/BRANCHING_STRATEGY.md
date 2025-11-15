# 🌳 Estrategia de Ramas (Branching Strategy)
## Hong Kong Premier League Stats - Proyecto Académico y SaaS

**Fecha:** 15 de noviembre de 2025
**Autor:** Claude AI + josangl08

---

## 📋 Índice

1. [Propuesta del Usuario](#propuesta-del-usuario)
2. [Análisis de la Propuesta](#análisis-de-la-propuesta)
3. [Opciones Recomendadas](#opciones-recomendadas)
4. [Recomendación Final](#recomendación-final)
5. [Flujo de Trabajo](#flujo-de-trabajo)
6. [Convenciones de Nomenclatura](#convenciones-de-nomenclatura)
7. [Comandos Git Útiles](#comandos-git-útiles)

---

## 🔍 Propuesta del Usuario

Tu propuesta original:

- **Fase 1** (UI/UX y Métricas): `main` → `dev` → `project` → `features`
- **Fase 2** (Contenido Instagram): `main` → `dev` → `features`
- **Fase 3** (IA/ML): `main` → `dev` → `project` → `features`

**Razonamiento - Contexto del Doble Propósito:**

El proyecto tiene **dos propósitos distintos** que justifican esta arquitectura:

1. **Propósito Académico** (Trabajo de máster en IA):
   - Requiere **Fase 1** (UI/UX y Métricas profesionales)
   - Requiere **Fase 3** (Implementación de IA/ML)
   - **NO requiere** Fase 2 (contenido Instagram)
   - Necesita rama limpia `project` solo con código core/académico

2. **Propósito Profesional/SaaS** (Producto completo):
   - Requiere **todas las fases** (1, 2 y 3)
   - Incluye funcionalidad de redes sociales (Fase 2)
   - Rama `develop` integra todo (académico + profesional)

**Flujo propuesto:**
- Fase 1 → `project` → `develop` → `main` (académico + profesional)
- Fase 2 → `develop` → `main` (solo profesional, skip `project`)
- Fase 3 → `project` → `develop` → `main` (académico + profesional)

**Resultado:**
- `project`: Solo Fase 1 + Fase 3 (base limpia para memoria académica)
- `develop`: Fase 1 + Fase 2 + Fase 3 (producto completo)
- `main`: Versión de producción completa

---

## ✅ Análisis de la Propuesta

### **Puntos Fuertes (Contexto Académico + Profesional):**

1. ✅ **Separación académico/profesional**: `project` mantiene solo código académico (Fase 1 + 3), perfecto para memoria de máster
2. ✅ **Flexibilidad de entregables**: Puedes entregar trabajo académico sin incluir código de Instagram
3. ✅ **Desarrollo paralelo**: Fase 2 (Instagram) no contamina rama académica mientras desarrollas Fase 3 (IA)
4. ✅ **Conceptualmente correcto**: Dos audiencias (profesor vs clientes) requieren dos ramas
5. ✅ **Escalabilidad**: Si en futuro añades Fase 4 (ej: app móvil no-académica), va a `develop` sin tocar `project`

### **Puntos a Considerar (No son blockers, solo requieren disciplina):**

1. ⚠️ **Sincronización necesaria**: Debes mergear `project → develop` regularmente (cada feature core completada)
2. ⚠️ **Flujo unidireccional**: NUNCA mergear `develop → project` (solo project → develop)
3. ⚠️ **Dependencias Fase 2**: Si Fase 2 necesita código de Fase 1 (UI components), mergear `project → develop` ANTES de empezar Fase 2
4. ⚠️ **Claridad en nomenclatura**: Usar notación correcta: `features → project → develop → main` (no al revés)

### **¿Es Posible Técnicamente?**

**SÍ**, pero con estas consideraciones:

```
# Flujo correcto de merges:
feature/fase1-metricas → project → dev → main
feature/fase2-instagram → dev → main
feature/fase3-clustering → project → dev → main
```

**Requisitos:**
- Sincronizar `dev` con `project` antes de cada merge de Fase 2
- Hacer merge de `project` a `dev` regularmente (ej: cada semana)
- Nunca mergear `dev` directamente a `main` sin pasar por `project` si hay cambios core pendientes

---

## 🎯 Opciones Recomendadas

### **OPCIÓN A: Simplificada (Recomendada para empezar) ⭐**

```
main (producción estable)
└── develop (rama principal de desarrollo)
    ├── feature/fase1-metricas-posicion
    ├── feature/fase1-ui-redesign
    ├── feature/fase1-visualizations
    ├── feature/fase2-instagram-templates
    ├── feature/fase2-match-detector
    ├── feature/fase3-clustering
    └── feature/fase3-recommendations
```

**Ventajas:**
- ✅ Simple y fácil de mantener
- ✅ Estándar de la industria (Git Flow simplificado)
- ✅ Menos riesgo de conflictos
- ✅ Ideal para equipo pequeño (1-2 personas)

**Desventajas:**
- ❌ No separa features core de features adicionales
- ❌ Todo se mezcla en `develop`

**Flujo de trabajo:**
```bash
# Crear feature
git checkout develop
git checkout -b feature/fase1-metricas-posicion

# Desarrollar...
git add .
git commit -m "feat: Add position-specific metrics"

# Finalizar feature
git checkout develop
git pull origin develop
git merge feature/fase1-metricas-posicion
git push origin develop

# Deploy a producción (cuando Fase 1 esté completa)
git checkout main
git merge develop
git push origin main
```

---

### **OPCIÓN B: Con Rama Intermedia (Tu propuesta mejorada) 🔧**

```
main (producción estable)
├── develop (desarrollo general)
│   ├── feature/fase2-instagram-templates
│   ├── feature/fase2-match-detector
│   └── feature/fase2-content-manager
│   └── [recibe merges de project regularmente]
│
└── project (desarrollo core académico/técnico)
    ├── feature/fase1-metricas-posicion
    ├── feature/fase1-ui-redesign
    ├── feature/fase1-visualizations
    ├── feature/fase3-clustering
    ├── feature/fase3-recommendations
    └── feature/fase3-ml-explainability
```

**Ventajas:**
- ✅ Separa claramente features core (1+3) de features adicionales (2)
- ✅ `project` sirve como rama de calidad para el trabajo académico
- ✅ Permite desarrollo paralelo sin interferencias
- ✅ Útil si quieres hacer releases separadas de core vs extras

**Desventajas:**
- ⚠️ Requiere sincronización constante entre `project` y `develop`
- ⚠️ Más complejo de mantener
- ⚠️ Riesgo de merge conflicts si no sincronizas frecuentemente

**Flujo de trabajo:**
```bash
# Feature de Fase 1 o 3 (core):
git checkout project
git checkout -b feature/fase1-metricas-posicion
# ... desarrollo ...
git checkout project
git merge feature/fase1-metricas-posicion
git push origin project

# Sincronizar project → develop (semanal o al terminar cada feature):
git checkout develop
git merge project
git push origin develop

# Feature de Fase 2 (adicional):
git checkout develop
git checkout -b feature/fase2-instagram-templates
# ... desarrollo ...
git checkout develop
git merge feature/fase2-instagram-templates
git push origin develop

# Deploy a main (cuando fase completa esté lista):
git checkout main
git merge develop
git push origin main
```

**CRÍTICO para Opción B:**
- ⚠️ **Antes de empezar Fase 2**, hacer: `git checkout develop && git merge project`
- ⚠️ **Cada semana**, sincronizar: `project → develop`
- ⚠️ **Nunca** hacer merge de `develop` a `project` (flujo unidireccional)

---

### **OPCIÓN C: Git Flow con Releases (Más robusto) 🏆**

```
main (producción)
├── develop (desarrollo principal)
│   ├── release/v1.0-fase1
│   ├── release/v2.0-fase2
│   ├── release/v3.0-fase3
│   ├── feature/fase1-*
│   ├── feature/fase2-*
│   └── feature/fase3-*
└── hotfix/* (correcciones urgentes en producción)
```

**Ventajas:**
- ✅ Estructura clara de releases
- ✅ Fácil rollback si algo falla
- ✅ Historial limpio de versiones
- ✅ Branches de release permiten QA/testing antes de producción
- ✅ Escalable a equipos grandes

**Desventajas:**
- ⚠️ Más overhead (más ramas que mantener)
- ⚠️ Puede ser excesivo para proyecto individual

**Flujo de trabajo:**
```bash
# Desarrollo de features (todas van a develop):
git checkout develop
git checkout -b feature/fase1-metricas-posicion
# ... desarrollo ...
git checkout develop
git merge feature/fase1-metricas-posicion

# Cuando Fase 1 esté lista para release:
git checkout develop
git checkout -b release/v1.0-fase1
# Hacer últimos ajustes, actualizar versión, documentación
git commit -m "chore: Prepare release v1.0"

# Mergear a producción:
git checkout main
git merge release/v1.0-fase1
git tag v1.0
git push origin main --tags

# Mergear de vuelta a develop:
git checkout develop
git merge release/v1.0-fase1
git branch -d release/v1.0-fase1

# Hotfix si hay bug crítico en producción:
git checkout main
git checkout -b hotfix/fix-critical-bug
# ... fix ...
git checkout main
git merge hotfix/fix-critical-bug
git tag v1.0.1
git checkout develop
git merge hotfix/fix-critical-bug
```

---

## 🏅 Recomendación Final

Basándome en tu contexto específico (**proyecto académico + SaaS con doble propósito**), mi recomendación es:

### **RECOMENDACIÓN PRINCIPAL: OPCIÓN B (Con rama `project`) 🏆⭐**

**Por qué es PERFECTA para tu caso:**
1. ✅ **Tienes doble audiencia**: Profesor (trabajo académico) vs Clientes (SaaS completo)
2. ✅ **Necesitas entregable académico limpio**: Rama `project` con solo Fase 1 + Fase 3 (sin Instagram)
3. ✅ **Fase 2 es opcional académicamente**: Instagram es valor añadido profesional, no requisito de máster
4. ✅ **Permite desarrollo paralelo**: Puedes trabajar Fase 2 sin afectar código académico
5. ✅ **Justificación clara**: Fácil explicar en memoria: "rama project = core académico, develop = producto completo"

**Estructura:**
```
main (producción completa: todas las fases)
├── develop (académico + profesional: Fase 1 + 2 + 3)
│   └── feature/fase2-* (solo Instagram, skip project)
│
└── project (solo académico: Fase 1 + 3)
    ├── feature/fase1-* (UI/UX y métricas)
    └── feature/fase3-* (IA/ML)
```

**Flujo de entregables:**
- **Memoria de máster**: Código de rama `project` (Fase 1 + 3)
- **Producto SaaS**: Código de rama `develop` o `main` (Fase 1 + 2 + 3)

**Reglas críticas (no negociables):**
```bash
# ✅ PERMITIDO: project → develop (sincronización)
git checkout develop
git merge project

# ❌ PROHIBIDO: develop → project (contaminaría código académico)
# NUNCA hagas esto:
git checkout project
git merge develop  # ❌❌❌
```

**Comandos de sincronización:**
```bash
# Cada vez que completes una feature de Fase 1 o Fase 3:
git checkout develop
git pull origin develop
git merge project
git push origin develop
```

---

### **ALTERNATIVA (si prefieres simplicidad): OPCIÓN A (Simplificada) 🔧**

**Cuándo elegir esta:**
- Prefieres velocidad sobre separación académico/profesional
- No te importa que el código académico incluya features de Instagram
- Confías en documentar en la memoria qué código es académico vs profesional

**Desventajas para tu caso:**
- ❌ Mezcla código académico con profesional (harder to explain)
- ❌ Entregable académico incluye código de Instagram (no es crítico, pero menos limpio)

---

### **FUTURO (cuando tengas usuarios): OPCIÓN C (Git Flow con Releases) 🚀**

**Cuándo migrar:**
- Usuarios reales pagando suscripción
- Equipo de más de 2 personas
- Necesitas QA/staging antes de producción
- Versiones múltiples en paralelo (v1.0 en prod, v2.0 en dev)

---

## 🎯 Flujo de Trabajo Recomendado (Opción B - Con `project`)

### **1. Configuración Inicial**

```bash
# Verificar ramas actuales
git branch -a

# Crear develop si no existe
git checkout -b develop
git push -u origin develop

# Crear project (rama académica) desde develop
git checkout develop
git checkout -b project
git push -u origin project

# Verificar estructura
git branch -a
# Deberías ver:
# * project
#   develop
#   main
#   remotes/origin/project
#   remotes/origin/develop
#   remotes/origin/main

# Proteger ramas en GitHub (si usas GitHub)
# Settings → Branches → Add rule para:
# - main: Require pull request reviews (producción)
# - project: Require pull request reviews (código académico)
# - develop: (opcional) Require pull request reviews
```

---

### **2. Desarrollo de Features**

#### **2.A. Features de Fase 1 o Fase 3 (Core Académico)**

```bash
# Empezar desde PROJECT (rama académica)
git checkout project
git pull origin project

# Crear rama de feature
git checkout -b feature/fase1-metricas-posicion

# Desarrollar...
git add .
git commit -m "feat: Add goalkeeper-specific metrics calculation"

# Push para backup (opcional)
git push -u origin feature/fase1-metricas-posicion
```

#### **2.B. Features de Fase 2 (Instagram - Solo Profesional)**

```bash
# Empezar desde DEVELOP (rama profesional completa)
git checkout develop
git pull origin develop

# IMPORTANTE: Asegurar que develop tiene los cambios de project
git merge project  # Solo si hay cambios nuevos en project

# Crear rama de feature (skip project)
git checkout -b feature/fase2-instagram-templates

# Desarrollar...
git add .
git commit -m "feat: Add pre-match Instagram template generator"

# Push para backup (opcional)
git push -u origin feature/fase2-instagram-templates
```

---

### **3. Finalizar Feature**

#### **3.A. Finalizar Feature de Fase 1 o Fase 3 (Académica)**

```bash
# PASO 1: Mergear a PROJECT (rama académica)
git checkout project
git pull origin project
git merge feature/fase1-metricas-posicion

# Resolver conflictos si los hay
# git status
# (editar archivos conflictivos)
# git add .
# git commit -m "merge: Resolve conflicts from fase1-metricas-posicion"

# Push a project
git push origin project

# PASO 2: Sincronizar PROJECT → DEVELOP
git checkout develop
git pull origin develop
git merge project  # Traer cambios académicos a develop
git push origin develop

# Borrar rama de feature (opcional)
git branch -d feature/fase1-metricas-posicion
git push origin --delete feature/fase1-metricas-posicion
```

**Regla de oro:**
- Fase 1/3: `feature → project → develop` (2 merges)

---

#### **3.B. Finalizar Feature de Fase 2 (Instagram - Solo Profesional)**

```bash
# PASO 1: Mergear DIRECTAMENTE a DEVELOP (skip project)
git checkout develop
git pull origin develop
git merge feature/fase2-instagram-templates

# Resolver conflictos si los hay
git push origin develop

# Borrar rama de feature (opcional)
git branch -d feature/fase2-instagram-templates
git push origin --delete feature/fase2-instagram-templates
```

**Regla de oro:**
- Fase 2: `feature → develop` (1 merge, skip project)

**⚠️ IMPORTANTE:** Features de Fase 2 NUNCA tocan rama `project`

---

### **4. Release a Producción (main)**

```bash
# Cuando Fase X esté completa y testeada
git checkout main
git pull origin main

# Mergear develop → main
git merge develop

# Crear tag de versión
git tag -a v1.0-fase1 -m "Release Fase 1: UI/UX y Métricas"

# Push a producción
git push origin main --tags

# Volver a develop
git checkout develop
```

---

## 📝 Convenciones de Nomenclatura

### **Ramas de Features**

**Formato:** `feature/{fase}-{descripcion-corta}`

**Ejemplos:**
- `feature/fase1-metricas-posicion`
- `feature/fase1-ui-redesign`
- `feature/fase1-player-view`
- `feature/fase2-instagram-templates`
- `feature/fase2-match-detector`
- `feature/fase3-clustering`
- `feature/fase3-knn-recommendations`

### **Ramas de Fixes**

**Formato:** `fix/{descripcion}`

**Ejemplos:**
- `fix/goalkeeper-save-rate-calculation`
- `fix/chart-loading-bug`
- `fix/csv-encoding-issue`

### **Ramas de Hotfix** (solo si usas Git Flow)

**Formato:** `hotfix/{version}-{descripcion}`

**Ejemplos:**
- `hotfix/v1.0.1-critical-crash`
- `hotfix/v1.0.2-data-loading-error`

---

## 🛠️ Comandos Git Útiles

### **Ver estado de ramas**

```bash
# Ver todas las ramas (locales y remotas)
git branch -a

# Ver ramas con último commit
git branch -v

# Ver ramas mergeadas a develop
git branch --merged develop

# Ver ramas NO mergeadas a develop
git branch --no-merged develop
```

---

### **Sincronización**

```bash
# Actualizar todas las referencias remotas
git fetch --all --prune

# Ver diferencias entre ramas
git diff develop..feature/fase1-metricas

# Ver commits en feature que no están en develop
git log develop..feature/fase1-metricas --oneline

# Ver archivos modificados entre ramas
git diff --name-only develop..feature/fase1-metricas
```

---

### **Merge vs Rebase**

**Merge (recomendado para features grandes):**
```bash
git checkout develop
git merge feature/fase1-metricas
# Crea commit de merge (historial completo)
```

**Rebase (para features pequeñas, mantiene historial lineal):**
```bash
git checkout feature/fase1-metricas
git rebase develop
# Resuelve conflictos si los hay
git checkout develop
git merge feature/fase1-metricas  # Fast-forward merge
```

⚠️ **NUNCA** hagas rebase de ramas públicas (develop, main)

---

### **Deshacer cambios**

```bash
# Descartar cambios locales NO commiteados
git checkout -- <file>

# Deshacer último commit (mantener cambios)
git reset --soft HEAD~1

# Deshacer último commit (descartar cambios)
git reset --hard HEAD~1

# Revertir commit específico (crea nuevo commit)
git revert <commit-hash>
```

---

### **Eliminar ramas**

```bash
# Eliminar rama local
git branch -d <branch>

# Eliminar rama remota
git push origin --delete <branch>

## 📊 Visualización del Flujo (Opción B - Dual Purpose)

---

```
main (producción completa)
  |
  o [v0.0 - Estado inicial]
  |
  |\_____ develop (producto completo)
  |       |
  |       |\_____ project (académico)
  |       |       |
  |       |       |\_____ feature/fase1-metricas
  |       |       |       o feat: Add goalkeeper metrics
  |       |       |       o feat: Add defender metrics
  |       |       |      /
  |       |       o [merge fase1-metricas]
  |       |      /
  |       o [merge project → develop]
  |       |
  |       |\_____ feature/fase2-instagram (skip project)
  |       |       o feat: Add pre-match template
  |       |       o feat: Add post-match template
  |       |      /
  |       o [merge fase2-instagram → develop SOLO]
  |      /
  o [v1.0-fase1 + v2.0-fase2 - Release Fase 1 + 2]
  |
  |\_____ develop
  |       |
  |       |\_____ project (académico)
  |       |       |
  |       |       |\_____ feature/fase3-clustering
  |       |       |       o feat: Implement K-Means
  |       |       |       o feat: Add archetype viz
  |       |       |      /
  |       |       o [merge fase3-clustering]
  |       |      /
  |       o [merge project → develop]
  |      /
  o [v3.0-fase3 - Release Fase 3]
```

**Leyenda:**
- 🎓 **Rama `project`**: Solo features académicas (Fase 1 + 3)
- 💼 **Rama `develop`**: Producto completo (Fase 1 + 2 + 3)
- 🚀 **Rama `main`**: Producción estable

**Entregables:**
- **Código académico**: `git checkout project` → Solo Fase 1 + 3
- **Código SaaS completo**: `git checkout main` → Fase 1 + 2 + 3

---

## ✅ Checklist de Buenas Prácticas

### **Antes de crear feature branch:**
- [ ] `git checkout develop`
- [ ] `git pull origin develop`
- [ ] `git checkout -b feature/...`

### **Durante desarrollo:**
- [ ] Commits atómicos (un cambio lógico por commit)
- [ ] Mensajes descriptivos (ver formato abajo)
- [ ] Push frecuente (backup)

### **Antes de merge:**
- [ ] Tests pasan localmente
- [ ] No hay console.logs / print() debug
- [ ] Actualizar develop: `git checkout develop && git pull`
- [ ] Resolver conflictos si los hay

### **Después de merge:**
- [ ] Verificar que develop funciona
- [ ] Borrar rama si ya no es necesaria
- [ ] Documentar cambios en CHANGELOG (si aplica)

---

## 📝 Formato de Commits (Conventional Commits)

**Formato:** `<type>(<scope>): <subject>`

**Types:**
- `feat`: Nueva funcionalidad
- `fix`: Corrección de bug
- `docs`: Cambios en documentación
- `style`: Formato (no afecta código: espacios, comas, etc.)
- `refactor`: Refactorización (ni feat ni fix)
- `test`: Añadir/modificar tests
- `chore`: Tareas de mantenimiento (build, dependencias, etc.)

**Ejemplos:**
```
feat(metrics): Add position-specific goalkeeper metrics
fix(player-view): Fix radar chart not showing for defenders
docs(readme): Update installation instructions
refactor(data): Optimize CSV loading performance
test(metrics): Add unit tests for clustering module
chore(deps): Update Dash to 3.2.1
```

---

## 🚀 Decisión Final para Tu Proyecto

### **Decisión: OPCIÓN B (Con rama `project` para separación académico/profesional) ⭐**

**Razones específicas de tu proyecto:**
1. ✅ **Doble propósito claro**: Trabajo académico (máster) + Producto SaaS
2. ✅ **Entregable académico limpio**: Rama `project` con solo Fase 1 + Fase 3
3. ✅ **Fase 2 no académica**: Instagram es extra profesional, no va en memoria
4. ✅ **Justificación sólida**: Fácil defender en memoria arquitectura de ramas
5. ✅ **Escalabilidad**: Features futuras no-académicas van a `develop` directamente

**Estructura final:**
```
main (producción completa: v1.0-fase1, v2.0-fase2, v3.0-fase3)
├── develop (producto completo: Fase 1 + 2 + 3)
│   └── feature/fase2-* (Instagram, skip project)
│
└── project (académico: Fase 1 + 3)
    ├── feature/fase1-* (UI/UX, Métricas)
    └── feature/fase3-* (IA/ML)
```

**Reglas críticas:**
- **project**: Solo código académico (Fase 1 + 3), siempre debe compilar
- **develop**: Producto completo (recibe merges de `project` + features de Fase 2)
- **main**: Producción estable (recibe merges solo cuando fase completa testeada)
- **Flujo unidireccional**: `project → develop` (NUNCA al revés)

**Entregables:**
- **Memoria académica**: Código de rama `project` + documentación
- **Producto SaaS**: Código de rama `main` (completo)

---

## 📞 Próximos Pasos

### **Inmediatos (ahora):**

1. ✅ **Revisar y aprobar** este documento
2. **Crear ramas base** (si no existen):
   ```bash
   git checkout -b develop
   git push -u origin develop
   git checkout -b project
   git push -u origin project
   ```

### **Al empezar Fase 1:**

3. **Crear primera feature branch** desde `project`:
   ```bash
   git checkout project
   git checkout -b feature/fase1-metricas-posicion
   ```
4. **Desarrollar** Fase 1 features desde `project`
5. **Mergear** cada feature completada: `feature → project → develop`

### **Al empezar Fase 2:**

6. **Sincronizar** `develop` con `project` antes:
   ```bash
   git checkout develop
   git merge project
   ```
7. **Crear features Fase 2** desde `develop` (skip `project`)

### **Al empezar Fase 3:**

8. **Crear features Fase 3** desde `project` (igual que Fase 1)
9. **Mantener sincronización** `project → develop` frecuente

### **Al completar cada fase:**

10. **Release a `main`** con tag de versión:
    ```bash
    git checkout main
    git merge develop
    git tag -a v1.0-fase1 -m "Release Fase 1"
    git push origin main --tags
    ```

### **Para memoria académica:**

11. **Exportar código académico**:
    ```bash
    git checkout project
    git archive -o proyecto-academico.zip HEAD
    ```

---

## 📚 Referencias

- [Git Flow](https://nvie.com/posts/a-successful-git-branching-model/) - Modelo original
- [GitHub Flow](https://docs.github.com/en/get-started/quickstart/github-flow) - Simplificado
- [Conventional Commits](https://www.conventionalcommits.org/) - Formato de commits
- [Semantic Versioning](https://semver.org/) - Versionado (MAJOR.MINOR.PATCH)

---

**Última actualización:** 15 de noviembre de 2025
**Versión:** 2.0 (Actualizado con contexto académico + profesional)
**Estado:** ✅ **APROBADO - Opción B (Con rama `project`)**
**Decisión:** Implementar flujo dual (académico + profesional) con rama `project`
**Próxima revisión:** Al completar Fase 1
