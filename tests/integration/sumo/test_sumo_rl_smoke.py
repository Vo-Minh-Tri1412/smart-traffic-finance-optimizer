from __future__ import annotations

import os
from pathlib import Path

from scripts.smoke.sumo_rl_smoke import find_sumo_home, package_net_paths


def test_find_sumo_home_prefers_explicit_path(tmp_path: Path) -> None:
    fake_sumo_home = tmp_path / "Sumo"
    bin_dir = fake_sumo_home / "bin"
    bin_dir.mkdir(parents=True)
    executable_suffix = ".exe" if os.name == "nt" else ""
    (bin_dir / f"sumo{executable_suffix}").write_text("", encoding="utf-8")
    (bin_dir / f"sumo-gui{executable_suffix}").write_text("", encoding="utf-8")

    assert find_sumo_home(str(fake_sumo_home)) == fake_sumo_home.resolve()


def test_package_net_paths_exist() -> None:
    net_file, route_file = package_net_paths()

    assert net_file.name == "single-intersection.net.xml"
    assert route_file.name == "single-intersection-vhvh.rou.xml"
    assert net_file.is_file()
    assert route_file.is_file()
