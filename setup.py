import os
from setuptools import setup

# variables used in buildout
here = os.path.abspath(os.path.dirname(__file__))
try:
    README = open(os.path.join(here, 'README.md')).read()
except:
    pass  # don't know why this fails with tox

requires = [
    'boto3==1.7.42',
    'botocore==1.10.42',
    'awscli==1.15.42'
    'invoke==0.18.1',
    'dcicutils==0.3.1',
    'flake8==2.4.1',
    'submit4dn==1.0.2',
    'urllib3',
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
    author_email='duplexa@gmail.com, jeremy_johnson@hms.harvard.edu',
    url='http://data.4dnucleome.org',
    license='MIT',
    classifiers=[
            'License :: OSI Approved :: MIT License',
            'Operating System :: POSIX :: Linux',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2.7',
            ],
    install_requires=requires,
    include_package_data=True,
    tests_require=tests_require,
    extras_require={
        'test': tests_require,
    },
    setup_requires=['pytest-runner', ],
    dependency_links=[
        'git+https://github.com/j1z0/python-lambda.git#egg=python_lambda',
        'git+https://github.com/SooLee/Benchmark.git#egg=Benchmark'
    ]
)
