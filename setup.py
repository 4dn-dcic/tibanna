import os
from setuptools import setup

# variables used in buildout
here = os.path.abspath(os.path.dirname(__file__))
try:
    README = open(os.path.join(here, 'README.md')).read()
except:
    pass  # don't know why this fails with tox

requires = [
    'boto3==1.4.2',
    'botocore==1.4.52',
    'awscli==1.10.62',
]

tests_require = [
    'pytest>=3.0.1',
    'pytest-mock',
    'pytest-cov',
]

setup(
    name='core',
    version=open("core/_version.py").readlines()[-1].split()[-1].strip("\"'"),
    description='core functionality for lambda',
    packages=['core'],
    zip_safe=False,
    author='4DN Team at Harvard Medical School',
    author_email='jeremy_johnson@hms.harvard.edu',
    url='http://data.4dnucleome.org',
    license='MIT',
    classifiers=[
            'License :: OSI Approved :: MIT License',
            'Operating System :: POSIX :: Linux',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.5',
            ],
    install_requires=requires,
    include_package_data=True,
    tests_require=tests_require,
    extras_require={
        'test': tests_require,
    },
    setup_requires=['pytest-runner', ],
)
