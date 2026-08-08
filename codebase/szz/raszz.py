from .base import BaseSZZ

class RASZZ(BaseSZZ):
    def __init__(self, pyszz_dir: str):
        super().__init__(pyszz_dir, 'raszz')
