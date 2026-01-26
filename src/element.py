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
        """
        Возвращает номер элемента в виде '1-2' или '3-4-5'.
        Для концевых элементов с terminal=True один стык заменяется на 0.
        """
        numbers = []
        for idx, j in enumerate(self.joints):
            n = j.number if j.number is not None else 0
            numbers.append(n)

        # концевой элемент с двумя стыками
        if getattr(self, "terminal", False) and len(numbers) == 2:
            # стартовый элемент
            if numbers[0] == 1:
                numbers[0] = 0
            else:
                numbers[1] = 0

        return "-".join(str(n) for n in numbers)

    def __repr__(self):
        return f"{self.element_type}({self.element_number()})"


# ===============================
# МИКСИН ДЛЯ ВЕТВЯЩИХСЯ ЭЛЕМЕНТОВ
# ===============================
class BranchingMixin:
    """Миксин для элементов, создающих ветви (Tee, Insert)"""

    def resolve(self, current_joint: "Joint"):
        joints = getattr(self, "joints", [])
        if len(joints) == 3:  # Tee
            main = joints[0] if joints[0] != current_joint else joints[2]
            branch = joints[1]
            return main, branch

        if len(joints) == 2:  # Insert (врезка)
            main = joints[0] if joints[0] != current_joint else joints[1]
            branch = joints[1] if main == joints[0] else joints[0]
            return main, branch

        return None, None


# ===============================
# ПРОХОДНЫЕ ЭЛЕМЕНТЫ
# ===============================
class Pipe(Element):
    def __init__(self, joint1: Joint, joint2: Joint):
        super().__init__("Катушка", [joint1, joint2])


class Elbow(Element):
    def __init__(self, joint1: Joint, joint2: Joint):
        super().__init__("Отвод", [joint1, joint2])


class Tee(BranchingMixin, Element):
    def __init__(self, joint_main_1: Joint, joint_branch: Joint, joint_main_2: Joint):
        super().__init__("Тройник", [joint_main_1, joint_branch, joint_main_2])
        self.main_joints = (joint_main_1, joint_main_2)
        self.branch_joint = joint_branch


class Adapter(Element):
    def __init__(self, joint1: Joint, joint2: Joint):
        super().__init__("Переход", [joint1, joint2])


class Fittings(Element):
    def __init__(self, joint1: Joint, joint2: Joint):
        super().__init__("ТПА", [joint1, joint2])


class Flange(Element):
    def __init__(self, joint1: Joint, joint2: Joint):
        super().__init__("Фланец", [joint1, joint2])


class Insert(Element, BranchingMixin):
    """Врезка — обычная катушка с двумя концами"""
    def __init__(self, joint_main: Joint, joint_branch: Joint):
        super().__init__("Врезка", [joint_main, joint_branch])


# ===============================
# КОНЦЕВЫЕ ЭЛЕМЕНТЫ
# ===============================
class Plug(Element):
    def __init__(self, joint1: Joint):
        super().__init__("Заглушка", [joint1])


class CandlePipe(Element):
    def __init__(self, joint1: Joint):
        super().__init__("Свечная труба", [joint1])


class PipeBreak(Element):
    def __init__(self, joint1: Joint):
        super().__init__("Разрыв трубы", [joint1])
