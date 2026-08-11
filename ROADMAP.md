# Ascendancy Auto-Management Roadmap

This file is the live project backlog and sequencing source.

The roadmap below is still the initial high-level sketch. It is intentionally preserved without inventing reverse-engineering facts that have not been established yet. Before implementation work starts, normalize these entries into agent-sized investigation/implementation items using [`docs/roadmap-authoring.md`](./docs/roadmap-authoring.md).

Future PRs must update the relevant roadmap item in the same change whenever they change its status, evidence, dependencies, supported binaries, direction, or acceptance criteria. Negative results and disproved premises should remain visible as `Dropped`, `Superseded`, or corrected items rather than disappearing.

---

## Initial milestone sketch (to be normalized)

## План до milestone «можно выбрать из двух профилей автоматизации»

1. **Зафиксировать целевую версию игры**
   Выбрать canonical Antagonizer + набор официальных патчей и сохранить vanilla-версию как reference для binary diff.

2. **Подготовить окружение для reverse engineering**
   Добиться воспроизводимого запуска игры, отладки и анализа executable; импортировать vanilla и Antagonizer в Ghidra и настроить их сравнение.

3. **Найти модель планеты и существующий auto-management**
   Определить, где хранится состояние планеты, как включается текущий self-management и какой код вызывается для него каждый ход.

4. **Найти UI-код управления планетой**
   Проследить существующий UI-toggle auto-management от клика игрока до изменения состояния планеты.

5. **Сделать минимальный исполняемый мод/patch**
   Подтвердить, что мы можем безопасно изменить Antagonizer: например, изменить поведение существующего элемента UI или добавить диагностическое различие для выбранной планеты.

6. **Добавить состояние профиля автоматизации**
   Представить текущий `auto-management on/off` как минимум тремя состояниями: `Manual`, `Agricultural`, `Industrial`. На этом этапе сами Agricultural/Industrial могут вести себя одинаково.

7. **Добавить выбор профиля в UI**
   Игрок может на экране планеты выбрать `Agricultural` или `Industrial`, переключаться между ними и вернуть планету в ручной режим.

### Milestone

Для каждой принадлежащей игроку планеты в UI можно выбрать **Manual / Agricultural / Industrial**, и игра корректно хранит и отображает выбранное состояние в течение текущей игровой сессии.

Реальное различие алгоритмов Agricultural и Industrial, их выполнение каждый ход и сохранение профиля в save game — следующие milestones.
