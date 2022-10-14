from setuptools import setup, find_packages

setup(name='ethodrome',
      version='0.6.0',
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
