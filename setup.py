from setuptools import setup, find_packages

# To use a consistent encoding
from codecs import open
import os
import versioneer

here = os.path.abspath(os.path.dirname(__file__))
ext_modules = []


def find_package_data(data_root, package_root):
    files = []
    for root, dirnames, filenames in os.walk(data_root):
        for fn in filenames:
            files.append(os.path.relpath(os.path.join(root, fn), package_root))
    return files


# Get the long description from the README file
with open(os.path.join(here, "README.rst"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="pele_platform",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description="Automatic platform to launch PELE simulations",
    long_description=long_description,
    url="https://github.com/NostrumBioDiscovery/pele_platform",
    author="Nostrum Biodiscovery",
    author_email="pelesupport@nostrumbiodiscovery.com",
    packages=find_packages(exclude=["docs", "tests", "tests.data", ]),
    package_data={
        "pele_platform/AdaptivePELE/atomset": ["*.pxd"],
        "pele_platform/AdaptivePELE/freeEnergies/": ["*.pyx"],
        "pele_platform": find_package_data("pele_platform/data", "pele_platform")
    },
    include_package_data=True,
    install_requires=[
        "scipy",
    ],
    ext_modules=ext_modules,  # accepts a glob pattern
)

