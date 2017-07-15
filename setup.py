try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(name='compactor',
      description='Compact overly humongous avi files',
      author='Ronny Eichler',
      author_email='ronny.eichler@gmail.com',
      version='0.0.3',
      install_requires=['tqdm'],
      packages=['compactor'],
      entry_points="""[console_scripts]
            compactor=compactor.compactor:main""")
