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
        """Возвращает номер элемента в виде '1-2' или '3-4-5'"""
        numbers = [str(j.number if j.number is not None else 0) for j in self.joints]
        return "-".join(numbers)

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
    """Катушка"""

    def __init__(self, joint1: Joint, joint2: Joint):
        super().__init__("Катушка", [joint1, joint2])


class Elbow(Element):
    """Отвод"""

    def __init__(self, joint1: Joint, joint2: Joint):
        super().__init__("Отвод", [joint1, joint2])


class Tee(BranchingMixin, Element):
    """Тройник"""

    def __init__(self, joint_main_1: Joint, joint_branch: Joint, joint_main_2: Joint):
        super().__init__("Тройник", [joint_main_1, joint_branch, joint_main_2])
        self.main_joints = (joint_main_1, joint_main_2)
        self.branch_joint = joint_branch


class Adapter(Element):
    """Переход"""

    def __init__(self, joint1: Joint, joint2: Joint):
        super().__init__("Переход", [joint1, joint2])


class Fittings(Element):
    """ТПА"""

    def __init__(self, joint1: Joint, joint2: Joint):
        super().__init__("ТПА", [joint1, joint2])


class Flange(Element):
    """Фланец"""

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
    """Заглушка"""

    def __init__(self, joint1: Joint):
        super().__init__("Заглушка", [joint1])


class CandlePipe(Element):
    """Свечная труба"""

    def __init__(self, joint1: Joint):
        super().__init__("Свечная труба", [joint1])


class PipeBreak(Element):
    """Разрыв трубы"""

    def __init__(self, joint1: Joint):
        super().__init__("Разрыв трубы", [joint1])
