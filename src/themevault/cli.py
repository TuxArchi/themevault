"""Interfaz de linea de comandos de ThemeVault.

La GUI (fase 2) va a consumir exactamente las mismas clases del core: la CLI
no es un atajo, es el motor completo.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .adapters import all_adapters, detected_adapters, get_adapter
from .backup import BackupEngine, current_themes
from .detect import detect_host, scan_system_assets
from .model import CATEGORIES, CATEGORY_LABELS, KIND_FILE, KIND_TREE, Manifest
from .preview import screenshot_tool
from .cover import build_cover
from .restore import BLOCKED, OK, WARN, apply_plan, build_plan, missing_assets, summarize
from .widgets import container_summary, from_items as widgets_from_items
from .util import human_size, run, which


# ------------------------------------------------------------------ formateo

def _paint(text: str, code: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def bold(text: str) -> str:
    return _paint(text, "1")


def dim(text: str) -> str:
    return _paint(text, "2")


def green(text: str) -> str:
    return _paint(text, "32")


def yellow(text: str) -> str:
    return _paint(text, "33")


def red(text: str) -> str:
    return _paint(text, "31")


def cyan(text: str) -> str:
    return _paint(text, "36")


STATUS_LABEL = {
    OK: green("[ok]"),
    WARN: yellow("[!] "),
    BLOCKED: red("[x] "),
    "failed": red("[x] "),
}


def _print_manifest(manifest: Manifest, *, verbose: bool = False) -> None:
    print(f"{bold(manifest.display_name())}  {dim(manifest.id)}")
    distro = manifest.host.get("distro", {})
    print(
        f"  Sistema   {distro.get('pretty', '?')}  ·  {manifest.de}"
        f"  ·  {manifest.host.get('session', '?')}"
    )
    print(f"  Creada    {manifest.created}")
    print(f"  Tamano    {human_size(manifest.total_size)}  ({len(manifest.items)} items)")

    palette = manifest.preview.get("palette") or []
    if palette:
        print(f"  Paleta    {'  '.join(palette)}")
    if manifest.preview.get("wallpaper"):
        print(f"  Fondo     {manifest.preview['wallpaper']}")
    if manifest.preview.get("screenshot"):
        print(f"  Captura   {manifest.preview['screenshot']}")
    if manifest.notes:
        print(f"  Nota      {manifest.notes}")

    if manifest.containers or manifest.widgets:
        print(f"\n  {bold('Widgets y paneles')}")
        widgets = manifest.widgets
        for container in manifest.containers:
            inside = [w for w in widgets if w.get("container") == container["name"]]
            if not inside:
                continue
            summary = container_summary(container)
            print(f"    {container['name']}" + (f"  {dim(summary)}" if summary else ""))
            for widget in inside:
                mark = green("●") if widget.get("installed", True) else yellow("●")
                suffix = dim("  (no instalado)") if not widget.get("installed", True) else ""
                print(f"      {mark} {widget['position']}. {widget['name']}{suffix}")

    grouped = manifest.by_category()
    for category in CATEGORIES:
        items = grouped.get(category)
        if not items:
            continue
        size = sum(item.size for item in items)
        print(f"\n  {bold(CATEGORY_LABELS[category])} ({len(items)}, {human_size(size)})")
        if verbose:
            for item in items:
                label = item.name if len(item.name) <= 52 else item.name[:49] + "..."
                print(f"    · {label:<54} {human_size(item.size):>9}")


# ------------------------------------------------------------------ comandos

def cmd_detect(args: argparse.Namespace) -> int:
    host = detect_host()
    distro = host["distro"]
    print(bold("Sistema"))
    print(f"  Distro    {distro.get('pretty')}  ({distro.get('id')} {distro.get('version')})")
    print(f"  Escritorio {host['de']}  ·  sesion {host['session']}")
    if host.get("desktop_env"):
        print(f"  XDG_CURRENT_DESKTOP {host['desktop_env']}")

    print(bold("\nAdaptadores"))
    for adapter in all_adapters():
        mark = green("si") if adapter.detect() else dim("no")
        print(f"  {adapter.id:<10} {adapter.label:<14} detectado: {mark}")
    if not detected_adapters():
        print(yellow("  Ningun adaptador activo: usa --adapter <id> al respaldar."))

    print(bold("\nHerramientas"))
    tools = [
        ("dconf", "gnome/cinnamon/mate"),
        ("xfconf-query", "xfce"),
        ("gsettings", "gnome"),
        (screenshot_tool() or "-", "capturas de portada"),
    ]
    for name, purpose in tools:
        state = green("ok") if which(name) else dim("falta")
        print(f"  {name:<14} {state:<6} {dim(purpose)}")

    assets = scan_system_assets()
    print(bold("\nActivos instalados"))
    for kind, names in assets.items():
        preview = ", ".join(names[:6]) + ("..." if len(names) > 6 else "")
        print(f"  {kind:<8} {len(names):>3}  {dim(preview)}")

    engine = BackupEngine(args.root)
    print(bold("\nCopias"))
    print(f"  {engine.summary()}")
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    engine = BackupEngine(args.root)
    adapters = None
    if args.adapter:
        adapters = []
        for adapter_id in args.adapter:
            adapter = get_adapter(adapter_id)
            if adapter is None:
                ids = ", ".join(a.id for a in all_adapters())
                print(red(f"Adaptador desconocido: {adapter_id}. Disponibles: {ids}"))
                return 2
            adapters.append(adapter)

    print(dim("Recolectando configuracion..."))
    manifest = engine.create(
        adapters=adapters,
        label=args.message or "",
        preview=not args.no_preview,
    )

    print(green("Copia creada") + f"  {bold(manifest.id)}")
    print(f"  {len(manifest.items)} items  ·  {human_size(manifest.total_size)}")
    skipped = manifest.host.get("skipped") or []
    if skipped:
        print(yellow(f"  {len(skipped)} elementos omitidos:"))
        for entry in skipped[:5]:
            print(dim(f"    · {entry['path']}: {entry['reason']}"))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    engine = BackupEngine(args.root)
    manifests = engine.load_all()
    if not manifests:
        print(dim("Todavia no hay copias. Crea una con: themevault backup"))
        return 0

    print(f"{bold('Copias')}  {dim(engine.summary())}\n")
    for manifest in manifests:
        palette = manifest.preview.get("palette") or []
        swatch = "".join(_paint("  ", f"48;2;{_rgb(c)}") for c in palette) if palette else ""
        label = manifest.display_name()
        if len(label) > 22:
            label = label[:21] + "…"
        print(f"  {label:<22} {cyan(manifest.id):<32} {manifest.de:<12} "
              f"{human_size(manifest.total_size):>9}  {swatch}")
    return 0


def _rgb(hex_color: str) -> str:
    value = hex_color.lstrip("#")
    return ";".join(str(int(value[i : i + 2], 16)) for i in (0, 2, 4))


def cmd_show(args: argparse.Namespace) -> int:
    engine = BackupEngine(args.root)
    manifest = engine.resolve(args.id)
    _print_manifest(manifest, verbose=True)
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    engine = BackupEngine(args.root)
    manifest = engine.resolve(args.id)
    store = engine.store(manifest.id)

    only = set(args.only) if args.only else None
    exclude = set(args.exclude) if args.exclude else None
    unknown = ((only or set()) | (exclude or set())) - set(CATEGORIES)
    if unknown:
        print(red(f"Categorias desconocidas: {', '.join(sorted(unknown))}"))
        print(dim(f"Validas: {', '.join(CATEGORIES)}"))
        return 2

    actions = build_plan(manifest, store, only=only, exclude=exclude)
    if not actions:
        print(yellow("No hay nada que restaurar con esos filtros."))
        return 1

    print(f"{bold('Restaurar')} {manifest.display_name()}  {dim(manifest.id)}\n")
    print("  " + summarize(actions))

    for action in actions:
        if action.status in (WARN, BLOCKED):
            print(f"  {STATUS_LABEL[action.status]} {action.item.name}: {action.message}")

    restored = {
        action.item.name
        for action in actions
        if action.status == OK and action.item.kind in (KIND_FILE, KIND_TREE)
    }
    missing = missing_assets(manifest, restored)
    if missing:
        shown = ", ".join(missing[:8]) + ("..." if len(missing) > 8 else "")
        print(yellow(f"\n  Aviso: faltan en este sistema {len(missing)} temas/iconos:"))
        print(dim(f"  {shown}"))
        print(dim("  Se restauran los archivos, pero si el tema activo no existe se vera el fallback."))

    saved_widgets = manifest.widgets or widgets_from_items(manifest.items, store)["widgets"]
    missing_widgets = [w["name"] for w in saved_widgets if not w.get("installed", True)]
    if missing_widgets:
        shown = ", ".join(missing_widgets[:8]) + ("..." if len(missing_widgets) > 8 else "")
        print(yellow(f"\n  Aviso: {len(missing_widgets)} widgets no estan instalados en este sistema:"))
        print(dim(f"  {shown}"))
        print(dim("  Se restaura su configuracion, pero apareceran como no disponibles."))

    if args.dry_run:
        print(dim("\nDry-run: no se aplico ningun cambio."))
        return 0

    if not args.yes:
        if not sys.stdin.isatty():
            print(red("\nHace falta --yes para restaurar sin confirmacion interactiva."))
            return 2
        answer = input("\n¿Aplicar la restauracion? [s/N] ").strip().lower()
        if answer not in ("s", "si", "sí", "y", "yes"):
            print(dim("Cancelado."))
            return 1

    print()
    report = apply_plan(actions, store, safety=not args.no_safety, engine_root=args.root)
    if report.safety_id:
        print(dim(f"Punto de restauracion previo: {report.safety_id}"))
    elif report.safety_error:
        print(yellow(f"Sin punto de restauracion: {report.safety_error}"))

    print(green(f"{report.applied} items restaurados"))
    if report.failures:
        print(red(f"{len(report.failures)} fallaron"))
        for name, message in report.failures:
            print(f"  {red('·')} {name}: {message}")
    if report.applied and manifest.de in ("kde", "gnome"):
        print(dim("\nReinicia la sesion (o el escritorio) para ver todos los cambios."))
    return 0 if report.ok else 1


def cmd_delete(args: argparse.Namespace) -> int:
    engine = BackupEngine(args.root)
    manifest = engine.resolve(args.id)
    if not args.yes:
        if not sys.stdin.isatty():
            print(red("Hace falta --yes para borrar sin confirmacion."))
            return 2
        answer = input(f"¿Borrar la copia {manifest.id}? [s/N] ").strip().lower()
        if answer not in ("s", "si", "sí", "y", "yes"):
            print(dim("Cancelado."))
            return 1
    engine.delete(manifest.id)
    print(green(f"Copia borrada: {manifest.id}"))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    engine = BackupEngine(args.root)
    manifest = engine.resolve(args.id)
    problems = engine.verify(manifest.id)
    if not problems:
        print(green(f"Copia intacta: {manifest.id}"))
        return 0
    print(red(f"{len(problems)} problemas en {manifest.id}"))
    for problem in problems:
        print(f"  · {problem}")
    return 1


def cmd_ui(args: argparse.Namespace) -> int:
    try:
        from .ui.app import main as gui_main
    except ImportError:
        print(red("Falta PySide6. Instala con: pip install 'themevault[gui]'"))
        return 2
    argv: list[str] = []
    if args.root:
        argv += ["--root", str(args.root)]
    if args.backup:
        argv += ["--backup", args.backup]
    return gui_main(argv)


def cmd_rebuild(args: argparse.Namespace) -> int:
    """Regenera portada y widgets de una copia existente."""
    engine = BackupEngine(args.root)
    manifest = engine.resolve(args.id)
    store = engine.store(manifest.id)
    base = engine.backup_dir(manifest.id)

    layout = widgets_from_items(manifest.items, store)
    manifest.containers = layout["containers"]
    manifest.widgets = layout["widgets"]

    preview = manifest.preview or {}
    desktop = base / preview["screenshot"] if preview.get("screenshot") else None
    wallpaper = base / preview["wallpaper"] if preview.get("wallpaper") else None
    themes = manifest.host.get("themes") or preview.get("themes") or current_themes()
    if themes and not manifest.host.get("themes"):
        manifest.host["themes"] = themes

    cover = build_cover(
        desktop,
        wallpaper,
        themes,
        base,
        palette=preview.get("palette", []),
    )
    if cover:
        preview.update(cover)
        manifest.preview = preview

    engine.save(manifest)

    print(green("Copia actualizada") + f"  {bold(manifest.id)}")
    print(f"  {len(manifest.containers)} contenedores · {len(manifest.widgets)} widgets")
    print(f"  portada: {'si' if cover else 'no disponible'}")
    return 0


def cmd_path(args: argparse.Namespace) -> int:
    engine = BackupEngine(args.root)
    print(engine.root)
    if args.open:
        run(["xdg-open", str(engine.root)])
    return 0


# ------------------------------------------------------------------ argumentos

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="themevault",
        description="Respaldo y restauracion de la personalizacion del escritorio Linux.",
    )
    parser.add_argument("--version", action="version", version=f"themevault {__version__}")
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="directorio de copias (por defecto ~/.local/share/themevault)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Permite escribir `themevault ui --root X` ademas de `themevault --root X ui`.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", type=Path, default=argparse.SUPPRESS, help=argparse.SUPPRESS)

    sub.add_parser("detect", parents=[common], help="muestra distro, escritorio y herramientas").set_defaults(func=cmd_detect)

    ui = sub.add_parser("ui", parents=[common], help="abre la interfaz grafica")
    ui.add_argument("--backup", help="abrir directamente el detalle de una copia")
    ui.set_defaults(func=cmd_ui)

    backup = sub.add_parser("backup", parents=[common], help="crea una copia del estado actual")
    backup.add_argument("-m", "--message", help="etiqueta descriptiva")
    backup.add_argument("-a", "--adapter", action="append", help="forzar adaptador (gnome/kde/xfce)")
    backup.add_argument("--no-preview", action="store_true", help="no generar portada")
    backup.set_defaults(func=cmd_backup)

    listing = sub.add_parser("list", parents=[common], help="lista las copias")
    listing.set_defaults(func=cmd_list)

    show = sub.add_parser("show", parents=[common], help="detalle de una copia")
    show.add_argument("id")
    show.set_defaults(func=cmd_show)

    restore = sub.add_parser("restore", parents=[common], help="restaura una copia")
    restore.add_argument("id")
    restore.add_argument("--dry-run", action="store_true", help="solo mostrar el plan")
    restore.add_argument("--only", action="append", help="restaurar solo estas categorias")
    restore.add_argument("--exclude", action="append", help="omitir estas categorias")
    restore.add_argument("--no-safety", action="store_true", help="no crear punto de restauracion previo")
    restore.add_argument("-y", "--yes", action="store_true", help="no pedir confirmacion")
    restore.set_defaults(func=cmd_restore)

    delete = sub.add_parser("delete", parents=[common], help="borra una copia")
    delete.add_argument("id")
    delete.add_argument("-y", "--yes", action="store_true")
    delete.set_defaults(func=cmd_delete)

    rebuild = sub.add_parser("rebuild", parents=[common], help="regenera portada y widgets de una copia")
    rebuild.add_argument("id")
    rebuild.set_defaults(func=cmd_rebuild)

    verify = sub.add_parser("verify", parents=[common], help="verifica la integridad de una copia")
    verify.add_argument("id")
    verify.set_defaults(func=cmd_verify)

    path = sub.add_parser("path", parents=[common], help="muestra (y opcionalmente abre) el directorio de copias")
    path.add_argument("--open", action="store_true")
    path.set_defaults(func=cmd_path)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(red(f"Error: {exc}"))
        return 1
    except KeyboardInterrupt:
        print(dim("\nInterrumpido."))
        return 130


if __name__ == "__main__":
    sys.exit(main())
