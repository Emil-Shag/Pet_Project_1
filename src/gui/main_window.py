# src/gui/main_window.py
from __future__ import annotations

import sys
from math import cos, radians, sin

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QFont, QPainterPath, QPen, QBrush
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QGraphicsScene, QGraphicsView,
    QGraphicsEllipseItem, QGraphicsTextItem, QGraphicsPathItem,
    QMessageBox, QInputDialog, QDialog, QScrollArea, QFormLayout, QCheckBox, QDialogButtonBox,
    QLabel
)

from src.scheme import Scheme
from src.report import ReportTable
from src.element import (
    Axis, Element,
    Pipe, Elbow, Tee, Adapter, Fittings, Flange, Insert,
    Plug, CandlePipe, PipeBreak,
)

# ============================================================
# ISOMETRY (as in your axes image)
# Z is up, X is up-right, Y is up-left
# ============================================================
COS30 = cos(radians(30))
SIN30 = sin(radians(30))
UNIT = 80

AXES_VEC: dict[Axis, QPointF] = {
    "Z": QPointF(0, -UNIT),
    "X": QPointF(+COS30 * UNIT, -SIN30 * UNIT),
    "Y": QPointF(-COS30 * UNIT, -SIN30 * UNIT),
}

PIPE_PEN = QPen(QColor(0, 120, 255), 3)
PIPE_PEN.setCapStyle(Qt.RoundCap)
PIPE_PEN.setJoinStyle(Qt.RoundJoin)


# =========================
# GRAPHICS ITEMS
# =========================
class JointItem(QGraphicsEllipseItem):
    """Fixed joint (not movable) to keep geometry stable."""
    def __init__(self, joint, pos: QPointF, get_show_temp_ids):
        self.joint = joint
        self._get_show_temp_ids = get_show_temp_ids

        r = 5
        super().__init__(-r, -r, 2 * r, 2 * r)
        self.setBrush(QBrush(QColor("black")))
        self.setPen(QPen(QColor("black"), 1))
        self.setPos(pos)
        self.setFlag(QGraphicsEllipseItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsEllipseItem.ItemIsMovable, False)

        self.label = QGraphicsTextItem("", self)
        self.label.setDefaultTextColor(QColor("black"))
        self.label.setFont(QFont("Arial", 12))
        self.label.setPos(8, -22)
        self.update_label()

    def update_label(self):
        # RULES:
        # - if joint excluded from diagnostics: do not show anything
        # - if numbered: show number
        # - else show temp_id only if show_temp_ids=True (pre-numbering phase)
        if getattr(self.joint, "diagnostic", None) is False:
            self.label.setPlainText("")
            return

        if self.joint.number is not None:
            self.label.setPlainText(str(self.joint.number))
            return

        if self._get_show_temp_ids():
            self.label.setPlainText(str(self.joint.temp_id))
        else:
            self.label.setPlainText("")


class ElementItem(QGraphicsPathItem):
    def __init__(self, element: Element):
        super().__init__()
        self.element = element
        self.setPen(PIPE_PEN)
        self.setFlag(QGraphicsPathItem.ItemIsSelectable, True)


# =========================
# DIAGNOSTICS DIALOG
# =========================
class DiagnosticsDialog(QDialog):
    """
    - internal joints (>=2 connections): auto True if None, but user can exclude
    - terminal joints (<=1): ask if None
    """
    def __init__(self, scheme: Scheme, start_joint, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Диагностируемость стыков")
        self.scheme = scheme
        self.start_joint = start_joint

        for j in self.scheme.joints:
            if j.diagnostic is None and len(j.elements) >= 2:
                j.diagnostic = True

        self.terminal_checks: list[tuple[object, QCheckBox]] = []
        self.internal_checks: list[tuple[object, QCheckBox]] = []

        root = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form = QFormLayout(inner)

        terminals = [j for j in self.scheme.joints if len(j.elements) <= 1 and j.diagnostic is None]
        internals = [j for j in self.scheme.joints if len(j.elements) >= 2 and j.diagnostic is True]

        if terminals:
            for j in terminals:
                chk = QCheckBox("diagnostic")
                chk.setChecked(True)
                form.addRow(f"Крайний стык ID {j.temp_id} (подключено: {len(j.elements)})", chk)
                self.terminal_checks.append((j, chk))
        else:
            form.addRow("Крайние стыки без diagnostic отсутствуют.", QWidget())

        if internals:
            form.addRow("—", QWidget())
            form.addRow("Подстраховка (внутренние стыки):", QWidget())
            for j in internals:
                chk = QCheckBox("diagnostic")
                chk.setChecked(True)
                form.addRow(f"Внутренний стык ID {j.temp_id} (подключено: {len(j.elements)})", chk)
                self.internal_checks.append((j, chk))

        scroll.setWidget(inner)
        root.addWidget(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def apply(self):
        for j, chk in self.terminal_checks:
            val = chk.isChecked()
            if j is self.start_joint and not val:
                j.diagnostic = True
            else:
                j.diagnostic = val

        for j, chk in self.internal_checks:
            val = chk.isChecked()
            if j is self.start_joint and not val:
                j.diagnostic = True
            else:
                j.diagnostic = val


# =========================
# MAIN WINDOW
# =========================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Конструктор трубопровода (изометрия, CAD-логика)")
        self.resize(1450, 900)

        self.scheme = Scheme()

        # ---- palette
        self.list_widget = QListWidget()
        for name in [
            "Катушка", "Отвод", "Тройник", "Переход", "ТПА", "Фланец",
            "Врезка", "Заглушка", "Свечная труба", "Разрыв трубы"
        ]:
            QListWidgetItem(name, self.list_widget)

        self.add_btn = QPushButton("Добавить")
        self.delete_btn = QPushButton("Удалить")
        self.diagnostics_btn = QPushButton("Диагностика")
        self.number_btn = QPushButton("Нумерация + Отчёт")

        # ---- start direction chooser (sets direction of start joint)
        self.start_dir_label = QLabel("Стартовое направление (для первого элемента):")

        self.btn_sx_plus = QPushButton("X+"); self.btn_sx_plus.setCheckable(True)
        self.btn_sx_minus = QPushButton("X-"); self.btn_sx_minus.setCheckable(True)
        self.btn_sy_plus = QPushButton("Y+"); self.btn_sy_plus.setCheckable(True)
        self.btn_sy_minus = QPushButton("Y-"); self.btn_sy_minus.setCheckable(True)
        self.btn_sz_plus = QPushButton("Z+"); self.btn_sz_plus.setCheckable(True)
        self.btn_sz_minus = QPushButton("Z-"); self.btn_sz_minus.setCheckable(True)

        # default start direction: X+
        self.btn_sx_plus.setChecked(True)

        self._start_buttons = [
            ("X", +1, self.btn_sx_plus),
            ("X", -1, self.btn_sx_minus),
            ("Y", +1, self.btn_sy_plus),
            ("Y", -1, self.btn_sy_minus),
            ("Z", +1, self.btn_sz_plus),
            ("Z", -1, self.btn_sz_minus),
        ]
        for _, _, b in self._start_buttons:
            b.clicked.connect(self._on_start_button_clicked)

        # ---- continuation direction chooser (for elbow / branch)
        self.dir_label = QLabel("Продолжение (для отвода/ветки):")

        self.btn_x_plus = QPushButton("X+"); self.btn_x_plus.setCheckable(True)
        self.btn_x_minus = QPushButton("X-"); self.btn_x_minus.setCheckable(True)
        self.btn_y_plus = QPushButton("Y+"); self.btn_y_plus.setCheckable(True)
        self.btn_y_minus = QPushButton("Y-"); self.btn_y_minus.setCheckable(True)
        self.btn_z_plus = QPushButton("Z+"); self.btn_z_plus.setCheckable(True)
        self.btn_z_minus = QPushButton("Z-"); self.btn_z_minus.setCheckable(True)

        # default continuation: Z+
        self.btn_z_plus.setChecked(True)

        self._dir_buttons = [
            ("X", +1, self.btn_x_plus),
            ("X", -1, self.btn_x_minus),
            ("Y", +1, self.btn_y_plus),
            ("Y", -1, self.btn_y_minus),
            ("Z", +1, self.btn_z_plus),
            ("Z", -1, self.btn_z_minus),
        ]
        for _, _, btn in self._dir_buttons:
            btn.clicked.connect(self._on_dir_button_clicked)

        def get_selected_dir():
            for axis, sign, btn in self._dir_buttons:
                if btn.isChecked():
                    return (axis, sign)
            return ("Z", +1)

        self.get_selected_dir = get_selected_dir

        # ---- left layout
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(self.list_widget)

        left_layout.addWidget(self.add_btn)
        left_layout.addWidget(self.delete_btn)

        left_layout.addSpacing(10)

        left_layout.addWidget(self.start_dir_label)
        srow1 = QWidget()
        s1 = QHBoxLayout(srow1); s1.setContentsMargins(0, 0, 0, 0)
        s1.addWidget(self.btn_sx_plus); s1.addWidget(self.btn_sx_minus)
        s1.addWidget(self.btn_sy_plus); s1.addWidget(self.btn_sy_minus)
        left_layout.addWidget(srow1)
        srow2 = QWidget()
        s2 = QHBoxLayout(srow2); s2.setContentsMargins(0, 0, 0, 0)
        s2.addWidget(self.btn_sz_plus); s2.addWidget(self.btn_sz_minus)
        left_layout.addWidget(srow2)

        left_layout.addSpacing(10)

        left_layout.addWidget(self.dir_label)
        row1 = QWidget()
        r1 = QHBoxLayout(row1); r1.setContentsMargins(0, 0, 0, 0)
        r1.addWidget(self.btn_x_plus); r1.addWidget(self.btn_x_minus)
        r1.addWidget(self.btn_y_plus); r1.addWidget(self.btn_y_minus)
        left_layout.addWidget(row1)
        row2 = QWidget()
        r2 = QHBoxLayout(row2); r2.setContentsMargins(0, 0, 0, 0)
        r2.addWidget(self.btn_z_plus); r2.addWidget(self.btn_z_minus)
        left_layout.addWidget(row2)

        left_layout.addSpacing(10)
        left_layout.addWidget(self.diagnostics_btn)
        left_layout.addWidget(self.number_btn)
        left_layout.addStretch(1)

        # ---- scene/view
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHints(self.view.renderHints())

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.addWidget(left)
        root_layout.addWidget(self.view, 1)
        self.setCentralWidget(root)

        # ---- stores
        self.show_temp_ids = True  # before numbering
        self.start_joint = self.scheme.create_joint(diagnostic=True)

        self.joint_items: dict[object, JointItem] = {}
        self.element_items: list[ElementItem] = []
        self.element_item_by_element: dict[Element, ElementItem] = {}

        # joint -> (axis, sign)
        self.joint_dir: dict[object, tuple[Axis, int]] = {}

        self.ensure_joint_item(self.start_joint, QPointF(0, 0))
        self._apply_start_dir_to_start_joint()  # from start buttons

        self.active_joint = self.start_joint
        self._select_only_joint(self.start_joint)
        self._set_dir_buttons_for_joint(self.active_joint)

        # ---- connections
        self.add_btn.clicked.connect(self.add_element)
        self.delete_btn.clicked.connect(self.delete_element)
        self.diagnostics_btn.clicked.connect(self.run_diagnostics)
        self.number_btn.clicked.connect(self.number_and_report)
        self.scene.selectionChanged.connect(self.on_selection_changed)

    # -----------------------
    # UI helpers
    # -----------------------
    def _get_show_temp_ids(self):
        return self.show_temp_ids

    def _on_start_button_clicked(self):
        sender = self.sender()
        if sender is None:
            return
        # mutual exclusivity
        if not sender.isChecked():
            sender.setChecked(True)
            return
        for _, _, b in self._start_buttons:
            if b is not sender:
                b.setChecked(False)

        # apply to start joint direction immediately
        self._apply_start_dir_to_start_joint()

    def _apply_start_dir_to_start_joint(self):
        axis, sign = self.get_start_dir()
        self.joint_dir[self.start_joint] = (axis, sign)
        # if start is currently active, update continuation button availability
        if getattr(self, "active_joint", None) is self.start_joint:
            self._set_dir_buttons_for_joint(self.start_joint)

    def get_start_dir(self) -> tuple[Axis, int]:
        for axis, sign, btn in self._start_buttons:
            if btn.isChecked():
                return (axis, sign)
        return ("X", +1)

    def _on_dir_button_clicked(self):
        sender = self.sender()
        if sender is None:
            return
        if not sender.isChecked():
            sender.setChecked(True)
            return
        for _, _, btn in self._dir_buttons:
            if btn is not sender:
                btn.setChecked(False)

    def _set_dir_buttons_for_joint(self, joint):
        axis0, _ = self.joint_dir.get(joint, ("X", +1))
        # disable axis of current direction (can't choose same axis for elbow/branch continuation)
        for axis, sign, btn in self._dir_buttons:
            btn.setEnabled(axis != axis0)

        # if selected now disabled -> select first enabled
        selected_axis, _ = self.get_selected_dir()
        if selected_axis == axis0:
            for axis, sign, btn in self._dir_buttons:
                if btn.isEnabled():
                    btn.setChecked(True)
                    for a2, s2, b2 in self._dir_buttons:
                        if b2 is not btn:
                            b2.setChecked(False)
                    break

    def _select_only_joint(self, joint):
        self.scene.clearSelection()
        self.joint_items[joint].setSelected(True)

    def _select_only_element_item(self, item: ElementItem):
        self.scene.clearSelection()
        item.setSelected(True)

    # -----------------------
    # selection
    # -----------------------
    def on_selection_changed(self):
        sel = self.scene.selectedItems()
        if not sel:
            return

        # enforce single-selection behavior
        if len(sel) > 1:
            keep = sel[-1]
            self.scene.clearSelection()
            keep.setSelected(True)
            sel = [keep]

        item = sel[0]
        if isinstance(item, JointItem):
            self.active_joint = item.joint
            self._set_dir_buttons_for_joint(self.active_joint)

    # -----------------------
    # scene helpers
    # -----------------------
    def ensure_joint_item(self, joint, pos: QPointF) -> JointItem:
        if joint in self.joint_items:
            return self.joint_items[joint]
        ji = JointItem(joint, pos, self._get_show_temp_ids)
        self.joint_items[joint] = ji
        self.scene.addItem(ji)
        return ji

    def joint_pos(self, joint) -> QPointF:
        return self.joint_items[joint].pos()

    def step_vec(self, axis: Axis, sign: int, scale: float = 1.0) -> QPointF:
        v = AXES_VEC[axis] * scale
        return v if sign >= 0 else -v

    # -----------------------
    # draw paths
    # -----------------------
    def build_path(self, element: Element) -> QPainterPath:
        t = element.element_type
        path = QPainterPath()

        if t in ("Катушка", "Переход", "ТПА", "Фланец"):
            j1, j2 = element.joints
            p1 = self.joint_pos(j1)
            p2 = self.joint_pos(j2)
            path.moveTo(p1)
            path.lineTo(p2)
            return path

        if t == "Отвод":
            j1, j2 = element.joints
            p1 = self.joint_pos(j1)
            p2 = self.joint_pos(j2)
            bend = getattr(element, "_bend_pos", None)
            if bend is None:
                bend = (p1 + p2) * 0.5
            path.moveTo(p1)
            path.lineTo(bend)
            path.lineTo(p2)
            return path

        if t == "Тройник":
            jm1, jb, jm2 = element.joints
            p_in = self.joint_pos(jm1)
            p_main2 = self.joint_pos(jm2)
            p_branch = self.joint_pos(jb)

            center = getattr(element, "_center_pos", None)
            if center is None:
                path.moveTo(p_in)
                path.lineTo(p_main2)
                path.moveTo(p_in)
                path.lineTo(p_branch)
                return path

            path.moveTo(p_in)
            path.lineTo(center)
            path.lineTo(p_main2)

            path.moveTo(center)
            path.lineTo(p_branch)
            return path

        if t == "Врезка":
            jb1, jb2 = element.joints
            p1 = self.joint_pos(jb1)
            p2 = self.joint_pos(jb2)
            path.moveTo(p1)
            path.lineTo(p2)
            return path

        if t in ("Заглушка", "Свечная труба", "Разрыв трубы"):
            j = element.joints[0]
            p = self.joint_pos(j)
            axis = getattr(element, "axis", "X")
            sign = getattr(element, "sign", +1)
            v = self.step_vec(axis, sign, 0.25)

            if t == "Заглушка":
                path.moveTo(p)
                path.lineTo(p + v)
                cap = p + v
                perp = QPointF(-v.y(), v.x()) * 0.2
                path.moveTo(cap - perp)
                path.lineTo(cap + perp)
                return path

            if t == "Свечная труба":
                path.moveTo(p)
                path.lineTo(p + v)
                cap = p + v
                perp = QPointF(-v.y(), v.x()) * 0.15
                path.moveTo(cap - perp)
                path.lineTo(cap + perp)
                return path

            # Pipe break
            gap = v * 0.3
            path.moveTo(p - v)
            path.lineTo(p - gap)
            path.moveTo(p + gap)
            path.lineTo(p + v)
            return path

        return path

    def redraw_scene(self):
        for it in self.element_items:
            it.setPath(self.build_path(it.element))
        for ji in self.joint_items.values():
            ji.update_label()

    # -----------------------
    # add / delete
    # -----------------------
    def add_element(self):
        selected = self.list_widget.currentItem()
        if not selected:
            QMessageBox.warning(self, "Ошибка", "Выберите элемент слева.")
            return

        name = selected.text()
        base_joint = self.active_joint
        base_pos = self.joint_pos(base_joint)

        axis0, sign0 = self.joint_dir.get(base_joint, ("X", +1))
        element: Element | None = None

        # pass-through continues along previous direction
        if name in ("Катушка", "Переход", "ТПА", "Фланец"):
            end_joint = self.scheme.create_joint(diagnostic=None)
            end_pos = base_pos + self.step_vec(axis0, sign0, 1.0)
            self.ensure_joint_item(end_joint, end_pos)

            if name == "Катушка":
                element = Pipe(base_joint, end_joint, axis=axis0)
            elif name == "Переход":
                element = Adapter(base_joint, end_joint, axis=axis0)
            elif name == "ТПА":
                element = Fittings(base_joint, end_joint, axis=axis0)
                tag, ok = QInputDialog.getText(self, "ТПА", "Номер ТПА (например №3.1). Можно пусто:")
                if ok and tag.strip():
                    element.tag = tag.strip()
            elif name == "Фланец":
                element = Flange(base_joint, end_joint, axis=axis0)

            self.joint_dir[end_joint] = (axis0, sign0)

            # IMPORTANT: select only end joint, not start
            self.active_joint = end_joint
            self._select_only_joint(end_joint)
            self._set_dir_buttons_for_joint(self.active_joint)

        elif name == "Отвод":
            axis1, sign1 = self.get_selected_dir()
            if axis1 == axis0:
                QMessageBox.warning(self, "Отвод", "Продолжение отвода не может быть по той же оси. Выберите другую ось.")
                return

            end_joint = self.scheme.create_joint(diagnostic=None)
            bend = base_pos + self.step_vec(axis0, sign0, 0.5)
            end_pos = bend + self.step_vec(axis1, sign1, 0.5)
            self.ensure_joint_item(end_joint, end_pos)

            element = Elbow(base_joint, end_joint, axis_from=axis0, axis_to=axis1)
            element._bend_pos = bend

            self.joint_dir[end_joint] = (axis1, sign1)

            self.active_joint = end_joint
            self._select_only_joint(end_joint)
            self._set_dir_buttons_for_joint(self.active_joint)

        elif name == "Тройник":
            axis_b, sign_b = self.get_selected_dir()
            if axis_b == axis0:
                QMessageBox.warning(self, "Тройник", "Ось ветви не может совпадать с осью магистрали.")
                return

            main2_joint = self.scheme.create_joint(diagnostic=None)
            branch_joint = self.scheme.create_joint(diagnostic=None)

            # Центр тройника (НЕ стык), ровно посередине
            center = base_pos + self.step_vec(axis0, sign0, 0.5)

            # Выход магистрали: ещё 0.5 (итого 1.0 от входного)
            main2_pos = center + self.step_vec(axis0, sign0, 0.5)

            # Ветка: 0.5 от центра
            branch_pos = center + self.step_vec(axis_b, sign_b, 0.5)

            self.ensure_joint_item(main2_joint, main2_pos)
            self.ensure_joint_item(branch_joint, branch_pos)

            element = Tee(base_joint, branch_joint, main2_joint, axis_main=axis0, axis_branch=axis_b)
            element._center_pos = center

            self.joint_dir[main2_joint] = (axis0, sign0)
            self.joint_dir[branch_joint] = (axis_b, sign_b)

            self.active_joint = main2_joint
            self._select_only_joint(main2_joint)
            self._set_dir_buttons_for_joint(self.active_joint)

        elif name == "Врезка":
            host = self.choose_host_element()
            if host is None:
                QMessageBox.warning(self, "Врезка", "Нет элементов-хозяев.")
                return

            axis_b, sign_b = self.get_selected_dir()

            attach_pos = base_pos
            axis_host = getattr(host, "axis", "X")
            if hasattr(host, "joints") and len(host.joints) >= 2 and host.joints[0] in self.joint_items and host.joints[1] in self.joint_items:
                p1 = self.joint_pos(host.joints[0])
                p2 = self.joint_pos(host.joints[1])
                attach_pos = (p1 + p2) * 0.5
                axis_host = getattr(host, "axis", axis_host)

            if axis_b == axis_host:
                QMessageBox.warning(self, "Врезка", "Ось ветви не должна совпадать с осью хоста.")
                return

            jb1 = self.scheme.create_joint(diagnostic=None)
            jb2 = self.scheme.create_joint(diagnostic=None)

            self.ensure_joint_item(jb1, attach_pos)
            self.ensure_joint_item(jb2, attach_pos + self.step_vec(axis_b, sign_b, 0.9))

            element = Insert(host, jb1, jb2, axis_host=axis_host, axis_branch=axis_b)
            self.joint_dir[jb1] = (axis_b, sign_b)
            self.joint_dir[jb2] = (axis_b, sign_b)

        elif name in ("Заглушка", "Свечная труба", "Разрыв трубы"):
            if name == "Заглушка":
                element = Plug(base_joint, axis=axis0)
                element.sign = sign0
            elif name == "Свечная труба":
                element = CandlePipe(base_joint, axis=axis0)
                element.sign = sign0
            else:
                element = PipeBreak(base_joint, axis=axis0)
                element.sign = sign0

            # terminal doesn't change active joint
            self._select_only_joint(base_joint)

        else:
            QMessageBox.warning(self, "Ошибка", f"Элемент {name} не реализован.")
            return

        # add and draw
        self.scheme.add_element(element)
        item = ElementItem(element)
        self.scene.addItem(item)
        self.element_items.append(item)
        self.element_item_by_element[element] = item

        self.redraw_scene()

        # TPA tag label
        if element.element_type == "ТПА" and getattr(element, "tag", None) and len(element.joints) == 2:
            j1, j2 = element.joints
            mid = (self.joint_pos(j1) + self.joint_pos(j2)) * 0.5
            text = QGraphicsTextItem(element.tag)
            text.setDefaultTextColor(QColor("black"))
            text.setFont(QFont("Arial", 14))
            text.setPos(mid + QPointF(10, -30))
            self.scene.addItem(text)

    def delete_element(self):
        """
        Deletes selected element if an element is selected.
        Otherwise deletes the last added element.
        """
        target_el: Element | None = None

        sel = self.scene.selectedItems()
        if sel and isinstance(sel[0], ElementItem):
            target_el = sel[0].element
        elif self.scheme.elements:
            target_el = self.scheme.elements[-1]

        if target_el is None:
            QMessageBox.information(self, "Удалить", "Нет элементов для удаления.")
            return

        # remove graphics item
        gitem = self.element_item_by_element.get(target_el)
        if gitem is not None:
            self.scene.removeItem(gitem)
            if gitem in self.element_items:
                self.element_items.remove(gitem)
            self.element_item_by_element.pop(target_el, None)

        # remove from scheme list
        if target_el in self.scheme.elements:
            self.scheme.elements.remove(target_el)

        # detach from joints; remove orphan joints
        joints_to_check = list(getattr(target_el, "joints", []))
        for j in joints_to_check:
            if target_el in j.elements:
                j.elements.remove(target_el)

        # remove orphan joints (no elements), except start_joint
        for j in joints_to_check:
            if j is self.start_joint:
                continue
            if len(j.elements) == 0:
                # remove graphics
                ji = self.joint_items.pop(j, None)
                if ji is not None:
                    self.scene.removeItem(ji)
                # remove from scheme
                if j in self.scheme.joints:
                    self.scheme.joints.remove(j)
                # remove direction
                self.joint_dir.pop(j, None)

        # active joint fallback:
        # prefer last joint of last element if exists, else start_joint
        if self.scheme.elements:
            last = self.scheme.elements[-1]
            # choose "end" joint if possible (second joint)
            lj = last.joints[-1] if last.joints else self.start_joint
            if lj in self.joint_items:
                self.active_joint = lj
                self._select_only_joint(lj)
        else:
            self.active_joint = self.start_joint
            self._select_only_joint(self.start_joint)

        self._set_dir_buttons_for_joint(self.active_joint)
        self.redraw_scene()

    def choose_host_element(self) -> Element | None:
        if not self.scheme.elements:
            return None
        items = [f"{i + 1}. {e.element_type}" for i, e in enumerate(self.scheme.elements)]
        val, ok = QInputDialog.getItem(self, "Врезка", "Выберите элемент-хозяин:", items, 0, False)
        if not ok:
            return None
        idx = int(val.split(".")[0]) - 1
        return self.scheme.elements[idx]

    # -----------------------
    # diagnostics / numbering
    # -----------------------
    def run_diagnostics(self):
        dlg = DiagnosticsDialog(self.scheme, self.start_joint, self)
        if dlg.exec() == QDialog.Accepted:
            dlg.apply()
            self.redraw_scene()

    def number_and_report(self):
        # complete diagnostics if needed
        if any(j.diagnostic is None for j in self.scheme.joints):
            dlg = DiagnosticsDialog(self.scheme, self.start_joint, self)
            if dlg.exec() != QDialog.Accepted:
                return
            dlg.apply()

        # numbering
        try:
            self.scheme.number_joints(self.start_joint)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка нумерации", str(e))
            return

        # IMPORTANT: after numbering, stop showing temp IDs
        self.show_temp_ids = False

        # redraw labels with new rule
        self.redraw_scene()

        report = ReportTable(self.scheme)
        txt = "\n".join([f"{r[0]:<10} {r[1]:<18} {r[2]}" for r in report.rows()])
        QMessageBox.information(self, "Отчёт", txt)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
