from src.element import Elbow, Pipe, Tee
from src.report import ReportTable
from src.scheme import Scheme

if __name__ == "__main__":

    def print_joints(scheme):
        print("Существующие стыки:")
        for joint in scheme.joints:
            print(f"  ID {joint.temp_id}")

    new_scheme = Scheme()

    start_joint = new_scheme.create_joint()

    print(f"Начальный стык создан: ID {start_joint.temp_id}")

    while True:
        print("\nДобавить элемент:")
        print("1 — Катушка")
        print("2 — Отвод")
        print("3 — Тройник")
        print("0 — Завершить ввод")

        choice = input("> ").strip()

        if choice == "0":
            break

        print_joints(new_scheme)
        base_id = int(input("Подключить к стыку ID: "))

        base_joint = next((j for j in new_scheme.joints if j.temp_id == base_id), None)

        if not base_joint:
            print("Неверный ID стыка")
            continue

        if len(base_joint.elements) == 2:
            print("Нельзя подключить новый элемент к этому стыку — он уже полностью занят")
            continue

        if choice in ("1", "2"):
            new_joint = new_scheme.create_joint()

            if choice == "1":
                element = Pipe(base_joint, new_joint)
            else:
                element = Elbow(base_joint, new_joint)

            new_scheme.add_element(element)
            print(f"Добавлен {element.element_type}")

        elif choice == "3":
            joint2 = new_scheme.create_joint()
            joint3 = new_scheme.create_joint()

            element = Tee(base_joint, joint2, joint3)
            new_scheme.add_element(element)

            print("Добавлен Тройник")

        else:
            print("Неизвестная команда")

    new_scheme.number_joints(start_joint)

    report = ReportTable(new_scheme)
    print("\nОТЧЁТ:")
    report.print()
