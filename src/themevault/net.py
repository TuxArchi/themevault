"""Utilidades de red comunes: contexto TLS con el almacén de CA del sistema.

El binario empaquetado (PyInstaller) trae su propio OpenSSL, compilado con
`OPENSSLDIR=/usr/lib/ssl`. En distribuciones como Arch o Fedora ese directorio
no existe o no tiene los certificados, así que la verificación TLS falla aunque
el sistema sí tenga un almacén válido. Acá se busca ese almacén y, si hace
falta, se crea el contexto con `cafile` explícito.
"""

from __future__ import annotations

import os
import ssl
from pathlib import Path

# Rutas habituales del almacén de CA según la distribución.
CANDIDATES = (
    "/etc/ssl/certs/ca-certificates.crt",  # Debian, Ubuntu, Arch, openSUSE
    "/etc/pki/tls/certs/ca-bundle.crt",  # Fedora, RHEL, CentOS
    "/etc/ssl/ca-bundle.pem",  # openSUSE
    "/etc/ssl/cert.pem",  # Alpine, macOS
    "/etc/ca-certificates/extracted/tls-ca-bundle.pem",
    "/usr/local/etc/openssl/cert.pem",  # macOS (Homebrew, Intel)
)


def ca_bundle() -> str:
    """Primer almacén de CA legible, o "" si no hay ninguno."""
    current = ssl.get_default_verify_paths()
    for candidate in (current.cafile, os.environ.get("SSL_CERT_FILE"), *CANDIDATES):
        if candidate and Path(candidate).is_file():
            return str(candidate)
    return ""


def ssl_context() -> ssl.SSLContext:
    """Contexto TLS que verifica contra el almacén del sistema."""
    default = ssl.get_default_verify_paths()
    if default.cafile and Path(default.cafile).is_file():
        return ssl.create_default_context()
    if default.capath and Path(default.capath).is_dir():
        return ssl.create_default_context()

    bundle = ca_bundle()
    if bundle:
        return ssl.create_default_context(cafile=bundle)
    return ssl.create_default_context()
