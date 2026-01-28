# src/scheme.py
from __future__ import annotations

from src.element import Element, Tee, Insert
from src.joint import Joint


class Scheme:
    def __init__(self):
        self.joints: list[Joint] = []
        self.elements: list[Element] = []

    def create_joint(self, diagnostic: bool | None = None) -> Joint:
        joint = Joint(diagnostic=diagnostic)
        self.joints.append(joint)
        return joint

    def add_element(self, element: Element):
        self.elements.append(element)

    def get_pending_joints(self) -> list[Joint]:
        """Стыки, для которых ещё не определили diagnostic"""
        return [j for j in self.joints if j.diagnostic is None]

    # -----------------------
    # ВСПОМОГАТЕЛЬНОЕ: соседи по графу
    # -----------------------
    @staticmethod
    def _neighbors(joint: Joint) -> list[Joint]:
        res: list[Joint] = []
        for el in joint.elements:
            for j in el.joints:
                if j is not joint:
                    res.append(j)
        return res

    # -----------------------
    # ПРОХОД ПО МАГИСТРАЛИ (основной ствол)
    # -----------------------
    def _next_main_joint(self, current: Joint, prev: Joint | None) -> Joint | None:
        """
        Возвращает следующий стык по магистрали из current, учитывая:
        - проходные элементы (2 стыка): идём на "другой конец", не возвращаясь в prev
        - тройник Tee: если current — магистральный стык, идём на второй магистральный
        Ветки здесь НЕ развиваем.
        """
        attached = sorted(current.elements, key=lambda e: e.element_type)

        for el in attached:
            # тройник: продолжение по main_joints
            if isinstance(el, Tee):
                if current in el.main_joints:
                    other_main = el.main_joints[0] if el.main_joints[1] is current else el.main_joints[1]
                    if other_main is not prev:
                        return other_main

            # проходной элемент на 2 стыка (Insert исключаем — он ветка)
            if len(el.joints) == 2 and not isinstance(el, Insert):
                j1, j2 = el.joints
                nxt = j2 if j1 is current else j1
                if nxt is not prev:
                    return nxt

        return None

    def _collect_main_trunk(self, start_joint: Joint) -> list[Joint]:
        """
        Возвращает список стыков магистрали в порядке потока: [J1, J2, J3, ...]
        Останавливается, когда продолжения нет.
        """
        trunk = [start_joint]
        visited = {start_joint}

        prev = None
        cur = start_joint

        while True:
            nxt = self._next_main_joint(cur, prev)
            if nxt is None or nxt in visited:
                break
            # на магистрали считаем только диагностируемые стыки
            if nxt.diagnostic is not True:
                break

            trunk.append(nxt)
            visited.add(nxt)
            prev, cur = cur, nxt

        return trunk

    # -----------------------
    # НУМЕРАЦИЯ ВЕТОК (DFS)
    # -----------------------
    def _dfs_number_component(self, start: Joint, number: int, visited: set[Joint]) -> int:
        """
        Нумерует связную компоненту графа, начиная со start, увеличивая number.
        Не заходит в уже visited (туда заранее кладём магистраль).
        """
        stack = [start]
        while stack:
            j = stack.pop()
            if j in visited or j.diagnostic is not True:
                continue

            number += 1
            j.number = number
            visited.add(j)

            neigh = self._neighbors(j)
            neigh_sorted = sorted(neigh, key=lambda x: x.temp_id, reverse=True)
            for n in neigh_sorted:
                if n not in visited and n.diagnostic is True:
                    stack.append(n)

        return number

    # -----------------------
    # ПУБЛИЧНЫЙ МЕТОД НУМЕРАЦИИ
    # -----------------------
    def number_joints(self, start_joint: Joint):
        """
        ЛОГИКА:
        1) Нумеруем магистраль целиком (по потоку)
        2) Собираем ответвления (Tee.branch_joint и Insert ветви) в порядке от начала магистрали
        3) Нумеруем каждую ветку целиком
        """
        if any(j.diagnostic is None for j in self.joints):
            raise ValueError("Есть стыки с неуказанным diagnostic. Сначала подтвердите их.")

        if start_joint.diagnostic is not True:
            raise ValueError("Стартовый стык не входит в диагностику")

        # очистка старых номеров
        for j in self.joints:
            j.number = None

        # 1) магистраль
        trunk = self._collect_main_trunk(start_joint)
        if not trunk:
            raise ValueError("Не удалось построить магистраль от стартового стыка")

        number = 1
        trunk[0].number = 1
        visited: set[Joint] = {trunk[0]}

        for j in trunk[1:]:
            number += 1
            j.number = number
            visited.add(j)

        # 2) собираем ветки в порядке "ближе к началу -> дальше"
        branch_seeds: list[tuple[int, Joint]] = []
        trunk_index = {j: idx for idx, j in enumerate(trunk)}

        # 2a) ветки от тройников
        for j in trunk:
            for el in j.elements:
                if isinstance(el, Tee):
                    seed = el.branch_joint
                    if seed.diagnostic is True and seed not in visited:
                        branch_seeds.append((trunk_index[j], seed))

        # 2b) ветки от врезок (Insert): привязаны к host_element
        for el in self.elements:
            if isinstance(el, Insert):
                host_joints = getattr(el.host_element, "joints", [])
                host_positions = [trunk_index[j] for j in host_joints if j in trunk_index]
                if not host_positions:
                    continue

                pos = min(host_positions)
                seed = el.joints[0]
                if seed.diagnostic is True and seed not in visited:
                    branch_seeds.append((pos, seed))

        branch_seeds.sort(key=lambda x: x[0])

        # 3) нумеруем ветки
        for _, seed in branch_seeds:
            number = self._dfs_number_component(seed, number, visited)

        return number

    def get_joint_by_number(self, number: int) -> Joint | None:
        for joint in self.joints:
            if joint.number == number:
                return joint
        return None

    def terminal_joints(self) -> list[Joint]:
        """Крайние стыки: подключены максимум к одному элементу"""
        return [j for j in self.joints if len(j.elements) <= 1]

    def internal_joints(self) -> list[Joint]:
        """Внутренние стыки: подключены минимум к двум элементам"""
        return [j for j in self.joints if len(j.elements) >= 2]
