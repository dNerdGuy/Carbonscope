from setuptools import setup, find_packages

setup(
    name="carbonscope",
    version="0.24.3",
    description="Bittensor subnet for decentralized corporate carbon emission estimation",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "bittensor>=6.0.0",
        "pydantic[email]>=2.0",
        "numpy>=1.24.0",
        "fastapi>=0.100.0",
        "uvicorn>=0.20.0",
        "sqlalchemy[asyncio]>=2.0.0",
        "aiosqlite>=0.19.0",
        "asyncpg>=0.29.0",
        "alembic>=1.12.0",
        "passlib[bcrypt]>=1.7.4",
        "PyJWT>=2.8.0",
        "httpx>=0.24.0",
        "slowapi>=0.1.9",
        "redis>=5.0.0",
        "python-multipart>=0.0.6",
        "pdfplumber>=0.10.0",
        "python-docx>=1.0.0",
        "openpyxl>=3.1.0",
        "reportlab>=4.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "ruff>=0.4.0",
        ],
    },
)
