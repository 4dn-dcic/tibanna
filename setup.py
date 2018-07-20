import os
from setuptools import setup

# variables used in buildout
here = os.path.abspath(os.path.dirname(__file__))
try:
    README = open(os.path.join(here, 'README.md')).read()
except:
    pass  # don't know why this fails with tox

# minimum requirements to create the core package. Covers pony and unicorn
with open('requirements-lambda-pony.txt') as f:
    inst_parsed = f.read().splitlines()
install_requires = [req.strip() for req in inst_parsed if '-e git' not in req]

# full requirements for unicorn (does not require dcicutils)
with open('requirements.txt') as f:
    set_parsed = f.read().splitlines()
setup_requires = [req.strip() for req in set_parsed if '-e git' not in req]

# full requirements for pony and running tests (includes dcicutils)
with open('requirements-4dn.txt') as f:
    tests_parsed = f.read().splitlines()
tests_require = [req.strip() for req in tests_parsed if '-e git' not in req]


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
    install_requires=install_requires,
    include_package_data=True,
    tests_require=tests_require,
    extras_require={
        'test': tests_require,
    },
    setup_requires=setup_requires,
    dependency_links=[
        'git+https://github.com/4dn-dcic/python-lambda.git#egg=python_lambda',
        'git+https://github.com/SooLee/Benchmark.git#egg=Benchmark'
    ]
)
