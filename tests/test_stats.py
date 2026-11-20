from testhub.stats import percentile


def test_percentile():
    assert percentile([1, 2, 3, 4], .5) == 2.5
    assert percentile([10], .95) == 10
    assert percentile([], .95) == 0
