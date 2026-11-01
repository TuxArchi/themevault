# Seguridad

## Versiones soportadas

| Versión | Soporte |
| ------- | ------- |
| 0.1.x   | ✅      |

## Cómo reportar una vulnerabilidad

**No abras un issue público.** Usá
[*Security → Report a vulnerability*](https://github.com/TuxArchi/themevault/security/advisories/new)
para abrir un aviso privado.

Incluí:

- versión de ThemeVault y de Python;
- distribución, escritorio y sesión (X11/Wayland);
- pasos para reproducir y el impacto que imaginás;
- logs o capturas si ayudan.

Respondemos dentro de los 7 días y coordinamos la divulgación.

## Qué hace la aplicación (y qué no)

Para evaluar un reporte sirve tener claro el modelo de seguridad:

- **Solo escribe dentro de `$HOME`.** Cualquier item cuya ruta quede fuera del
  home se bloquea en el plan de restauración.
- **Nunca pide `sudo` ni escribe en `/usr`.** Los temas del sistema se
  referencian por nombre, no se copian.
- **No usa la red.** Ni telemetría ni actualizaciones automáticas.
- **Restaurar es reversible**: antes de aplicar se crea una copia del estado
  actual.
- **Lee configuración del escritorio** (dconf, xfconf, archivos INI) y ejecuta
  utilidades del sistema (`dconf`, `xfconf-query`, `kreadconfig6`,
  `kscreen-doctor`, `rsvg-convert`, herramientas de captura). No ejecuta nada
  que venga dentro de una copia.

Quedan fuera de alcance los problemas que requieran que un atacante ya controle
tu cuenta de usuario o tu sesión gráfica.
