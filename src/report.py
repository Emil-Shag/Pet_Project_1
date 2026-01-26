# report.py

TERMINAL_TYPES = {
    "Заглушка",
    "Свечная труба",
    "Разрыв трубы",
    "Фланец",
    "ТПА",
}


class ReportTable:
    """Отчёт по схеме с корректным отображением 0 и стабильной сортировкой"""

    def __init__(self, scheme):
        self.scheme = scheme

    # -----------------------
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # -----------------------
    def _is_terminal(self, element) -> bool:
        return element.element_type in TERMINAL_TYPES

    def _joint_numbers(self, element):
        return [j.number for j in element.joints if j.number is not None]

    def _display_number(self, element) -> str:
        nums = self._joint_numbers(element)

        # --- ТРОЙНИК ---
        if element.element_type == "Тройник" and len(nums) == 3:
            nums = sorted(nums)
            return f"{nums[0]}-{nums[1]}-{nums[2]}"

        # --- КОНЦЕВЫЕ ---
        if self._is_terminal(element):
            if not nums:
                return "0-0"

            # стартовый элемент
            if 1 in nums:
                return f"0-{nums[0]}"

            return f"{nums[0]}-0"

        # --- ПРОХОДНЫЕ ---
        if len(nums) == 1:
            return f"{nums[0]}-0"

        return f"{nums[0]}-{nums[1]}"

    def _sort_key(self, element):
        nums = self._joint_numbers(element)

        # концевой на стартовом стыке — всегда первый
        if self._is_terminal(element) and 1 in nums:
            return (-1, -1)

        if nums:
            return (min(nums), max(nums))

        return (9999, 9999)

    # -----------------------
    # ОСНОВНОЙ ИНТЕРФЕЙС
    # -----------------------
    def rows(self):
        rows = []

        sorted_elements = sorted(self.scheme.elements, key=self._sort_key)

        for element in sorted_elements:
            rows.append(
                [
                    self._display_number(element),
                    element.element_type,
                    "",
                ]
            )

        return rows

    def print(self):
        header = ["№ элемента", "Наименование", "Толщина"]
        print(f"{header[0]:<15} {header[1]:<20} {header[2]}")
        print("-" * 50)

        for row in self.rows():
            print(f"{row[0]:<15} {row[1]:<20} {row[2]}")
