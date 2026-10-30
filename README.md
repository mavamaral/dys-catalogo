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
| `CNAME` | Dominio propio para GitHub Pages |

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
- Requiere Python 3 con Pillow (`pip install pillow`).
- Para probar la página en la compu: `python3 -m http.server` y abrir `http://localhost:8000`.
