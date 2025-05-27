import pandas as pd
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token="BOT_TOKEN")
dp = Dispatcher()


# Состояния FSM
class Form(StatesGroup):
    choose_university = State()
    math = State()
    russian = State()
    physics = State()
    computer_science = State()
    dvi_math = State()  # Для ДВИ МГУ
    achievements = State()  # Для индивидуальных достижений


# Загрузка данных из Excel
def load_universities(file_path):
    df = pd.read_excel(file_path)
    universities = {}

    for _, row in df.iterrows():
        university_name = row["ВУЗ"]
        direction_name = row["Направление"]

        if university_name not in universities:
            universities[university_name] = {}

        direction = {
            "description": row["Описание"],
            "total_score": int(row["Проходной балл"]),
            "dvi_required": row["Требуется ДВИ"],
            "dvi_min_score": int(row["Мин. балл ДВИ"]) if pd.notna(row["Мин. балл ДВИ"]) else 0,
            "optional": []
        }

        # Обработка выборочных предметов
        if pd.notna(row.get("Выборочные предметы", "")) and row["Выборочные предметы"] != "-":
            direction["optional"] = [
                s.strip().lower()
                for s in str(row["Выборочные предметы"]).split(",")
                if s.strip()
            ]

        # Добавляем предметы с минимальными баллами
        for subject in ["Math", "Russian", "Physics", "Computer_science"]:
            col_name = subject
            if pd.notna(row.get(col_name, "")) and row[col_name] != "-":
                direction[subject.lower()] = int(row[col_name])

        universities[university_name][direction_name] = direction

    return universities


# Проверка прохождения на направление
def check_direction(direction, scores, achievements=0):
    user_total = 0
    # Проверка обязательных предметов (исключая выборочные)
    required_subjects = {
        k: v for k, v in direction.items()
        if k not in ["optional", "description", "total_score", "dvi_required", "dvi_min_score"]
           and k not in direction["optional"]
    }

    for subject, min_score in required_subjects.items():
        user_total += scores.get(subject, 0)
        if scores.get(subject, 0) < min_score:
            return False, None, 0

    # Проверка ДВИ (если требуется)
    if direction.get("dvi_required") == "да":
        user_total += scores.get("dvi_math", 0)
        if scores.get("dvi_math", 0) < direction["dvi_min_score"]:
            return False, None, 0
    arr = []
    if direction.get("optional"):
        for subj in direction["optional"]:
            arr.append(scores.get(subj, 0))
    if arr:
        user_total += max(arr)
    # Проверка выборочных предметов (если есть)
    if direction.get("optional"):
        if not any(
                scores.get(subj, 0) >= direction.get(subj, 0)
                for subj in direction["optional"]
        ):
            return False, None
    user_total += achievements
    # Сравниваем с проходным баллом
    if user_total >= direction["total_score"]:
        return True, "passed", user_total
    else:
        return True, "recommend_paid", user_total


# Загрузка данных
UNIVERSITIES = load_universities(PATH_TO_FILE)

# Клавиатура для выбора вуза
def university_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="МГУ")],
            [KeyboardButton(text="ВШЭ")],
            [KeyboardButton(text="Физтех")],
            [KeyboardButton(text="МИФИ")],
            [KeyboardButton(text="Бауманка")]
        ],
        resize_keyboard=True
    )
    return keyboard


# Обработчики команд
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer(
        "Привет! Выбери вуз для проверки:",
        reply_markup=university_keyboard()
    )
    await state.set_state(Form.choose_university)


@dp.message(Form.choose_university)
async def process_university(message: types.Message, state: FSMContext):
    university = message.text
    if university not in UNIVERSITIES:
        await message.answer("Пожалуйста, выбери вуз из списка:", reply_markup=university_keyboard())
        return

    await state.update_data(university=university)
    await message.answer(
        f"Отлично! Ты выбрал {university}. Теперь введи свой результат по математике (ЕГЭ):",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(Form.math)


# Обработчики ввода баллов
@dp.message(Form.math, F.text.isdigit())
async def process_math(message: types.Message, state: FSMContext):
    score = int(message.text)
    if not (0 <= score <= 100):
        await message.answer("Пожалуйста, введите корректный балл (0-100)")
        return

    await state.update_data(math=score)
    await message.answer("Теперь введи результат по русскому языку:")
    await state.set_state(Form.russian)


@dp.message(Form.russian, F.text.isdigit())
async def process_russian(message: types.Message, state: FSMContext):
    score = int(message.text)
    if not (0 <= score <= 100):
        await message.answer("Пожалуйста, введите корректный балл (0-100)")
        return

    await state.update_data(russian=score)
    await message.answer("Теперь введи результат по физике:")
    await state.set_state(Form.physics)


@dp.message(Form.physics, F.text.isdigit())
async def process_physics(message: types.Message, state: FSMContext):
    score = int(message.text)
    if not (0 <= score <= 100):
        await message.answer("Пожалуйста, введите корректный балл (0-100)")
        return

    data = await state.get_data()
    university = data.get("university", "")

    await state.update_data(physics=score)

    # Если МГУ - запрашиваем ДВИ по математике
    if university == "МГУ":
        await message.answer("Теперь введи результат ДВИ по математике")
        await state.set_state(Form.dvi_math)
    else:
        await message.answer("Теперь введи результат по информатике:")
        await state.set_state(Form.computer_science)



@dp.message(Form.computer_science, F.text.isdigit())
async def process_computer_science(message: types.Message, state: FSMContext):
    score = int(message.text)
    if not (0 <= score <= 100):
        await message.answer("Пожалуйста, введите корректный балл (0-100)")
        return

    await state.update_data(computer_science=score)

    data = await state.get_data()
    university = data.get("university", "")

    await message.answer(f"Введи свои индивидуальные достижения для {university} (баллы от 0 до 10):")
    await state.set_state(Form.achievements)
@dp.message(Form.dvi_math, F.text.isdigit())
async def process_dvi_math(message: types.Message, state: FSMContext):
    score = int(message.text)
    if not (0 <= score <= 100):
        await message.answer("Пожалуйста, введите корректный балл (0-100)")
        return

    await state.update_data(dvi_math=score)
    await message.answer("Теперь введи результат по информатике:")
    await state.set_state(Form.computer_science)


@dp.message(Form.achievements, F.text.isdigit())
async def process_achievements(message: types.Message, state: FSMContext):
    achievements = int(message.text)
    if not (0 <= achievements <= 10):
        await message.answer("Пожалуйста, введите корректное количество баллов (0-10):")
        return

    user_data = await state.get_data()
    await state.clear()

    university = user_data.get("university", "")
    directions = UNIVERSITIES.get(university, {})

    # Собираем результаты
    results = []
    for dir_name, direction in directions.items():
        passed, status, res = check_direction(direction, user_data, achievements)
        if passed:
            if status == "passed":
                status_text = f"✅ Проходной балл: {res} >= {direction['total_score']} (проходите!)"
            else:
                status_text = f"⚠️ Ваш балл {res} < {direction['total_score']} (советуем платное отделение)"

            results.append(
                f"▪ {direction['description']}\n"
                f"  {status_text}"
            )

    # Формируем сообщение
    if results:
        result_message = (
                f"🎓 Результаты для {university}:\n\n" +
                "\n\n".join(results) +
                "\n\n📊 Твои баллы:\n" +
                f"Математика (ЕГЭ): {user_data.get('math', 0)}\n" +
                (f"ДВИ по математике: {user_data.get('dvi_math', 0)}\n" if "dvi_math" in user_data else "") +
                f"Русский язык: {user_data.get('russian', 0)}\n" +
                f"Физика: {user_data.get('physics', 0)}\n" +
                f"Информатика: {user_data.get('computer_science', 0)}\n" +
                f"Индивидуальные достижения: {achievements}\n"
        )
    else:
        result_message = (
                f"😔 В {university} ты не проходишь ни на одно направление.\n\n" +
                "📊 Твои баллы:\n" +
                f"Математика (ЕГЭ): {user_data.get('math', 0)}\n" +
                (f"ДВИ по математике: {user_data.get('dvi_math', 0)}\n" if "dvi_math" in user_data else "") +
                f"Русский язык: {user_data.get('russian', 0)}\n" +
                f"Физика: {user_data.get('physics', 0)}\n" +
                f"Информатика: {user_data.get('computer_science', 0)}\n" +
                f"Индивидуальные достижения: {achievements}\n"
        )

    await message.answer(result_message)


# Обработчик некорректного ввода
@dp.message(F.text)
async def process_incorrect_input(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == Form.choose_university:
        await message.answer("Пожалуйста, выбери вуз из списка:", reply_markup=university_keyboard())
    elif current_state in [Form.math, Form.russian, Form.physics, Form.computer_science, Form.dvi_math,
                           Form.achievements]:
        await message.answer("Пожалуйста, введите число")


# Запуск бота
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
