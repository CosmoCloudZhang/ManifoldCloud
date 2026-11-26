"""Exercise the CosmoHub client and Flagship CLI with fabricated HTTP replies."""

from base64 import b64encode
import json
import logging
import traceback
from urllib.parse import parse_qs, urlsplit

import pandas as pd
import pytest
import responses

from manifoldcloud.core.config import load
from manifoldcloud.acquisition.cosmohub import CosmoHubClient, CosmoHubError
from manifoldcloud.core.provenance import verified_entry
from manifoldcloud.acquisition import fetch_flagship
from manifoldcloud.acquisition.fetch_flagship import main


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


def _serve_query(result):
    """Fabricate CosmoHub's replies for one query whose result is the given file."""
    responses.reset()
    _user_reply()
    responses.get(f"{API}/catalogs/syntax", json={"data": {"columns": []}})
    responses.post(f"{API}/queries", json={"id": 42})
    responses.get(f"{API}/queries", json=[{"id": 42, "status": "SUCCEEDED", "download_results": RESULT_URL}])
    responses.get(RESULT_URL, body=result.read_bytes(), content_type="application/octet-stream")


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


@responses.activate
def test_syntax_check_reads_the_replies_cosmohub_gives():
    _user_reply()
    responses.get(f"{API}/catalogs/syntax", json={"data": {"columns": [{"name": "galaxy_id"}]}})
    responses.get(f"{API}/catalogs/syntax", json={"error": {"message": f"no such column near {PASSWORD}"}})
    with CosmoHubClient() as client:
        client.sign_in(EMAIL, PASSWORD)
        assert "data" in client.check_syntax("SELECT galaxy_id")
        with pytest.raises(CosmoHubError, match="rejected the query syntax") as error:
            client.check_syntax("SELECT nothing")
    assert PASSWORD not in str(error.value)


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
    args = ["--data-root", str(data)]
    with caplog.at_level(logging.DEBUG):
        main([*args, "--fetch", "--poll-interval", "0"], environ=ENV.copy())
    raw = data / "raw" / "flagship2" / "mirror_843"
    output = raw / "flagship.parquet"
    pd.testing.assert_frame_equal(pd.read_parquet(output), table)
    assert verified_entry(raw / "manifest.json", output)["row_count"] == len(table)
    assert (raw / "query.sql").is_file()

    responses.replace(responses.GET, f"{API}/user", status=403, body=f"Forbidden {PASSWORD} {TOKEN}")
    with pytest.raises(SystemExit) as error:
        main([*args, "--fetch", "--resume", "42"], environ=ENV.copy())
    assert error.value.code == 1
    stdout, stderr = capsys.readouterr()
    trace = "".join(traceback.format_exception(error.value))
    captured = [stdout.encode(), stderr.encode(), caplog.text.encode(), trace.encode()]
    captured.extend(path.read_bytes() for path in tmp_path.rglob("*") if path.is_file())
    for secret in (EMAIL, PASSWORD, TOKEN, ROTATED_TOKEN, AUTHORIZATION):
        assert all(secret.encode() not in content for content in captured)


@responses.activate
def test_a_result_that_is_not_the_requested_table_is_refused(tmp_path, flagship_parquet, capsys):
    source, _ = flagship_parquet
    _serve_query(source)
    data = tmp_path / "data"
    data.mkdir()
    with pytest.raises(SystemExit) as error:   # the catalogue is not a count result
        main(["--data-root", str(data), "--check", "--poll-interval", "0"], environ=ENV.copy())
    assert error.value.code == 1
    assert "missing required columns" in capsys.readouterr().err
    raw = data / "raw" / "flagship2" / "mirror_843"
    assert (raw / "count_query.sql").is_file()
    assert not list(raw.glob("*.parquet*"))   # neither the result nor a partial copy is kept


@pytest.mark.parametrize("options", [
    [], ["--resume", "42"], ["--refresh"], ["--check", "--fetch"], ["--fetch", "--verify"],
    ["--verify", "--resume", "42"], ["--columns", "--refresh"],
    # Options of earlier versions; --verify is offline, so nothing is requested if one were accepted.
    ["--verify", "--count"], ["--verify", "--submit"], ["--verify", "--check-only"],
    ["--verify", "--mode", "manual"], ["--verify", "--input", "x.parquet"],
])
def test_the_command_needs_one_step_and_rejects_retired_options(tmp_path, options):
    with pytest.raises(SystemExit) as error:
        main(["--data-root", str(tmp_path), *options], environ=ENV.copy())
    assert error.value.code == 2


@pytest.mark.parametrize("missing", [False, True])
@responses.activate
def test_columns_compares_the_request_with_the_catalogue_metadata(tmp_path, missing):
    columns = load().flagship.columns
    requested = columns[1:] if missing else columns
    _user_reply()
    metadata = {"id": 353, "columns": [{"name": name} for name in requested]}
    responses.get(f"{API}/catalogs/353", json=metadata)
    args = ["--columns", "--data-root", str(tmp_path)]
    if missing:
        with pytest.raises(SystemExit) as error:
            main(args, environ=ENV.copy())
        assert error.value.code == 1
    else:
        main(args, environ=ENV.copy())
        raw = tmp_path / "raw" / "flagship2" / "mirror_843"
        assert json.loads((raw / "catalog_metadata.json").read_text()) == metadata


def _acquire(tmp_path, data, catalogue, count_row):
    """Run the count query and the data query against fabricated replies."""
    config = load()
    cuts = [f"n_i{int(round(cut * 10))}" for cut in fetch_flagship.COUNT_CUTS]
    counts = {name: [0] for name in ["n_all", "n_kind_01", *cuts, *(f"{cut}_kind_01" for cut in cuts)]}
    counts.update({name: [value] for name, value in count_row.items()})
    for name, table, step in (("counts", pd.DataFrame(counts), "--check"), ("rows", catalogue, "--fetch")):
        path = tmp_path / f"{name}.parquet"
        table.to_parquet(path, index=False)
        _serve_query(path)
        main(["--data-root", str(data), step, "--poll-interval", "0"], environ=ENV.copy())
    return config


@responses.activate
def test_a_stored_result_is_not_queried_again(tmp_path, flagship_parquet, monkeypatch, capsys):
    _, row = flagship_parquet
    row["kind"] = 0
    data = tmp_path / "data"
    data.mkdir()
    config = _acquire(tmp_path, data, row, {"n_i265_kind_01": 1})
    folder = fetch_flagship.flagship_folder(data)
    capsys.readouterr()
    responses.reset()   # no reply and no credential from here on: a sign-in attempt would fail
    for step, name in (("--check", "count result"), ("--fetch", "catalogue")):
        main(["--data-root", str(data), step], environ={})
        text = capsys.readouterr().out
        assert f"The Flagship {name} is already stored" in text
        assert ("The data query will return 1 rows." in text) == (step == "--check")
    assert not responses.calls

    _serve_query(tmp_path / "rows.parquet")
    main(["--data-root", str(data), "--fetch", "--refresh", "--poll-interval", "0"], environ=ENV.copy())
    assert "Submitted CosmoHub query 42" in capsys.readouterr().out

    assert fetch_flagship._stored(config, folder, False)
    with monkeypatch.context() as patch:   # the settings now ask for another query
        patch.setattr(fetch_flagship, "_query", lambda config, count: "SELECT 1")
        assert not fetch_flagship._stored(config, folder, False)
    fetch_flagship._save_query(config, folder, "test", False)   # as an interrupted run leaves it
    assert not fetch_flagship._stored(config, folder, False)


@responses.activate
def test_verify_compares_rows_with_the_count_query_offline(tmp_path, flagship_parquet, monkeypatch, capsys):
    _, row = flagship_parquet
    row["kind"] = 0
    catalogue = pd.concat([row] * 4, ignore_index=True)
    catalogue["lsst_i_el_model3_ext"] = [1e-29, 1e-29, 1e-29, 3e-30]   # i = 23.9, 23.9, 23.9, 25.2
    data = tmp_path / "data"
    data.mkdir()
    config = _acquire(tmp_path, data, catalogue, {"n_i265_kind_01": 4, "n_i253_kind_01": 4})
    text = capsys.readouterr().out
    assert "n_i265_kind_01: 4" in text and "The data query will return 4 rows." in text
    assert "This differs by more than 10%" in text   # four rows are far below the real density
    responses.reset()   # from here on any request would fail: the check is offline
    monkeypatch.setattr(fetch_flagship, "REFERENCE_DENSITY", 4 / config.diffsky.area_deg2)
    main(["--verify", "--data-root", str(data)])
    assert "Flagship acquisition verified." in capsys.readouterr().out
    result = fetch_flagship.verify(config, fetch_flagship.flagship_folder(data))
    assert result["rows"] == result["bright_rows"] == 4
    assert 25.1 < result["faintest_i"] < 25.3

    monkeypatch.setattr(fetch_flagship, "REFERENCE_DENSITY", 2 * 4 / config.diffsky.area_deg2)
    with pytest.raises(ValueError, match="density differs from the reference by more than 10%"):
        fetch_flagship.verify(config, fetch_flagship.flagship_folder(data))
    assert not responses.calls


@pytest.mark.parametrize("change, message", [
    ({"count": 5}, "count query found 5"),
    ({"ra_gal": 240.0}, "outside the mirror box"),
    ({"kind": 2}, "not galaxies"),
    ({"lsst_i_el_model3_ext": 1e-31}, "fail noiseless i < 26.5"),
    ({"lsst_i_el_model3_ext": 0.0}, "without a positive i-band flux"),
])
@responses.activate
def test_verify_names_the_failed_check(tmp_path, flagship_parquet, change, message):
    _, row = flagship_parquet
    row["kind"] = 0
    catalogue = pd.concat([row] * 2, ignore_index=True)
    for column, value in change.items():
        if column != "count":
            catalogue.loc[1, column] = value
    data = tmp_path / "data"
    data.mkdir()
    config = _acquire(tmp_path, data, catalogue, {"n_i265_kind_01": change.get("count", 2)})
    with pytest.raises(ValueError, match=message):
        fetch_flagship.verify(config, fetch_flagship.flagship_folder(data))


@responses.activate
def test_verify_tells_a_missing_file_from_a_changed_one(tmp_path, flagship_parquet, capsys):
    with pytest.raises(SystemExit) as error:
        main(["--verify", "--data-root", str(tmp_path)])
    assert error.value.code == 1
    assert "count result has not been acquired yet" in capsys.readouterr().err

    _, row = flagship_parquet
    row["kind"] = 0
    data = tmp_path / "data"
    data.mkdir()
    config = _acquire(tmp_path, data, row, {"n_i265_kind_01": 1})
    folder = fetch_flagship.flagship_folder(data)
    (folder / "flagship.parquet").unlink()
    with pytest.raises(ValueError, match="catalogue has not been acquired yet"):
        fetch_flagship.verify(config, folder)
    (folder / "counts.parquet").chmod(0o600)
    (folder / "counts.parquet").write_bytes(b"changed")
    with pytest.raises(ValueError, match="count result has no manifest record or differs"):
        fetch_flagship.verify(config, folder)
