from utils.shuffled_cycle import shuffled_cycle


def test_shuffled_cycle():
    sc = shuffled_cycle(range(4))
    print([next(sc) for _ in range(10)])

    sc = shuffled_cycle(range(4), shuffle='block')
    print([next(sc) for _ in range(10)])

    sc = shuffled_cycle(range(4), shuffle='full')
    print([next(sc) for _ in range(10)])
