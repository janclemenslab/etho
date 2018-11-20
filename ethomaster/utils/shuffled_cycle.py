from typing import Iterable
from itertools import cycle
import random


class shuffled_cycle(cycle):
    """Shuffled cycle.

    cycle('ABCD')                  --> ABCD ABCD ABCD ...
    cycle('ABCD', shuffle='block') --> ACBD BDCA CDAB ...
    cycle('ABCD', shuffle='full')  --> ACCBBDBDCABA ...
    """

    def __init__(self, it: Iterable, shuffle: str=None):
        """.

        Arguments:
            it: Iterable
            shuffle: None, 'block', 'full'
        """
        super(shuffled_cycle, self).__init__()
        self._shuffle = shuffle
        self._it = list(it)
        self._pos = -1


    def __next__(self):
        """Return next item in iterator."""
        self._pos = (self._pos+1) % len(self._it)  # wrap index
        if self._shuffle is 'block':
            if self._pos==0:
                random.shuffle(self._it)  # in-place shuffle
            idx = self._pos
        elif self._shuffle is 'full':
            idx = random.randint(0, len(self._it)-1)  # since randint bounds are inclusive
        else:
            idx = self._pos
        return self._it[idx]
