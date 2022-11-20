## Отчет
См. [файл](./REPORT.pdf).

## Инструкция по запуску
Prerequisites:
1. Установить Docker
2. Сделать virtualenv c Python 3.9+ на локальной машине.

Обучение модели:
1. Открыть папку [jupyter](jupyter).
2. Установить зависимости из файла [requirements.txt](jupyter/requirements.txt) в виртуальное окружение, созданное на предыдущем шаге.
3. Запустить ноутбук [Recommender.ipynb](jupyter/Recommender.ipynb).
4. Путь к чекпойнту с обученной моделью будет выведен в ячейке с кодом ```print(checkpoint_callback.best_model_path)```. Эмбеддинги треков будут сохранены в файле [track_embeddings.pt](jupyter/track_embeddings.pt).

Использование обученной модели для выдачи предсказаний, проведения A/B тестов:
1. Скопировать чекпойнт и файл с эмбеддингами в папку [checkpoints](botify/checkpoints).
2. Из папки [botify](botify) запустить команду ```docker-compose up -d --build```.