import os
import io
from setuptools import setup

# variables used in buildout
here = os.path.abspath(os.path.dirname(__file__))
with io.open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# for the time being, use the UNICORN (non-4DN) requirements when
# installing via setup.py. The other requirements are commented out
# below in case we want to adjust this

# full requirements for unicorn (does not require dcicutils)
with open('requirements.txt') as f:
    set_parsed = f.read().splitlines()
install_requires = [req.strip() for req in set_parsed if 'git+' not in req]

# install_requires = [
#     'python-lambda-4dn==0.11.1',
#     'Benchmark-4dn==0.5.2',
#     'awscli==1.15.42',
#     'botocore==1.10.42',
#     'boto3==1.7.42',
#     'urllib3==1.23',
#     'requests==2.20.0'
# ]

setup_requires = install_requires + ['pytest-runner']

tests_requires = [
    'flake8',
    'pytest',
    'pytest-cov',
    'pytest-runner',
    'mock'
]


setup(
    name='tibanna',
    version=open("tibanna/_version.py").readlines()[-1].split()[-1].strip("\"'"),
    description='tibanna functionality for lambda',
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=['tibanna', 'tibanna_4dn'],
    zip_safe=False,
    author='4DN Team at Harvard Medical School',
    author_email='duplexa@gmail.com, jeremy_johnson@hms.harvard.edu, carl_vitzthum@hms.harvard.edu',
    url='http://data.4dnucleome.org',
    license='MIT',
    classifiers=[
            'License :: OSI Approved :: MIT License',
            'Operating System :: POSIX :: Linux',
            'Programming Language :: Python',
            'Programming Language :: Python :: 3'
            ],
    install_requires=install_requires,
    include_package_data=True,
    setup_requires=setup_requires,
    tests_require=tests_requires,
    entry_points={
        'console_scripts': [
             'tibanna = tibanna.__main__:main',
             'tibanna_4dn = tibanna_4dn.__main__:main',
        ]
    }
)
