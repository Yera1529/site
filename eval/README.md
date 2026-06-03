# Eval-инфраструктура для подбора норм

## Запуск
```bash
# baseline (без реальных вызовов Gemini-судьи)
python eval/run_eval.py --tag baseline

# после Фазы 4 — с Gemini-судьёй для Precision@5
python eval/run_eval.py --tag after_phase4 --judge gemini

# CI / pre-merge
python eval/run_eval.py --tag pr --fail-under 0.85
```

## Что меряется
| Метрика | Цель | Что считает |
|---|---|---|
| Recall@5 | ≥ 0.90 | Доля эталонных норм (`expected_top3`), попавших в топ-5 |
| Precision@5 | ≥ 0.70 | Gemini-судья оценивает релевантность каждой нормы в топ-5 |
| MRR@10 | ≥ 0.50 | 1/ранг первой попадающей эталонной нормы |
| StDev Top-5 | ≥ 0.05 | Защита от «76% у всех» |
| Clean ratio | = 1.00 | Доля кейсов, где в топ-5 НЕТ ничего из `must_not_contain` |
| Rerank share | ≥ 0.80 | Доля норм в топ-5, реально пришедших из Gemini-реранкера (а не FAISS-fallback) |

## Что в каждом кейсе

```json
{
  "id": "01_alcohol_evening",
  "title": "...",
  "fabula": "3–5 предложений реалистичной фабулы",
  "violations_input": "что следователь введёт в поле «Нарушения»",
  "addressee": "руководитель организации",
  "expected_domain": "один из 12 из плейбука, раздел 6.1",
  "expected_top3": [
    {"law_name_regex": "...", "article_pattern": "...", "rationale": "..."}
  ],
  "must_not_contain": ["Уголовный кодекс", "..."]
}
```

`law_name_regex` и `article_pattern` — регулярные выражения (re.IGNORECASE), потому что точные формулировки названий законов и номеров статей плавают между редакциями JSONL.

## Добавление нового кейса

1. Создай `eval/cases/NN_short_name.json` по образцу.
2. Заполни `expected_top3` — посмотри в `backend/unified_laws_200upk.jsonl`, какие есть профильные законы для домена.
3. Заполни `must_not_contain` — что не должно вылезти даже в худшем случае.
4. Прогон: `python eval/run_eval.py --tag check_new_case`.
5. Если baseline на этом кейсе >0.6 — кейс «слишком простой», переформулируй фабулу.

## Структура папок

```
eval/
├── cases/           # эталонные дела (10 шт.)
├── results/         # JSONL логов прогонов (создаётся автоматически)
│   └── <tag>_<timestamp>/
│       ├── <case_id>.json
│       └── _summary.json
├── run_eval.py      # ранер
├── judge_prompts.py # Gemini-судья
└── README.md
```
