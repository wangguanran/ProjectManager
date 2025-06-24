import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="vprjcore",
    version="0.0.1",
    author="wangguanran",
    author_email="elvans.wang@gmail.com",
    description="A project manager for V-Projects.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/wangguanran/ProjectManager",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=[
        'GitPython',
        'importlib-metadata; python_version < "3.8"',
    ],
    entry_points={
        'console_scripts': [
            'vprj = vprjcore.project:main',
        ],
    },
) 