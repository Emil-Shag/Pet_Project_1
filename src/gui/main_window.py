
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

SYMBOL_PEN = QPen(QColor(0, 120, 255), 2)
SYMBOL_PEN.setCapStyle(Qt.RoundCap)
SYMBOL_PEN.setJoinStyle(Qt.RoundJoin)

THIN_BLACK = QPen(QColor(0, 0, 0), 1)

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
        # Rules:
        # - excluded from diagnostics => hide
        # - numbered => show number
        # - else show temp_id only if show_temp_ids=True
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
        # separate symbol path (valves/flanges/adapters/etc.)
        self.symbol = QGraphicsPathItem(self)
        self.symbol.setPen(SYMBOL_PEN)

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
        self.resize(1550, 900)

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
        self.connect_btn = QPushButton("Соединить (байпас)")

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
        left_layout.addWidget(self.connect_btn)

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

        # connect (bypass) mode state
        self.connect_mode = False
        self.connect_first_joint = None
        # bypass alignment anchors
        self.last_bypass_pair = None  # (A_joint, B_joint)
        # UI drawing tweak: store bend for the element that was "connected" to another joint
        # element -> QPointF bend point
        self.element_connection_bend: dict[Element, QPointF] = {}
        self.element_connection_keep: dict[Element, object] = {}

        self.ensure_joint_item(self.start_joint, QPointF(0, 0))
        self._apply_start_dir_to_start_joint()

        self.active_joint = self.start_joint
        self._select_only_joint(self.start_joint)
        self._set_dir_buttons_for_joint(self.active_joint)

        # ---- connections
        self.add_btn.clicked.connect(self.add_element)
        self.delete_btn.clicked.connect(self.delete_element)
        self.connect_btn.clicked.connect(self.toggle_connect_mode)

        self.diagnostics_btn.clicked.connect(self.run_diagnostics)
        self.number_btn.clicked.connect(self.number_and_report)
        self.scene.selectionChanged.connect(self.on_selection_changed)

    # -----------------------
    # geometry helpers
    # -----------------------
    def step_vec(self, axis: Axis, sign: int, scale: float = 1.0) -> QPointF:
        v = AXES_VEC[axis] * scale
        return v if sign >= 0 else -v

    def _axis_line_intersection(self, p1: QPointF, d1: QPointF, p2: QPointF, d2: QPointF) -> QPointF | None:
        """
        Solve p1 + t*d1 = p2 + u*d2 for t,u. Return intersection point if not parallel.
        """
        det = d1.x() * (-d2.y()) - d1.y() * (-d2.x())  # det([d1, -d2])
        if abs(det) < 1e-9:
            return None
        rhs = p2 - p1
        t = (rhs.x() * (-d2.y()) - rhs.y() * (-d2.x())) / det
        return p1 + d1 * t

    def _project_point_to_axis_line(self, p: QPointF, origin: QPointF, d: QPointF) -> QPointF:
        """Project point p to line origin + t*d."""
        v = p - origin
        dd = d.x() * d.x() + d.y() * d.y()
        if dd == 0:
            return origin
        t = (v.x() * d.x() + v.y() * d.y()) / dd
        return origin + d * t

    # -----------------------
    # UI helpers
    # -----------------------
    def _get_show_temp_ids(self):
        return self.show_temp_ids

    def _on_start_button_clicked(self):
        sender = self.sender()
        if sender is None:
            return
        if not sender.isChecked():
            sender.setChecked(True)
            return
        for _, _, b in self._start_buttons:
            if b is not sender:
                b.setChecked(False)
        self._apply_start_dir_to_start_joint()

    def _apply_start_dir_to_start_joint(self):
        axis, sign = self.get_start_dir()
        self.joint_dir[self.start_joint] = (axis, sign)
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
        for axis, sign, btn in self._dir_buttons:
            btn.setEnabled(axis != axis0)

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

    # -----------------------
    # connect (bypass) mode
    # -----------------------
    def toggle_connect_mode(self):
        self.connect_mode = not self.connect_mode
        self.connect_first_joint = None

        if self.connect_mode:
            self.connect_btn.setText("Соединить (выберите 1-й стык)")
            QMessageBox.information(
                self, "Соединить (байпас)",
                "Режим соединения включён.\n"
                "Кликните по 1-му стыку, затем по 2-му стыку.\n"
                "Стыки будут объединены в один.\n\n"
                "Линия соединения будет нарисована с последним участком параллельно магистрали."
            )
        else:
            self.connect_btn.setText("Соединить (байпас)")

    # -----------------------
    # selection
    # -----------------------
    def on_selection_changed(self):
        sel = self.scene.selectedItems()
        if not sel:
            return

        if len(sel) > 1:
            keep = sel[-1]
            self.scene.clearSelection()
            keep.setSelected(True)
            sel = [keep]

        item = sel[0]

        if isinstance(item, JointItem):
            clicked_joint = item.joint

            if self.connect_mode:
                self._handle_connect_click(clicked_joint)
                return

            # NORMAL MODE: clicking a joint moves "building cursor" there (so you can build branches)
            self.active_joint = clicked_joint
            self._select_only_joint(clicked_joint)
            self._set_dir_buttons_for_joint(clicked_joint)
            return

        # ElementItem selection: no cursor move

    def _handle_connect_click(self, joint):
        if self.connect_first_joint is None:
            self.connect_first_joint = joint
            self.connect_btn.setText("Соединить (выберите 2-й стык)")
            QMessageBox.information(self, "Соединить (байпас)",
                                    f"Первый стык выбран: ID {joint.temp_id}.\nТеперь выберите второй стык.")
            return

        first = self.connect_first_joint
        second = joint

        if second is first:
            QMessageBox.warning(self, "Соединить (байпас)", "Вы выбрали тот же стык. Выберите другой.")
            return

        keep, drop = first, second  # keep = first selected (as you requested)

        # remember bypass anchors BEFORE merge
        self.last_bypass_pair = (keep, drop)

        # Find the "incoming" element that ends at drop (usually last element of a branch)
        incoming_element = None
        for e in list(drop.elements):
            # Prefer element that is not also attached to keep (rare but can happen)
            if keep not in getattr(e, "joints", []):
                incoming_element = e
                break
        if incoming_element is None and drop.elements:
            incoming_element = drop.elements[0]

        # Compute an L-bend so the last segment is parallel to the "magистраль" direction at keep.
        p_keep = self.joint_pos(keep)
        p_drop = self.joint_pos(drop)

        axis_keep, sign_keep = self.joint_dir.get(keep, ("X", +1))
        axis_drop, sign_drop = self.joint_dir.get(drop, ("X", +1))

        d_main = self.step_vec(axis_keep, sign_keep, 1.0)
        d_branch = self.step_vec(axis_drop, sign_drop, 1.0)

        # Intersection of lines: drop + t*branch and keep + u*main => perfect 2-axis polyline
        bend = self._axis_line_intersection(p_drop, d_branch, p_keep, d_main)

        # Fallback: projection to main line (still guarantees last segment parallel to main)
        if bend is None:
            bend = self._project_point_to_axis_line(p_drop, p_keep, d_main)

        # Merge joints in model
        try:
            self.scheme.merge_joints(keep, drop)  # must exist in Scheme
        except Exception as e:
            QMessageBox.critical(self, "Соединить (байпас)", f"Ошибка при объединении стыков: {e}")
            return

        # auto bypass alignment
        if self.last_bypass_pair:
            self._auto_align_bypass(self.last_bypass_pair[0], keep)

        # SOFT SNAP after alignment: directions строго X/Y/Z, длины любые
        self._apply_soft_snap_chain_from(self.start_joint)

        # store bend override for drawing on incoming element
        if incoming_element is not None:
            self.element_connection_bend[incoming_element] = bend
            self.element_connection_keep[incoming_element] = keep

        # remove drop from direction map
        self.joint_dir.pop(drop, None)

        # remove drop graphics item
        drop_item = self.joint_items.pop(drop, None)
        if drop_item is not None:
            self.scene.removeItem(drop_item)

        # set cursor to keep
        self.active_joint = keep
        self._set_dir_buttons_for_joint(keep)
        self._select_only_joint(keep)

        # exit connect mode
        self.connect_mode = False
        self.connect_first_joint = None
        self.connect_btn.setText("Соединить (байпас)")

        self.redraw_scene()

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

    # -----------------------
    # draw paths
    # -----------------------
    def build_paths(self, element: Element) -> tuple[QPainterPath, QPainterPath]:
        t = element.element_type
        pipe = QPainterPath()
        sym = QPainterPath()

        # If element was used as a "connection-to-keep" after merge, draw via bend
        bend = self.element_connection_bend.get(element)
        keep_joint = self.element_connection_keep.get(element)
        if bend is not None and keep_joint is not None and keep_joint in getattr(element, "joints", []):
            js = element.joints
            if len(js) >= 2:
                other = js[0] if js[1] is keep_joint else js[1]
                if other in self.joint_items and keep_joint in self.joint_items:
                    p1 = self.joint_pos(other)
                    p2 = self.joint_pos(keep_joint)
                    pipe.moveTo(p1)
                    pipe.lineTo(bend)
                    pipe.lineTo(p2)

                    return pipe, sym

        if t in ("Катушка", "Переход", "ТПА", "Фланец"):
            j1, j2 = element.joints
            p1 = self.joint_pos(j1)
            if t == "Катушка":
                axis = element.axis
                sign = self.joint_dir.get(j2, (axis, +1))[1]
                p2 = p1 + self.step_vec(axis, sign, element.display_len)
                pipe.moveTo(p1)
                pipe.lineTo(p2)
                return pipe, sym

            p2 = self.joint_pos(j2)
            mid = (p1 + p2) * 0.5
            axis = getattr(element, "axis", "X")
            sign = self.joint_dir.get(j2, (axis, +1))[1]
            v = self.step_vec(axis, sign, 0.22)  # along axis
            perp = QPointF(-v.y(), v.x())  # screen-perp


            # ===== ПЕРЕХОД (как на примере: "треугольная" вставка) =====

            if t == "Переход":
                # base pipeline
                pipe.moveTo(p1)
                pipe.lineTo(p2)
                n = perp * 0.55
                pA = mid - v * 0.95
                pB = mid + v * 0.95
                pC = mid + n
                pD = mid - n * 0.25

                sym.moveTo(pA)
                sym.lineTo(pC)
                sym.lineTo(pB)
                sym.lineTo(pD)
                sym.lineTo(pA)

                sym.moveTo(mid - v * 0.25)
                sym.lineTo(mid + n * 0.55)

                return pipe, sym

            # ===== ТПА (песочные часы) =====

            if t == "ТПА":
                # 1) ось элемента
                d = p2 - p1
                L = (d.x() * d.x() + d.y() * d.y()) ** 0.5
                if L < 1e-9:
                    return pipe, sym
                e_main = d / L

                # 2) ось "ширины" ТПА — фиксированная ISO-ось (стабильно, без "поворотов")
                # берём ось, отличную от axis элемента
                main_axis = getattr(element, "axis", "X")
                if main_axis == "X":
                    body_axis = "Y"
                elif main_axis == "Y":
                    body_axis = "X"
                else:  # Z
                    body_axis = "X"
                e_body = self.step_vec(body_axis, +1, 1.0)
                eb_len = (e_body.x() * e_body.x() + e_body.y() * e_body.y()) ** 0.5
                e_body = e_body / max(eb_len, 1e-9)

                # 3) размеры
                HALF_W = UNIT * 0.35 * 1.20  # полуширина "оснований" и концов креста (в пикселях)


                # точки на "основаниях" (пластинках)
                p1_top = p1 + e_body * HALF_W
                p1_bot = p1 - e_body * HALF_W
                p2_top = p2 + e_body * HALF_W
                p2_bot = p2 - e_body * HALF_W

                # 4) основания (две пластинки у стыков)
                sym.moveTo(p1_top);
                sym.lineTo(p1_bot)
                sym.moveTo(p2_top);
                sym.lineTo(p2_bot)

                # крест — диагонали ДОЛЖНЫ касаться оснований (как на твоём эталоне)
                sym.moveTo(p1_top);
                sym.lineTo(p2_bot)
                sym.moveTo(p1_bot);
                sym.lineTo(p2_top)

                return pipe, sym

            # ===== ФЛАНЕЦ (как на примере: две параллельные пластинки) =====

            if t == "Фланец":
                # base pipeline
                pipe.moveTo(p1)
                pipe.lineTo(p2)
                pL1 = mid - v * 0.55
                pL2 = mid + v * 0.55
                plate = perp * 0.55
                # two plates crossing pipe
                sym.moveTo(pL1 - plate)
                sym.lineTo(pL1 + plate)
                sym.moveTo(pL2 - plate)
                sym.lineTo(pL2 + plate)

                return pipe, sym


        if t == "Отвод":
            j1, j2 = element.joints
            p1 = self.joint_pos(j1)
            p2 = self.joint_pos(j2)
            bend = getattr(element, "_bend_pos", None)
            if bend is None:
                # fallback: пересечение осевых линий (чтобы L был по ISO-осям)
                axis_from, sign_from = self.joint_dir.get(j1, (element.axis_from, +1))
                axis_to, sign_to = self.joint_dir.get(j2, (element.axis_to, +1))
                d1 = self.step_vec(axis_from, sign_from, 1.0)
                d2 = self.step_vec(axis_to, sign_to, 1.0)
                bend = self._axis_line_intersection(p1, d1, p2, d2) or (p1 + p2) * 0.5

            pipe.moveTo(p1)
            pipe.lineTo(bend)
            pipe.lineTo(p2)

            return pipe, sym

        if t == "Тройник":
            jm1, jb, jm2 = element.joints
            p_in = self.joint_pos(jm1)
            p_main2 = self.joint_pos(jm2)
            p_branch = self.joint_pos(jb)

            center = getattr(element, "_center_pos", None)
            if center is None:
                pipe.moveTo(p_in)
                pipe.lineTo(p_main2)
                pipe.moveTo(p_in)
                pipe.lineTo(p_branch)

                return pipe, sym

            pipe.moveTo(p_in)
            pipe.lineTo(center)
            pipe.lineTo(p_main2)
            pipe.moveTo(center)
            pipe.lineTo(p_branch)

            return pipe, sym

        if t == "Врезка":
            jb1, jb2 = element.joints
            p1 = self.joint_pos(jb1)
            p2 = self.joint_pos(jb2)
            pipe.moveTo(p1)
            pipe.lineTo(p2)

            return pipe, sym

        if t in ("Заглушка", "Свечная труба", "Разрыв трубы"):
            j = element.joints[0]
            p = self.joint_pos(j)
            axis = getattr(element, "axis", "X")
            sign = getattr(element, "sign", +1)
            v = self.step_vec(axis, sign, 0.28)

            if t == "Заглушка":
                # arc-like cap + short lead (approx like your sample)
                lead = p + v * 0.55
                pipe.moveTo(p)
                pipe.lineTo(lead)
                r = 10
                # draw a quarter-ish arc using cubic (screen space)
                # direction depends on sign: flip arc sideways
                side = QPointF(-v.y(), v.x())
                side = side / max(1.0, (side.x() * side.x() + side.y() * side.y()) ** 0.5)
                side = side * (r * (1 if sign >= 0 else -1))
                c1 = lead + side * 0.4
                c2 = lead + side * 1.2 + QPointF(0, r * 0.2)
                end = lead + side * 1.4 + QPointF(0, r * 0.6)
                sym.moveTo(lead)
                sym.cubicTo(c1, c2, end)

                return pipe, sym

            if t == "Свечная труба":
                # line with arrow at the end (as in sample)
                end = p + v
                pipe.moveTo(p)
                pipe.lineTo(end)
                # arrow head in screen space
                dirv = (end - p)
                perp = QPointF(-dirv.y(), dirv.x())
                # normalize
                dl = (dirv.x() * dirv.x() + dirv.y() * dirv.y()) ** 0.5 or 1.0
                dirn = dirv / dl
                pl = (perp.x() * perp.x() + perp.y() * perp.y()) ** 0.5 or 1.0
                perpn = perp / pl
                ah = 10
                aw = 5
                a1 = end - dirn * ah + perpn * aw
                a2 = end - dirn * ah - perpn * aw
                sym.moveTo(end)
                sym.lineTo(a1)
                sym.moveTo(end)
                sym.lineTo(a2)

                return pipe, sym

            gap = v * 0.3
            # pipe break with hatch marks like sample
            a = p - v
            b = p - gap
            c = p + gap
            d = p + v
            pipe.moveTo(a)
            pipe.lineTo(b)
            pipe.moveTo(c)
            pipe.lineTo(d)
            # hatch marks near the break end
            hatch_dir = QPointF(-v.y(), v.x())
            hl = 10
            hatch_dir = hatch_dir / max(1.0, (
            hatch_dir.x() * hatch_dir.x() + hatch_dir.y() * hatch_dir.y()) ** 0.5)
            hatch = hatch_dir * hl
            # 4 small hatches
            base = d - v * 0.2
            for k in range(4):
                off = (-v) * (0.05 * k)
                p0 = base + off
                sym.moveTo(p0)
                sym.lineTo(p0 + hatch)

            return pipe, sym

        return pipe, sym

    def redraw_scene(self):
        for it in self.element_items:
            pipe_path, sym_path = self.build_paths(it.element)
            it.setPath(pipe_path)
            it.symbol.setPath(sym_path)
        for ji in self.joint_items.values():
            ji.update_label()

    # =========================================================
    # AUTO BYPASS ALIGNMENT
    # =========================================================

    def _auto_align_bypass(self, A, B):
        path = self._find_path(A, B)
        if not path:
            return
        pipes = [e for e in path if e.element_type == "Катушка"]
        elbows = [e for e in path if e.element_type == "Отвод"]
        if not pipes and not elbows:
            return
        pA = self.joint_pos(A)
        pB = self.joint_pos(B)

        p_end = self._simulate_path_position(A, path)
        error = pB - p_end

        axis_groups = {
            ("X", +1): [],
            ("X", -1): [],
            ("Y", +1): [],
            ("Y", -1): [],
            ("Z", +1): [],
            ("Z", -1): [],
        }

        for p in pipes:
            j1, j2 = p.joints
            axis, sign = self.joint_dir.get(j2, ("X", +1))
            axis_groups[(axis, sign)].append(p)

        for e in elbows:
            j1, j2 = e.joints
            axis1 = e.axis_from
            axis2 = e.axis_to
            sign1 = self.joint_dir.get(j1, (axis1, +1))[1]
            sign2 = self.joint_dir.get(j2, (axis2, +1))[1]

            axis_groups[(axis1, sign1)].append(("elbow_from", e))
            axis_groups[(axis2, sign2)].append(("elbow_to", e))

        for (axis, sign), group in axis_groups.items():
            if not group:
                continue

            d = self.step_vec(axis, sign, 1.0)
            mag = d.x() * d.x() + d.y() * d.y()

            if mag == 0:
                continue

            proj = (error.x() * d.x() + error.y() * d.y()) / mag
            delta_each = proj / len(group)

            for typ, obj in group:
                if typ == "pipe":
                    obj.display_len = max(0.2, obj.display_len + delta_each)
                elif typ == "elbow_from":
                    obj.display_len_from = max(0.2, obj.display_len_from + delta_each)
                elif typ == "elbow_to":
                    obj.display_len_to = max(0.2, obj.display_len_to + delta_each)

        self._rebuild_branch_geometry(A, path)
        self.redraw_scene()

    def _simulate_path_position(self, start_joint, elements):
        pos = QPointF(self.joint_pos(start_joint))

        for e in elements:
            if e.element_type == "Катушка":
                axis = e.axis
                j2 = e.joints[1]
                sign = self.joint_dir.get(j2, (axis, +1))[1]
                pos += self.step_vec(axis, sign, e.display_len)
            elif e.element_type == "Отвод":
                j1, j2 = e.joints
                sign1 = self.joint_dir.get(j1, (e.axis_from, +1))[1]
                sign2 = self.joint_dir.get(j2, (e.axis_to, +1))[1]
                pos += self.step_vec(e.axis_from, sign1, e.display_len_from)
                pos += self.step_vec(e.axis_to, sign2, e.display_len_to)
        return pos

    def _rebuild_branch_geometry(self, start_joint, elements):
        pos = QPointF(self.joint_pos(start_joint))

        current = start_joint


        for e in elements:

            if e.element_type == "Катушка":
                j2 = e.joints[1]
                axis = e.axis
                sign = self.joint_dir.get(j2, (axis, +1))[1]
                pos = pos + self.step_vec(axis, sign, e.display_len)
                self.joint_items[j2].setPos(pos)
                current = j2

            elif e.element_type == "Отвод":
                j1, j2 = e.joints

                sign1 = self.joint_dir.get(j1, (e.axis_from, +1))[1]
                sign2 = self.joint_dir.get(j2, (e.axis_to, +1))[1]

                bend = pos + self.step_vec(e.axis_from, sign1, e.display_len_from)
                end = bend + self.step_vec(e.axis_to, sign2, e.display_len_to)

                e._bend_pos = bend
                self.joint_items[j2].setPos(end)

                pos = end
                current = j2

    def _find_path(self, start, end):
        visited = set()
        def dfs(joint):
            if joint == end:
                return []

            visited.add(joint)

            for e in joint.elements:
                for j in e.joints:
                    if j in visited:
                        continue
                    result = dfs(j)
                    if result is not None:
                        return [e] + result
            return None

        return dfs(start)

    def axis_vec(self, axis: str, sign: int, scale: float = 1.0) -> QPointF:
        v = self.step_vec(axis, sign, scale)


        return v

    # -----------------------
    # SOFT SNAP: keep ANY length, but force direction strictly to iso X/Y/Z
    # -----------------------


    def _iso_unit(self, axis: str, sign: int = +1) -> QPointF:
        v = self.step_vec(axis, sign, 1.0)

        ln = (v.x() * v.x() + v.y() * v.y()) ** 0.5

        if ln < 1e-9:

            return QPointF(1, 0)

        return v / ln


    def _closest_axis_dir(self, d: QPointF) -> tuple[str, int, QPointF]:
        """Return (axis, sign, axis_unit_vec) that best matches vector d by angle (dot)."""

        L = (d.x() * d.x() + d.y() * d.y()) ** 0.5

        if L < 1e-9:
            # fallback
            u = self._iso_unit("X", +1)
            return "X", +1, u
        u = d / L

        best_axis = "X"
        best_sign = +1
        best_dot = -1e9
        best_u = self._iso_unit("X", +1)

        for ax in ("X", "Y", "Z"):

            for sg in (+1, -1):
                au = self._iso_unit(ax, sg)
                dot = u.x() * au.x() + u.y() * au.y()

                if dot > best_dot:
                    best_dot = dot
                    best_axis = ax
                    best_sign = sg
                    best_u = au
        return best_axis, best_sign, best_u


    def _soft_snap_segment(self, p1: QPointF, p2: QPointF) -> tuple[QPointF, str, int]:
        """Project p2 onto closest iso axis direction from p1 keeping original length."""

        d = p2 - p1
        L = (d.x() * d.x() + d.y() * d.y()) ** 0.5
        axis, sign, au = self._closest_axis_dir(d)
        p2s = p1 + au * L

        return p2s, axis, sign



    def _apply_soft_snap_for_element(self, start_joint, end_joint):
        """Enforce that (start -> end) is strictly along iso X/Y/Z while keeping length.
        Updates end joint position, and stores joint_dir for stable downstream behavior.
        """


        if start_joint not in self.joint_items or end_joint not in self.joint_items:

            return
        p1 = self.joint_items[start_joint].pos()
        p2 = self.joint_items[end_joint].pos()
        p2s, axis, sign = self._soft_snap_segment(p1, p2)
        self.joint_items[end_joint].setPos(p2s)
        self.joint_dir[end_joint] = (axis, sign)



    def _apply_soft_snap_chain_from(self, root_joint):
        """Soft-snap all connected segments out of root_joint (best-effort).
        Uses current element items to traverse edges and snap endpoint positions.
        """

        # build adjacency by joints via existing elements_items
        adj = {}

        for it in self.element_items:
            e = it.element
            js = getattr(e, "joints", [])

            if len(js) < 2:
                continue
            # for Tee we snap its main continuation and branch separately elsewhere

            if getattr(e, "element_type", "") == "Тройник" and len(js) == 3:
                pairs = [(js[0], js[2]), (js[0], js[1])]
            elif getattr(e, "element_type", "") == "Врезка" and len(js) == 2:
                pairs = [(js[0], js[1])]
            else:
                pairs = [(js[0], js[1])]
            for a, b in pairs:
                adj.setdefault(a, set()).add(b)
                adj.setdefault(b, set()).add(a)

        seen = set()
        stack = [root_joint]
        seen.add(root_joint)

        while stack:
            j = stack.pop()

            for nb in adj.get(j, ()):
                if nb in seen:
                    continue
                # snap nb relative to j
                if j in self.joint_items and nb in self.joint_items:
                    p1 = self.joint_items[j].pos()
                    p2 = self.joint_items[nb].pos()
                    p2s, axis, sign = self._soft_snap_segment(p1, p2)
                    self.joint_items[nb].setPos(p2s)
                    self.joint_dir[nb] = (axis, sign)
                seen.add(nb)
                stack.append(nb)

    def plane_vec(self, main_axis: str, plane: str | None, scale: float) -> QPointF:
        """
        Returns a vector in the element plane, perpendicular to main axis, using isometric basis.
        plane: "XY","XZ","YZ" or None (auto)
        """

        # choose secondary axis that forms plane with main_axis

        if plane is None:
            sec = {"X": "Y", "Y": "X", "Z": "X"}[main_axis]
        else:

            if main_axis not in plane:
                sec = {"X": "Y", "Y": "X", "Z": "X"}[main_axis]
            else:
                sec = (plane.replace(main_axis, ""))  # remaining letter

        return self.step_vec(sec, +1, scale)

    def _basis_main_plane(self, p1: QPointF, p2: QPointF, main_axis: str, main_sign: int, plane: str | None):
        """
        Returns two unit vectors in screen space:
        e_main  - along the element (p1->p2)
        e_plane - in the chosen element plane (iso axis), made orthogonal to e_main (Gram-Schmidt)
        """

        # MAIN: strictly iso axis direction, but ANY length (soft-snap model should already align)
        d = p2 - p1
        L = (d.x() * d.x() + d.y() * d.y()) ** 0.5
        if L < 1e-9:
            return QPointF(1, 0), QPointF(0, 1), 1.0
        e_main = self._iso_unit(main_axis, main_sign)
        # PLANE: iso plane axis (no screen-perp)
        vp = QPointF(self.plane_vec(main_axis, plane, 1.0))
        vp_len = (vp.x() * vp.x() + vp.y() * vp.y()) ** 0.5
        if vp_len < 1e-9:
            vp = QPointF(-e_main.y(), e_main.x())
            vp_len = 1.0
        e_plane = vp / vp_len
        return e_main, e_plane, L

    def _poly_from_local(self, origin: QPointF, e_main: QPointF, e_plane: QPointF, L: float,
                             pts: list[tuple[float, float]]):
        """
        local coords:
        u in [0..1] along element length
        v in [-0.5..0.5] across (relative to L, so v*L)
        """

        out = []
        for u, v in pts:
            out.append(origin + e_main * (u * L) + e_plane * (v * L))
        return out

    # -----------------------
    # add / delete
    # -----------------------
    def add_element(self):
        selected = self.list_widget.currentItem()
        if not selected:
            QMessageBox.warning(self, "Ошибка", "Выберите элемент")
            return

        elem_name = selected.text()

        # строим всегда от active_joint (он выставляется кликом по JointItem)
        start_joint = getattr(self, "active_joint", None) or self.start_joint
        if start_joint not in self.joint_items:
            start_joint = self.start_joint
        start_pos = self.joint_items[start_joint].pos()


        # =======================
        # ПРОХОДНЫЕ (2 стыка)
        # =======================
        if elem_name in ["Катушка", "Отвод", "Переход", "ТПА", "Фланец"]:
            end_joint = self.scheme.create_joint()
            # первичная позиция (для отвода зададим позже точно)
            raw_end_pos = QPointF(start_pos.x() + AXES_VEC["X"].x(), start_pos.y() + AXES_VEC["X"].y())
            self.ensure_joint_item(end_joint, raw_end_pos)

            if elem_name == "Катушка":
                elem = Pipe(start_joint, end_joint)
            elif elem_name == "Отвод":
                # --- FIX: отвод должен быть L-образным по реальным стыкам,
                # а не "мягко снапнутой" прямой.
                axis_from, sign_from = self.joint_dir.get(start_joint, ("X", +1))
                axis_to, sign_to = self.get_selected_dir()
                # запрет совпадения осей (как в Elbow.__init__)
                if axis_to == axis_from:
                    axis_to = "Y" if axis_from != "Y" else "Z"
                elem = Elbow(start_joint, end_joint, axis_from=axis_from, axis_to=axis_to)

                bend = start_pos + self.step_vec(axis_from, sign_from, elem.display_len_from)
                end_pos = bend + self.step_vec(axis_to, sign_to, elem.display_len_to)
                elem._bend_pos = bend
                self.joint_items[end_joint].setPos(end_pos)
                self.joint_dir[end_joint] = (axis_to, sign_to)
            elif elem_name == "Переход":
                elem = Adapter(start_joint, end_joint)
            elif elem_name == "ТПА":
                elem = Fittings(start_joint, end_joint)
            elif elem_name == "Фланец":
                elem = Flange(start_joint, end_joint)

            self.scheme.add_element(elem)
            it = ElementItem(elem)
            self.element_items.append(it)
            self.element_item_by_element[elem] = it
            self.scene.addItem(it)
            # МЯГКИЙ СНАП: только для прямых проходных (катушка/переход/тпа/фланец)
            if elem_name != "Отвод":
                self._apply_soft_snap_for_element(start_joint, end_joint)

            # курсор на новый стык
            self.active_joint = end_joint
            self._select_only_joint(end_joint)
            self._set_dir_buttons_for_joint(end_joint)
            self.redraw_scene()
            return

        # =======================
        # ТРОЙНИК (3 стыка)
        # =======================
        if elem_name == "Тройник":
            # Создаём два новых стыка: продолжение магистрали + ветвь
            main2_joint = self.scheme.create_joint()
            branch_joint = self.scheme.create_joint()

            raw_main2_pos = QPointF(start_pos.x() + AXES_VEC["X"].x(), start_pos.y() + AXES_VEC["X"].y())
            raw_branch_pos = QPointF(start_pos.x() + AXES_VEC["Z"].x(), start_pos.y() + AXES_VEC["Z"].y())
            self.ensure_joint_item(main2_joint, raw_main2_pos)
            self.ensure_joint_item(branch_joint, raw_branch_pos)

            # ВАЖНО: Tee(start, branch, main2) как у тебя было
            elem = Tee(start_joint, branch_joint, main2_joint)
            self.scheme.add_element(elem)
            it = ElementItem(elem)
            self.element_items.append(it)
            self.element_item_by_element[elem] = it
            self.scene.addItem(it)

            # МЯГКИЙ СНАП обоих плеч
            self._apply_soft_snap_for_element(start_joint, main2_joint)
            self._apply_soft_snap_for_element(start_joint, branch_joint)



            # по умолчанию продолжаем магистраль (выделяем main2)
            self.active_joint = main2_joint
            self._select_only_joint(main2_joint)
            self._set_dir_buttons_for_joint(main2_joint)
            self.redraw_scene()
            return

        # =======================
        # ВРЕЗКА (2 стыка) / КОНЦЕВЫЕ (1 стык)
        # =======================
        if elem_name in ["Врезка", "Заглушка", "Свечная труба", "Разрыв трубы"]:
            if elem_name == "Врезка":
                end_joint = self.scheme.create_joint()
                raw_end_pos = QPointF(start_pos.x() + AXES_VEC["Z"].x(), start_pos.y() + AXES_VEC["Z"].y())
                self.ensure_joint_item(end_joint, raw_end_pos)

                elem = Insert(start_joint, end_joint)
                self.scheme.add_element(elem)
                it = ElementItem(elem)
                self.element_items.append(it)
                self.element_item_by_element[elem] = it
                self.scene.addItem(it)
                self._apply_soft_snap_for_element(start_joint, end_joint)

                self.active_joint = end_joint
                self._select_only_joint(end_joint)
                self._set_dir_buttons_for_joint(end_joint)
                self.redraw_scene()
                return

            # концевые: рисуем короткий хвост (для визуала), но элемент подключён к одному стыку
            # (если у тебя концевые должны вообще не создавать второй стык — оставляем так)
            if elem_name == "Заглушка":
                elem = Plug(start_joint)
            elif elem_name == "Свечная труба":
                elem = CandlePipe(start_joint)
            elif elem_name == "Разрыв трубы":
                elem = PipeBreak(start_joint)

            self.scheme.add_element(elem)
            it = ElementItem(elem)
            self.element_items.append(it)
            self.element_item_by_element[elem] = it
            self.scene.addItem(it)

            # можно нарисовать короткий “маркер” конца (необязательно)
            # здесь просто ничего не рисуем, т.к. у тебя сами символы рисуются в build_paths()

            self.active_joint = start_joint
            self._select_only_joint(start_joint)
            self._set_dir_buttons_for_joint(start_joint)
            self.redraw_scene()
            return

        QMessageBox.warning(self, "Ошибка", f"Элемент {elem_name} не реализован")



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

        # remove any connection bend overlays bound to this element
        self.element_connection_bend.pop(target_el, None)
        self.element_connection_keep.pop(target_el, None)

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
                ji = self.joint_items.pop(j, None)
                if ji is not None:
                    self.scene.removeItem(ji)
                if j in self.scheme.joints:
                    self.scheme.joints.remove(j)
                self.joint_dir.pop(j, None)

        # cursor fallback
        if self.scheme.elements:
            last = self.scheme.elements[-1]
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
        if any(j.diagnostic is None for j in self.scheme.joints):
            dlg = DiagnosticsDialog(self.scheme, self.start_joint, self)
            if dlg.exec() != QDialog.Accepted:
                return
            dlg.apply()

        try:
            self.scheme.number_joints(self.start_joint)  # must be cycle-safe in Scheme
        except Exception as e:
            QMessageBox.critical(self, "Ошибка нумерации", str(e))
            return

        self.show_temp_ids = False
        self.redraw_scene()

        report = ReportTable(self.scheme)
        txt = "\n".join([f"{r[0]:<10} {r[1]:<18} {r[2]}" for r in report.rows()])
        QMessageBox.information(self, "Отчёт", txt)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
