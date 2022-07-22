import pytest

from secateur.utils import TokenBucket, chunks


def test_token_bucket() -> None:
    b = TokenBucket(time=50.0, value=100.0, rate=2.0, max=200.0)
    assert b.value_at(50) == 100
    assert b.value_at(99) == 198
    assert b.value_at(101) == 200
    assert b.value_at(500) == 200
    assert b.value_at(1) == 2
    assert b.value_at(-5) == -10

    b = b.withdraw(time=100.0, value=100.0)
    b = b.withdraw(time=101.0, value=100.0)
    assert b.value == 2.0


@pytest.mark.parametrize(
    "iterable,size,output",
    [
        ([1, 2, 3], 2, [[1, 2], [3]]),
        ([1, 2], 2, [[1, 2]]),
        ([1], 2, [[1]]),
        ([], 2, []),
    ],
)
def test_chunks(iterable, size, output):
    assert list(chunks(iterable, size)) == output
