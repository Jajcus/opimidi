#!/usr/bin/python3

from setuptools import setup, find_packages

setup(
    name="opimidi",
    version="0.1.dev0",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'opimidi = opimidi.main:main',
            'opimidi_set_permissions = opimidi.tools:opimidi_set_permissions',
        ],
    },
    install_requires=["evdev>=0.6.4"],

    author="Jacek Konieczny",
    author_email="jajcus@jajcus.net",
    description="Orange Pi-based MIDI controller",
    license="BSD",
    keywords="orangepi midi",
    url="https://github.com/jajcus/opimidi/",
)

