"""Package and verify a drag-to-Applications macOS installation image."""
import hashlib
from pathlib import Path
import platform
import plistlib
import subprocess
from tempfile import TemporaryDirectory
import tomllib

root = Path(__file__).resolve().parents[1]
version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
bundle = root / "dist" / "RemyPlayer.app"
image = root / "dist" / f"RemyPlayer-{version}-macos-{platform.machine()}.dmg"


def check_bundle(path):
    """校验待分发应用的版本、完整签名及资源，不启动播放器界面。

    --version 在创建 QApplication 前退出，因此不会加载媒体或发起播放。
    版本不符或存在本地图标备份时拒绝打包；外部校验命令失败时直接传播异常。
    """
    with (path / "Contents" / "Info.plist").open("rb") as source:
        info = plistlib.load(source)
    if info["CFBundleShortVersionString"] != version:
        raise RuntimeError("Build the application with the release version first")
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(path)], check=True)
    executable = path / "Contents" / "MacOS" / info["CFBundleExecutable"]
    actual = subprocess.check_output([str(executable), "--version"], text=True).strip()
    if actual != version:
        raise RuntimeError(f"Application version mismatch: {actual}")
    if list(path.rglob("icon.old.*")):
        raise RuntimeError("Local icon backups must not be included in the release")


check_bundle(bundle)
with TemporaryDirectory(prefix="remyplayer-dmg-") as temporary:
    stage = Path(temporary) / "installer"
    stage.mkdir()
    subprocess.run(["ditto", str(bundle), str(stage / bundle.name)], check=True)
    (stage / "Applications").symlink_to("/Applications")
    (stage / "安装说明.txt").write_text(
        f"RemyPlayer {version}\n\n"
        "请先退出正在运行的旧版本，再将 RemyPlayer.app 拖入 Applications。\n"
        "复制完成后推出安装镜像，从应用程序文件夹启动。\n\n"
        "适用：Apple Silicon Mac（arm64），macOS 14 或更新版本。\n"
        "本包采用本地临时签名，尚未进行 Developer ID 签名或 Apple 公证。\n"
        "更新保留原有音乐库和偏好；不会修改音乐文件。\n",
        encoding="utf-8",
    )
    (stage / "更新日志.md").write_text((root / "CHANGELOG.md").read_text(), encoding="utf-8")
    subprocess.run([
        "hdiutil", "create", "-ov", "-volname", f"RemyPlayer {version}",
        "-srcfolder", str(stage), "-format", "UDZO", "-fs", "HFS+", str(image),
    ], check=True)
    subprocess.run(["hdiutil", "verify", str(image)], check=True)
    mount = Path(temporary) / "mounted"
    mount.mkdir()
    subprocess.run([
        "hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint", str(mount), str(image),
    ], check=True)
    try:
        check_bundle(mount / bundle.name)
        if (mount / "Applications").readlink() != Path("/Applications"):
            raise RuntimeError("Missing Applications installation shortcut")
    finally:
        subprocess.run(["hdiutil", "detach", str(mount)], check=True)

checksum = hashlib.sha256(image.read_bytes()).hexdigest()
image.with_suffix(".dmg.sha256").write_text(f"{checksum}  {image.name}\n")
print(f"Verified installer: {image}")
