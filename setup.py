from setuptools import setup, find_packages

setup(
    name="photon-cli",
    version="0.1.0",
    author="Pratham Jain",
    author_email="dhruv.diddi@gmail.com",
    description="Distributed Robotic Communication CLI",
    long_description="# Photon\n\nDistributed communication for robots.",
    long_description_content_type="text/markdown",
    url="https://github.com/GetSoloTech/photon-cli", 
    packages=find_packages(include=["photon", "photon.*"]),
    include_package_data=True,
    license="Apache 2.0",
    classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "typer",
        "rich",
        "lerobot[feetech,lekiwi]==0.4.0",
        "requests",
        "transformers",
        "accelerate"
    ],
    extras_require={
        "dev": ["pytest", "black", "isort"],
    },
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "photon=photon.cli:app",
        ],
    },
)