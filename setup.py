#!/usr/bin/env python
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

try:
    import pypandoc
    long_description = pypandoc.convert('README.md', 'rst',
                                        format='markdown_github',
                                        extra_args=("--no-wrap",))
except:
    long_description = ''

setup(name='gcalcli',
      version='4.0.0',
      maintainer='Eric Davis, Brian Hartvigsen',
      maintainer_email='edavis@insanum.com, brian.andrew@brianandjenny.com',
      description='Google Calendar Command Line Interface',
      long_description=long_description,
      url='https://github.com/jcrowgey/gcalcli',
      license='MIT',
      packages = ['gcalcli'],
      install_requires=[
          'python-dateutil',
          'python-gflags',
          'httplib2',
          'google-api-python-client',
          'oauth2client'
      ],
      extras_require={
          'vobject':  ["vobject"],
          'parsedatetime': ["parsedatetime"],
      },
      entry_points = {
          'console_scripts':
              ['gcalcli=gcalcli.gcalcli:main'],
      },
      classifiers=[
          "Development Status :: 5 - Production/Stable",
          "Environment :: Console",
          "Intended Audience :: End Users/Desktop",
          "License :: OSI Approved :: MIT License",
          "Programming Language :: Python :: 3.5",
      ])
