from src.element import Element
from src.joint import Joint


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
        start_joint.number = current_number

        visited = set()
        visited.add(start_joint)

        def dfs(joint: Joint):
            nonlocal current_number

            for neighbor in self._get_neighbors(joint):
                if neighbor not in visited:
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
