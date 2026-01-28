# main.py
from __future__ import annotations

from typing import Optional

from src.scheme import Scheme
from src.report import ReportTable
from src.element import (
    Element,
    Pipe, Elbow, Tee, Adapter, Fittings, Flange,
    Insert, Plug, CandlePipe, PipeBreak,
)


def print_joints(scheme: Scheme) -> None:
    print("\nСуществующие стыки:")
    for joint in scheme.joints:
        if joint.diagnostic is True:
            diag = "✓"
        elif joint.diagnostic is False:
            diag = "✗"
        else:
            diag = "?"

        num = joint.number if joint.number is not None else "-"
        print(f"  ID {joint.temp_id:<3}  diagnostic={diag}  number={num}")


def print_elements(scheme: Scheme) -> None:
    print("\nСуществующие элементы:")
    if not scheme.elements:
        print("  (пока нет элементов)")
        return
    for idx, elem in enumerate(scheme.elements, 1):
        host = ""
        if elem.element_type == "Врезка" and hasattr(elem, "host_element"):
            host = f"  [host={elem.host_element.element_type}]"
        print(f"  {idx:>2}: {elem.element_type:<12} joints={[j.temp_id for j in elem.joints]}{host}")


def get_joint_by_temp_id(scheme: Scheme, temp_id: int):
    return next((j for j in scheme.joints if j.temp_id == temp_id), None)


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


def finalize_diagnostics_console(scheme: Scheme, start_joint) -> None:
    """
    Новый алгоритм:
    1) Внутренние стыки (len(elements) >= 2) -> diagnostic=True автоматически (если None)
    2) Крайние стыки (len(elements) <= 1) -> спрашиваем y/n (если None)
    3) Подстраховка: предложить исключить из диагностики некоторые автоматически-True стыки
    """
    # 1) авто-диагностика для внутренних
    auto_true = []
    for j in scheme.joints:
        if j.diagnostic is None and len(j.elements) >= 2:
            j.diagnostic = True
            auto_true.append(j)

    # 2) спрашиваем только крайние (в т.ч. "висячие")
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
                    j.diagnostic = False
                    break
                print("Введите y или n.")
    else:
        print("\nКрайних стыков без признака diagnostic нет.")

    # 3) подстраховка — исключение внутренних авто-стыков
    # Список кандидатов: внутренние стыки, которые сейчас True
    candidates = [j for j in scheme.joints if len(j.elements) >= 2 and j.diagnostic is True]

    if candidates:
        print("\nПодстраховка: внутренние стыки автоматически считаются диагностируемыми.")
        ans = input("Хотите ИСКЛЮЧИТЬ какие-то из них из диагностики? (y/n) [n]: ").strip().lower()
        if ans in ("y", "yes", "д", "да"):
            print("Введите ID стыков через пробел (например: 3 7 12). Пусто = не исключать.")
            for j in candidates:
                connected = [e.element_type for e in j.elements]
                print(f"  ID {j.temp_id} (элементы: {connected})")

            line = input("> ").strip()
            if line:
                try:
                    ids = {int(x) for x in line.split()}
                except ValueError:
                    print("❌ Не удалось разобрать список ID. Пропускаю исключение.")
                    ids = set()

                for j in candidates:
                    if j.temp_id in ids:
                        # стартовый стык нельзя выключать (иначе нумерация не стартует)
                        if j is start_joint:
                            print(f"⚠️ ID {j.temp_id} — стартовый стык, оставляю diagnostic=True.")
                            continue
                        j.diagnostic = False
                        print(f"✔ Исключён из диагностики: стык ID {j.temp_id}")


def main():
    scheme = Scheme()

    # стартовый стык сразу диагностируемый
    start_joint = scheme.create_joint(diagnostic=True)
    print(f"Начальный стык создан: ID {start_joint.temp_id}")

    while True:
        print("\nДобавить элемент:")
        print(" 1 — Катушка")
        print(" 2 — Отвод")
        print(" 3 — Тройник (ветвление)")
        print(" 4 — Переход")
        print(" 5 — ТПА")
        print(" 6 — Фланец")
        print(" 7 — Врезка (ветка, привязана к элементу магистрали)")
        print(" 8 — Заглушка (концевой)")
        print(" 9 — Свечная труба (концевой)")
        print("10 — Разрыв трубы (концевой)")
        print(" 0 — Завершить ввод")

        choice = input("> ").strip()
        if choice == "0":
            break

        element: Optional[Element] = None

        # -----------------------
        # ВРЕЗКА: выбираем element-хозяин и создаём ветку (diagnostic пока None)
        # -----------------------
        if choice == "7":
            host = choose_element(scheme, "Выберите элемент-хозяин для врезки (номер из списка): ")
            if host is None:
                print("❌ Нет элементов или неверный выбор.")
                continue

            jb1 = scheme.create_joint(diagnostic=None)
            jb2 = scheme.create_joint(diagnostic=None)

            element = Insert(host, jb1, jb2)
            scheme.add_element(element)
            print(f"✔ Добавлена Врезка (ветка) к элементу: {host.element_type}")

            print_joints(scheme)
            continue

        # -----------------------
        # Для остальных элементов — выбираем базовый стык по ID
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

        # -----------------------
        # ПРОХОДНЫЕ (2 стыка): создаём новый стык с diagnostic=None
        # -----------------------
        if choice in ("1", "2", "4", "5", "6"):
            new_joint = scheme.create_joint(diagnostic=None)

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

            scheme.add_element(element)
            print(f"✔ Добавлен {element.element_type}")

        # -----------------------
        # ТРОЙНИК: base_joint — магистральный; создаём branch и main2 как diagnostic=None
        # -----------------------
        elif choice == "3":
            branch_joint = scheme.create_joint(diagnostic=None)
            main2_joint = scheme.create_joint(diagnostic=None)

            element = Tee(base_joint, branch_joint, main2_joint)
            scheme.add_element(element)
            print("✔ Добавлен Тройник")

        # -----------------------
        # КОНЦЕВЫЕ (1 стык)
        # -----------------------
        elif choice in ("8", "9", "10"):
            if choice == "8":
                element = Plug(base_joint)
                scheme.add_element(element)
                print("✔ Добавлена Заглушка")
            elif choice == "9":
                element = CandlePipe(base_joint)
                scheme.add_element(element)
                print("✔ Добавлена Свечная труба")
            elif choice == "10":
                element = PipeBreak(base_joint)
                scheme.add_element(element)
                print("✔ Добавлен Разрыв трубы")

        else:
            print("❌ Неизвестная команда.")
            continue

        print_joints(scheme)

    # -----------------------
    # Финализация diagnostic перед нумерацией
    # -----------------------
    finalize_diagnostics_console(scheme, start_joint)

    # -----------------------
    # НУМЕРАЦИЯ + ОТЧЁТ
    # -----------------------
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
