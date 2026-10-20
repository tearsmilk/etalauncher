"""Entry point (PyInstaller / `python run.py`). `--selftest` runs headless checks for CI."""
import sys


def selftest():
    import json
    import os
    import tempfile
    import time

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # CI has no display
    tmp = tempfile.mkdtemp()
    os.environ["ETA_DATA"] = tmp
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from eta.accounts import AccountStore, offline_uuid, validate
    from eta.catalog import DemoProvider
    from eta.instances import InstanceStore
    from eta.paths import Settings

    report = {}
    # offline UUID like the vanilla server (UUID.nameUUIDFromBytes("OfflinePlayer:" + name))
    assert offline_uuid("Notch") == "b50ad385-829d-3141-a216-7e7d7539ba7f"
    assert validate("ab") and validate("имя") and validate("a" * 17) and validate("Steve_09") is None
    accounts = AccountStore()
    acc = accounts.add_offline("Steve_09")
    assert validate("steve_09", accounts.names())
    assert AccountStore().get(acc["uuid"])["name"] == "Steve_09"
    # catalog
    prov = DemoProvider()
    hits, total = prov.search(loaders=["fabric"], sort="downloads")
    assert total and all("fabric" in p["loaders"] for p in hits)
    assert all(hits[i]["downloads"] >= hits[i + 1]["downloads"] for i in range(len(hits) - 1))
    assert prov.search(query="магия")[1] >= 1 and prov.versions(hits[0]["slug"])
    report["catalog"] = len(prov.items)

    from eta.ui import (AddAccountDialog, CreateInstanceDialog, InstallDialog, LaunchDialog, MainWindow,
                        ProjectDialog)

    settings = Settings()
    instances = InstanceStore()
    win = MainWindow(app, settings, accounts, instances, prov)
    win.resize(1240, 800)
    win.show()
    win.start(fast=True)
    t0 = time.monotonic()
    while win.root.currentIndex() == 0 and time.monotonic() - t0 < 5:
        app.processEvents()
        time.sleep(0.005)
    assert win.root.currentIndex() == 1, "loading page did not finish"
    for key in ("home", "modpacks", "accounts", "settings", "home"):
        win.go(key)
        app.processEvents()
        win.grab()
    # catalog filters and «more»
    mp = win.modpacks
    win.go("modpacks")
    mp.f_loaders["neoforge"].setChecked(True)
    app.processEvents()
    q = mp.query()
    assert q["loaders"] == ["neoforge"]
    mp.reset_filters()
    rows = [mp.results.itemAt(i).widget() for i in range(mp.results.count()) if mp.results.itemAt(i).widget()]
    assert any(type(r).__name__ == "ProjectRow" for r in rows)
    mp.more()
    app.processEvents()
    # project page + install (fast) → instance
    slug = prov.items[1]["slug"]
    ProjectDialog(win, prov, slug).grab()
    dlg = InstallDialog(win, prov.project(slug))
    dlg.start(fast=True)
    t0 = time.monotonic()
    while dlg.result_inst is None and time.monotonic() - t0 < 5:
        app.processEvents()
        time.sleep(0.002)
    assert dlg.result_inst and instances.get(dlg.result_inst["id"])["mods"] > 0
    # own instance
    ci = CreateInstanceDialog(win)
    ci.name.setText("Выживание")
    ci.loader = "quilt"
    inst = instances.add(ci.name.text(), ci.version.currentData(), ci.loader)
    win.select_instance(inst["id"], go_home=False)
    mp.show_tab("mine")
    app.processEvents()
    assert win.instance()["id"] == inst["id"]
    # account dialog: live validation
    ad = AddAccountDialog(win)
    ad.name.setText("x")
    assert not ad.ok.isEnabled()
    ad.name.setText("Alex_2")
    assert ad.ok.isEnabled() and "UUID" in ad.uuid.text()
    acc2 = accounts.add_offline("Alex_2")
    win.select_account(acc2["uuid"])
    assert win.account()["name"] == "Alex_2"
    # launch dialog (demo flow)
    ld = LaunchDialog(win, inst, acc2)
    t0 = time.monotonic()
    while ld.bar.value() < 100 and time.monotonic() - t0 < 6:
        app.processEvents()
        time.sleep(0.002)
    assert ld.bar.value() == 100
    win.apply_theme()
    win.go("home")
    app.processEvents()
    assert "Alex_2" in win.home.greet.text()
    report["instances"] = len(instances.items)
    report["accounts"] = len(accounts.items)
    win.close()
    print("eta selftest ok", json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        code = selftest()
        sys.stdout.flush()
        sys.stderr.flush()
        import os

        os._exit(code)  # every check ran; skip interpreter teardown of Qt objects
    from eta.ui import main

    sys.exit(main())
