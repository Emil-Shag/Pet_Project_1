from abc import ABC

from src.joint import Joint


class Element(ABC):
    """Абстрактный класс для элементов"""

    def __init__(self, element_type: str, joints: list[Joint]):
        self.element_type = element_type
        self.joints = joints

        for joint in joints:
            joint.elements.append(self)

    def element_number(self) -> str:
        """Номер элемента вида: 1-2; 3-4-5"""
        numbers = [str(j.number) for j in self.joints]
        return "-".join(numbers)

    def __repr__(self):
        return f"{self.element_type}({self.element_number()})"


class Pipe(Element):
    """Катушка"""

    def __init__(self, joint1: Joint, joint2: Joint):
        super().__init__("Катушка", [joint1, joint2])


class Elbow(Element):
    """Отвод"""

    def __init__(self, joint1: Joint, joint2: Joint):
        super().__init__("Отвод", [joint1, joint2])


class Tee(Element):
    """Тройник"""

    def __init__(self, joint1: Joint, joint2: Joint, joint3: Joint):
        super().__init__("Тройник", [joint1, joint2, joint3])
