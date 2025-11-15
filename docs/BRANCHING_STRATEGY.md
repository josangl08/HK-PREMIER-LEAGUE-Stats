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

**Razonamiento:**
- Todo llega a `dev` en el orden correcto de desarrollo
- Solo las fases 1 y 3 (core del proyecto) pasan por `project`
- La fase 2 (contenido social) va directamente a `dev`

---

## ✅ Análisis de la Propuesta

### **Puntos Fuertes:**

1. ✅ **Separación lógica**: Distingue entre features core (1 y 3) y features adicionales (2)
2. ✅ **Flexibilidad**: Permite desarrollo paralelo
3. ✅ **Concepto correcto**: Usar rama intermedia para integración

### **Puntos a Mejorar:**

1. ⚠️ **Complejidad de mantenimiento**: Dos ramas de integración (`dev` y `project`) requiere sincronización constante
2. ⚠️ **Riesgo de divergencia**: Si `project` y `dev` no se sincronizan frecuentemente, pueden divergir
3. ⚠️ **Dependencias cruzadas**: Si Fase 2 depende de código de Fase 1 (que está en `project`), necesitas merge previo
4. ⚠️ **Flujo de merge confuso**: La notación `main → dev → project` puede interpretarse al revés (debería ser `features → project → dev → main`)

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

Basándome en tu contexto (proyecto académico + SaaS individual), mi recomendación es:

### **FASE INICIAL (ahora - próximos 2 meses): OPCIÓN A (Simplificada) ⭐**

**Por qué:**
- Estás trabajando solo (o equipo muy pequeño)
- Necesitas velocidad de desarrollo
- Las 3 fases tienen cierta interdependencia (Fase 2 depende de UI de Fase 1)
- Menos overhead, más foco en código

**Estructura:**
```
main
└── develop
    └── feature/fase{X}-{descripcion}
```

**Cuándo hacer merges a main:**
- ✅ Al completar Fase 1 (UI/UX sólida)
- ✅ Al completar Fase 2 (contenido Instagram funcionando)
- ✅ Al completar Fase 3 (IA implementada)

---

### **FASE DE CRECIMIENTO (futuro): OPCIÓN C (Git Flow con Releases) 🏆**

**Cuándo migrar:**
- Cuando tengas usuarios reales
- Cuando necesites QA antes de deploy
- Si se une más gente al equipo
- Cuando necesites mantener versión estable en producción + desarrollar v2.0 en paralelo

---

### **Si INSISTES en separar core de extras: OPCIÓN B (Con project) 🔧**

**Condiciones:**
- ⚠️ **DEBES** sincronizar `project → develop` semanalmente (mínimo)
- ⚠️ **NUNCA** mergear `develop → project` (flujo unidireccional)
- ⚠️ **ANTES de empezar Fase 2**, hacer merge de `project → develop` para tener features de Fase 1

**Comandos críticos:**
```bash
# Cada viernes o al terminar feature core:
git checkout develop
git pull origin develop
git pull origin project
git merge project
git push origin develop
```

---

## 🎯 Flujo de Trabajo Recomendado (Opción A)

### **1. Configuración Inicial**

```bash
# Verificar ramas
git branch -a

# Crear develop si no existe
git checkout -b develop
git push -u origin develop

# Proteger ramas en GitHub (si usas GitHub)
# Settings → Branches → Add rule
# - main: Require pull request reviews
# - develop: (opcional) Require pull request reviews
```

---

### **2. Desarrollo de Features**

```bash
# Siempre empezar desde develop actualizado
git checkout develop
git pull origin develop

# Crear rama de feature (nomenclatura más abajo)
git checkout -b feature/fase1-metricas-posicion

# Desarrollar...
# (hacer commits atómicos y descriptivos)
git add .
git commit -m "feat: Add goalkeeper-specific metrics calculation"

# Push para backup (opcional)
git push -u origin feature/fase1-metricas-posicion
```

---

### **3. Finalizar Feature**

```bash
# Actualizar develop antes de merge
git checkout develop
git pull origin develop

# Mergear feature
git merge feature/fase1-metricas-posicion

# Resolver conflictos si los hay
# git status
# (editar archivos conflictivos)
# git add .
# git commit -m "merge: Resolve conflicts from fase1-metricas-posicion"

# Push a develop
git push origin develop

# Borrar rama local (opcional, mantener para historial)
git branch -d feature/fase1-metricas-posicion

# Borrar rama remota (opcional)
git push origin --delete feature/fase1-metricas-posicion
```

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

## 📊 Visualización del Flujo (Opción A)

```
main (producción)
  |
  o [v0.0 - Estado inicial]
  |
  |\_____ develop
  |       |
  |       o [commit inicial]
  |       |\_____ feature/fase1-metricas
  |       |       o feat: Add goalkeeper metrics
  |       |       o feat: Add defender metrics
  |       |      /
  |       o [merge fase1-metricas]
  |       |
  |       |\_____ feature/fase1-ui-redesign
  |       |       o feat: Update color palette
  |       |       o feat: Add KPI cards
  |       |      /
  |       o [merge fase1-ui-redesign]
  |      /
  o [v1.0-fase1 - Release Fase 1]
  |
  |\_____ develop
  |       |\_____ feature/fase2-instagram-templates
  |       |       o feat: Add pre-match template
  |       |       o feat: Add post-match template
  |       |      /
  |       o [merge fase2-instagram]
  |      /
  o [v2.0-fase2 - Release Fase 2]
  |
  |\_____ develop
  |       |\_____ feature/fase3-clustering
  |       |       o feat: Implement K-Means
  |       |       o feat: Add archetype visualization
  |       |      /
  |       o [merge fase3-clustering]
  |      /
  o [v3.0-fase3 - Release Fase 3]
```

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

### **Recomendación: OPCIÓN A (Simplificada)**

**Razones:**
1. ✅ Eres el único desarrollador (o equipo muy pequeño)
2. ✅ Las 3 fases tienen interdependencias
3. ✅ Necesitas velocidad de desarrollo
4. ✅ No tienes usuarios en producción aún (puedes permitirte inestabilidad temporal en main)
5. ✅ Menos overhead = más tiempo para codear

**Estructura final:**
```
main (releases estables: v1.0-fase1, v2.0-fase2, v3.0-fase3)
└── develop (desarrollo activo)
    ├── feature/fase1-*
    ├── feature/fase2-*
    └── feature/fase3-*
```

**Reglas:**
- **develop** siempre debe compilar y correr (sin crashes)
- **main** solo recibe merges cuando una fase está COMPLETA y TESTEADA
- **features** pueden estar rotas mientras desarrollas (es normal)

---

## 📞 Próximos Pasos

1. **Confirmar** que estás de acuerdo con Opción A (o indicar si prefieres B o C)
2. **Crear rama develop** si no existe
3. **Empezar feature branches** para Fase 1:
   - `feature/fase1-metricas-posicion`
   - `feature/fase1-ui-redesign`
   - `feature/fase1-visualizations`
4. **Actualizar este documento** según decisión final
5. **Commit y push** de este documento a la rama actual

---

## 📚 Referencias

- [Git Flow](https://nvie.com/posts/a-successful-git-branching-model/) - Modelo original
- [GitHub Flow](https://docs.github.com/en/get-started/quickstart/github-flow) - Simplificado
- [Conventional Commits](https://www.conventionalcommits.org/) - Formato de commits
- [Semantic Versioning](https://semver.org/) - Versionado (MAJOR.MINOR.PATCH)

---

**Última actualización:** 15 de noviembre de 2025
**Estado:** Pendiente de aprobación
**Próxima revisión:** Al completar Fase 1
