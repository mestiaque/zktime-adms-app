# ZKTimeAdms.spec
# PyInstaller spec — bundles app.py + server.py (Flask) into a single EXE.
# Build command:  pyinstaller ZKTimeAdms.spec

import sys
from PyInstaller.utils.hooks import collect_all

# Collect everything Flask and its dependencies need
flask_datas,    flask_bins,    flask_hiddens    = collect_all("flask")
werkzeug_datas, werkzeug_bins, werkzeug_hiddens = collect_all("werkzeug")
click_datas,    click_bins,    click_hiddens     = collect_all("click")
jinja2_datas,   jinja2_bins,   jinja2_hiddens    = collect_all("jinja2")
requests_datas, requests_bins, requests_hiddens  = collect_all("requests")
urllib3_datas,  urllib3_bins,  urllib3_hiddens   = collect_all("urllib3")

all_datas  = flask_datas  + werkzeug_datas  + click_datas  + jinja2_datas  + requests_datas  + urllib3_datas
all_bins   = flask_bins   + werkzeug_bins   + click_bins   + jinja2_bins   + requests_bins   + urllib3_bins
all_hidden = (
    flask_hiddens + werkzeug_hiddens + click_hiddens +
    jinja2_hiddens + requests_hiddens + urllib3_hiddens + [
        # Explicit hidden imports that PyInstaller misses for Flask
        "flask",
        "flask.app",
        "flask.logging",
        "flask.templating",
        "werkzeug",
        "werkzeug.serving",
        "werkzeug.routing",
        "werkzeug.exceptions",
        "werkzeug.middleware.proxy_fix",
        "jinja2",
        "click",
        "itsdangerous",
        "requests",
        "urllib3",
        "urllib3.contrib",
        "certifi",
        "charset_normalizer",
        "idna",
        "tkinter",
        "tkinter.scrolledtext",
        "tkinter.messagebox",
        "tkinter.simpledialog",
        "logging",
        "logging.handlers",
        "threading",
        "socket",
    ]
)

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=all_bins,
    datas=all_datas,
    hiddenimports=all_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ZKTimeAdms",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # no black terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon="app_icon.ico",    # remove this line if you have no icon file
    onefile=True,
)
