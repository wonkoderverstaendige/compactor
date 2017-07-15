try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(name='compactr',
      description='Compact overly humongous avi files',
      author='Ronny Eichler',
      author_email='ronny.eichler@gmail.com',
      version='0.0.3',
      install_requires=['tqdm'],
      packages=['compactr'],
      entry_points="""[console_scripts]
            compactr=compactr.compactr:main""")
