from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.maps.rebuild_retained_osm_net import _net_body_sha256, main


def test_net_body_sha256_ignores_generated_header(tmp_path: Path) -> None:
    body = b'<net version="1.20"><edge id="e0"/></net>\n'
    first = tmp_path / "first.net.xml"
    second = tmp_path / "second.net.xml"
    first.write_bytes(b"generated at 01:00\n" + body)
    second.write_bytes(b"different command and timestamp\n" + body)

    expected = hashlib.sha256(body).hexdigest()
    assert _net_body_sha256(first) == expected
    assert _net_body_sha256(second) == expected


def test_net_body_sha256_requires_net_marker(tmp_path: Path) -> None:
    source = tmp_path / "not-a-net.xml"
    source.write_bytes(b'<osm version="0.6"/>')

    with pytest.raises(ValueError, match="body marker not found"):
        _net_body_sha256(source)


@pytest.mark.parametrize("existing_target", ["output", "qa"])
def test_cli_refuses_existing_output_or_qa_without_invoking_netconvert(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    existing_target: str,
) -> None:
    output = tmp_path / "candidate.net.xml"
    qa = tmp_path / "candidate.qa.json"
    target = output if existing_target == "output" else qa
    target.write_bytes(b"preserve me")

    def unexpected_subprocess(*args: object, **kwargs: object) -> None:
        raise AssertionError("netconvert must not run when an output path already exists")

    monkeypatch.setattr(
        "scripts.maps.rebuild_retained_osm_net.subprocess.run", unexpected_subprocess
    )
    result = main(
        [
            "--profile",
            str(tmp_path / "missing-profile.json"),
            "--output",
            str(output),
            "--qa",
            str(qa),
        ]
    )

    assert result == 1
    assert target.read_bytes() == b"preserve me"
    assert not qa.exists() if existing_target == "output" else not output.exists()
