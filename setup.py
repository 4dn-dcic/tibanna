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
# to add packages installed from github, use `dependency_links` in setup
setup_requires = [req.strip() for req in set_parsed if 'git+' not in req]

# full requirements for pony and running tests (includes dcicutils)
# with open('requirements-4dn.txt') as f:
#     tests_parsed = f.read().splitlines()
# tests_require = [req.strip() for req in tests_parsed if 'git+' not in req]


setup(
    name='tibanna',
    version=open("tibanna/_version.py").readlines()[-1].split()[-1].strip("\"'"),
    description='tibanna functionality for lambda',
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=['tibanna', 'tibanna_4dn'],
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
            'Programming Language :: Python :: 3.6'
            ],
    install_requires=setup_requires,
    include_package_data=True,
    setup_requires=setup_requires
)
