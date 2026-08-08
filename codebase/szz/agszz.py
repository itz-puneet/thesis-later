from .base import BaseSZZ

class AGSZZ(BaseSZZ):
    def __init__(self, pyszz_dir: str):
        super().__init__(pyszz_dir, 'agszz')
