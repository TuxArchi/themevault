# Cómo contribuir a ThemeVault

Gracias por querer aportar. Este documento explica cómo está armado el proyecto
y qué se espera de un cambio.

> ¿No venís a escribir código? También sirve reportar bugs con buenos datos,
> probar en un escritorio que no tengamos o **invitar un café**:
> [ko-fi.com/tuxarchi](https://ko-fi.com/tuxarchi).

## Puesta en marcha

```bash
git clone https://github.com/TuxArchi/themevault.git
cd themevault
python3 -m venv .venv
.venv/bin/pip install -e '.[gui,dev]'
.venv/bin/python -m pytest -q
.venv/bin/themevault detect
.venv/bin/themevault ui
```

Sin `[gui]` la app funciona igual por CLI; los tests de la interfaz se saltean
solos si falta PySide6.

## Arquitectura en 30 segundos

```
adaptador por DE  ->  Collector  ->  BlobStore (manifest + blobs)
                                        |
                              restore: plan -> aplicar -> rollback
```

- **No agregues lógica de un DE fuera de `adapters/`.** El core no sabe qué es
  Plasma ni GNOME.
- **Nada de `sudo`.** La aplicación solo escribe dentro de `$HOME`.
- **Todo lo que se restaure debe pasar por `build_plan()`**, para que aparezca
  en el `--dry-run` y respete los bloqueos por ruta.

## Agregar un entorno nuevo

1. Creá `src/themevault/adapters/tuentorno.py` heredando de `Adapter`.
2. Implementá `_collect()` (usa `collector.add_file`, `add_tree`, `add_dconf`,
   `add_setting`), `themes()` y, si aplica, `preview_sources()`.
3. Registralo en `adapters/__init__.py`.
4. Sumá un test con datos de ejemplo en `tests/test_widgets.py` o uno nuevo.
5. Probá en una máquina real: `themevault backup` y después `restore --dry-run`.

## Estilo

- Python 3.10+, `from __future__ import annotations`, tipado donde aporte.
- Identificadores en inglés, textos de interfaz en español.
- Sin dependencias nuevas en el core (solo stdlib). `Pillow`/`PySide6` son
  opcionales y viven detrás de extras.
- Los mensajes de la CLI usan los helpers de color de `cli.py`; no imprimas
  ANSI a mano.

## Tests

```bash
.venv/bin/python -m pytest -q
```

Los tests no tocan tu escritorio: usan `HOME` temporales y `monkeypatch` para
las rutas del sistema. Si tu cambio toca rutas reales, agregá uno que falle sin
el arreglo.

## Pull requests

- Un cambio por PR, con título en imperativo (`fix: ...`, `feat: ...`,
  `docs: ...`).
- Contá **qué probaste y en qué distribución/escritorio**.
- Si tocás la interfaz, adjuntá una captura.
- CI tiene que pasar (tests en 3.10 / 3.12 / 3.13 + arranque de la GUI).

## Reportar bugs

Usá la plantilla de issue. Lo que más ayuda:

- salida de `themevault --version` y `themevault detect`;
- distribución y versión, escritorio y sesión (X11/Wayland);
- pasos exactos y qué esperabas ver;
- si es visual, una captura.

## Código de conducta

Al participar aceptás el [código de conducta](CODE_OF_CONDUCT.md).
