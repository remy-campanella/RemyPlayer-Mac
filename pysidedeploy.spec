[app]
title = RemyPlayer
project_dir = .
input_file = run.py
exec_directory = dist
project_file =
icon = src/remyplayer/resources/icon.icns

[python]
packages = Nuitka==4.1.1

[qt]
qml_files =
excluded_qml_plugins =
modules = Concurrent,Core,DBus,Gui,Multimedia,Network,Svg,Widgets
plugins = platforms,platforms/darwin,styles,imageformats,iconengines,multimedia,tls

[nuitka]
macos.permissions =
mode = standalone
extra_args = --quiet --noinclude-qt-translations --include-package=remyplayer --include-package=mutagen --include-package=pypinyin --include-package-data=pypinyin --include-data-dir=src/remyplayer/resources=remyplayer/resources --macos-app-name=RemyPlayer --macos-app-version=0.0.0 --macos-signed-app-name=app.remygrad.remyplayer
