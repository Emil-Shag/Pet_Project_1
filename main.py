from typing import Optional

from src.element import Adapter, CandlePipe, Elbow, Element, Fittings, Flange, Insert, Pipe, PipeBreak, Plug, Tee
from src.report import ReportTable
from src.scheme import Scheme

if __name__ == "__main__":

    def print_joints(scheme: Scheme):
        print("Существующие стыки:")
        for joint in scheme.joints:
            diag = "✓" if getattr(joint, "diagnostic", True) else "✗"
            print(f"  ID {joint.temp_id} (diagnostic={diag})")

    new_scheme = Scheme()

    # Создаем стартовый стык
    start_joint = new_scheme.create_joint()
    print(f"Начальный стык создан: ID {start_joint.temp_id}")

    while True:
        print("\nДобавить элемент:")
        print("1 — Катушка")
        print("2 — Отвод")
        print("3 — Тройник")
        print("4 — Переход")
        print("5 — ТПА")
        print("6 — Фланец")
        print("7 — Врезка")
        print("8 — Заглушка")
        print("9 — Свечная труба")
        print("10 — Разрыв трубы")
        print("0 — Завершить ввод")

        choice = input("> ").strip()
        if choice == "0":
            break

        element: Optional[Element] = None  # переменная для всех элементов

        # =======================
        # ВРЕЗКА
        # =======================
        if choice == "7":
            print("\nВыберите элемент, в который врезка будет вставлена:")
            for idx, elem in enumerate(new_scheme.elements, 1):
                print(f"{idx}: {elem}")

            try:
                elem_idx = int(input("> ")) - 1
                base_element = new_scheme.elements[elem_idx]
            except ValueError, IndexError:
                print("Неверный выбор элемента")
                continue

            # создаём новые стыки для врезки
            main_joint = new_scheme.create_joint()
            branch_joint = new_scheme.create_joint()

            # создаём врезку с двумя концами
            element = Insert(main_joint, branch_joint)
            print(f"Добавлена Врезка к {base_element}")

        else:
            # =======================
            # ПРОХОДНЫЕ И КОНЦЕВЫЕ ЭЛЕМЕНТЫ
            # =======================
            try:
                base_id = int(input("Подключить к стыку ID: "))
            except ValueError:
                print("Неверный ID")
                continue

            base_joint = next((j for j in new_scheme.joints if j.temp_id == base_id), None)
            if not base_joint:
                print("Неверный ID стыка")
                continue

            # ПРОХОДНЫЕ ЭЛЕМЕНТЫ
            if choice in ("1", "2", "4", "5", "6"):
                new_joint = new_scheme.create_joint()

                if choice == "1":
                    element = Pipe(base_joint, new_joint)
                elif choice == "2":
                    element = Elbow(base_joint, new_joint)
                elif choice == "4":
                    element = Adapter(base_joint, new_joint)
                elif choice == "5":
                    element = Fittings(base_joint, new_joint)
                elif choice == "6":
                    element = Flange(base_joint, new_joint)

                print(f"Добавлен {element.element_type}")

            # ВЕТВЯЩИЕСЯ ЭЛЕМЕНТЫ
            elif choice == "3":  # Тройник
                joint2 = new_scheme.create_joint()
                joint3 = new_scheme.create_joint()
                element = Tee(base_joint, joint2, joint3)
                print("Добавлен Тройник")

            # КОНЦЕВЫЕ ЭЛЕМЕНТЫ
            elif choice in ("8", "9", "10"):
                # Разрешаем добавлять концевой элемент к любому стыку
                if choice == "8":
                    element = Plug(base_joint)
                    print("Добавлена Заглушка")
                elif choice == "9":
                    element = CandlePipe(base_joint)
                    print("Добавлена Свечная труба")
                elif choice == "10":
                    element = PipeBreak(base_joint)
                    print("Добавлен Разрыв трубы")

            else:
                print("Неизвестная команда")

        # =======================
        # ДОБАВЛЕНИЕ ЭЛЕМЕНТА В СХЕМУ
        # =======================
        if element is not None:
            new_scheme.add_element(element)

        print_joints(new_scheme)

    # =======================
    # НУМЕРАЦИЯ СТЫКОВ
    # =======================
    try:
        new_scheme.number_joints(start_joint)
    except Exception as e:
        print(f"Ошибка нумерации: {e}")

    # =======================
    # ВАЛИДАЦИЯ СХЕМЫ
    # =======================
    try:
        new_scheme.validate()
        print("\nСхема прошла проверку валидности")
    except Exception as e:
        print(f"\nОшибка валидации схемы: {e}")

    # =======================
    # ОТЧЁТ
    # =======================
    report = ReportTable(new_scheme)
    print("\nОТЧЁТ:")
    report.print()
