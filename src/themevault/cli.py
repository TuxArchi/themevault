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

    if manifest.keybinds:
        print(f"\n  {bold('Atajos de teclado')} {dim(f'({len(manifest.keybinds)})')}")
        for entry in manifest.keybinds:
            combo = entry.get("combo") or entry.get("key") or ""
            action = " ".join(
                part for part in (entry.get("dispatcher", ""), entry.get("arg", "")) if part
            )
            details = []
            if entry.get("submap"):
                details.append(f"submapa {entry['submap']}")
            if entry.get("description"):
                details.append(str(entry["description"]))
            suffix = dim("  · " + " · ".join(details)) if details else ""
            print(f"    {combo:<22} {action}{suffix}")

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
        ("hyprctl", "hyprland"),
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
    extra = f"  ·  {len(manifest.keybinds)} atajos" if manifest.keybinds else ""
    print(f"  {len(manifest.items)} items  ·  {human_size(manifest.total_size)}{extra}")
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
    if report.applied and manifest.de in ("kde", "gnome", "hyprland"):
        if manifest.de == "hyprland":
            print(dim("\nEjecuta `hyprctl reload` o reinicia la sesion para aplicar los cambios."))
        else:
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

    from .hypr import keybinds_from_items

    layout = widgets_from_items(manifest.items, store)
    manifest.containers = layout["containers"]
    manifest.widgets = layout["widgets"]
    manifest.keybinds = keybinds_from_items(manifest.items, store)

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
    print(
        f"  {len(manifest.containers)} contenedores · {len(manifest.widgets)} widgets"
        f" · {len(manifest.keybinds)} atajos"
    )
    print(f"  portada: {'si' if cover else 'no disponible'}")
    return 0


def cmd_export_profile(args: argparse.Namespace) -> int:
    from pathlib import Path

    from .profile import build_profile, export_bundle, is_handle, output_dir, validate

    if not args.author:
        print(red("Falta --author (tu usuario de GitHub, sin @)."))
        return 2
    if not is_handle(args.author):
        print(red("--author debe ser tu usuario de GitHub (sin @, sin espacios)."))
        return 2

    engine = BackupEngine(args.root)
    manifest = engine.resolve(args.id)
    store = engine.store(manifest.id)

    name = args.name or manifest.label or manifest.display_name()
    profile, dropped = build_profile(
        manifest,
        store,
        name=name,
        author=args.author,
        license=args.license,
        description=args.description or manifest.notes,
        include_cover=args.with_cover,
    )

    problems = validate(profile)
    if problems:
        print(red("El perfil no pasó la validación:"))
        for problem in problems:
            print(f"  · {problem}")
        return 1

    base = Path(args.out).expanduser() if args.out else Path.cwd()
    out = output_dir(base, profile)
    export_bundle(profile, out, manifest=manifest, store=store)

    print(green("Perfil generado") + f"  {bold(profile.id)}")
    print(f"  {out}")
    print(f"  {len(profile.settings)} ajustes · escritorio {profile.desktop} · licencia {profile.license}")
    if profile.requires:
        print("  requiere: " + ", ".join(f"{k}={v}" for k, v in profile.requires.items()))
    for note in dropped:
        print(dim(f"  · {note}"))
    print(dim("\nRevisá profile.json antes de publicarlo."))
    print(dim(f"Cuando esté listo: themevault publish-profile {out}"))
    return 0


def cmd_publish_profile(args: argparse.Namespace) -> int:
    from pathlib import Path

    from . import publish as pub

    folder = Path(args.folder).expanduser()
    profile, problems = pub.load(folder)
    if profile is None or problems:
        print(red("El perfil no se puede publicar:"))
        for problem in problems:
            print(f"  · {problem}")
        return 1

    print(green("Perfil válido") + f"  {bold(profile.id)}")
    print(
        f"  {len(profile.settings)} ajustes · escritorio {profile.desktop} · "
        f"licencia {profile.license} · portada {'sí' if profile.cover else 'no'}"
    )

    mismatch = pub.author_mismatch(profile)
    if mismatch:
        if not args.allow_author:
            print(red(f"El autor no coincide: {mismatch}."))
            print(
                dim(
                    "Usá --allow-author si sos maintainer y publicás/importás "
                    "en nombre de otra persona."
                )
            )
            return 1
        print(dim(f"Autor distinto al de gh ({mismatch}); se permite por --allow-author."))

    repo = Path(args.repo).expanduser() if args.repo else pub.default_repo()
    if not (repo / "profiles").is_dir():
        print(f"Clonando el repositorio de perfiles en {repo}…")
        try:
            pub.clone(repo)
        except pub.PublishError as exc:
            print(red(f"No se pudo clonar: {exc}"))
            print(dim("Pasá --repo con un clon existente si ya lo tenés."))
            return 1

    if profile.id in pub.index_ids(repo) and not args.force:
        print(red(f"Ya hay un perfil con id «{profile.id}» en el repositorio."))
        print(dim("Cambiá el nombre, o usá --force para reemplazarlo (solo si es tuyo)."))
        return 1

    try:
        target = pub.stage(repo, folder)
        summary = pub.rebuild_index(repo)
    except pub.PublishError as exc:
        print(red(f"No se pudo preparar el repositorio: {exc}"))
        return 1

    print(green("Perfil copiado") + f"  {target}")
    for line in summary.splitlines():
        print(dim(f"  {line}"))

    branch = args.branch or f"perfil/{profile.id}"
    if not args.pr:
        print("\nSiguientes pasos:")
        print(f"  cd {repo}")
        print(f"  git checkout -b {branch}")
        print(f"  git add profiles/{profile.id} index.json")
        print(f'  git commit -m "perfil: {profile.id}"')
        print(f"  git push -u origin {branch}")
        print("  gh pr create --fill")
        return 0

    if not args.yes:
        answer = input(f"¿Crear la rama {branch}, subirla y abrir el PR? [s/N] ")
        if answer.strip().lower() not in ("s", "si", "sí", "y", "yes"):
            print("Cancelado. El perfil quedó copiado en el clon local.")
            return 1

    try:
        pub.prepare_branch(repo, profile.id, branch)
        pub.push_branch(repo, branch)
        url = pub.open_pr(repo, profile)
    except pub.PublishError as exc:
        print(red(f"No se pudo abrir el PR: {exc}"))
        print(dim("El commit local quedó hecho; revisá la salida de git."))
        return 1

    print(green("Pull request abierto") + (f"  {url}" if url else ""))
    print(dim("CI valida esquema, índice y ausencia de datos personales."))
    return 0


def cmd_install_widgets(args: argparse.Namespace) -> int:
    from . import widgets_install

    engine = BackupEngine(args.root)
    manifest = engine.resolve(args.id)
    store = engine.store(manifest.id)
    try:
        result = widgets_install.install_from_backup(manifest, store, args.only)
    except RuntimeError as exc:
        print(red(f"Error: {exc}"))
        return 1

    for entry in result["installed"]:
        print(green(f"  instalado  {entry['id']}"))
    for entry in result["failed"]:
        print(red(f"  fallo      {entry['id']}: {entry['message']}"))
    if result["installed"]:
        print(dim("\nReinicia plasmashell (o la sesion) para verlo en el panel."))
    return 0 if not result["failed"] else 1


def cmd_widgets(args: argparse.Namespace) -> int:
    from . import store_client

    try:
        if args.action == "search":
            found = store_client.search(args.target)
            if not found:
                print(dim("Sin resultados."))
                return 0
            for item in found:
                print(f"  {cyan(str(item['id'])):>10}  {item['name']}  {dim(item['author'])}")
            return 0
        info = store_client.install(int(args.target))
        print(green(f"Instalado {info['name']} ({info['version']})"))
        return 0
    except (store_client.StoreError, ValueError) as exc:
        print(red(f"Error: {exc}"))
        return 1


def cmd_revert_layout(args: argparse.Namespace) -> int:
    """Vuelve al appletsrc anterior guardado por el restore por pantalla."""
    from . import screen_restore

    if screen_restore.revert():
        print(green("Layout anterior restaurado y plasmashell reiniciado."))
        return 0
    print(red("No hay un respaldo .themevault.bak del layout."))
    return 1


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
    backup.add_argument(
        "-a",
        "--adapter",
        action="append",
        help="forzar adaptador (gnome/kde/xfce/hyprland)",
    )
    backup.add_argument(
        "--no-preview",
        action="store_true",
        help="no guardar captura ni fondo: la copia queda solo con configuracion",
    )
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

    widgets = sub.add_parser("widgets", parents=[common], help="buscar o instalar widgets de la tienda")
    widgets.add_argument("action", choices=("search", "install"))
    widgets.add_argument("target", help="texto a buscar o id del widget")
    widgets.set_defaults(func=cmd_widgets)

    export = sub.add_parser(
        "export-profile",
        parents=[common],
        help="genera un perfil compartible (sin datos personales) desde una copia",
    )
    export.add_argument("id")
    export.add_argument("--name", help="nombre visible del perfil")
    export.add_argument("--author", default="", help="autor (obligatorio)")
    export.add_argument("--license", default="CC-BY-SA-4.0", choices=(
        "CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0", "MIT", "GPL-3.0-or-later",
    ))
    export.add_argument("--description", default="")
    export.add_argument("--with-cover", action="store_true", help="incluir la captura (puede mostrar tu fondo)")
    export.add_argument("--out", help="carpeta de salida")
    export.set_defaults(func=cmd_export_profile)

    publish = sub.add_parser(
        "publish-profile",
        parents=[common],
        help="valida un perfil y prepara el pull request al repositorio",
    )
    publish.add_argument("folder", help="carpeta con profile.json")
    publish.add_argument("--repo", help="clon del repositorio (por defecto, en la caché)")
    publish.add_argument("--branch", default="", help="nombre de la rama")
    publish.add_argument(
        "--pr", action="store_true", help="crear la rama, subirla y abrir el PR con gh"
    )
    publish.add_argument("--yes", action="store_true", help="no pedir confirmación con --pr")
    publish.add_argument(
        "--force", action="store_true", help="reemplazar un perfil con el mismo id"
    )
    publish.add_argument(
        "--allow-author",
        action="store_true",
        help="permitir un autor distinto al usuario de gh (maintainers)",
    )
    publish.set_defaults(func=cmd_publish_profile)

    install = sub.add_parser(
        "install-widgets",
        parents=[common],
        help="instala widgets que vienen dentro de una copia",
    )
    install.add_argument("id")
    install.add_argument("--only", action="append", help="instalar solo estos ids")
    install.set_defaults(func=cmd_install_widgets)

    revert = sub.add_parser(
        "revert-layout",
        parents=[common],
        help="deshace el ultimo restore por pantalla (usa el .bak)",
    )
    revert.set_defaults(func=cmd_revert_layout)

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
