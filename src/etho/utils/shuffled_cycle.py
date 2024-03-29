from typing import Iterable
from itertools import cycle
import random


class shuffled_cycle(cycle):
    """Shuffled cycle.

    cycle('ABCD')                  --> ABCD ABCD ABCD ...
    cycle('ABCD', shuffle='block') --> ACBD BDCA CDAB ...
    cycle('ABCD', shuffle='full')  --> ACCBBDBDCABA ...
    """

    def __init__(self, it: Iterable, shuffle: str = "block"):
        """.

        Arguments:
            it: Iterable
            shuffle: None, 'block', 'full'
        """
        allowed_shuffles = ["block", "full"]
        if shuffle not in allowed_shuffles:
            raise ValueError(f"shuffle should be one of {allowed_shuffles}.")
        super(shuffled_cycle, self).__init__()
        self._shuffle = shuffle
        self._it = list(it)
        self._pos = -1

    def __next__(self):
        """Return next item in iterator."""
        self._pos = (self._pos + 1) % len(self._it)  # wrap index
        if self._shuffle == "block":
            if self._pos == 0:
                random.shuffle(self._it)  # in-place shuffle the iterator
            idx = self._pos
        elif self._shuffle == "full":
            idx = random.randint(0, len(self._it) - 1)  # since randint bounds are inclusive
        # else:
        #     idx = self._pos
        return self._it[idx]

    def __deepcopy__(self, memo=None):
        cp = shuffled_cycle(self._it, shuffle=self._shuffle)
        cp._pos = self._pos
        return cp
