import pytest

from nighttrader.config import load_limits, load_universe


@pytest.fixture(scope="session")
def universe():
    return load_universe()


@pytest.fixture(scope="session")
def limits():
    return load_limits()
