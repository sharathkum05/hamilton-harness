from pathlib import Path

import pytest

from repkit.pack import Pack, load_pack

DEMO_PACK = Path(__file__).parent.parent / "packs" / "loop-sneakers"


@pytest.fixture
def pack() -> Pack:
    return load_pack(DEMO_PACK)
