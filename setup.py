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
    description='Tibanna runs portable pipelines (in CWL/WDL) on the AWS Cloud.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=['tibanna', 'awsf3'],
    zip_safe=False,
    author='4DN Team at Harvard Medical School',
    author_email='duplexa@gmail.com, jeremy_johnson@hms.harvard.edu,' +
                 'carl_vitzthum@hms.harvard.edu, Michele_Berselli@hms.harvard.edu',
    url='http://github.com/4dn-dcic/tibanna',
    license='MIT',
    classifiers=[
            'License :: OSI Approved :: MIT License',
            'Operating System :: POSIX :: Linux',
            'Programming Language :: Python',
            'Programming Language :: Python :: 3'
            ],
    install_requires=install_requires,
    include_package_data=True,
    setup_requires=install_requires,
    tests_require=tests_requires,
    entry_points={
        'console_scripts': [
             'tibanna = tibanna.__main__:main',
             'awsf3 = awsf3.__main__:main',
        ]
    }
)
