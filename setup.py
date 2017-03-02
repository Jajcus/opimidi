#!/usr/bin/python3

from setuptools import setup, find_packages

setup(
    name="opimidi",
    version="0.1.dev0",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'opimidi = opimidi.main:main',
        ],
    },

    author="Jacek Konieczny",
    author_email="jajcus@jajcus.net",
    description="Orange Pi-based MIDI controller",
    license="GPLv2+",
    keywords="orangepi midi",
    url="https://github.com/jajcus/opimidi/",
)

