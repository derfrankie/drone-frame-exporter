from __future__ import annotations

from pathlib import Path

from setuptools.dist import Distribution
from setuptools import find_packages, setup


APP = ["src/app/macos_bundle.py"]
APP_NAME = "Drone Frame Extractor"
ROOT = Path(__file__).resolve().parent

OPTIONS = {
    "argv_emulation": False,
    "packages": find_packages("src"),
    "includes": [
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtWebChannel",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "fitparse",
        "gpxpy",
        "rich",
        "typer",
    ],
    "plist": {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": "com.derfrankie.droneframeextractor",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
    },
}


class Py2AppDistribution(Distribution):
    def __init__(self, attrs=None) -> None:
        super().__init__(attrs)
        object.__setattr__(self, "_py2app_install_requires", [])
        object.__setattr__(self, "_py2app_extras_require", {})

    @property
    def install_requires(self):
        return []

    @install_requires.setter
    def install_requires(self, value) -> None:
        object.__setattr__(self, "_py2app_install_requires", value)

    @property
    def extras_require(self):
        return {}

    @extras_require.setter
    def extras_require(self, value) -> None:
        object.__setattr__(self, "_py2app_extras_require", value)


setup(
    name="drone-frame-extractor-macos-app",
    version="0.1.0",
    app=APP,
    options={"py2app": OPTIONS},
    package_dir={"": "src"},
    packages=find_packages("src"),
    distclass=Py2AppDistribution,
)
