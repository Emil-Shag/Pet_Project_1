from abc import ABC

from src.joint import Joint


class Element(ABC):
    """Абстрактный класс для элементов"""

    def __init__(self, element_type: str, joints: list[Joint], role: str):
        self.element_type = element_type
        self.joints = joints
        self.role = role

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
        super().__init__("Катушка", [joint1, joint2], role="pass")


class Elbow(Element):
    """Отвод"""

    def __init__(self, joint1: Joint, joint2: Joint):
        super().__init__("Отвод", [joint1, joint2], role="pass")


class Tee(Element):
    """ Тройник """
    def __init__(self, joint1: Joint, joint2: Joint, joint3: Joint):
        super().__init__("Тройник", [joint1, joint2, joint3], role="branch")


class Adapter(Element):
    """ Переход """
    def __init__(self, joint1: Joint, joint2: Joint):
        super().__init__("Переход", [joint1, joint2], role="pass")


class Plug(Element):
    """ Заглушка """
    def __init__(self, joint1: Joint):
        super().__init__("Заглушка", [joint1], role="terminal")


class Fittings(Element):
    """ ТПА """
    def __init__(self, joint1: Joint, joint2: Joint):
        super().__init__("ТПА", [joint1, joint2], role="pass")


class Flange(Element):
    """ Фланец """
    def __init__(self, joint1: Joint, joint2: Joint):
        super().__init__("Фланец", [joint1, joint2], role="pass")


class CandlePipe(Element):
    """ Свечная труба """
    def __init__(self, joint1: Joint):
        super().__init__("Свечная труба", [joint1], role="terminal")


class PipeBreak(Element):
    """ Разрыв трубы """
    def __init__(self, joint1: Joint):
        super().__init__("Разрыв трубы", [joint1], role="terminal")


class Branch(Element):
    """ Врезка """
    def __init__(self, joint1: Joint, joint2: Joint):
        super().__init__("Врезка", [joint1, joint2], role="branch")
