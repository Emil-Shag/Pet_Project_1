from src.element import BranchingMixin, Element
from src.joint import Joint


class Scheme:
    def __init__(self):
        self.joints: list[Joint] = []
        self.elements: list[Element] = []

    def create_joint(self, diagnostic: bool = True) -> Joint:
        joint = Joint()
        joint.diagnostic = diagnostic
        self.joints.append(joint)
        return joint

    def add_element(self, element: Element):
        self.elements.append(element)

    # -----------------------
    # ВАЛИДАЦИЯ КОНЦЕВЫХ ЭЛЕМЕНТОВ
    # -----------------------
    def validate_terminal_elements(self):
        """
        Выставляет terminal=True только для концевых элементов на конце ветвей.
        Также стартовый элемент.
        """
        for element in self.elements:
            if element.element_type not in (
                "Заглушка", "Свечная труба", "Разрыв трубы", "Фланец", "ТПА"
            ):
                continue

            # стартовый элемент
            if any(j.number == 1 for j in element.joints):
                setattr(element, "terminal", True)
                continue

            # ищем конец ветви: стык без других элементов
            end_joint = None
            for joint in element.joints:
                if all(e == element for e in joint.elements):
                    end_joint = joint
                    break
            setattr(element, "terminal", end_joint is not None)

    def number_joints(self, start_joint: Joint):
        """
        Базовая нумерация стыков.
        Нумерует все диагностируемые стыки последовательно.
        """
        if not start_joint.diagnostic:
            raise ValueError("Стартовый стык не входит в диагностику")

        number = 1

        # стартовый стык
        start_joint.number = number
        visited = {start_joint}

        # остальные стыки
        for joint in self.joints:
            if joint in visited:
                continue
            if not joint.diagnostic:
                continue

            number += 1
            joint.number = number
            visited.add(joint)