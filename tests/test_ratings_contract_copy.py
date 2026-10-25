"""site/lib/ratings-contract.ts is a byte-for-byte copy of the contract's Phase 13C block, the
same way site/lib/contract.ts copies the main block."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "docs" / "phases" / "phase-10-contract.md"
COPY = ROOT / "site" / "lib" / "ratings-contract.ts"


def test_the_site_rating_types_are_the_13c_block() -> None:
    blocks = re.findall(r"```ts\n(.*?)```", CONTRACT.read_text(encoding="utf-8"), re.S)
    assert len(blocks) == 2, "the main block and the Phase 13C block"
    assert COPY.read_text(encoding="utf-8") == blocks[1]
