from abc import ABC
from src.joint import Joint


class Element(ABC):
    """Абстрактный класс для всех элементов трубопровода"""

    def __init__(self, element_type: str, joints: list[Joint]):
        self.element_type = element_type
        self.joints = joints

        for joint in joints:
            joint.elements.append(self)

    def element_number(self) -> str:
        """Сырой номер по стыкам (без '0-' правил)"""
        return "-".join(str(j.number) for j in self.joints)

    def __repr__(self):
        return f"{self.element_type}({self.element_number()})"


class Pipe(Element):
    def __init__(self, joint1: Joint, joint2: Joint):
        super().__init__("Катушка", [joint1, joint2])


class Elbow(Element):
    def __init__(self, joint1: Joint, joint2: Joint):
        super().__init__("Отвод", [joint1, joint2])


class Adapter(Element):
    def __init__(self, joint1: Joint, joint2: Joint):
        super().__init__("Переход", [joint1, joint2])


class Fittings(Element):
    def __init__(self, joint1: Joint, joint2: Joint):
        super().__init__("ТПА", [joint1, joint2])


class Flange(Element):
    def __init__(self, joint1: Joint, joint2: Joint):
        super().__init__("Фланец", [joint1, joint2])


class Tee(Element):
    """
    Тройник: два стыка — магистральные (на одной прямой), третий — ветвь.
    ВАЖНО: joint_main_1 и joint_main_2 должны быть именно магистральными.
    """
    def __init__(self, joint_main_1: Joint, joint_branch: Joint, joint_main_2: Joint):
        super().__init__("Тройник", [joint_main_1, joint_branch, joint_main_2])
        self.main_joints = (joint_main_1, joint_main_2)
        self.branch_joint = joint_branch


class Insert(Element):
    """
    Врезка в твоей логике НЕ вмешивается в магистральную нумерацию.
    Она — отдельная ветвь, "привязанная" к элементу магистрали (host_element),
    но НЕ подключенная к магистральным стыкам как граф.
    """
    def __init__(self, host_element: Element, joint_branch_1: Joint, joint_branch_2: Joint):
        super().__init__("Врезка", [joint_branch_1, joint_branch_2])
        self.host_element = host_element


# Концевые элементы (по желанию можешь оставить как было)
class Plug(Element):
    def __init__(self, joint1: Joint):
        super().__init__("Заглушка", [joint1])


class CandlePipe(Element):
    def __init__(self, joint1: Joint):
        super().__init__("Свечная труба", [joint1])


class PipeBreak(Element):
    def __init__(self, joint1: Joint):
        super().__init__("Разрыв трубы", [joint1])
