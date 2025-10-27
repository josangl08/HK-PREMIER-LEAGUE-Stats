# Guía de Estilo Visual - Sports Dashboard (Estilo HKFA)

Este documento define las convenciones visuales y de diseño para la interfaz de usuario del Sports Dashboard, inspiradas en el sitio oficial de la Hong Kong Premier League (HKFA). El objetivo es crear una experiencia de usuario coherente, moderna y profesional.

## 1. Paleta de Colores

La paleta se basa en un tema oscuro con un acento de color vibrante para crear contraste y energía.

| Rol                   | Color           | Código Hex | Código RGB        | Uso                                                        |
| --------------------- | --------------- | ---------- | ----------------- | ---------------------------------------------------------- |
| **Fondo Primario**    | Gris Oscuro     | `#18181A`  | `rgb(24, 24, 26)` | Fondos principales de la aplicación y secciones.           |
| **Fondo Secundario**  | Gris Elevado    | `#232326`  | `rgb(35, 35, 38)` | Tarjetas, modales, y elementos elevados sobre el fondo.    |
| **Acento Principal**  | Rojo HKFA       | `#ED1C24`  | `rgb(237, 28, 36)`| Botones primarios, enlaces activos, KPIs y elementos clave. |
| **Texto Principal**   | Blanco Puro     | `#FFFFFF`  | `rgb(255, 255, 255)`| Títulos, párrafos y texto principal sobre fondos oscuros.  |
| **Texto Secundario**  | Gris Claro      | `#A7A7A7`  | `rgb(167, 167, 167)`| Metadatos, fechas, placeholders y texto de menor énfasis.  |
| **Bordes y Divisores**| Gris Sutil      | `#3A3A3C`  | `rgb(58, 58, 60)` | Líneas divisorias sutiles y bordes de componentes.         |

## 2. Tipografía

La tipografía principal es **Roboto**, importada desde Google Fonts. Ofrece una excelente legibilidad y una estética moderna.

### Jerarquía de Texto

| Elemento             | Fuente         | Peso (Weight) | Tamaño (Font Size) | Transformación de Texto |
| -------------------- | -------------- | ------------- | ------------------ | ----------------------- |
| **Título H1**        | `Roboto`       | `700` (Bold)  | `2.5rem` (40px)    | `uppercase`             |
| **Título H2**        | `Roboto`       | `700` (Bold)  | `2rem` (32px)      | `uppercase`             |
| **Título H3**        | `Roboto`       | `700` (Bold)  | `1.5rem` (24px)    | `none`                  |
| **Cuerpo de Texto**  | `Roboto`       | `400` (Regular)| `1rem` (16px)      | `none`                  |
| **Subtítulos/Labels** | `Roboto`       | `500` (Medium)| `0.875rem` (14px)  | `uppercase`             |
| **Enlaces**          | `Roboto`       | `500` (Medium)| `1rem` (16px)      | `none`                  |

## 3. Layout y Espaciado

Se utiliza un sistema de espaciado consistente para mantener un ritmo visual limpio y ordenado.

*   **Contenedor Principal:** Ancho máximo de `1400px`, centrado en la página.
*   **Padding de Secciones:** `32px` (vertical y horizontal) para dar espacio al contenido.
*   **Gap entre Componentes:** `16px` de espacio entre tarjetas o elementos similares.
*   **Radio de Borde (Border Radius):** Se utiliza un radio estándar de `12px` para tarjetas y `8px` para botones y inputs.

## 4. Componentes

### Botones (`<button>`)

| Tipo          | Fondo           | Texto     | Borde                   | Hover                                   |
|---------------|-----------------|-----------|-------------------------|-----------------------------------------|
| **Primario**  | `#ED1C24`       | `#FFFFFF` | `none`                  | Ligero aumento de brillo (`brightness(1.1)`) |
| **Secundario**| `transparent`   | `#ED1C24` | `1px solid #ED1C24`     | Fondo `#ED1C24`, Texto `#FFFFFF`        |

### Tarjetas (`<Card>`)

*   **Fondo:** `#232326` (Gris Elevado)
*   **Sombra:** `none` (se basa en el contraste de color, no en sombras).
*   **Borde:** `none`.
*   **Radio de Borde:** `12px`.
*   **Padding interno:** `24px`.

### Barra de Navegación (`<Navbar>`)

*   **Fondo:** `rgba(24, 24, 26, 0.8)` (Fondo Primario con transparencia).
*   **Filtro de Fondo:** `backdrop-filter: blur(10px)` para un efecto de "vidrio esmerilado".
*   **Posición:** Fija en la parte superior (`position: sticky`).
*   **Enlaces:**
    *   **Estado normal:** Texto `#A7A7A7` (Gris Claro).
    *   **Estado activo/hover:** Texto `#FFFFFF` (Blanco Puro) y un sutil subrayado rojo.

### Inputs y Dropdowns

*   **Fondo:** `transparent`.
*   **Borde:** `1px solid #3A3A3C`.
*   **Texto:** `#A7A7A7` para el placeholder, `#FFFFFF` para el texto introducido.
*   **Foco (Focus):** El borde cambia al color de acento `#ED1C24`.

## 5. Iconografía

Se debe utilizar una librería de iconos moderna y limpia como **Feather Icons** o **Bootstrap Icons**. Los iconos deben ser consistentes en grosor y estilo.

*   **Color:** `#A7A7A7` (Gris Claro).
*   **Tamaño:** `20px` por defecto.
*   **Hover:** El color cambia a `#FFFFFF` (Blanco Puro).

---
*Última actualización: 27 de octubre de 2024*

