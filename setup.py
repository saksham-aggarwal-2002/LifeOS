"""Builds LifeOS.app. Run ./build_app.sh rather than calling this directly."""
from setuptools import setup

setup(
    name="LifeOS",
    app=["main.py"],
    options={
        "py2app": {
            "iconfile": "assets/LifeOS.icns",
            "plist": {
                "CFBundleName": "LifeOS",
                "CFBundleDisplayName": "LifeOS",
                "CFBundleIdentifier": "com.saksham.lifeos",
                "CFBundleShortVersionString": "0.1.0",
                "NSHighResolutionCapable": True,
            },
        }
    },
)
