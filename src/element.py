from __future__ import annotations
from abc import ABC
from src.joint import Joint
from typing import Literal

Axis = Literal["X", "Y", "Z"]


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
    def __init__(self, joint1: Joint, joint2: Joint, axis: Axis = "X", display_len: float = 1.0):
        super().__init__("Катушка", [joint1, joint2])
        self.axis: Axis = axis
        self.display_len = display_len


class Elbow(Element):
    def __init__(self, joint1: Joint, joint2: Joint, axis_from: Axis = "X", axis_to: Axis = "Y",
                 display_len_from: float = 0.5, display_len_to: float = 0.5):
        super().__init__("Отвод", [joint1, joint2])
        if axis_from == axis_to:
            raise ValueError("Elbow axis_from и axis_to должны отличаться")
        self.axis_from: Axis = axis_from
        self.axis_to: Axis = axis_to
        self.display_len_from = display_len_from
        self.display_len_to = display_len_to


class Adapter(Element):
    def __init__(self, joint1: Joint, joint2: Joint, axis: Axis = "X"):
        super().__init__("Переход", [joint1, joint2])
        self.axis: Axis = axis


class Fittings(Element):
    def __init__(self, joint1: Joint, joint2: Joint, axis: str = "X", plane: str | None = None):
        super().__init__("ТПА", [joint1, joint2])
        self.axis = axis
        # plane: one of "XY","XZ","YZ" (default is any plane containing axis)
        self.plane = plane


class Flange(Element):
    def __init__(self, joint1: Joint, joint2: Joint, axis: Axis = "X"):
        super().__init__("Фланец", [joint1, joint2])
        self.axis: Axis = axis


class Tee(Element):
    def __init__(
        self,
        joint_main_1: Joint,
        joint_branch: Joint,
        joint_main_2: Joint,
        axis_main: Axis = "X",
        axis_branch: Axis = "Z",
    ):
        super().__init__("Тройник", [joint_main_1, joint_branch, joint_main_2])

        if axis_main == axis_branch:
            raise ValueError("Tee axis_main и axis_branch должны отличаться")

        self.main_joints = (joint_main_1, joint_main_2)
        self.branch_joint = joint_branch

        self.axis_main: Axis = axis_main
        self.axis_branch: Axis = axis_branch


class Insert(Element):
    """
    Врезка = ветка, привязанная к элементу host_element.
    Не вмешивается в магистральную нумерацию.
    """
    def __init__(
        self,
        host_element: Element,
        joint_branch_1: Joint,
        joint_branch_2: Joint,
        axis_host: Axis = "X",
        axis_branch: Axis = "Z",
    ):
        super().__init__("Врезка", [joint_branch_1, joint_branch_2])

        if axis_host == axis_branch:
            raise ValueError("Insert axis_host и axis_branch должны отличаться")

        self.host_element = host_element
        self.axis_host: Axis = axis_host
        self.axis_branch: Axis = axis_branch


class Plug(Element):
    def __init__(self, joint1: Joint, axis: Axis = "X"):
        super().__init__("Заглушка", [joint1])
        self.axis: Axis = axis


class CandlePipe(Element):
    def __init__(self, joint1: Joint, axis: Axis = "X"):
        super().__init__("Свечная труба", [joint1])
        self.axis: Axis = axis


class PipeBreak(Element):
    def __init__(self, joint1: Joint, axis: Axis = "X"):
        super().__init__("Разрыв трубы", [joint1])
        self.axis: Axis = axis
