"""MAX-only CA trust; no credentials, HTTP requests or real receivers."""

import hashlib
import ssl

from kiro_crew.max.client import API_ORIGIN, _max_ssl_context


def test_max_uses_current_official_endpoint():
    assert API_ORIGIN == "https://platform-api2.max.ru"


def test_max_trust_is_scoped_and_keeps_hostname_and_chain_validation():
    before = ssl.create_default_context().get_ca_certs(binary_form=True)
    context = _max_ssl_context()
    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED
    roots = context.get_ca_certs(binary_form=True)
    fingerprint = "d26d2d0231b7c39f92cc738512ba54103519e4405d68b5bd703e9788ca8ecf31"
    assert fingerprint in {hashlib.sha256(cert).hexdigest() for cert in roots}
    assert set(before).issubset(roots)
    assert ssl.create_default_context().get_ca_certs(binary_form=True) == before
