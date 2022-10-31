from setuptools import setup, find_packages
import codecs
import re
import os


here = os.path.abspath(os.path.dirname(__file__))


def read(*parts):
    with codecs.open(os.path.join(here, *parts), 'r') as fp:
        return fp.read()


def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


setup(name='ethodrome',
      version=find_version("src/etho/__init__.py"),
      description='ethodrome',
      url='http://github.com/janclemenslab/ethodrome',
      author='Jan Clemens',
      author_email='clemensjan@googlemail.com',
      license='MIT',
      packages=find_packages('src'),
      package_dir={'': 'src'},
      install_requires=[
          'zerorpc', 'pandas', 'pyzmq', 'pygame', 'numpy', 'pandas',
      ],
      tests_require=['pytest'],
      extras_require={
        'rpi camera': ["picamera[array]"],
        'NI daqmx': ["pydaqmx"],
        'ptrgrey flycapture': ["flycapture2"],
        'opencv': ["opencv"],
      },
      include_package_data=True,
      zip_safe=False
      )
