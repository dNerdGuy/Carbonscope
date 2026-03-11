from setuptools import setup, find_packages

setup(
    name="carbonscope",
    version="0.1.0",
    description="Bittensor subnet for decentralized corporate carbon emission estimation",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "bittensor>=6.0.0",
        "pydantic>=2.0",
        "numpy>=1.24.0",
        "fastapi>=0.100.0",
        "uvicorn>=0.20.0",
        "sqlalchemy[asyncio]>=2.0.0",
        "aiosqlite>=0.19.0",
        "passlib[bcrypt]>=1.7.4",
        "PyJWT>=2.8.0",
        "pydantic[email]>=2.0",
        "httpx>=0.24.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
        ],
    },
)
