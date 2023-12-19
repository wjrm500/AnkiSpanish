from setuptools import setup, find_packages

setup(
    name="lexideck",
    version="1.0.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "lexideck = app.main:main",
        ],
    },
)
