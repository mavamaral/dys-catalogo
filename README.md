# DYS Online · Pedidos mayoristas

Página pública donde los clientes mayoristas arman su pedido y lo mandan por WhatsApp.
Se publica con GitHub Pages en **https://mayoristas.dysonline.com.ar**.

| Archivo | Qué es |
|---|---|
| `index.html` | La página completa (estilos y código adentro) |
| `productos.json` | Productos exportados del catálogo privado + fecha `actualizado` |
| `fotos/` | Fotos JPG de ~600 px, una por producto (`<id>.jpg`); `fuentes.json` es interno del script |
| `assets/` | Logo e íconos de contacto |
| `scripts/sync.py` | Regenera `productos.json` y `fotos/` desde la base del artefacto |
| `vendedores.json` | Vendedores y sus WhatsApp (se edita a mano; la sincronización no lo toca) |
| `CNAME` | Dominio propio para GitHub Pages |

## Links por vendedor

| Link | El pedido llega a |
|---|---|
| https://mayoristas.dysonline.com.ar/ | DYS Online (11 6566-6568) |
| https://mayoristas.dysonline.com.ar/?v=leandro-varela | Leandro Varela |
| https://mayoristas.dysonline.com.ar/?v=daniel-saracchi | Daniel Saracchi |

El navegador del cliente recuerda el vendedor: si después entra sin `?v=`, el pedido
sigue yendo al mismo vendedor. Si entra con otro `?v=`, se reemplaza. Un código que no
existe en `vendedores.json` manda el pedido al número general.

### Cómo agregar, editar o borrar un vendedor

Editá `vendedores.json` en GitHub (abrí el archivo → ícono del lápiz → *Commit changes*):

```json
{
  "general": { "nombre": "DYS Online", "whatsapp": "5491165666568" },
  "vendedores": [
    { "codigo": "leandro-varela", "nombre": "Leandro Varela", "whatsapp": "5491153232875" },
    { "codigo": "daniel-saracchi", "nombre": "Daniel Saracchi", "whatsapp": "5491131594583" }
  ]
}
```

- **Agregar:** copiá una línea de `vendedores`, cambiá los tres datos y separala con una coma
  de la anterior (la última línea va sin coma). El link es `https://mayoristas.dysonline.com.ar/?v=<codigo>`.
- **Editar:** cambiá `nombre` o `whatsapp`. Si cambiás el `codigo`, el link viejo deja de andar.
- **Borrar:** eliminá la línea (y la coma que sobre). Sus clientes pasan al número general.
- `codigo`: minúsculas, sin espacios ni acentos (usá guiones). `whatsapp`: 549 + código de área sin 0 + número sin 15, todo junto.
- Los cambios se ven en uno o dos minutos. Si el archivo queda mal escrito, todos los pedidos van al número general:
  podés revisarlo pegándolo en https://jsonlint.com.

## Pedido

- Pedido mínimo: **$200.000 sin IVA** (`MIN_ORDER` en `index.html`). Hasta llegar, el botón de WhatsApp queda desactivado.
- Datos obligatorios: Nombre/Comercio, CUIT (11 números), Teléfono, Localidad, Retira/Envío y,
  si es Envío, Dirección. Se guardan en el navegador para el próximo pedido.

## Cómo se actualiza

Los datos salen de la base del catálogo privado (artefacto de Claude
`https://claude.ai/artifact/UesiHXTsmwhgKjQgvWBeAq`, colección `productos`). Esa base
solo se puede leer desde Claude (herramientas *ArtifactData* y *Artifact*), por eso la
sincronización la hace una **tarea programada de Claude** todos los días a las 7:00
(hora de Buenos Aires), que sigue los pasos de abajo y hace commit solo si cambió algo.

### Hacerlo a mano (un paso)

Abrí una sesión de Claude Code sobre este repositorio y escribí:

> Sincronizá el catálogo siguiendo el README.

(O desde claude.ai → Tareas programadas → "Sincronizar catálogo DYS" → *Ejecutar ahora*.)

### Pasos de la sincronización (para Claude)

1. `ArtifactData` → `action: "list"`, `url: https://claude.ai/artifact/UesiHXTsmwhgKjQgvWBeAq`,
   `collection: "productos"`, `query: {"limit": 1000}`, `out_dir: "/tmp/dys/db"`.
   Si devuelve `next_cursor`, seguir pidiendo con ese cursor al mismo `out_dir`.
2. `python3 scripts/sync.py plan --db /tmp/dys/db` → imprime una lista JSON de rutas `seed/...`.
3. Si la lista no está vacía: `Artifact` → `action: "read"`, misma `url`, `paths: <esa lista>`
   (hasta 256 por llamada), `out_dir: "/tmp/dys/src"`.
4. `python3 scripts/sync.py build --db /tmp/dys/db --seed /tmp/dys/src`
   (si hubo `AVISO: falta la foto …`, bajar esas rutas y repetir este paso).
5. Si la última línea dice `CAMBIOS: si`:
   `git add -A productos.json fotos && git commit -m "Actualizar catálogo AAAA-MM-DD" && git push origin main`.
   Si dice `CAMBIOS: no`, no hacer nada.

Notas:
- La fecha "Precios actualizados al …" es la del último día en que algo cambió
  (precio, stock, producto o foto), no la de la última revisión.
- Requiere Python 3 con Pillow. Si `python3 -c "import PIL"` falla:
  `python3 -m pip install --target /tmp/pylib pillow` y `export PYTHONPATH=/tmp/pylib`.
- Para probar la página en la compu: `python3 -m http.server` y abrir `http://localhost:8000`.
