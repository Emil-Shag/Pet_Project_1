# src/gui/main_window.py
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsScene, QGraphicsView,
    QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget, QMessageBox
)
from PySide6.QtGui import QPen, QColor, QPainter
from PySide6.QtCore import Qt, QPointF

import sys
from math import cos, sin, radians

from ..scheme import Scheme
from ..element import Pipe, Elbow, Tee, Adapter, Fittings, Flange, Insert, Plug, CandlePipe, PipeBreak
from ..report import ReportTable

# Изометрические коэффициенты
COS30 = cos(radians(30))  # ≈0.866
SIN30 = sin(radians(30))  # 0.5

# Длина линии по оси
UNIT = 80

# Направления осей 120°
AXES = {
    'X': (1 * COS30 * UNIT, 1 * SIN30 * UNIT),
    'Y': (-0.5 * UNIT, 0.866 * UNIT),
    'Z': (-0.5 * UNIT, -0.866 * UNIT)
}

class JointItem:
    """Хранит позицию стыка на сцене и ссылку на Joint"""
    def __init__(self, joint, pos: QPointF):
        self.joint = joint
        self.pos = pos

class ElementItem:
    """Хранит графический объект элемента"""
    def __init__(self, element, start_joint_item, end_joint_item=None, branch_joint_item=None):
        self.element = element
        self.start = start_joint_item
        self.end = end_joint_item
        self.branch = branch_joint_item

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Конструктор трубопровода (Изометрия)")
        self.resize(1200, 800)

        # Схема
        self.scheme = Scheme()

        # Сцена и вид
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHints(self.view.renderHints() | QPainter.Antialiasing)

        # Панель инструментов
        self.list_widget = QListWidget()
        for name in ["Катушка", "Отвод", "Тройник", "Переход", "ТПА",
                     "Фланец", "Врезка", "Заглушка", "Свечная труба", "Разрыв трубы"]:
            QListWidgetItem(name, self.list_widget)

        self.add_btn = QPushButton("Добавить элемент")
        self.report_btn = QPushButton("Сформировать отчёт")

        layout = QVBoxLayout()
        layout.addWidget(self.list_widget)
        layout.addWidget(self.add_btn)
        layout.addWidget(self.report_btn)
        layout.addWidget(self.view)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Стартовый стык
        self.start_joint = self.scheme.create_joint()
        self.joint_items = {self.start_joint: JointItem(self.start_joint, QPointF(0, 0))}
        self.elements_items = []

        # Соединяем сигналы
        self.add_btn.clicked.connect(self.add_element)
        self.report_btn.clicked.connect(self.generate_report)

    def add_element(self):
        selected = self.list_widget.currentItem()
        if not selected:
            QMessageBox.warning(self, "Ошибка", "Выберите элемент")
            return

        elem_name = selected.text()

        # Для простоты все новые элементы идут вдоль оси X
        last_joint_item = max(self.joint_items.values(), key=lambda j: j.pos.x())
        start_joint = last_joint_item.joint
        start_pos = last_joint_item.pos

        # Создаём новые стыки
        if elem_name in ["Катушка", "Отвод", "Переход", "ТПА", "Фланец"]:
            end_joint = self.scheme.create_joint()
            end_pos = QPointF(start_pos.x() + AXES['X'][0], start_pos.y() + AXES['X'][1])
            self.joint_items[end_joint] = JointItem(end_joint, end_pos)

            # Создаём элемент
            if elem_name == "Катушка":
                elem = Pipe(start_joint, end_joint)
            elif elem_name == "Отвод":
                elem = Elbow(start_joint, end_joint)
            elif elem_name == "Переход":
                elem = Adapter(start_joint, end_joint)
            elif elem_name == "ТПА":
                elem = Fittings(start_joint, end_joint)
            elif elem_name == "Фланец":
                elem = Flange(start_joint, end_joint)

            self.scheme.add_element(elem)
            self.elements_items.append(ElementItem(elem, self.joint_items[start_joint], self.joint_items[end_joint]))

            # Рисуем линию
            self.scene.addLine(start_pos.x(), start_pos.y(), end_pos.x(), end_pos.y(),
                               QPen(QColor("blue"), 4))

        elif elem_name == "Тройник":
            # Тройник: основная линия и ветвь вниз (ось Z)
            main2_joint = self.scheme.create_joint()
            branch_joint = self.scheme.create_joint()

            main2_pos = QPointF(start_pos.x() + AXES['X'][0], start_pos.y() + AXES['X'][1])
            branch_pos = QPointF(start_pos.x() + AXES['Z'][0], start_pos.y() + AXES['Z'][1])

            self.joint_items[main2_joint] = JointItem(main2_joint, main2_pos)
            self.joint_items[branch_joint] = JointItem(branch_joint, branch_pos)

            elem = Tee(start_joint, branch_joint, main2_joint)
            self.scheme.add_element(elem)
            self.elements_items.append(ElementItem(elem,
                                                   self.joint_items[start_joint],
                                                   self.joint_items[main2_joint],
                                                   self.joint_items[branch_joint]))
            # Основной ствол
            self.scene.addLine(start_pos.x(), start_pos.y(), main2_pos.x(), main2_pos.y(),
                               QPen(QColor("blue"), 4))
            # Ответвление
            self.scene.addLine(start_pos.x(), start_pos.y(), branch_pos.x(), branch_pos.y(),
                               QPen(QColor("green"), 4))

        elif elem_name in ["Врезка", "Заглушка", "Свечная труба", "Разрыв трубы"]:
            # Концевой элемент или врезка
            end_joint = self.scheme.create_joint()
            end_pos = QPointF(start_pos.x() + AXES['X'][0], start_pos.y() + AXES['X'][1])
            self.joint_items[end_joint] = JointItem(end_joint, end_pos)

            if elem_name == "Врезка":
                elem = Insert(start_joint, end_joint)
            elif elem_name == "Заглушка":
                elem = Plug(start_joint)
            elif elem_name == "Свечная труба":
                elem = CandlePipe(start_joint)
            elif elem_name == "Разрыв трубы":
                elem = PipeBreak(start_joint)

            self.scheme.add_element(elem)
            self.elements_items.append(ElementItem(elem, self.joint_items[start_joint], self.joint_items[end_joint]))
            self.scene.addLine(start_pos.x(), start_pos.y(), end_pos.x(), end_pos.y(),
                               QPen(QColor("red"), 4))

        else:
            QMessageBox.warning(self, "Ошибка", f"Элемент {elem_name} не реализован")

    def generate_report(self):
        try:
            self.scheme.number_joints(self.start_joint)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка нумерации", str(e))
            return

        report = ReportTable(self.scheme)
        msg = "\n".join([f"{r[0]:<6} {r[1]:<15}" for r in report.rows()])
        QMessageBox.information(self, "Отчёт по схеме", msg)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
