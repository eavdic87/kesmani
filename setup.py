from setuptools import setup, find_packages

setup(
    name="kesmani",
    version="1.0.0",
    description="Kesmani Trading Intelligence System",
    author="Kesmani",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "yfinance>=0.2.31",
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "streamlit>=1.30.0",
        "plotly>=5.18.0",
        "ta>=0.11.0",
        "python-dotenv>=1.0.0",
        "requests>=2.31.0",
        "schedule>=1.2.0",
        "Jinja2>=3.1.0",
    ],
    extras_require={
        "dev": ["pytest>=7.0.0"],
    },
)
