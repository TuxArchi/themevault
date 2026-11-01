"""Tests del contexto TLS (el AppImage trae su propio OpenSSL)."""

from __future__ import annotations

from types import SimpleNamespace

from themevault import net


def _paths(cafile: str = "", capath: str = "") -> SimpleNamespace:
    return SimpleNamespace(cafile=cafile, capath=capath)


def test_ca_bundle_usa_candidato_del_sistema(tmp_path, monkeypatch):
    bundle = tmp_path / "ca.pem"
    bundle.write_text("")
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.setattr(net, "CANDIDATES", (str(bundle),))
    monkeypatch.setattr(net.ssl, "get_default_verify_paths", lambda: _paths("/no/existe"))

    assert net.ca_bundle() == str(bundle)


def test_ca_bundle_respeta_ssl_cert_file(tmp_path, monkeypatch):
    suelto = tmp_path / "env.pem"
    suelto.write_text("")
    sistema = tmp_path / "sistema.pem"
    sistema.write_text("")
    monkeypatch.setenv("SSL_CERT_FILE", str(suelto))
    monkeypatch.setattr(net, "CANDIDATES", (str(sistema),))
    monkeypatch.setattr(net.ssl, "get_default_verify_paths", lambda: _paths("/no/existe"))

    assert net.ca_bundle() == str(suelto)


def test_ca_bundle_vacio_sin_almacen(monkeypatch):
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.setattr(net, "CANDIDATES", ("/no/existe/ca.pem",))
    monkeypatch.setattr(net.ssl, "get_default_verify_paths", lambda: _paths())

    assert net.ca_bundle() == ""


def test_ssl_context_usa_cafile_explicito(tmp_path, monkeypatch):
    bundle = tmp_path / "ca.pem"
    bundle.write_text("")
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.setattr(net, "CANDIDATES", (str(bundle),))
    monkeypatch.setattr(net.ssl, "get_default_verify_paths", lambda: _paths("/no/existe"))

    visto: dict = {}

    def fake_context(cafile=None):
        visto["cafile"] = cafile
        return "contexto"

    monkeypatch.setattr(net.ssl, "create_default_context", fake_context)

    assert net.ssl_context() == "contexto"
    assert visto["cafile"] == str(bundle)


def test_ssl_context_no_toca_el_default_si_sirve(tmp_path, monkeypatch):
    cafile = tmp_path / "default.pem"
    cafile.write_text("")
    monkeypatch.setattr(net.ssl, "get_default_verify_paths", lambda: _paths(str(cafile)))

    visto: dict = {}

    def fake_context(cafile=None):
        visto["cafile"] = cafile
        return "contexto"

    monkeypatch.setattr(net.ssl, "create_default_context", fake_context)

    assert net.ssl_context() == "contexto"
    assert visto["cafile"] is None
