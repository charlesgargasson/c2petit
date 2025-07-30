from setuptools import setup, find_packages

setup(
    name='c2petit',
    version='0.0.1',
    packages=find_packages(),
    install_requires=[
        'aiohttp',
    ],
    entry_points={
        'console_scripts': [
            'c2petit=src.core.core:main',
            'c2p=src.core.core:main',
        ],
    },
)