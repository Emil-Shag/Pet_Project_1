# src/scheme.py
from __future__ import annotations

from collections import deque
from typing import Optional

from src.joint import Joint
from src.element import Element, Tee, Insert


class Scheme:
    def __init__(self):
        self.joints: list[Joint] = []
        self.elements: list[Element] = []

    def create_joint(self, diagnostic: Optional[bool] = None) -> Joint:
        j = Joint(diagnostic=True if diagnostic is True else False if diagnostic is False else True)
        # ВАЖНО: чтобы поддержать None в GUI-логике диагностики,
        # мы храним None отдельно (как атрибут), если надо:
        if diagnostic is None:
            j.diagnostic = None
        self.joints.append(j)
        return j

    def add_element(self, element: Element):
        self.elements.append(element)

    # =========================
    # GRAPH HELPERS
    # =========================
    def _neighbors(self, joint: Joint) -> list[Joint]:
        """Соседние стыки по всем элементам, которые реально соединяют joint с другими стыками."""
        out: list[Joint] = []
        for el in joint.elements:
            for j in el.joints:
                if j is not joint:
                    out.append(j)
        return out

    def _is_diag(self, j: Joint) -> bool:
        return getattr(j, "diagnostic", True) is True

    # =========================
    # MERGE (for bypass cycles)
    # =========================
    def merge_joints(self, keep: Joint, drop: Joint) -> None:
        """
        Объединяет два стыка в один:
        - все элементы, которые ссылались на drop, начинают ссылаться на keep
        - keep.elements пополняется
        - drop удаляется из scheme.joints
        """
        if keep is drop:
            return

        # переназначаем ссылки у элементов
        for el in list(drop.elements):
            el.joints = [keep if j is drop else j for j in el.joints]
            if el not in keep.elements:
                keep.elements.append(el)

        drop.elements.clear()

        # diagnostic merge policy
        kd = getattr(keep, "diagnostic", None)
        dd = getattr(drop, "diagnostic", None)
        if kd is True or dd is True:
            keep.diagnostic = True
        elif kd is False and dd is False:
            keep.diagnostic = False
        else:
            keep.diagnostic = kd if kd is not None else dd

        if drop in self.joints:
            self.joints.remove(drop)

    # =========================
    # NUMBERING (mainline first, then branches, supports cycles)
    # =========================
    def number_joints(self, start_joint: Joint):
        """
        Нумерация стыков:
        - идём по магистрали от start_joint
        - у тройника: ВСЕ 3 стыка тройника получают номера подряд (цельный элемент)
        - ветви нумеруются после магистрали (в порядке "ближе к старту")
        - циклы допустимы: если пришли в уже пронумерованный стык — дальше по этому пути не идём
        - нумеруем только diagnostic=True
        """
        if not self._is_diag(start_joint):
            raise ValueError("Стартовый стык не входит в диагностику")

        # reset
        for j in self.joints:
            j.number = None

        num = 1
        start_joint.number = num
        visited: set[Joint] = {start_joint}

        branch_queue = deque()  # joints to start branches from (in order encountered)

        def enqueue_if_new(j: Optional[Joint]):
            if j is None:
                return
            if not self._is_diag(j):
                return
            if j in visited:
                return
            # IMPORTANT: assign number immediately when we enqueue from a Tee to keep Tee joints consecutive
            nonlocal num
            num += 1
            j.number = num
            visited.add(j)
            branch_queue.append(j)

        def number_if_new(j: Optional[Joint]) -> bool:
            """Assigns next number if joint is diagnostic and not visited. Returns True if numbered."""
            if j is None:
                return False
            if not self._is_diag(j):
                return False
            if j in visited:
                return False
            nonlocal num
            num += 1
            j.number = num
            visited.add(j)
            return True

        def get_tee_at_joint(joint: Joint) -> Optional[Tee]:
            for el in joint.elements:
                if isinstance(el, Tee):
                    return el
            return None

        def handle_branching_from_joint(joint: Joint):
            """
            - Tee: number main_out, then number+enqueue branch immediately (so 3 joints consecutive for Tee)
            - Insert: does NOT affect mainline; but its other joint becomes a branch start (enqueue/number now)
            """
            tee = get_tee_at_joint(joint)
            if tee is not None:
                # determine main_out and branch
                mj1, mj2 = tee.main_joints
                branch = tee.branch_joint
                if joint is mj1:
                    main_out = mj2
                elif joint is mj2:
                    main_out = mj1
                else:
                    # joint is branch itself — then for traversal treat as normal later
                    main_out = None

                return main_out, branch

            # Inserts: they represent a branch start but should not become "main step"
            # If current joint has Insert attached, enqueue its other joint as a branch start.
            for el in joint.elements:
                if isinstance(el, Insert):
                    # Insert has 2 joints: main & branch (in your model)
                    j_other = el.joints[0] if el.joints[1] is joint else el.joints[1]
                    # number+enqueue now (so insert joint gets a number, but traversal of that branch is later)
                    enqueue_if_new(j_other)

            return None, None

        def pick_linear_next(prev: Optional[Joint], cur: Joint) -> Optional[Joint]:
            """
            Choose next joint along mainline when not forced by Tee:
            - among neighbors, prefer not visited, diagnostic=True, and not prev
            - if multiple (cycle), pick deterministic by temp_id
            """
            cands = []
            for nb in self._neighbors(cur):
                if nb in visited:
                    continue
                if prev is not None and nb is prev:
                    continue
                if not self._is_diag(nb):
                    continue
                cands.append(nb)
            if not cands:
                return None
            cands.sort(key=lambda x: x.temp_id)
            return cands[0]

        # --------------------------
        # 1) MAINLINE traversal
        # --------------------------
        prev = None
        cur = start_joint

        while True:
            # if Tee at cur (and cur is on its mainline), force main_out, and number branch immediately
            main_out, branch = handle_branching_from_joint(cur)

            if main_out is not None:
                # number main_out first
                if number_if_new(main_out):
                    # then number+enqueue branch (so Tee joints are consecutive)
                    enqueue_if_new(branch)
                    prev, cur = cur, main_out
                    continue
                else:
                    # main_out already visited => cycle or already numbered
                    # still ensure branch is queued if possible (but without renumbering)
                    if branch is not None and self._is_diag(branch) and branch not in visited:
                        enqueue_if_new(branch)
                    break

            # normal linear step
            nxt = pick_linear_next(prev, cur)
            if nxt is None:
                break

            number_if_new(nxt)  # always true here, but safe for cycles
            prev, cur = cur, nxt

        # --------------------------
        # 2) BRANCHES traversal (BFS order by closeness)
        # --------------------------
        while branch_queue:
            start_b = branch_queue.popleft()

            stack = [start_b]
            while stack:
                j = stack.pop()

                # branching inside branch
                main_out, branch = handle_branching_from_joint(j)
                if main_out is not None:
                    if number_if_new(main_out):
                        enqueue_if_new(branch)  # number+enqueue branch-of-branch now
                        stack.append(main_out)
                    else:
                        # reached already-numbered joint => cycle closure, stop this direction
                        if branch is not None and self._is_diag(branch) and branch not in visited:
                            enqueue_if_new(branch)
                    continue

                # generic neighbors
                for nb in self._neighbors(j):
                    if not self._is_diag(nb):
                        continue
                    if nb in visited:
                        continue  # cycle closure / already numbered
                    number_if_new(nb)
                    stack.append(nb)
