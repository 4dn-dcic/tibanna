"""Version information."""
import tomlkit
import os
from pathlib import Path


def _get_project_meta():
    try:
        toml_path = Path(__file__).parent.parent.joinpath('pyproject.toml')
        with open(toml_path) as pyproject:
            file_contents = pyproject.read()

        return tomlkit.parse(file_contents)['tool']['poetry']
    except:
        return "version_not_found"
    

pkg_meta = _get_project_meta()

# Lambdas are deployed with the TIBANNA_VERSION env variable and get version information from there, as
# they can't parse the pyproject.toml. For all other use cases, fall back to the pyproject.toml version
__version__ = os.environ.get('TIBANNA_VERSION', False) or str(pkg_meta['version'])

