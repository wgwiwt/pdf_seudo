# Hero "Pacientes, no papeleo" — Spec de replicación

Referencia: hero de letters.app (Framer). Este documento describe **exactamente** cómo reconstruirlo en HTML/CSS/React. Cambia las copys por las de tu producto pero **respeta la estructura, paleta, tipografía y proporciones**.

---

## 1. Estructura general (de fuera hacia dentro)

```
<section class="hero">           ← contenedor con gradiente azul + radios grandes
  <div class="hero__copy">        ← bloque superior centrado: título + subtítulo + CTA
    <h1>Título grande</h1>
    <p>Subtítulo con énfasis selectivos</p>
    <a class="cta">CTA</a>
  </div>
  <div class="hero__envelope">    ← composición inferior: sobre + 2 cartas rotadas
    <svg class="envelope-base" />
    <article class="card card--before"> … </article>  ← rotada -3deg, fuente manuscrita
    <article class="card card--after">  … </article>  ← rotada +1deg, fuente tipográfica
    <svg class="envelope-flap" />
    <svg class="envelope-stamp" />
  </div>
</section>
```

Es **un hero único de pantalla completa** (1431×778 capturado; debe ser fluido). El sobre con las dos cartas está **pegado al borde inferior** y es lo primero que ve el usuario después del título.

---

## 2. Contenedor `.hero`

| Propiedad | Valor |
|---|---|
| `background` | `linear-gradient(180deg, #779BC1 0%, #9ABFDA 58%, #CBDFEC 100%)` |
| `border-radius` | `28px 28px 48px 48px` (más redondeado abajo que arriba) |
| `padding` | `120px 0 0` desktop · `140px 20px 20px` móvil (<810px) |
| `display` | `flex; flex-direction: column; justify-content: space-between; align-items: center` |
| `overflow` | `hidden` |
| `min-height` | `100vh` o `778px` (lo que aplique) |

**Importante:** los tres stops del gradiente son colores planos en azul cielo, **sin saturación alta y sin transiciones bruscas**. No uses morados ni verdes. Stop intermedio en **58 %**, no 50 %.

---

## 3. Tipografía

Fuente principal: **Open Runde** (open-source, geometric rounded sans). Disponible en `https://github.com/lauridskern/open-runde`. Si no puedes incluirla, sustituye por **Nunito** o **Manrope** (similares geométricas redondeadas). **No uses Inter ni Roboto.**

Fuente manuscrita (solo carta "Antes"): **The Doctor FreeVersion** o cualquier handwriting suelto (Caveat, Kalam). **No uses scripts elegantes tipo Dancing Script.**

### Escala exacta

| Rol | Fuente | Tamaño | Peso | Line-height | Color |
|---|---|---|---|---|---|
| H1 (`Pacientes, no papeleo.`) | Open Runde | **80px** | 600 | **90%** | `#FFFFFF` |
| Subtítulo `<p>` | Open Runde | **18px** | 400 | 140% | `#FFFFFF` |
| Énfasis dentro del subtítulo | Open Runde | 18px | **600** | 140% | `#FFFFFF` |
| Texto CTA | Open Runde Semibold | 17px | 600 | 23.8px (~140%) | `#FFFFFF` |
| Carta "Antes" (manuscrita) | The Doctor FreeVersion | **14px** | 400 | 19.6px (140%) | `#BEBECC` |
| Carta "Después" (tipográfica) | Open Runde Regular | **13px** | 400 | 18.9px (140%) | `#60606C` |
| Captions `Antes` / `Después` | Open Runde | 17px | **600** | 140% | `#60606C` |

**H1 con line-height 90% es deliberado** — el título debe sentirse compacto, casi tocando entre líneas. No uses 1.2.

### Énfasis en el subtítulo
Algunas palabras clave van en **semibold** dentro del mismo párrafo (no en otra línea, no en otro color). En el original son: *"tu propio estilo"*, *"ilimitadas"*, *"más alta calidad"*, *"5 horas semanales"*. Adapta a tu copy: elige **2–4 frases cortas** que quieras resaltar y ponlas en `<span style="font-weight:600">`.

---

## 4. CTA "Regístrate gratis"

```css
.cta {
  background: #070709;          /* casi negro, NO #000 puro */
  color: #FFFFFF;
  border: 2px solid rgba(255, 255, 255, 0.1);  /* borde interior sutil */
  border-radius: 100px;          /* píldora completa */
  padding: 14px 28px;            /* aprox; ajustar al alto del texto */
  font: 600 17px/1.4 'Open Runde Semibold', sans-serif;
  box-shadow:
    0  1px 2px 0 rgba(36,36,40,0.10),
    0  3px 3px 0 rgba(36,36,40,0.09),
    0  6px 4px 0 rgba(36,36,40,0.05),
    0 11px 4px 0 rgba(36,36,40,0.01);
  cursor: pointer;
  transition: transform .15s ease, box-shadow .15s ease;
}
.cta:hover { transform: translateY(-1px); }
```

La **sombra acumulada en capas** es lo que da el aspecto premium. **No la simplifiques a una sola `box-shadow`**.

---

## 5. Las dos cartas (Antes / Después)

Son el elemento más distintivo. Son **dos `<article>` en posición absoluta**, cada una con rotación distinta, encima de un SVG de sobre que ocupa la parte inferior.

### Card "Antes" (manuscrita)
- `transform: rotate(-3deg)`
- Fondo: blanco `#FFFFFF`
- `border-radius: ~12px`
- `box-shadow: 0 20px 40px -10px rgba(0,0,0,.15), 0 4px 8px rgba(0,0,0,.06)`
- Padding interior: ~24px
- Tamaño aprox: 280–320px ancho × 200–240px alto
- Contenido: párrafo en fuente manuscrita, color `#BEBECC` (gris muy claro, como tinta envejecida)
- Debajo de la card o encima, badge/caption "Antes" con icono pequeño a la izquierda

### Card "Después" (limpia)
- `transform: rotate(+1deg)` (ligeramente la otra dirección)
- Misma base (blanco, mismo radius, misma sombra)
- Solapada con la "Antes" — la "Después" va **un poco delante y a la derecha**
- Contenido: mismo párrafo pero **transcrito a texto limpio** en Open Runde Regular 13px, color `#60606C`
- Caption "Después" con icono check

### Layout de las dos cards
- Posicionadas **abajo-centro** del hero
- Se superponen ~30–40% de su ancho
- La "Antes" a la izquierda (rotación negativa), la "Después" a la derecha (rotación positiva)
- Ambas **emergen del borde superior del sobre SVG** (parecen estar saliendo de él)

---

## 6. Sobre (envelope) decorativo

SVG ilustrado que ocupa **toda la parte inferior** del hero y se corta visualmente en el borde inferior. Tres piezas:

1. **Base del sobre** (rectángulo con solapa inferior) — color blanco roto o azul claro, line-art negro fino
2. **Solapa superior** (la "V" que se abre) — encima de las cartas en orden de capas, pero las cartas asoman por arriba
3. **Sello/estampilla** (pequeño cuadrado decorativo arriba a la derecha)

**Estilo del line-art:** trazo fino (1.5–2px), negro `#000`, ligeramente "pixelado" (efecto `image-rendering: pixelated` en el original — es opcional).

> Si no tienes el SVG, **usa un placeholder** (rectángulo blanco con borde negro 2px) y deja un TODO en el código para sustituirlo por el ilustración final.

---

## 7. Composición vertical del hero (de arriba a abajo)

```
┌─────────────────────────────────────────┐
│  padding-top: 120px                      │
│                                          │
│         H1 (80px, blanco)                │
│         ↕ ~24px                          │
│         subtítulo (18px, blanco)         │
│         ↕ ~32px                          │
│         [ CTA píldora negra ]            │
│                                          │
│         ↕ flex space-between             │
│                                          │
│      ┌──────┐  ┌──────┐                  │
│      │Antes │  │Despué│  ← cards         │
│      └──────┘  └──────┘                  │
│   ╲___________________╱  ← sobre SVG     │
└─────────────────────────────────────────┘
   border-radius: 28 28 48 48
```

Usa `justify-content: space-between` para que el bloque de texto se quede arriba y el sobre quede abajo automáticamente.

---

## 8. Responsive

| Breakpoint | Cambios |
|---|---|
| `<810px` | `padding: 140px 20px 20px`. H1 baja a **48–56px**. Subtítulo a 16px. Cards se apilan verticalmente (o se reducen al 70%). |
| `<480px` | Cards al 60%, sobre escalado. H1 a **40px**. |

El gradiente y los colores **no cambian** entre breakpoints.

---

## 9. Tokens de color (copiar a tu sistema)

```css
:root {
  --sky-1: #779BC1;     /* gradient top */
  --sky-2: #9ABFDA;     /* gradient mid (stop 58%) */
  --sky-3: #CBDFEC;     /* gradient bottom */
  --ink:   #070709;     /* CTA bg, line-art */
  --paper: #FFFFFF;     /* card bg */
  --text-on-card: #60606C;  /* "Después" body, captions */
  --text-handwritten: #BEBECC; /* "Antes" body */
  --border-soft: rgba(255,255,255,0.1);
}
```

---

## 10. Checklist de fidelidad (antes de dar por hecho el componente)

- [ ] Gradiente con stop intermedio en **58%**, no 50%.
- [ ] `border-radius` **asimétrico**: 28px arriba, 48px abajo.
- [ ] H1 con `line-height: 90%` (compacto).
- [ ] Énfasis en subtítulo son **semibold inline**, no color distinto.
- [ ] CTA con **4 capas de sombra** acumuladas, no una sola.
- [ ] Borde de 2px `rgba(255,255,255,0.1)` en el CTA (visible pero sutil).
- [ ] Card "Antes" rotada `-3deg`, "Después" `+1deg`.
- [ ] Las cards **se solapan** y asoman por encima del sobre.
- [ ] Fuente manuscrita real (no script elegante) en la card "Antes".
- [ ] Sin gradientes adicionales, sin glow, sin partículas, sin blur backgrounds.

---

## 11. Qué adaptar para tu proyecto (anonimaizer)

Mantén **toda la estructura visual**, cambia:
- **Copy del H1**: a tu propuesta de valor en 3–4 palabras.
- **Copy del subtítulo**: misma fórmula (1 frase + frase de beneficio con énfasis).
- **CTA**: tu acción primaria.
- **Contenido de las cartas**: la metáfora "antes vs después" probablemente funciona para anonimización (texto con datos personales vs texto anonimizado). Si es así, **la card "Antes" debería resaltar nombres/datos en otro color** (ej. rojo suave `#D4574A`) para que se vean los datos sensibles, y la "Después" mostrar los mismos con `[REDACTED]` o tachados.

---

## 12. Stack sugerido para Antigravity

- **React + Tailwind** o **React + CSS modules** (cualquiera vale, el spec es framework-agnóstico)
- Componente único `<Hero />` con sub-componentes `<LetterCard variant="before|after" />` y `<EnvelopeSVG />`
- Fuentes vía `@font-face` o Google Fonts (Nunito/Manrope como fallback)
- Sin animaciones complejas en v1 — solo `hover` en el CTA

Adjunto archivo `referencia.html` en este mismo proyecto con una implementación funcional para que verifiques visualmente la fidelidad antes de pasarle el spec al agente.
