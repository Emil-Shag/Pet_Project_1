# main.py
from __future__ import annotations

from typing import Optional

from src.scheme import Scheme
from src.report import ReportTable
from src.element import (
    Element, Axis,
    Pipe, Elbow, Tee, Adapter, Fittings, Flange,
    Insert, Plug, CandlePipe, PipeBreak,
)


# -----------------------
# helpers (console UI)
# -----------------------
def print_joints(scheme: Scheme) -> None:
    print("\nСтыки:")
    for j in scheme.joints:
        if j.diagnostic is True:
            d = "✓"
        elif j.diagnostic is False:
            d = "✗"
        else:
            d = "?"
        n = j.number if j.number is not None else "-"
        print(f"  ID {j.temp_id:<3}  diagnostic={d}  number={n}  connected={len(j.elements)}")


def print_elements(scheme: Scheme) -> None:
    print("\nЭлементы:")
    if not scheme.elements:
        print("  (пока нет)")
        return
    for idx, e in enumerate(scheme.elements, 1):
        extra = ""
        if e.element_type == "Врезка" and hasattr(e, "host_element"):
            extra = f" host={getattr(e.host_element, 'element_type', '?')}"
        print(f"  {idx:>2}: {e.element_type:<12} joints={[j.temp_id for j in e.joints]}{extra}")


def get_joint_by_temp_id(scheme: Scheme, temp_id: int):
    return next((j for j in scheme.joints if j.temp_id == temp_id), None)


def ask_axis(prompt: str = "Ось (X/Y/Z) [X]: ") -> Axis:
    v = input(prompt).strip().upper()
    return v if v in ("X", "Y", "Z") else "X"


def ask_two_axes(prompt1: str, prompt2: str, default1: Axis = "X", default2: Axis = "Z") -> tuple[Axis, Axis]:
    a1 = input(prompt1).strip().upper() or default1
    a1 = a1 if a1 in ("X", "Y", "Z") else default1
    a2 = input(prompt2).strip().upper() or default2
    a2 = a2 if a2 in ("X", "Y", "Z") else default2
    if a1 == a2:
        print("⚠️ Оси совпали — заменяю вторую на Z (или X).")
        a2 = "Z" if a1 != "Z" else "X"
    return a1, a2


def choose_element(scheme: Scheme, prompt: str) -> Optional[Element]:
    if not scheme.elements:
        return None
    print_elements(scheme)
    try:
        idx = int(input(prompt).strip())
        if 1 <= idx <= len(scheme.elements):
            return scheme.elements[idx - 1]
    except ValueError:
        pass
    return None


# -----------------------
# new diagnostics confirmation algorithm
# -----------------------
def finalize_diagnostics_console(scheme: Scheme, start_joint) -> None:
    """
    1) Внутренние стыки (len(elements) >= 2) -> diagnostic=True автоматически (если None)
    2) Спрашиваем только крайние стыки (len(elements) <= 1) -> y/n (если None)
    3) Подстраховка: предложить исключить из диагностики внутренние стыки, которые True
    """
    # 1) auto-true for internal joints
    for j in scheme.joints:
        if j.diagnostic is None and len(j.elements) >= 2:
            j.diagnostic = True

    # 2) ask only terminal joints that are still None
    pending_terminals = [j for j in scheme.joints if j.diagnostic is None and len(j.elements) <= 1]

    if pending_terminals:
        print("\nПодтвердите диагностику только для КРАЙНИХ стыков (заняты с одной стороны):")
        for j in pending_terminals:
            connected = [e.element_type for e in j.elements]
            while True:
                ans = input(
                    f"Стык ID {j.temp_id} (элементы: {connected}) диагностируемый? (y/n) [y]: "
                ).strip().lower()
                if ans in ("", "y", "yes", "д", "да"):
                    j.diagnostic = True
                    break
                if ans in ("n", "no", "н", "нет"):
                    # стартовый лучше не выключать
                    if j is start_joint:
                        print("⚠️ Стартовый стык нельзя исключить. Оставляю diagnostic=True.")
                        j.diagnostic = True
                    else:
                        j.diagnostic = False
                    break
                print("Введите y или n.")
    else:
        print("\nКрайних стыков без признака diagnostic нет.")

    # 3) backup: allow excluding some internal joints
    candidates = [j for j in scheme.joints if len(j.elements) >= 2 and j.diagnostic is True]
    if not candidates:
        return

    print("\nПодстраховка: внутренние стыки автоматически считаются диагностируемыми.")
    ans = input("Хотите ИСКЛЮЧИТЬ какие-то из них из диагностики? (y/n) [n]: ").strip().lower()
    if ans not in ("y", "yes", "д", "да"):
        return

    print("Введите ID стыков через пробел (например: 3 7 12). Пусто = не исключать.")
    for j in candidates:
        connected = [e.element_type for e in j.elements]
        print(f"  ID {j.temp_id} (элементы: {connected})")

    line = input("> ").strip()
    if not line:
        return
    try:
        ids = {int(x) for x in line.split()}
    except ValueError:
        print("❌ Не удалось разобрать список ID. Пропускаю.")
        return

    for j in candidates:
        if j.temp_id in ids:
            if j is start_joint:
                print(f"⚠️ ID {j.temp_id} — стартовый стык, оставляю diagnostic=True.")
                continue
            j.diagnostic = False
            print(f"✔ Исключён: стык ID {j.temp_id}")


def main():
    scheme = Scheme()

    # стартовый стык: всегда диагностируемый
    start_joint = scheme.create_joint(diagnostic=True)
    print(f"Начальный стык создан: ID {start_joint.temp_id}")

    while True:
        print("\nДобавить элемент:")
        print(" 1 — Катушка")
        print(" 2 — Отвод")
        print(" 3 — Тройник")
        print(" 4 — Переход")
        print(" 5 — ТПА")
        print(" 6 — Фланец")
        print(" 7 — Врезка (привязана к элементу)")
        print(" 8 — Заглушка")
        print(" 9 — Свечная труба")
        print("10 — Разрыв трубы")
        print(" 0 — Завершить ввод")

        choice = input("> ").strip()
        if choice == "0":
            break

        element: Optional[Element] = None

        # -----------------------
        # INSERT: choose host element, then create branch joints
        # -----------------------
        if choice == "7":
            host = choose_element(scheme, "Выберите элемент-хозяин для врезки (номер из списка): ")
            if host is None:
                print("❌ Нет элементов или неверный выбор.")
                continue

            axis_host = getattr(host, "axis", "X")
            axis_branch = ask_axis("Ось ветви врезки (X/Y/Z) [Z]: ")  # пользователь
            if axis_branch == axis_host:
                print("⚠️ Ось ветви совпала с осью хоста — меняю ветвь на Z/X.")
                axis_branch = "Z" if axis_host != "Z" else "X"

            jb1 = scheme.create_joint(diagnostic=None)
            jb2 = scheme.create_joint(diagnostic=None)

            element = Insert(host, jb1, jb2, axis_host=axis_host, axis_branch=axis_branch)
            scheme.add_element(element)
            print("✔ Добавлена Врезка")

            print_joints(scheme)
            continue

        # -----------------------
        # for other elements: attach to a joint (by ID)
        # -----------------------
        print_joints(scheme)
        try:
            base_id = int(input("Подключить к стыку ID: ").strip())
        except ValueError:
            print("❌ Неверный ID.")
            continue

        base_joint = get_joint_by_temp_id(scheme, base_id)
        if base_joint is None:
            print("❌ Стык с таким ID не найден.")
            continue

        # pass-through (2 joints, 1 axis)
        if choice in ("1", "4", "5", "6"):
            axis = ask_axis()
            new_joint = scheme.create_joint(diagnostic=None)

            if choice == "1":
                element = Pipe(base_joint, new_joint, axis=axis)
            elif choice == "4":
                element = Adapter(base_joint, new_joint, axis=axis)
            elif choice == "5":
                element = Fittings(base_joint, new_joint, axis=axis)
            elif choice == "6":
                element = Flange(base_joint, new_joint, axis=axis)

            scheme.add_element(element)
            print(f"✔ Добавлен {element.element_type}")

        # elbow (two axes)
        elif choice == "2":
            axis_from, axis_to = ask_two_axes(
                "Ось 1 (X/Y/Z) [X]: ",
                "Ось 2 (X/Y/Z) [Z]: ",
                default1="X",
                default2="Z",
            )
            new_joint = scheme.create_joint(diagnostic=None)
            element = Elbow(base_joint, new_joint, axis_from=axis_from, axis_to=axis_to)
            scheme.add_element(element)
            print("✔ Добавлен Отвод")

        # tee (main + branch)
        elif choice == "3":
            axis_main = ask_axis("Ось магистрали (X/Y/Z) [X]: ")
            axis_branch = ask_axis("Ось ветви (X/Y/Z) [Z]: ")
            if axis_branch == axis_main:
                print("⚠️ Ось ветви совпала с магистралью — меняю ветвь на Z/X.")
                axis_branch = "Z" if axis_main != "Z" else "X"

            branch_joint = scheme.create_joint(diagnostic=None)
            main2_joint = scheme.create_joint(diagnostic=None)
            element = Tee(base_joint, branch_joint, main2_joint, axis_main=axis_main, axis_branch=axis_branch)
            scheme.add_element(element)
            print("✔ Добавлен Тройник")

        # terminals (1 joint, 1 axis)
        elif choice in ("8", "9", "10"):
            axis = ask_axis()

            if choice == "8":
                element = Plug(base_joint, axis=axis)
            elif choice == "9":
                element = CandlePipe(base_joint, axis=axis)
            else:
                element = PipeBreak(base_joint, axis=axis)

            scheme.add_element(element)
            print(f"✔ Добавлен {element.element_type}")

        else:
            print("❌ Неизвестная команда.")
            continue

        print_joints(scheme)

    # finalize diagnostics (only terminal joints asked)
    finalize_diagnostics_console(scheme, start_joint)

    # number joints + report
    try:
        scheme.number_joints(start_joint)
    except Exception as e:
        print(f"Ошибка нумерации: {e}")

    if hasattr(scheme, "validate_terminal_elements"):
        scheme.validate_terminal_elements()

    report = ReportTable(scheme)
    print("\nОТЧЁТ:")
    report.print()


if __name__ == "__main__":
    main()
