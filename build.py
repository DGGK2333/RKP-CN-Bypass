#!/usr/bin/env python3
"""RKP CN Bypass - 打包与校验脚本。

用法：
    python3 build.py            # 生成 dist/RKP-CN-Bypass-<version>.zip 与 SHA256SUMS
    python3 build.py --verify   # 打包后额外校验产物、module.prop 与 update.json

设计要点：
  * zip 内文件位于根目录，文件名仅含 ASCII，条目路径使用 "/"，Unix 权限位正确；
  * 不包含 UTF-8 BOM，不允许 CRLF（Android 的 sh 无法解析 CRLF 脚本）；
  * 固定条目时间戳，保证同一份源码重复打包得到的内容一致（可复现）。
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
REPO = "DGGK2333/RKP-CN-Bypass"

# 刷入包内容：Magisk / KernelSU / APatch 安装器只会用到这些文件。
MODULE_FILES = [
    "module.prop",
    "customize.sh",
    "post-fs-data.sh",
    "service.sh",
    "uninstall.sh",
]
EXECUTABLE = {"customize.sh", "post-fs-data.sh", "service.sh", "uninstall.sh"}
FIXED_DATE = (2020, 1, 1, 0, 0, 0)  # zip 条目时间戳，保证可复现


def fail(msg: str) -> "NoReturn":  # noqa: F821 - 仅用于类型提示
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(1)


def read_props() -> dict[str, str]:
    props: dict[str, str] = {}
    for raw in (ROOT / "module.prop").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        props[key.strip()] = value.strip()
    return props


def check_source_file(name: str) -> bytes:
    path = ROOT / name
    if not path.is_file():
        fail(f"缺少必需文件：{name}")
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        fail(f"{name} 含有 UTF-8 BOM，Android 无法正确解析")
    if b"\r\n" in data:
        fail(f"{name} 使用 CRLF 换行，请改为 LF")
    return data


def build() -> tuple[Path, dict[str, str]]:
    props = read_props()
    version = props.get("version", "")
    if not re.fullmatch(r"v\d+\.\d+(?:\.\d+)?", version):
        fail(f"module.prop 中 version 格式异常：{version!r}（应形如 v1.1 / v1.2.0）")

    DIST.mkdir(parents=True, exist_ok=True)
    out = DIST / f"RKP-CN-Bypass-{version}.zip"
    payload = [(name, check_source_file(name)) for name in MODULE_FILES]

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for name, data in payload:
            info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3  # Unix，便于安装器读取权限位
            mode = 0o755 if name in EXECUTABLE else 0o644
            info.external_attr = (0o100000 | mode) << 16
            zf.writestr(info, data)

    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    (DIST / "SHA256SUMS").write_text(
        f"{digest}  {out.name}\n", encoding="utf-8", newline="\n"
    )
    print(f"built: dist/{out.name} ({out.stat().st_size} bytes)")
    print(f"sha256: {digest}")
    return out, props


def verify() -> None:
    zip_path, props = build()

    with zipfile.ZipFile(zip_path) as zf:
        if zf.namelist() != MODULE_FILES:
            fail(f"刷入包内容异常：{zf.namelist()}")
        if zf.testzip() is not None:
            fail("刷入包内存在损坏条目")
        for info in zf.infolist():
            data = zf.read(info.filename)
            if data.startswith(b"\xef\xbb\xbf") or b"\r\n" in data:
                fail(f"刷入包内 {info.filename} 编码/换行异常")
            if info.filename.endswith(".sh") and (info.external_attr >> 16) & 0o111 == 0:
                fail(f"刷入包内 {info.filename} 缺少可执行权限")
        if zf.read("module.prop") != (ROOT / "module.prop").read_bytes():
            fail("刷入包内 module.prop 与源码不一致")

    version = props["version"]
    version_code = int(props["versionCode"])
    update = json.loads((ROOT / "update.json").read_text(encoding="utf-8"))
    expected_zip_url = f"https://github.com/{REPO}/releases/download/{version}/RKP-CN-Bypass-{version}.zip"
    expected_changelog = f"https://raw.githubusercontent.com/{REPO}/main/CHANGELOG.md"

    problems = []
    if update.get("version") != version:
        problems.append(f"update.json version={update.get('version')!r}，应为 {version!r}")
    if update.get("versionCode") != version_code:
        problems.append(
            f"update.json versionCode={update.get('versionCode')!r}，应为 {version_code}"
        )
    if update.get("zipUrl") != expected_zip_url:
        problems.append(f"update.json zipUrl 应为 {expected_zip_url}")
    if update.get("changelog") != expected_changelog:
        problems.append(f"update.json changelog 应为 {expected_changelog}")

    update_json_url = f"https://raw.githubusercontent.com/{REPO}/main/update.json"
    if props.get("updateJson") != update_json_url:
        problems.append(f"module.prop updateJson 应为 {update_json_url}")

    changelog = ROOT / "CHANGELOG.md"
    if not changelog.is_file() or f"## {version}" not in changelog.read_text(encoding="utf-8"):
        problems.append(f"CHANGELOG.md 缺少 ## {version} 小节")

    if problems:
        for p in problems:
            print(f"error: {p}", file=sys.stderr)
        raise SystemExit(1)

    print(f"verify: ok（{REPO} {version} / versionCode {version_code}）")


if __name__ == "__main__":
    if "--verify" in sys.argv[1:]:
        verify()
    else:
        build()
