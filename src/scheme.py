# src/scheme.py
from __future__ import annotations
from collections import deque
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
    def _neighbors(self, joint: Joint) -> list[Joint]:
        """Соседние стыки по элементам (обычные связи по стыкам)."""
        out = []
        for e in joint.elements:
            for j in e.joints:
                if j is not joint:
                    out.append(j)
        return out

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
        Нумерация:
        - идём по магистрали от start_joint
        - у тройника: номера трёх стыков идут подряд (цельный элемент)
        - обход ветви тройника откладываем, чтобы магистраль пронумеровалась первой
        """
        if not start_joint.diagnostic:
            raise ValueError("Стартовый стык не входит в диагностику")

        # сброс старых номеров (важно, чтобы не мешали повторные нумерации)
        for j in self.joints:
            j.number = None

        def is_diag(j: Joint) -> bool:
            return getattr(j, "diagnostic", True) is True

        current = start_joint
        num = 1
        current.number = num
        visited = {current}

        # ветви откладываем сюда (по близости к началу они попадут раньше)
        branch_queue = deque()

        def pick_next_main_from_joint(joint: Joint) -> tuple[Joint | None, Joint | None]:
            """
            Если в joint сидит тройник и joint — его магистральный стык,
            возвращаем (main_next, branch_joint). Иначе (None, None).
            """
            for e in joint.elements:
                if isinstance(e, Tee):
                    # в твоём element.py у Tee есть main_joints и branch_joint
                    mj1, mj2 = e.main_joints
                    bj = e.branch_joint

                    if joint is mj1:
                        return mj2, bj
                    if joint is mj2:
                        return mj1, bj
            return None, None

        def pick_linear_next(prev: Joint | None, joint: Joint) -> Joint | None:
            """
            Выбираем "следующий" стык по магистрали, если это линейный проход:
            - берём соседа, который не visited и не prev (если prev задан)
            """
            candidates = []
            for nb in self._neighbors(joint):
                if nb in visited:
                    continue
                if prev is not None and nb is prev:
                    continue
                if not is_diag(nb):
                    continue
                candidates.append(nb)
            if not candidates:
                return None
            # если вдруг несколько — берём первый (для MVP), потом улучшим правилом
            return candidates[0]

        prev = None

        # 1) сначала идём по магистрали
        while True:
            # обработка тройника: main_next и branch должны получить номера подряд
            main_next, branch = pick_next_main_from_joint(current)

            if main_next is not None and is_diag(main_next) and main_next not in visited:
                num += 1
                main_next.number = num
                visited.add(main_next)

                # ветвь тройника: номер сразу следом (чтобы у тройника было подряд),
                # но сам обход ветви откладываем
                if branch is not None and is_diag(branch) and branch not in visited:
                    num += 1
                    branch.number = num
                    visited.add(branch)
                    branch_queue.append(branch)

                prev, current = current, main_next
                continue

            # обычный линейный шаг
            nxt = pick_linear_next(prev, current)
            if nxt is None:
                break
            num += 1
            nxt.number = num
            visited.add(nxt)
            prev, current = current, nxt

        # 2) затем идём по ветвям (в порядке близости: как их добавили в очередь)
        while branch_queue:
            start_branch = branch_queue.popleft()

            # локальный DFS от стартового стыка ветви
            stack = [start_branch]
            while stack:
                j = stack.pop()
                for nb in self._neighbors(j):
                    if nb in visited:
                        continue
                    if not is_diag(nb):
                        continue

                    # если на ветви встречается тройник — применяем ту же логику:
                    # main_next/branch получат номера подряд, а вторую ветвь в очередь
                    main_next, branch = pick_next_main_from_joint(j)

                    if main_next is not None and is_diag(main_next) and main_next not in visited:
                        num += 1
                        main_next.number = num
                        visited.add(main_next)
                        stack.append(main_next)

                        if branch is not None and is_diag(branch) and branch not in visited:
                            num += 1
                            branch.number = num
                            visited.add(branch)
                            branch_queue.append(branch)
                        continue

                    # обычный шаг
                    num += 1
                    nb.number = num
                    visited.add(nb)
                    stack.append(nb)

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

