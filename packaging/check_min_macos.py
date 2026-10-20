"""Fail if any Mach-O file in the bundle requires a newer macOS than the target (default 11.0)
or lacks an x86_64 slice — this is what makes the app start on Big Sur / Intel."""
import subprocess
import sys
from pathlib import Path

target = tuple(int(x) for x in (sys.argv[2] if len(sys.argv) > 2 else "11.0").split("."))
bundle = Path(sys.argv[1])
bad = []
checked = 0
for path in bundle.rglob("*"):
    if not path.is_file() or path.is_symlink():
        continue
    with open(path, "rb") as fh:
        magic = fh.read(4)
    if magic not in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xce\xfa\xed\xfe"):
        continue
    checked += 1
    archs = subprocess.run(["lipo", "-archs", str(path)], capture_output=True, text=True).stdout.split()
    if "x86_64" not in archs:
        bad.append(f"{path}: no x86_64 slice ({archs})")
        continue
    out = subprocess.run(["otool", "-arch", "x86_64", "-l", str(path)], capture_output=True, text=True).stdout
    lines = out.splitlines()
    for i, line in enumerate(lines):
        line = line.strip()
        version = None
        if line == "cmd LC_BUILD_VERSION":
            for nxt in lines[i + 1:i + 6]:
                if nxt.strip().startswith("minos"):
                    version = nxt.split()[1]
        elif line == "cmd LC_VERSION_MIN_MACOSX":
            for nxt in lines[i + 1:i + 4]:
                if nxt.strip().startswith("version"):
                    version = nxt.split()[1]
        if version:
            parts = tuple(int(x) for x in version.split("."))
            if parts > target:
                bad.append(f"{path}: needs macOS {version}")
            break
print(f"checked {checked} Mach-O files")
if bad:
    print("\n".join(bad))
    sys.exit(1)
print("all binaries run on macOS", ".".join(map(str, target)), "x86_64")
