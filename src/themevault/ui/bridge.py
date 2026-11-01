"""Puente Python <-> QML.

La vista no ejecuta logica: pide trabajos al backend y recibe diccionarios
planos. Los trabajos pesados (empaquetar temas, restaurar) corren en un hilo
aparte para que la ventana nunca se congele.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    Property,
    QObject,
    QRunnable,
    QThreadPool,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QDesktopServices

from ..adapters import all_adapters
from ..backup import BackupEngine
from ..detect import detect_host, scan_system_assets
from ..profile import to_manifest as profile_to_manifest
from ..model import CATEGORIES, CATEGORY_LABELS, Manifest
from ..preview import screenshot_tool
from .. import community, screen_restore, store_client, widgets_install
from ..restore import OK, apply_plan, build_plan, missing_assets
from ..screens import detect as detect_screens
from ..widgets import from_items as widgets_from_items
from ..widgets import grouped as group_widgets
from ..util import human_size, which
from .models import BackupListModel, de_label, pretty_date, preview_source, thumb_url
from .thumbs import HERO_RADIUS, HERO_SIZE


class _Signals(QObject):
    done = Signal(str, object)
    error = Signal(str, str)


class _Job(QRunnable):
    def __init__(self, action: str, fn):
        super().__init__()
        self.action = action
        self.fn = fn
        self.signals = _Signals()

    def run(self) -> None:
        try:
            result = self.fn()
        except Exception as exc:  # el hilo no debe morir en silencio
            self.signals.error.emit(self.action, str(exc))
            return
        self.signals.done.emit(self.action, result)


STATUS_TEXT = {
    "backup": "Creando la copia…",
    "plan": "Analizando la copia…",
    "restore": "Restaurando…",
    "verify": "Verificando la integridad…",
    "screens": "Aplicando el layout por pantalla…",
    "installbt": "Instalando widgets…",
    "store_search": "Buscando en la tienda…",
    "store_install": "Instalando desde la tienda…",
    "community": "Cargando la comunidad…",
    "community_apply": "Aplicando el perfil…",
}


class Backend(QObject):
    backupsChanged = Signal()
    busyChanged = Signal()
    statusChanged = Signal()
    backupCreated = Signal("QVariantMap")
    planReady = Signal("QVariantMap")
    restoreFinished = Signal("QVariantMap")
    backupDeleted = Signal(str)
    verified = Signal("QVariantMap")
    screenRestoreFinished = Signal("QVariantMap")
    widgetsInstalled = Signal("QVariantMap")
    storeResults = Signal("QVariantList")
    storeInstalled = Signal("QVariantMap")
    communityProfiles = Signal("QVariantList")
    communityApplied = Signal("QVariantMap")
    failed = Signal(str, str)

    def __init__(self, root: Path | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self.engine = BackupEngine(Path(root) if root else None)
        self._model = BackupListModel(self)
        self._pool = QThreadPool.globalInstance()
        self._jobs: set[_Job] = set()
        self._pending = 0
        self._status = ""
        self.refresh()

    # ------------------------------------------------------------- propiedades

    @Property(QObject, constant=True)
    def backups(self) -> QObject:
        return self._model

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._pending > 0

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Property(int, notify=backupsChanged)
    def backupCount(self) -> int:  # noqa: N802
        return self._model.rowCount()

    @Property(str, notify=backupsChanged)
    def storageSummary(self) -> str:  # noqa: N802
        return self.engine.summary()

    @Property(str, constant=True)
    def rootPath(self) -> str:  # noqa: N802
        return str(self.engine.root)

    # --------------------------------------------------------------- comandos

    @Slot()
    def refresh(self) -> None:
        manifests = self.engine.load_all()
        base = {m.id: str(self.engine.backup_dir(m.id)) for m in manifests}
        self._model.set_manifests(manifests, base)
        self.backupsChanged.emit()

    @Slot(str, str, bool)
    def createBackup(self, label: str, notes: str, preview: bool) -> None:  # noqa: N802
        def work() -> dict:
            manifest = self.engine.create(label=label.strip(), notes=notes.strip(), preview=preview)
            return self._created_payload(manifest)

        self._submit("backup", work)

    @Slot(str)
    def requestPlan(self, backup_id: str) -> None:  # noqa: N802
        def work() -> dict:
            manifest = self.engine.load(backup_id)
            return self._plan_payload(manifest)

        self._submit("plan", work)

    @Slot(str, list, bool)
    def applyRestore(self, backup_id: str, categories: list, safety: bool) -> None:  # noqa: N802
        chosen = [c for c in categories if c in CATEGORIES]

        def work() -> dict:
            manifest = self.engine.load(backup_id)
            store = self.engine.store(backup_id)
            actions = build_plan(manifest, store, only=set(chosen) or None)
            report = apply_plan(actions, store, safety=safety, engine_root=self.engine.root)
            return {
                "id": backup_id,
                "applied": report.applied,
                "total": len(actions),
                "safety": report.safety_id or "",
                "safetyError": report.safety_error or "",
                "failures": [[name, message] for name, message in report.failures],
            }

        self._submit("restore", work)

    @Slot(str, "QVariantList", bool)
    def applyScreenRestore(self, backup_id: str, mapping: list, safety: bool) -> None:  # noqa: N802
        pairs: dict[int, int] = {}
        for entry in mapping:
            try:
                source = int(entry.get("source"))
                target = int(entry.get("target"))
            except (AttributeError, TypeError, ValueError):
                continue
            if target >= 0:
                pairs[source] = target

        def work() -> dict:
            manifest = self.engine.load(backup_id)
            store = self.engine.store(backup_id)
            safety_id = ""
            if safety:
                try:
                    snapshot = BackupEngine(self.engine.root).create(
                        label="Punto de restauracion (pantallas)", preview=False
                    )
                    safety_id = snapshot.id
                except Exception:
                    pass
            result = screen_restore.apply(manifest, store, pairs)
            result["id"] = backup_id
            result["safety"] = safety_id
            return result

        self._submit("screens", work)

    @Slot(str, "QVariantList")
    def installBackupWidgets(self, backup_id: str, ids: list) -> None:  # noqa: N802
        wanted = [str(i) for i in ids]

        def work() -> dict:
            manifest = self.engine.load(backup_id)
            store = self.engine.store(backup_id)
            result = widgets_install.install_from_backup(manifest, store, wanted or None)
            if result["installed"]:
                try:
                    screen_restore.restart_plasma()
                except Exception:
                    pass
            return result

        self._submit("installbt", work)

    @Slot(str)
    def searchStore(self, query: str) -> None:  # noqa: N802
        def work():
            return store_client.search(query)

        self._submit("store_search", work)

    @Slot(int)
    def installStoreWidget(self, item_id: int) -> None:  # noqa: N802
        def work() -> dict:
            return store_client.install(item_id)

        self._submit("store_install", work)

    @Slot(bool)
    def communityRefresh(self, force: bool) -> None:  # noqa: N802
        def work() -> list:
            entries = community.fetch_index(force=force)
            return [
                {
                    "id": e.get("id", ""),
                    "name": e.get("name", ""),
                    "author": e.get("author", ""),
                    "desktop": e.get("desktop", ""),
                    "description": e.get("description", ""),
                    "palette": e.get("palette") or [],
                    "license": e.get("license", ""),
                    "requires": e.get("requires") or {},
                    "settings": e.get("settings", 0),
                    "cover": community.cover_url(e),
                }
                for e in entries
            ]

        self._submit("community", work)

    @Slot(str, bool)
    def communityApply(self, profile_id: str, safety: bool) -> None:  # noqa: N802
        def work() -> dict:
            entries = community.fetch_index()
            entry = next((e for e in entries if e.get("id") == profile_id), None)
            if entry is None:
                raise RuntimeError("ese perfil ya no esta en la comunidad")

            profile = community.fetch_profile(entry)
            manifest = profile_to_manifest(profile)
            actions = build_plan(manifest, None)
            report = apply_plan(actions, None, safety=safety, engine_root=self.engine.root)

            assets = scan_system_assets()
            missing = []
            for kind in ("icons", "cursor"):
                name = profile.requires.get(kind)
                if name and name not in assets.get(kind, []):
                    missing.append(name)

            return {
                "id": profile.id,
                "name": profile.name,
                "applied": report.applied,
                "total": len(actions),
                "blocked": len(report.blocked),
                "failures": [[n, m] for n, m in report.failures],
                "missing": missing,
                "safety": report.safety_id or "",
            }

        self._submit("community_apply", work)

    @Slot(str)
    def deleteBackup(self, backup_id: str) -> None:  # noqa: N802
        try:
            self.engine.delete(backup_id)
        except Exception as exc:
            self.failed.emit("delete", str(exc))
            return
        self.refresh()
        self.backupDeleted.emit(backup_id)

    @Slot(str)
    def verifyBackup(self, backup_id: str) -> None:  # noqa: N802
        def work() -> dict:
            return {"id": backup_id, "problems": self.engine.verify(backup_id)}

        self._submit("verify", work)

    @Slot()
    def openFolder(self) -> None:  # noqa: N802
        self.engine.root.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.engine.root)))

    # ---------------------------------------------------------- datos de vista

    @Slot(str, result="QVariantMap")
    def detail(self, backup_id: str) -> dict:  # noqa: N802
        try:
            manifest = self.engine.load(backup_id)
        except Exception as exc:
            return {"error": str(exc)}
        base = self.engine.backup_dir(manifest.id)
        preview = manifest.preview or {}
        # En el detalle se prefiere la captura limpia; la portada compuesta
        # (con cursor e iconos) queda para la tarjeta de la galeria.
        source = preview_source(manifest, str(base), ("screenshot", "wallpaper", "cover"))
        hero = thumb_url(source, base, size=HERO_SIZE, radius=HERO_RADIUS, top_only=False) if source else ""

        if manifest.widgets or manifest.containers:
            containers = group_widgets(manifest.containers, manifest.widgets)
        else:  # copias viejas: se derivan del appletsrc ya guardado
            layout = widgets_from_items(manifest.items, self.engine.store(manifest.id))
            containers = group_widgets(layout["containers"], layout["widgets"])

        heroes: list[str] = []
        for screen in preview.get("screens") or []:
            rel = screen.get("file")
            if rel and (base / rel).exists():
                heroes.append(QUrl.fromLocalFile(str(base / rel)).toString())
        if not heroes and hero:
            heroes = [hero]

        samples = preview.get("samples") or {}
        sample_icons = [
            QUrl.fromLocalFile(str(base / rel)).toString()
            for rel in samples.get("icons", [])
            if rel and (base / rel).exists()
        ]
        sample_cursor = ""
        if samples.get("cursor") and (base / samples["cursor"]).exists():
            sample_cursor = QUrl.fromLocalFile(str(base / samples["cursor"])).toString()

        panels = []
        for panel in preview.get("panels") or []:
            rel = panel.get("file")
            if not rel or not (base / rel).exists():
                continue
            entry = dict(panel)
            entry["url"] = QUrl.fromLocalFile(str(base / rel)).toString()
            panels.append(entry)

        grouped = manifest.by_category()
        categories = []
        for key in CATEGORIES:
            items = grouped.get(key)
            if not items:
                continue
            categories.append(
                {
                    "name": key,
                    "label": CATEGORY_LABELS[key],
                    "count": len(items),
                    "sizeText": human_size(sum(i.size for i in items)),
                    "items": [
                        {
                            "name": item.name,
                            "sizeText": human_size(item.size) if item.size else "ajuste",
                            "kind": item.kind,
                        }
                        for item in items
                    ],
                }
            )

        host = manifest.host or {}
        distro = host.get("distro") or {}
        skipped = host.get("skipped") or []
        return {
            "error": "",
            "id": manifest.id,
            "title": manifest.label or pretty_date(manifest.created),
            "created": pretty_date(manifest.created),
            "de": manifest.de,
            "deLabel": de_label(manifest.de),
            "distro": distro.get("pretty", "—"),
            "session": host.get("session", "—"),
            "sizeText": human_size(manifest.total_size),
            "itemsText": f"{len(manifest.items)} elementos",
            "hero": hero,
            "heroes": heroes,
            "screens": preview.get("screens") or [],
            "hasHero": bool(hero),
            "palette": list(preview.get("palette") or []),
            "notes": manifest.notes or "",
            "categories": categories,
            "skipped": [{"path": s.get("path", ""), "reason": s.get("reason", "")} for s in skipped],
            "containers": containers,
            "widgetCount": sum(len(c.get("items", [])) for c in containers),
            "themes": manifest.host.get("themes", {}) or preview.get("themes", {}) or {},
            "sampleCursor": sample_cursor,
            "sampleIcons": sample_icons,
            "panels": panels,
        }

    @Slot(result="QVariantMap")
    def systemInfo(self) -> dict:  # noqa: N802
        host = detect_host()
        distro = host["distro"]
        assets = scan_system_assets()
        return {
            "distro": distro.get("pretty", "—"),
            "distroId": distro.get("id", ""),
            "de": de_label(host["de"]),
            "session": host["session"],
            "root": str(self.engine.root),
            "storage": self.engine.summary(),
            "backups": len(self.engine.ids()),
            "adapters": [
                {"id": a.id, "label": a.label, "detected": a.detect()} for a in all_adapters()
            ],
            "tools": self._tools(),
            "assets": {
                "themes": len(assets.get("themes", [])),
                "icons": len(assets.get("icons", [])),
            },
        }

    # ---------------------------------------------------------------- interno

    def _tools(self) -> list[dict]:
        tools = [
            ("dconf", "GNOME / Cinnamon / MATE"),
            ("xfconf-query", "Xfce"),
            ("gsettings", "GNOME"),
            (screenshot_tool() or "-", "capturas de portada"),
        ]
        return [{"name": name, "purpose": purpose, "ok": bool(which(name))} for name, purpose in tools]

    def _submit(self, action: str, fn) -> None:
        self._pending += 1
        self._status = STATUS_TEXT.get(action, "Trabajando…")
        self.busyChanged.emit()
        self.statusChanged.emit()

        job = _Job(action, fn)
        job.signals.done.connect(lambda act, res, j=job: self._on_done(act, res, j))
        job.signals.error.connect(lambda act, msg, j=job: self._on_error(act, msg, j))
        self._jobs.add(job)
        self._pool.start(job)

    def _finish(self) -> None:
        self._pending = max(0, self._pending - 1)
        if self._pending == 0:
            self._status = ""
        self.busyChanged.emit()
        self.statusChanged.emit()

    def _on_done(self, action: str, result, job: "_Job") -> None:
        self._jobs.discard(job)
        self._finish()
        if action == "backup":
            self.refresh()
            self.backupCreated.emit(result)
        elif action == "plan":
            self.planReady.emit(result)
        elif action == "restore":
            self.refresh()
            self.restoreFinished.emit(result)
        elif action == "verify":
            self.verified.emit(result)
        elif action == "screens":
            self.refresh()
            self.screenRestoreFinished.emit(result)
        elif action == "installbt":
            self.widgetsInstalled.emit(result)
        elif action == "store_search":
            self.storeResults.emit(result)
        elif action == "store_install":
            self.storeInstalled.emit(result)
        elif action == "community":
            self.communityProfiles.emit(result)
        elif action == "community_apply":
            self.communityApplied.emit(result)

    def _on_error(self, action: str, message: str, job: "_Job") -> None:
        self._jobs.discard(job)
        self._finish()
        self.failed.emit(action, message)

    # --------------------------------------------------------------- payloads

    @staticmethod
    def _created_payload(manifest: Manifest) -> dict:
        return {
            "id": manifest.id,
            "title": manifest.label or pretty_date(manifest.created),
            "items": len(manifest.items),
            "sizeText": human_size(manifest.total_size),
        }

    def _plan_payload(self, manifest: Manifest) -> dict:
        store = self.engine.store(manifest.id)
        actions = build_plan(manifest, store)

        groups: dict[str, dict] = {}
        for action in actions:
            key = action.item.category
            group = groups.setdefault(
                key,
                {
                    "name": key,
                    "label": CATEGORY_LABELS.get(key, key),
                    "total": 0,
                    "ok": 0,
                    "blocked": 0,
                },
            )
            group["total"] += 1
            if action.status == OK:
                group["ok"] += 1
            else:
                group["blocked"] += 1

        categories = [groups[key] for key in CATEGORIES if key in groups]
        widgets = manifest.widgets
        if not widgets:
            widgets = widgets_from_items(manifest.items, store)["widgets"]

        return {
            "id": manifest.id,
            "title": manifest.label or pretty_date(manifest.created),
            "de": manifest.de,
            "deLabel": de_label(manifest.de),
            "deTotal": len(actions),
            "deApplicable": sum(g["ok"] for g in categories),
            "categories": categories,
            "kde": manifest.de == "kde",
            "screens": [
                {
                    "index": s.get("index", 0),
                    "name": s.get("name", ""),
                    "summary": s.get("summary", ""),
                    "custom": bool(s.get("custom")),
                    "width": s.get("width", 0),
                    "height": s.get("height", 0),
                }
                for s in (manifest.preview.get("screens") or [])
            ],
            "targetScreens": [
                {
                    "index": index,
                    "name": screen.name,
                    "width": screen.width,
                    "height": screen.height,
                }
                for index, screen in enumerate(detect_screens())
            ],
            "missing": missing_assets(manifest),
            "missingWidgets": widgets_install.missing_from_backup(manifest),
        }
