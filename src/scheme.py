from src.element import Element
from src.joint import Joint
from src.validation import SchemeValidationError

class Scheme:
    """Сборка элементов в схему"""

    def __init__(self):
        self.joints = []
        self.elements = []

    def create_joint(self) -> Joint:
        """Создание стыка"""
        joint = Joint()
        self.joints.append(joint)
        return joint

    def add_element(self, element: Element):
        """Добавление элемента"""
        self.elements.append(element)

    @staticmethod
    def _get_neighbors(joint: Joint) -> list[Joint]:
        """Добавление соседнего стыка"""
        neighbors = []
        for element in joint.elements:
            for j in element.joints:
                if j is not joint:
                    neighbors.append(j)
        return neighbors

    def number_joints(self, start_joint: Joint):
        """Добавление нумерации стыков"""
        current_number = 1

        if not start_joint.diagnostic:
            raise ValueError("Стартовый стык не входит в диагностику")

        start_joint.number = current_number
        visited = {start_joint}

        def dfs(joint: Joint):
            nonlocal current_number

            for neighbor in self._get_neighbors(joint):
                if neighbor in visited:
                    continue
                if not neighbor.diagnostic:
                    continue
                current_number += 1
                neighbor.number = current_number
                visited.add(neighbor)
                dfs(neighbor)

        dfs(start_joint)

    def get_joint_by_number(self, number: int) -> Joint | None:
        for joint in self.joints:
            if joint.number == number:
                return joint
        return None

    def validate(self):
        self._validate_joints_not_empty()
        self._validate_terminal_joints()
        self._validate_no_open_welds()

    def _validate_joints_not_empty(self):
        if not self.elements:
            raise SchemeValidationError("Схема не содержит элементов")

    def _validate_terminal_joints(self):
        for element in self.elements:
            if element.role != "terminal":
                continue

            joint = element.joints[0]

            connected = joint.elements

            if len(connected) > 2:
                raise SchemeValidationError(
                    f"Стык {joint.temp_id}: к концевому элементу подключено более одного элемента"
                )

            for e in connected:
                if e is not element and e.role == "terminal":
                    raise SchemeValidationError(
                        f"Стык {joint.temp_id}: два концевых элемента на одном стыке"
                    )

    def _validate_no_open_welds(self):
        for joint in self.joints:
            if len(joint.elements) == 1:
                element = joint.elements[0]

                if element.role != "terminal":
                    raise SchemeValidationError(
                        f"Открытый сварной шов: стык {joint.temp_id}"
                    )

    def apply_diagnostic_boundaries(self):
        for element in self.elements:
            element.apply_diagnostic_boundary()