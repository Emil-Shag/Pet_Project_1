class ReportTable:
    """Отчёт по схеме"""

    def __init__(self, scheme):
        self.scheme = scheme

    def rows(self):
        """Возвращает строки таблицы отчёта"""
        rows = []
        for element in self.scheme.elements:
            rows.append([element.element_number(), element.element_type, ""])
        return rows

    def print(self):
        """Вывод таблицы в консоль"""
        header = ["№ элемента", "Наименование", "Толщина"]
        print(f"{header[0]:<15} {header[1]:<15} {header[2]}")
        print("-" * 45)

        for row in self.rows():
            print(f"{row[0]:<15} {row[1]:<15} {row[2]}")
