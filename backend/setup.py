from setuptools import setup, find_packages

setup(
    name="aaa-real-estate-backend",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.68.0",
        "uvicorn>=0.15.0",
        "langgraph>=0.0.15",
        "langgraph-checkpoint-redis>=0.1.0",
        "langgraph-swarm>=0.0.14",
        "celery>=5.2.0",
        "redis>=4.0.0",
        "sqlalchemy>=1.4.0",
        "supabase>=0.7.0",
        "openai>=0.27.0",
        "facebook-business>=13.0.0",
        "google-api-python-client>=2.0.0",
        "hubspot-api-client>=1.0.0",
        "pydantic>=2.0.0",
        "python-dotenv>=0.19.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.2.5",
            "pytest-cov>=2.12.1",
            "black>=21.9b0",
            "flake8>=3.9.2",
            "mypy>=0.910",
        ]
    },
)