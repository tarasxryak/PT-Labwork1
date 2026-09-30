# РГР по теории вероятностей, вариант 4, «Ужас Аркхэма», колода Декстера Дрейка
# вероятность того, что к концу первого хода в игровой зоне будет актив для исследования
# считается точно по формулам отчёта и проверяется методом Монте-Карло
#
# запуск: python dexter_first_turn.py [число_испытаний] [seed]

import random
import sys
from dataclasses import dataclass
from fractions import Fraction
from math import comb


@dataclass(frozen=True)
class Card:
    name: str
    kind: str                     # 'asset', 'event', 'skill', 'weakness'
    cost: int = 0
    investigates: bool = False
    spell_or_item: bool = False   # подходит для «Для следующего фокуса…»
    item: bool = False            # подходит для «Манипуляции»


FMNT = "Для следующего фокуса…"
PRESTIDIGITATION = "Манипуляция"
NECRONOMICON = "Некрономикон"
PARANOIA = "Паранойя"


def build_deck():
    deck = []

    def add(card, copies=1):
        deck.extend([card] * copies)

    add(Card("Ментальное видение", "asset", 4, True, True, False))
    add(Card("Воровские инструменты", "asset", 3, True, True, True))
    add(Card("Динамо-фонарь", "asset", 1, True, True, True), 2)

    add(Card("Резонансный покров", "asset", 3, False, True, True))
    add(Card("Космическое пламя", "asset", 3, False, True, False))
    add(Card("Джим Кальвер", "asset", 4))
    add(Card("Счастливый оберег", "asset", 2, False, True, True))
    add(Card("Спиритическая интуиция", "asset", 2))
    add(Card("Счастливый портсигар", "asset", 2, False, True, True))
    add(Card("Бескурковый M1903", "asset", 3, False, True, True))
    add(Card("Оливье Бишоп", "asset", 4))
    add(Card("Подвешенный язык", "asset", 2))
    add(Card("Загребущие ручонки", "asset", 1))
    add(Card("Розочка", "asset", 1, False, True, True), 2)

    add(Card(FMNT, "event", 0))
    add(Card("Предостережение", "event", 0))
    add(Card("Защитная магия", "event", 1))
    add(Card("Воля космоса", "event", 0))
    add(Card("Проникновение со взломом", "event", 2))
    add(Card("Красный день календаря", "event", 0))
    add(Card(PRESTIDIGITATION, "event", 1))
    add(Card("Неприкосновенный запас", "event", 0), 2)

    add(Card("Духовная связь", "skill"))
    add(Card("Прочь с глаз", "skill"))
    add(Card("Храбрость", "skill"), 2)
    add(Card("Ловкость рук", "skill"), 2)

    add(Card(NECRONOMICON, "weakness"))
    add(Card(PARANOIA, "weakness"))

    assert len(deck) == 33
    return deck


def draw_non_weakness(deck, set_aside):
    # при подготовке слабости откладываются и заменяются следующей картой
    while True:
        card = deck.pop()
        if card.kind == "weakness":
            set_aside.append(card)
        else:
            return card


def setup(rng, deck_template):
    deck = deck_template[:]
    rng.shuffle(deck)             # верх колоды — конец списка
    set_aside = []

    hand = [draw_non_weakness(deck, set_aside) for _ in range(5)]

    # замена по условию: оставляем «Фокус» и по одному экземпляру каждого актива
    keep, seen_assets = [], set()
    for card in hand:
        if card.name == FMNT:
            keep.append(card)
        elif card.kind == "asset" and card.name not in seen_assets:
            keep.append(card)
            seen_assets.add(card.name)
        else:
            set_aside.append(card)

    # новые карты берутся, пока отложенные ещё не вернулись в колоду
    replaced = 5 - len(keep)
    keep += [draw_non_weakness(deck, set_aside) for _ in range(replaced)]

    deck += set_aside
    rng.shuffle(deck)
    return keep, deck


def can_play_investigator_asset(hand, deck, resources, necronomicon):
    if necronomicon:
        return False
    if any(c.investigates and c.cost <= resources for c in hand):
        return True
    # «Фокус» стоит 0 и играет найденный актив со скидкой 2
    if any(c.name == FMNT for c in hand):
        return any(c.investigates and c.spell_or_item
                   and max(c.cost - 2, 0) <= resources for c in deck)
    return False


def prestidigitation_combo(card, hand, resources, necronomicon):
    # редкая комбинация, которой нет в аналитической модели:
    # «Манипуляция» играет вещь без действия, свойство Декстера играет вторую вещь,
    # и в конце хода на руку возвращается вторая, а исследовательская остаётся
    if necronomicon or not (card.investigates and card.item):
        return False
    if not any(c.name == PRESTIDIGITATION for c in hand):
        return False
    rest = hand[:]
    rest.remove(card)
    others = [c.cost for c in rest if c.kind == "asset" and c.item]
    if not others:
        return False
    return resources >= 1 + max(card.cost - 2, 0) + min(others)


def first_turn(hand, deck, use_prestidigitation):
    resources, actions, necronomicon = 5, 3, False
    hand = hand[:]

    while actions > 0:
        if can_play_investigator_asset(hand, deck, resources, necronomicon):
            return True
        # карта, взятая последним действием, уже не успеет сыграть
        if actions == 1 and not use_prestidigitation:
            return False
        card = deck.pop()
        actions -= 1
        if card.name == NECRONOMICON:
            necronomicon = True       # в зоне угрозы: активы играть нельзя
        elif card.name == PARANOIA:
            resources = 0             # сбросить все ресурсы
        else:
            hand.append(card)
            if actions == 0:
                return (use_prestidigitation and
                        prestidigitation_combo(card, hand, resources,
                                               necronomicon))
    return False


def simulate(n_trials, seed, use_prestidigitation):
    rng = random.Random(seed)
    template = build_deck()
    successes = sum(first_turn(*setup(rng, template), use_prestidigitation)
                    for _ in range(n_trials))
    return successes / n_trials


def exact():
    # этап 1: в стартовой руке нет хороших карт
    p_no_good_hand = Fraction(comb(26, 5), comb(31, 5))

    # этап 2: N_k — число рук, при которых в замену уходит k карт
    # s — одиночные активы, r — «Розочки», вторая «Розочка» тоже уходит в замену
    n_k = {k: 0 for k in range(6)}
    for s in range(6):
        for r in range(3):
            j = 5 - s - r
            if 0 <= j <= 14:
                k = 5 - s if r == 0 else 4 - s
                n_k[k] += comb(10, s) * comb(2, r) * comb(14, j)
    assert sum(n_k.values()) == comb(26, 5)

    p_no_good_mulligan = sum(
        Fraction(n_k[k], comb(26, 5)) * Fraction(comb(21, k), comb(26, k))
        for k in range(6)
    )

    # этап 3: хорошая карта первым добором, вторым, или «Паранойя» и затем «Фокус»
    p_turn = (Fraction(5, 28) + Fraction(21, 28) * Fraction(5, 27)
              + Fraction(1, 28) * Fraction(1, 27))

    p_hand_only = 1 - p_no_good_hand * p_no_good_mulligan
    p_total = 1 - p_no_good_hand * p_no_good_mulligan * (1 - p_turn)
    # для сравнения: при отсутствии хороших карт игрок меняет все пять
    p_hard = 1 - p_no_good_hand * Fraction(comb(21, 5), comb(26, 5)) * (1 - p_turn)
    return (n_k, p_no_good_hand, p_no_good_mulligan, p_turn,
            p_hand_only, p_total, p_hard)


def main():
    n_trials = int(sys.argv[1]) if len(sys.argv) > 1 else 4_000_000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 2026

    n_k, p1, p2, p3, p_hand, p_total, p_hard = exact()
    print("Точный расчёт")
    print("  N_k:", n_k)
    print(f"  P(нет хороших в руке)             = {p1} ≈ {float(p1):.6f}")
    print(f"  P(нет хороших после замены | ...) = {p2} ≈ {float(p2):.6f}")
    print(f"  P(ход спасает | ...)              = {p3} ≈ {float(p3):.6f}")
    print(f"  P(A), только рука                 ≈ {float(p_hand):.6f}")
    print(f"  P(A), полная модель               = {p_total} ≈ {float(p_total):.6f}")
    print(f"  P(A), если менять все 5 карт      ≈ {float(p_hard):.6f}")

    print(f"\nМонте-Карло, {n_trials} испытаний, seed = {seed}")
    for flag, label in ((False, "модель отчёта"),
                        (True, "с комбинацией «Манипуляции»")):
        p_hat = simulate(n_trials, seed, flag)
        print(f"  {label:30s}: {p_hat:.6f}")


if __name__ == "__main__":
    main()
