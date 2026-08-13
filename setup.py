from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="email-finder",
    version="1.0.0",
    author="AswaGhosh1",
    author_email="your.email@example.com",
    description="Interactive email discovery tool using SMTP verification",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/AswaGhosh1/email-finder",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=[
        "dnspython>=2.4.0",
    ],
    entry_points={
        "console_scripts": [
            "email-finder=email_finder.main:main",
        ],
    },
)
