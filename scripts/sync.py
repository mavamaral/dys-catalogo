#!/usr/bin/env python3
"""Regenera productos.json y fotos/ a partir de la base del catálogo (artefacto de Claude).

Uso (desde la raíz del repo):

  1) python3 scripts/sync.py plan  --db <carpeta_db>
     Muestra (en JSON) las fotos "seed/..." que hay que bajar del artefacto
     porque son nuevas o cambiaron de ruta. Las que ya están exportadas no hace
     falta volver a bajarlas.

  2) python3 scripts/sync.py build --db <carpeta_db> [--seed <carpeta_con_seed>] [--force-date]
     Escribe productos.json y fotos/*.jpg. Solo toca archivos si algo cambió y
     solo actualiza la fecha "actualizado" si cambiaron productos o fotos.
     Última línea: "CAMBIOS: si" o "CAMBIOS: no".

<carpeta_db> es la carpeta con un .json por documento de la colección
"productos" (lo que deja ArtifactData list con out_dir; se aceptan tanto
<carpeta_db>/*.json como <carpeta_db>/productos/*.json).
<carpeta_con_seed> es la carpeta donde quedó "seed/xxx.jpg" al leer los
archivos publicados del artefacto (Artifact read con paths + out_dir).
"""
import argparse
import base64
import datetime as dt
import hashlib
import io
import json
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT_JSON = ROOT / "productos.json"
FOTOS = ROOT / "fotos"
MANIFEST = FOTOS / "fuentes.json"
MAX_SIDE = 600
QUALITY = 80
BA_TZ = dt.timezone(dt.timedelta(hours=-3))  # Argentina no usa horario de verano
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def load_docs(db: Path):
    d = db / "productos" if (db / "productos").is_dir() else db
    docs = []
    for f in sorted(d.glob("*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        doc = doc.get("data", doc) if isinstance(doc.get("data"), dict) else doc
        docs.append((f.stem, doc))
    if not docs:
        sys.exit(f"No encontré documentos en {d}")
    return docs


def load_manifest():
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def source_key(foto: str) -> str:
    """Identifica la fuente de la foto sin guardar la data URL entera."""
    if foto.startswith("data:"):
        return "data:" + hashlib.sha256(foto.encode()).hexdigest()[:16]
    return foto


def to_jpg(raw: bytes) -> bytes:
    im = Image.open(io.BytesIO(raw))
    im.load()
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=QUALITY, optimize=True, progressive=True)
    return buf.getvalue()


def decode_data_url(u: str) -> bytes:
    _, _, payload = u.partition(",")
    return base64.b64decode(payload)


def cmd_plan(args):
    man = load_manifest()
    need = set()
    for doc_id, d in load_docs(Path(args.db)):
        foto = str(d.get("foto") or "")
        if not foto.startswith("seed/"):
            continue
        prev = man.get(doc_id)
        if not prev or prev.get("src") != foto or not (FOTOS / f"{doc_id}.jpg").exists():
            need.add(foto)
    print(json.dumps(sorted(need)))


def clean(v):
    return re.sub(r"\s+", " ", str(v or "")).strip()


def cmd_build(args):
    docs = load_docs(Path(args.db))
    seed_dir = Path(args.seed) if args.seed else None
    man = load_manifest()
    new_man = {}
    FOTOS.mkdir(exist_ok=True)
    fotos_changed = False
    productos = []
    problemas = []

    for doc_id, d in docs:
        if not SAFE_ID.match(doc_id):
            problemas.append(f"id raro, salteado: {doc_id!r}")
            continue
        foto = str(d.get("foto") or "")
        key = source_key(foto) if foto else ""
        dest = FOTOS / f"{doc_id}.jpg"
        raw = None
        if foto.startswith("data:"):
            raw = decode_data_url(foto)
        elif foto.startswith("seed/") and seed_dir and (seed_dir / foto).is_file():
            raw = (seed_dir / foto).read_bytes()

        foto_rel = ""
        if raw is not None:
            try:
                jpg = to_jpg(raw)
            except Exception as e:  # imagen corrupta: seguimos sin foto
                problemas.append(f"foto ilegible ART. {d.get('art')}: {e}")
                jpg = None
            if jpg:
                if not dest.exists() or dest.read_bytes() != jpg:
                    dest.write_bytes(jpg)
                    fotos_changed = True
                new_man[doc_id] = {"src": key}
        elif foto and man.get(doc_id, {}).get("src") == key and dest.exists():
            new_man[doc_id] = man[doc_id]  # ya exportada, sin cambios
        elif foto:
            problemas.append(f"falta la foto {foto} (ART. {d.get('art')}): bajala y volvé a correr")
            if dest.exists():
                new_man[doc_id] = man.get(doc_id, {"src": key})

        if dest.exists() and doc_id in new_man:
            v = hashlib.sha1(dest.read_bytes()).hexdigest()[:8]
            foto_rel = f"fotos/{doc_id}.jpg?v={v}"

        try:
            precio = round(float(d.get("precio") or 0))
        except (TypeError, ValueError):
            precio = 0
        try:
            orden = float(d.get("orden") or 0)
            orden = int(orden) if orden.is_integer() else orden
        except (TypeError, ValueError):
            orden = 0
        productos.append({
            "id": doc_id,
            "art": clean(d.get("art")),
            "nombre": clean(d.get("nombre")),
            "detalle": clean(d.get("detalle")),
            "precio": precio,
            "categoria": clean(d.get("categoria")),
            "animal": clean(d.get("animal")) or "Perros",
            "orden": orden,
            "etiqueta": clean(d.get("etiqueta")),
            "sinStock": bool(d.get("sinStock")),
            "foto": foto_rel,
        })

    productos.sort(key=lambda p: (p["art"], p["id"]))

    # Borrar fotos de productos que ya no existen
    keep = {f"{i}.jpg" for i in new_man}
    for f in FOTOS.glob("*.jpg"):
        if f.name not in keep:
            f.unlink()
            fotos_changed = True

    try:
        prev = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    except FileNotFoundError:
        prev = {}
    changed = fotos_changed or prev.get("productos") != productos
    fecha = prev.get("actualizado")
    if changed or not fecha or args.force_date:
        fecha = dt.datetime.now(BA_TZ).date().isoformat()
    out = {"actualizado": fecha, "productos": productos}
    text = json.dumps(out, ensure_ascii=False, indent=1) + "\n"
    if not OUT_JSON.exists() or OUT_JSON.read_text(encoding="utf-8") != text:
        OUT_JSON.write_text(text, encoding="utf-8")
        changed = True
    man_text = json.dumps(dict(sorted(new_man.items())), indent=1) + "\n"
    if not MANIFEST.exists() or MANIFEST.read_text(encoding="utf-8") != man_text:
        MANIFEST.write_text(man_text, encoding="utf-8")

    for p in problemas:
        print("AVISO:", p)
    sin_foto = sum(1 for p in productos if not p["foto"])
    print(f"{len(productos)} productos · {sum(p['sinStock'] for p in productos)} sin stock · "
          f"{sin_foto} sin foto · actualizado {fecha}")
    print("CAMBIOS:", "si" if changed else "no")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--db", required=True)
    b = sub.add_parser("build")
    b.add_argument("--db", required=True)
    b.add_argument("--seed")
    b.add_argument("--force-date", action="store_true")
    args = ap.parse_args()
    {"plan": cmd_plan, "build": cmd_build}[args.cmd](args)


if __name__ == "__main__":
    main()
