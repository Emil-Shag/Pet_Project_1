# report.py
class ReportTable:
    """Отчёт по схеме без DFS, с корректным отображением 0 для концевых элементов"""

    def __init__(self, scheme):
        self.scheme = scheme

    def rows(self):
        """Возвращает строки таблицы отчёта"""
        rows = []

        # сортируем элементы: концевой на стартовом стыке идёт первым
        sorted_elements = sorted(
            self.scheme.elements,
            key=lambda e: (
                (
                    0
                    if any(
                        j.number == 1
                        and e.element_type in ("Заглушка", "Свечная труба", "Разрыв трубы", "Фланец", "ТПА")
                        for j in e.joints
                    )
                    else 1
                ),
                min([j.number for j in e.joints if getattr(j, "diagnostic", True)] or [0]),
            ),
        )

        for element in sorted_elements:
            num_str = element.element_number()

            # концевые элементы
            if element.element_type in ("Заглушка", "Свечная труба", "Разрыв трубы", "Фланец", "ТПА"):
                joints = num_str.split("-")
                if any(j.number == 1 for j in element.joints):
                    num_str = f"0-{joints[-1]}"
                else:
                    num_str = f"{joints[0]}-0"

            # исправление тройника: средний номер — ответвление
            if element.element_type == "Тройник" and len(element.joints) == 3:
                numbers = sorted([j.number for j in element.joints])
                main1 = numbers[0]
                main2 = numbers[2]
                branch = numbers[1]
                num_str = f"{main1}-{branch}-{main2}"

            rows.append([num_str, element.element_type, ""])
        return rows

    def print(self):
        """Вывод таблицы в консоль"""
        header = ["№ элемента", "Наименование", "Толщина"]
        print(f"{header[0]:<15} {header[1]:<15} {header[2]}")
        print("-" * 45)

        for row in self.rows():
            print(f"{row[0]:<15} {row[1]:<15} {row[2]}")
