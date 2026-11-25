"""Exercise the CosmoHub client and Flagship CLI with fabricated HTTP replies."""

from base64 import b64encode
import json
import logging
import traceback
from urllib.parse import parse_qs, urlsplit

import pandas as pd
import pytest
import responses

from manifoldcloud.config import load
from manifoldcloud.cosmohub import CosmoHubClient, CosmoHubError
from manifoldcloud.provenance import verified_entry
from scripts.fetch_flagship import main


API = "https://api.cosmohub.pic.es"
EMAIL = "fake-reviewer@example.invalid"
PASSWORD = "fake-only-password-7e91"
TOKEN = "fake-session-token-8bd9"
ROTATED_TOKEN = "fake-rotated-token-9cf0"
RESULT_URL = f"{API}/results/fixture.parquet"
ENV = {"COSMOHUB_EMAIL": EMAIL, "COSMOHUB_PASSWORD": PASSWORD}
AUTHORIZATION = "Basic " + b64encode(f"{EMAIL}:{PASSWORD}".encode()).decode()


def _user_reply(*, token=TOKEN):
    def sign_in(request):
        assert request.headers["Authorization"] == AUTHORIZATION
        assert PASSWORD not in request.url
        return 200, {"X-Token": token}, "{}"

    responses.add_callback(responses.GET, f"{API}/user", callback=sign_in)


@pytest.fixture
def flagship_parquet(tmp_path):
    config = load()
    table = pd.DataFrame({name: [1] for name in config.flagship.columns})
    table["ra_gal"] = 230.0
    table["dec_gal"] = 25.0
    table["lsst_i_el_model3_ext"] = 1e-29
    path = tmp_path / "downloaded.parquet"
    table.to_parquet(path, index=False)
    return path, table


@responses.activate
def test_sign_in_rejects_failed_exchange_without_echoing_supplied_data():
    responses.get(f"{API}/user", status=401, body=f"Rejected {EMAIL} {PASSWORD}")
    with CosmoHubClient() as client:
        with pytest.raises(CosmoHubError) as error:
            client.sign_in(EMAIL, PASSWORD)
    assert error.value.status_code == 401
    formatted = "".join(traceback.format_exception(error.value))
    assert EMAIL not in formatted
    assert PASSWORD not in formatted
    assert AUTHORIZATION not in formatted


@responses.activate
def test_sign_in_and_rotation_use_only_the_expected_credentials():
    _user_reply()

    def catalogue(request):
        assert request.headers["Authorization"] == f"Token {TOKEN}"
        return 200, {"X-Token": ROTATED_TOKEN}, '{"id": 353, "columns": []}'

    def syntax(request):
        assert request.headers["Authorization"] == f"Token {ROTATED_TOKEN}"
        assert parse_qs(urlsplit(request.url).query) == {"sql": ["SELECT galaxy_id"]}
        return 200, {}, '{}'

    responses.add_callback(responses.GET, f"{API}/catalogs/353", callback=catalogue)
    responses.add_callback(responses.GET, f"{API}/catalogs/syntax", callback=syntax)
    with CosmoHubClient() as client:
        client.sign_in(EMAIL, PASSWORD)
        assert client.catalog_metadata(353)["id"] == 353
        client.check_syntax("SELECT galaxy_id")


@pytest.mark.parametrize("status", ["FAILED", "CANCELLED"])
@responses.activate
def test_poll_raises_on_unsuccessful_terminal_state(status):
    _user_reply()
    responses.get(f"{API}/queries", json=[{"id": 42, "status": status, "error": PASSWORD}])
    with CosmoHubClient() as client:
        client.sign_in(EMAIL, PASSWORD)
        with pytest.raises(CosmoHubError, match=status) as error:
            client.poll(42, interval=0)
    assert PASSWORD not in str(error.value)


@responses.activate
def test_cancel_and_cross_origin_download_are_separately_authenticated(tmp_path):
    _user_reply()
    external = "https://storage.example.invalid/result.parquet"

    def cancel(request):
        assert request.headers["Authorization"] == f"Token {TOKEN}"
        return 204, {}, ""

    def redirect(request):
        assert request.headers["Authorization"] == f"Token {TOKEN}"
        return 302, {"Location": external}, ""

    def result(request):
        assert "Authorization" not in request.headers
        assert "X-Token" not in request.headers
        return 200, {"Content-Type": "application/octet-stream"}, b"mock result"

    responses.add_callback(responses.POST, f"{API}/queries/42/cancel", callback=cancel)
    responses.add_callback(responses.GET, RESULT_URL, callback=redirect)
    responses.add_callback(responses.GET, external, callback=result)
    destination = tmp_path / "result.parquet"
    with CosmoHubClient() as client:
        client.sign_in(EMAIL, PASSWORD)
        client.cancel(42)
        client.download(RESULT_URL, destination)
    assert destination.read_bytes() == b"mock result"


@responses.activate
def test_mocked_cli_api_flow_keeps_credentials_out_of_artifacts_and_errors(
    tmp_path, flagship_parquet, capsys, caplog,
):
    source, table = flagship_parquet
    _user_reply()
    responses.get(f"{API}/catalogs/syntax", json={})

    def submit(request):
        assert request.headers["Authorization"] == f"Token {TOKEN}"
        payload = json.loads(request.body)
        assert payload["format"] == "parquet"
        assert "SELECT" in payload["sql"]
        return 200, {"X-Token": ROTATED_TOKEN}, '{"id": 42}'

    responses.add_callback(responses.POST, f"{API}/queries", callback=submit)
    for status in ("PENDING", "PROCESSING", "SUCCEEDED"):
        query = {"id": 42, "status": status}
        if status == "SUCCEEDED":
            query["download_results"] = RESULT_URL
        authorization = responses.matchers.header_matcher({"Authorization": f"Token {ROTATED_TOKEN}"})
        responses.get(f"{API}/queries", json=[query], match=(authorization,))
    responses.get(RESULT_URL, body=source.read_bytes(), content_type="application/octet-stream")

    data = tmp_path / "data"
    data.mkdir()
    args = ["--mode", "api", "--data-root", str(data)]
    with caplog.at_level(logging.DEBUG):
        main([*args, "--submit", "--poll-interval", "0"], environ=ENV.copy())
    raw = data / "raw" / "flagship2" / "mirror_843"
    output = raw / "flagship.parquet"
    pd.testing.assert_frame_equal(pd.read_parquet(output), table)
    assert verified_entry(raw / "manifest.json", output)["row_count"] == len(table)
    assert (raw / "query.sql").is_file()

    responses.replace(responses.GET, f"{API}/user", status=403, body=f"Forbidden {PASSWORD} {TOKEN}")
    with pytest.raises(SystemExit) as error:
        main([*args, "--resume", "42"], environ=ENV.copy())
    assert error.value.code == 1
    stdout, stderr = capsys.readouterr()
    trace = "".join(traceback.format_exception(error.value))
    captured = [stdout.encode(), stderr.encode(), caplog.text.encode(), trace.encode()]
    captured.extend(path.read_bytes() for path in tmp_path.rglob("*") if path.is_file())
    for secret in (EMAIL, PASSWORD, TOKEN, ROTATED_TOKEN, AUTHORIZATION):
        assert all(secret.encode() not in content for content in captured)


@responses.activate
def test_manual_cli_writes_sql_and_ingests_without_network(tmp_path, flagship_parquet, capsys):
    source, table = flagship_parquet
    data = tmp_path / "data"
    data.mkdir()
    args = ["--mode", "manual", "--data-root", str(data)]
    main(args, environ=ENV.copy())
    assert capsys.readouterr().out.strip()
    raw = data / "raw" / "flagship2" / "mirror_843"
    assert (raw / "query.sql").is_file()
    main([*args, "--input", str(source)], environ=ENV.copy())
    output = raw / "flagship.parquet"
    pd.testing.assert_frame_equal(pd.read_parquet(output), table)
    assert verified_entry(raw / "manifest.json", output)["row_count"] == len(table)
    assert not responses.calls


@pytest.mark.parametrize("missing", [False, True])
@responses.activate
def test_check_only_verifies_requested_columns(tmp_path, missing):
    columns = load().flagship.columns
    requested = columns[1:] if missing else columns
    _user_reply()
    metadata = {"id": 353, "columns": [{"name": name} for name in requested]}
    responses.get(f"{API}/catalogs/353", json=metadata)
    args = ["--mode", "api", "--check-only", "--data-root", str(tmp_path)]
    if missing:
        with pytest.raises(SystemExit) as error:
            main(args, environ=ENV.copy())
        assert error.value.code == 1
    else:
        main(args, environ=ENV.copy())
        raw = tmp_path / "raw" / "flagship2" / "mirror_843"
        assert json.loads((raw / "catalog_metadata.json").read_text()) == metadata
