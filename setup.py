#!/usr/bin/python3

from setuptools import setup, find_packages, Extension
import subprocess

# https://gist.github.com/smidm/ff4a2c079fed97a92e9518bd3fa4797c
def pkgconfig(*packages, **kw):
    """
    Query pkg-config for library compile and linking options. Return configuration in distutils
    Extension format.
    
    Usage: 
    
    pkgconfig('opencv')
    
    pkgconfig('opencv', 'libavformat')
    
    pkgconfig('opencv', optional='--static')
    
    pkgconfig('opencv', config=c)
    
    returns e.g.  
       
    {'extra_compile_args': [],
     'extra_link_args': [],
     'include_dirs': ['/usr/include/ffmpeg'],
     'libraries': ['avformat'],
     'library_dirs': []}
     
     Intended use:
          
     distutils.core.Extension('pyextension', sources=['source.cpp'], **c)
     
     Set PKG_CONFIG_PATH environment variable for nonstandard library locations.
    
    based on work of Micah Dowty (http://code.activestate.com/recipes/502261-python-distutils-pkg-config/)
    """
    config = kw.setdefault('config', {})
    optional_args = kw.setdefault('optional', '')

    # { <distutils Extension arg>: [<pkg config option>, <prefix length to strip>], ...}
    flag_map = {'include_dirs': ['--cflags-only-I', 2],
                'library_dirs': ['--libs-only-L', 2],
                'libraries': ['--libs-only-l', 2],
                'extra_compile_args': ['--cflags-only-other', 0],
                'extra_link_args': ['--libs-only-other', 0],
                }
    for package in packages:
        for distutils_key, (pkg_option, n) in flag_map.items():
            items = subprocess.check_output(['pkg-config', optional_args, pkg_option, package]).decode('utf8').split()
            config.setdefault(distutils_key, []).extend([i[n:] for i in items])
    return config

alsa_config = pkgconfig("alsa", config={"extra_compile_args": ["-Wall"]})

seq_ext = Extension("opimidi.alsa._seq",
                    ["opimidi/alsa/_seq.c"],
		    **alsa_config
                    )

setup(
    name="opimidi",
    version="0.1.dev0",
    packages=find_packages(),
    ext_modules=[seq_ext],
    entry_points={
        'console_scripts': [
            'opimidi = opimidi.main:main',
            'opimidi_set_permissions = opimidi.tools:opimidi_set_permissions',
            'opimidi_start_usb = opimidi.usb:opimidi_start_usb',
            'opimidi_stop_usb = opimidi.usb:opimidi_stop_usb',
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

