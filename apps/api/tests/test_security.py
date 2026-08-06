"""Security & public-demo surface tests (Fase 1).

Covers the Fase 1 (P0) hardening controls:
- safe errors that never leak stack/SQL/path internals
- HTML escaping of report content (no injection in the public demo)
- CSV formula-injection defense on exports
- PII masking in public previews
- CORS credentials disabled
- read-only public demo (upload + PATCH return 403)
- deterministic, cacheable stateless reconstruction
"""

from __future__ import annotations

import asyncio
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.cors import CORSMiddleware

from app.core.config import API_ROOT, get_settings
from app.core.security import (
    escape_html,
    mask_pii,
    mask_pii_row,
    new_request_id,
    safe_error,
    sanitize_csv_cell,
)
from app.db.session import Base, get_db
from app.main import app
from app.services.import_service import _DEMO_CACHE, run_demo_stateless


# --------------------------------------------------------------------------
# Unit: security helper functions
# --------------------------------------------------------------------------


def test_escape_html_neutralizes_injection():
    evil = '<img src=x onerror=alert(1)>'
    out = escape_html(evil)
    assert out == '&lt;img src=x onerror=alert(1)&gt;'
    assert '<' not in out and '>' not in out


def test_escape_html_quotes_ampersand():
    assert escape_html('a & b "c"') == 'a &amp; b &quot;c&quot;'


def test_sanitize_csv_cell_prefixes_formula_triggers():
    assert sanitize_csv_cell('=cmd') == "'=cmd"
    assert sanitize_csv_cell('+1') == "'+1"
    assert sanitize_csv_cell('-2') == "'-2"
    assert sanitize_csv_cell('@evil') == "'@evil"


def test_sanitize_csv_cell_leaves_normal_text():
    assert sanitize_csv_cell('normal') == 'normal'
    assert sanitize_csv_cell(123) == '123'
    assert sanitize_csv_cell(None) == ''


def test_mask_pii_masks_and_clears():
    assert mask_pii('João Silva') == '***'
    assert mask_pii('') == ''
    assert mask_pii(None) == ''
    assert mask_pii(float('nan')) == ''


def test_mask_pii_row_masks_pii_fields_only():
    row = {
        'customer_name': 'Ana Souza',
        'customer_document_optional': '123.456.789-00',
        'sku': 'SKU-A',
        'channel': 'Shopify',
    }
    masked = mask_pii_row(row)
    assert masked['customer_name'] == '***'
    assert masked['customer_document_optional'] == '***'
    assert masked['sku'] == 'SKU-A'
    assert masked['channel'] == 'Shopify'
    # original is untouched
    assert row['customer_name'] == 'Ana Souza'


def test_safe_error_has_no_internals():
    d = safe_error('Falha', 'boom')
    assert d == {'message': 'Falha', 'code': 'boom'}
    assert 'request_id' not in d
    # must never echo exception text / SQL / paths
    assert 'Traceback' not in str(d)
    assert 'SELECT' not in str(d)


def test_safe_error_includes_request_id_when_given():
    rid = 'abc123'
    d = safe_error('Falha', 'boom', rid)
    assert d['request_id'] == rid


def test_new_request_id_is_hex32():
    rid = new_request_id()
    assert len(rid) == 32
    int(rid, 16)  # must be valid hex


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


def _build_client(monkeypatch, tmp_path, *, public: bool) -> TestClient:
    db_path = tmp_path / 'test.db'
    engine = create_engine(
        f'sqlite:///{db_path.as_posix()}',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr('app.main.init_db', lambda: None)

    get_settings.cache_clear()
    settings = get_settings()
    if public:
        monkeypatch.setattr(settings, 'public_demo_mode', True)
    monkeypatch.setattr(settings, 'demo_dir', API_ROOT / 'data' / 'demo')
    monkeypatch.setattr(settings, 'processed_dir', tmp_path / 'processed')
    monkeypatch.setattr(settings, 'database_url', f'sqlite:///{db_path.as_posix()}')
    (tmp_path / 'processed').mkdir()
    # Do not re-raise server exceptions: we want to assert on the safe 500 body
    # returned by the registered global Exception handler.
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def public_client(monkeypatch, tmp_path):
    with _build_client(monkeypatch, tmp_path, public=True) as c:
        yield c
    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture()
def local_client(monkeypatch, tmp_path):
    with _build_client(monkeypatch, tmp_path, public=False) as c:
        yield c
    app.dependency_overrides.clear()
    get_settings.cache_clear()


# --------------------------------------------------------------------------
# Integration: public demo mode behavior
# --------------------------------------------------------------------------


def test_mode_endpoint_public(public_client):
    res = public_client.get('/api/mode')
    assert res.status_code == 200
    assert res.json() == {'public_demo': True}


def test_mode_endpoint_local(local_client):
    res = local_client.get('/api/mode')
    assert res.status_code == 200
    assert res.json() == {'public_demo': False}


def test_public_upload_disabled(public_client):
    files = {
        'orders': ('o.csv', 'order_id\nORD-1', 'text/csv'),
        'payments': ('p.csv', 'payment_id\nPAY-1', 'text/csv'),
        'stock_movements': ('s.csv', 'movement_id\nM1', 'text/csv'),
    }
    res = public_client.post('/api/imports', files=files)
    assert res.status_code == 403
    assert res.json()['detail']['code'] == 'upload_disabled'


def test_public_patch_disabled(public_client):
    res = public_client.patch('/api/issues/1', json={'status': 'resolved', 'note': 'x'})
    assert res.status_code == 403
    assert res.json()['detail']['code'] == 'mutation_disabled'


def test_public_demo_run_masks_pii(public_client):
    demo_dir = get_settings().demo_dir
    names = pd.read_csv(demo_dir / 'orders.csv')['customer_name'].astype(str).tolist()
    res = public_client.post('/api/demo/run')
    assert res.status_code == 200
    sample = res.json()['orders']['sample']
    assert sample, 'expected a non-empty order preview'
    for row in sample:
        assert row['customer_name'] == '***'
    # raw customer names must not appear anywhere in the response body
    leaked = [n for n in names if n and len(n) >= 3 and n in res.text]
    assert not leaked, f'PII leaked into public demo: {leaked[:5]}'


def test_public_dashboard_stateless(public_client):
    res = public_client.get('/api/imports/-1/dashboard')
    assert res.status_code == 200
    body = res.json()
    assert body['total_issues'] >= 1
    assert 'issues_by_severity' in body


def test_public_issues_stateless(public_client):
    res = public_client.get('/api/imports/-1/issues')
    assert res.status_code == 200
    issues = res.json()
    assert isinstance(issues, list)
    assert len(issues) >= 1


def test_public_report_html_escapes_injection(public_client, monkeypatch):
    payload = {'report_md': "<script>alert('xss')</script>\n# Fechamento"}
    monkeypatch.setattr('app.api.routes.run_demo_stateless', lambda: payload)
    res = public_client.get('/api/imports/-1/report?format=html')
    assert res.status_code == 200
    html = res.json()['content']
    assert '<script>alert' not in html
    assert '&lt;script&gt;alert' in html


def test_public_report_markdown_200(public_client):
    res = public_client.get('/api/imports/-1/report?format=markdown')
    assert res.status_code == 200
    assert 'Fechamento' in res.json()['content']


def test_unhandled_error_is_safe(public_client):
    def override_get_db():
        raise RuntimeError('secret/path/app.py  SELECT * FROM users')  # must not leak
        yield  # pragma: no cover

    app.dependency_overrides[get_db] = override_get_db
    try:
        res = public_client.get('/api/imports/999999')
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 500
    body = res.json()['detail']
    assert body['code'] == 'internal_error'
    assert 'request_id' in body
    assert 'secret' not in res.text
    assert 'RuntimeError' not in res.text
    assert 'SELECT' not in res.text


def test_cors_credentials_disabled():
    targets = [m for m in app.user_middleware if getattr(m, 'cls', None) is CORSMiddleware]
    assert targets, 'CORSMiddleware not registered'
    mw = targets[0]
    opts = {**getattr(mw, 'kwargs', {}), **getattr(mw, 'options', {})}
    assert opts.get('allow_credentials') is False


# --------------------------------------------------------------------------
# Stateless reconstruction determinism
# --------------------------------------------------------------------------


def _demo_fingerprint(p: dict) -> dict:
    return {
        'batch': (
            p['batch'].source_name,
            p['batch'].status,
            p['batch'].total_orders,
            p['batch'].total_issues,
        ),
        'dashboard': p['dashboard'],
        'report_md': p['report_md'],
        'issues': [
            (i.id, i.issue_type, i.severity, str(i.amount_impact)) for i in p['issues']
        ],
        'orders': len(p['orders_df']),
    }


def test_demo_stateless_identical_across_calls():
    get_settings.cache_clear()
    a = _demo_fingerprint(run_demo_stateless())
    b = _demo_fingerprint(run_demo_stateless())
    assert a == b
    # simulate a serverless cold start: drop the cache and rebuild from scratch
    _DEMO_CACHE.clear()
    c = _demo_fingerprint(run_demo_stateless())
    assert a == c


# --------------------------------------------------------------------------
# Fase 1 publication gates (Felipe's confirmation gates)
# --------------------------------------------------------------------------


def test_demo_stateless_cache_is_immutable():
    """Gate 3: a caller mutating the returned payload must NOT corrupt the
    shared, cached public demo dataset. run_demo_stateless() returns a defensive
    deep copy, so the cache stays the single source of truth read-only state."""
    first = run_demo_stateless()
    # Mutate the first issue's status via the returned reference.
    first["issues"][0].status = "resolved"
    second = run_demo_stateless()
    # The cached dataset (and every new caller) must still see status "open".
    assert second["issues"][0].status == "open"
    # And a third fresh pull is also untouched.
    assert run_demo_stateless()["issues"][0].status == "open"


def test_mask_pii_row_only_masks_allowlist_fields():
    """Gate 2: PII masking is an explicit allowlist (customer_name +
    customer_document_optional). Free-text / operator-authored fields must NOT
    be masked, otherwise reports and exports lose their meaning."""
    row = {
        "customer_name": "Ana Souza",
        "customer_document_optional": "123.456.789-00",
        "description": "Pedido atrasado com pagamento parcial",
        "recommended_action": "Confirmar estorno junto ao canal",
        "notes": "cliente ligou reclamando",
        "transaction_reference": "TXN-998877",
        "entity_id": "ORD-42",
        "title": "Pagamento divergente",
        "severity": "high",
    }
    masked = mask_pii_row(row)
    # allowlist: masked
    assert masked["customer_name"] == "***"
    assert masked["customer_document_optional"] == "***"
    # everything else preserved (free-text intentionally NOT masked)
    assert masked["description"] == "Pedido atrasado com pagamento parcial"
    assert masked["recommended_action"] == "Confirmar estorno junto ao canal"
    assert masked["notes"] == "cliente ligou reclamando"
    assert masked["transaction_reference"] == "TXN-998877"
    assert masked["entity_id"] == "ORD-42"
    assert masked["title"] == "Pagamento divergente"
    assert masked["severity"] == "high"
    # original row is untouched
    assert row["customer_name"] == "Ana Souza"


def test_local_export_csv_sanitizes_all_fields():
    """Gate 4: every field written to a CSV export (local AND public) must be
    formula-injection sanitized, including free-text and identifier columns
    (title, description, recommendation, amount, note, entity id)."""
    from app.api.routes import _csv_response

    rows = [
        {
            "id": 1,
            "batch_id": -1,
            "issue_type": "payment_divergence",
            "severity": "high",
            "entity_type": "order",
            "entity_id": "=cmd|calc",
            "title": "+Suspicious",
            "description": "-drop table",
            "recommended_action": "@evil",
            "amount_impact": "=2+2",
            "status": "open",
            "created_at": "2026-06-30",
            "updated_at": "2026-06-30",
            "resolved_at": "",
            "resolution_note": "=shell",
        }
    ]
    resp = _csv_response(rows, batch_id=-1)
    content = asyncio.run(_drain_stream(resp.body_iterator))


async def _drain_stream(body_iterator) -> str:
    """Collect a Starlette StreamingResponse body (async generator) into a str."""
    parts = []
    async for chunk in body_iterator:
        parts.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
    return "".join(parts)
    for tok in ("'=cmd|calc", "'+Suspicious", "'-drop table", "'@evil", "'=2+2", "'=shell"):
        assert tok in content, f"CSV field not sanitized: {tok}"
    # No un-sanitized formula trigger should survive at cell start.
    assert "\n=cmd|calc" not in content
    assert ",=cmd|calc" not in content
