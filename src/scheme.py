from src.element import BranchingMixin, Element
from src.joint import Joint


class SchemeValidationError(Exception):
    pass


class Scheme:
    """Сборка элементов в схему"""

    def __init__(self):
        self.joints: list[Joint] = []
        self.elements: list[Element] = []

    def create_joint(self, diagnostic: bool = True) -> Joint:
        """Создание стыка"""
        joint = Joint()
        joint.diagnostic = diagnostic
        self.joints.append(joint)
        return joint

    def add_element(self, element: Element):
        """Добавление элемента"""
        self.elements.append(element)

    # -----------------------
    # НУМЕРАЦИЯ СТЫКОВ
    # -----------------------
    def number_joints(self, start_joint: Joint):
        if not getattr(start_joint, "diagnostic", True):
            raise ValueError("Стартовый стык не входит в диагностику")

        number = 1
        start_joint.number = number
        visited = {start_joint}
        branches: list[tuple[Joint, Joint]] = []

        current = start_joint
        came_from = None

        # 1️⃣ Нумерация основного ствола
        while True:
            neighbors = Scheme._get_neighbors(current, came_from)

            if not neighbors:
                break

            if len(neighbors) > 1:
                main_pair, branch_pair = Scheme._resolve_branch(current, came_from, neighbors)
                if branch_pair is not None:
                    branches.append(branch_pair)
                next_joint, _ = main_pair
            else:
                next_joint, _ = neighbors[0]

            if next_joint in visited:
                break

            number += 1
            next_joint.number = number
            visited.add(next_joint)

            came_from = current
            current = next_joint

        # 2️⃣ Нумерация ветвей
        for branch_joint, from_joint in branches:
            number = self._number_branch(branch_joint, from_joint, number, visited)

        # 3️⃣ Островки
        for joint in self.joints:
            if not getattr(joint, "diagnostic", True) or joint in visited:
                continue

            number += 1
            joint.number = number
            visited.add(joint)

            number = self._number_branch(joint, None, number, visited)

    # -----------------------
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # -----------------------
    def _number_branch(self, start: Joint, came_from: Joint, number: int, visited: set) -> int:
        stack = [(start, came_from)]

        while stack:
            joint, prev = stack.pop()
            if joint in visited:
                continue

            number += 1
            joint.number = number
            visited.add(joint)

            for next_joint, _ in Scheme._get_neighbors(joint, prev):
                stack.append((next_joint, joint))

        return number

    @staticmethod
    def _get_neighbors(joint: Joint, came_from: Joint = None) -> list[tuple[Joint, Element]]:
        """Возвращает соседние стыки для обхода"""
        neighbors = []
        for element in joint.elements:
            for j in element.joints:
                if j is not joint and (came_from is None or j != came_from) and getattr(j, "diagnostic", True):
                    neighbors.append((j, element))
        return neighbors

    @staticmethod
    def _resolve_branch(current: Joint, came_from: Joint, options: list[tuple[Joint, Element]]):
        """
        Универсальный метод для ветвящихся элементов.
        Возвращает кортежи:
            - main_pair: tuple[Joint, Element]
            - branch_pair: tuple[Joint, Joint] | None
        """
        for joint, element in options:
            if isinstance(element, BranchingMixin):
                main, branch = element.resolve(current)

                # fallback на текущий стык, если resolve вернул None
                if main is None:
                    main = joint

                main_pair = (main, element)
                branch_pair = (branch, current) if branch is not None else None
                return main_pair, branch_pair

        # fallback: первый элемент в списке
        return options[0], None

    def get_joint_by_number(self, number: int) -> Joint | None:
        for joint in self.joints:
            if joint.number == number:
                return joint
        return None

    # -----------------------
    # ВАЛИДАЦИЯ
    # -----------------------
    def validate(self):
        """Проверка валидности схемы"""
        for joint in self.joints:
            if not joint.elements:
                continue

            # собираем концевые и проходные элементы на стыке
            terminal_elements = [
                e
                for e in joint.elements
                if e.element_type in ("Заглушка", "Свечная труба", "Разрыв трубы", "Фланец", "ТПА")
            ]
            passing_elements = [
                e
                for e in joint.elements
                if e.element_type not in ("Заглушка", "Свечная труба", "Разрыв трубы", "Фланец", "ТПА")
            ]

            if terminal_elements and passing_elements:
                # Разрешаем для стартового стыка
                if joint == self.joints[0]:
                    continue  # пропускаем проверку для стартового стыка
                # иначе для обычного стыка — ошибка
                raise ValueError(f"Стык {joint.number}: концевой элемент не может сочетаться с проходным")
