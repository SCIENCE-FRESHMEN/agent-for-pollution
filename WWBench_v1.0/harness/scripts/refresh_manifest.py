# -*- coding: utf-8 -*-
"""对已解包的发布目录就地重算 MANIFEST.sha256(与 build_release.py 的清单逻辑一致)。

用途:发布后做过就地修复(文档口径、capsule 回填、附件补充、results 重跑)时,
保持哈希清单与产物一致。用法:python scripts/refresh_manifest.py [--root 上级目录]
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    args = ap.parse_args()
    root = Path(args.root)
    files = sorted(p for p in root.rglob("*")
                   if p.is_file() and p.name != "MANIFEST.sha256"
                   and "__pycache__" not in p.parts)
    lines = [f"{sha256(p)}  {p.relative_to(root).as_posix()}" for p in files]
    (root / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[manifest] {len(lines)} 条 -> {root / 'MANIFEST.sha256'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
