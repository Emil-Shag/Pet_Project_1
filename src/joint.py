class Joint:
    """Стыки (сварные швы)"""

    _counter = 1

    def __init__(self):
        self.temp_id = Joint._counter
        Joint._counter += 1
        self.number = None
        self.elements = []

    def __repr__(self):
        return f"Joint({self.number})"
