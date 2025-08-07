from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio
import random
import json
import sqlite3
from aiogram.types import FSInputFile
from aiogram.types import BotCommand

from config import BOT_TOKEN
from db import (init_db, create_user, get_balance, update_balance, create_user_with_referrer,
             get_user_stats, update_game_stats, get_referral_info, add_referral_bonus,
             delete_user, add_withdrawal, add_bet_to_history, update_bet_result,
             add_deposit, update_deposit_status, get_deposit_by_invoice, get_user_bet_history,
             get_user_by_id, get_leaderboard_by_winnings, get_leaderboard_by_balance,
             init_cashback_table, add_loss_to_cashback, get_cashback_info, claim_cashback)
from aiogram.types import CallbackQuery
from cryptobot import crypto_bot
from db import add_deposit, update_deposit_status, get_deposit_by_invoice

# Импортируем игровые функции из games.py
from games import (
    play_bowling_direct, play_dice_duel_direct, play_basketball_direct,
    play_dice_higher_direct, play_dice_even_direct, play_triada_direct,
    play_darts_direct, play_slots_direct, process_game_queue,
    MINES_COEFFICIENTS, TOWER_COEFFICIENTS
)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

init_db()
init_cashback_table()

# Настройки канала - убедитесь что бот добавлен в канал как администратор
CHANNEL_ID = "-1002816845887"
SUBSCRIPTION_CHANNEL = "@NNDICEWIN"

# Система очереди ставок
game_queue = []
is_game_running = False

# Отслеживание активных ставок пользователей
user_active_bets = {}

# История ставок пользователей (последние 5 ставок)
user_bet_history = {}

class GameState(StatesGroup):
    main_menu = State()
    play_menu = State()
    profile = State()
    bot_games = State()
    channel_games = State()

    # Игры в боте
    mines_setup = State()
    tower_setup = State()
    mines_playing = State() # Новое состояние для игры в мины
    tower_playing = State() # Новое состояние для игры в башню
    combination_game = State()
    twist_setup = State()
    twist_game = State()

    # Игры в канале
    channel_bowling = State()
    channel_basketball = State()
    channel_dice_duel = State()
    channel_dice_higher = State()
    channel_dice_even = State()
    channel_triada = State()
    channel_darts = State()
    channel_slots = State()

    # Ставки
    waiting_bet = State()
    change_bet_amount = State()

    # CryptoBot
    crypto_deposit = State()
    crypto_withdraw = State()

    # Админ функции
    admin_add_money = State()
    admin_delete_user = State()
    admin_check_balance = State()

    # Лидерборд
    leaderboard = State()

    # Просмотр истории и кэшбека
    viewing_history = State()
    viewing_cashback = State()

async def check_subscription(user_id):
    """Проверяет подписку пользователя на канал."""
    try:
        member = await bot.get_chat_member(chat_id=SUBSCRIPTION_CHANNEL, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Ошибка проверки подписки: {e}")
        return False

def get_subscription_keyboard():
    """Возвращает клавиатуру для проверки подписки."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Подписаться на канал", url="https://t.me/NNDICEWIN")],
            [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subscription")]
        ]
    )
    return keyboard

def get_start_keyboard(has_active_bets=False):
    """Возвращает стартовую клавиатуру."""
    if has_active_bets:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🎮 Играть"), KeyboardButton(text="👤 Профиль")],
                [KeyboardButton(text="💳 Кошелек"), KeyboardButton(text="📊 Мои ставки")]
            ],
            resize_keyboard=True,
            one_time_keyboard=False
        )
    else:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🎮 Играть"), KeyboardButton(text="👤 Профиль")],
                [KeyboardButton(text="💳 Кошелек")]
            ],
            resize_keyboard=True,
            one_time_keyboard=False
        )
    return keyboard

def get_play_menu_keyboard():
    """Возвращает клавиатуру меню игр."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🤖 Играть в боте")],
            [KeyboardButton(text="💬 Играть в канале")],
            [KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_bot_games_keyboard():
    """Возвращает клавиатуру игр в боте."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💣 Мины"), KeyboardButton(text="🏗 Башня")],
            [KeyboardButton(text="🌪 Твист"), KeyboardButton(text="🎯 Комбинация")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_channel_games_keyboard():
    """Возвращает клавиатуру игр в канале."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎳 Боулинг"), KeyboardButton(text="🏀 Баскетбол")],
            [KeyboardButton(text="🎲 Кубы (дуэль)"), KeyboardButton(text="🎲 Больше/меньше")],
            [KeyboardButton(text="🎲 Чет/нечет"), KeyboardButton(text="🎲 Триада")],
            [KeyboardButton(text="🎯 Дартс"), KeyboardButton(text="🎰 Слоты")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_bet_input_keyboard():
    """Возвращает клавиатуру для ввода ставки."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_basketball_keyboard():
    """Возвращает клавиатуру для игры в баскетбол."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎯 Попадание (x1.8)")],
            [KeyboardButton(text="❌ Мимо (x1.3)")],
            [KeyboardButton(text="💰 Изменить сумму")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_dice_duel_choice_keyboard():
    """Возвращает клавиатуру для игры в кубы (дуэль)."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏆 Победа (x1.8)"), KeyboardButton(text="💀 Поражение (x1.8)")],
            [KeyboardButton(text="💰 Изменить сумму")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_dice_higher_lower_keyboard():
    """Возвращает клавиатуру для игры больше/меньше."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⬆️ Больше")],
            [KeyboardButton(text="⬇️ Меньше")],
            [KeyboardButton(text="💰 Изменить сумму")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_dice_even_odd_keyboard():
    """Возвращает клавиатуру для игры чет/нечет."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="2️⃣ Четное"), KeyboardButton(text="1️⃣ Нечетное")],
            [KeyboardButton(text="💰 Изменить сумму")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_triada_keyboard():
    """Возвращает клавиатуру для игры триада."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="1️⃣"), KeyboardButton(text="2️⃣"), KeyboardButton(text="3️⃣")],
            [KeyboardButton(text="4️⃣"), KeyboardButton(text="5️⃣"), KeyboardButton(text="6️⃣")],
            [KeyboardButton(text="💰 Изменить сумму")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_bowling_choice_keyboard():
    """Возвращает клавиатуру для игры в боулинг."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏆 Победа (x1.8)"), KeyboardButton(text="💀 Поражение (x1.8)")],
            [KeyboardButton(text="💰 Изменить сумму")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_darts_keyboard():
    """Возвращает клавиатуру для игры в дартс."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔴 Красное (x1.8)"), KeyboardButton(text="⚪ Белое (x1.8)")],
            [KeyboardButton(text="💰 Изменить сумму")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_mines_count_keyboard():
    """Возвращает клавиатуру для выбора количества мин."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="2 мины"), KeyboardButton(text="3 мины"), KeyboardButton(text="4 мины")],
            [KeyboardButton(text="5 мин"), KeyboardButton(text="6 мин"), KeyboardButton(text="7 мин")],
            [KeyboardButton(text="8 мин"), KeyboardButton(text="9 мин"), KeyboardButton(text="10 мин")],
            [KeyboardButton(text="11 мин"), KeyboardButton(text="12 мин"), KeyboardButton(text="13 мин")],
            [KeyboardButton(text="14 мин"), KeyboardButton(text="15 мин"), KeyboardButton(text="16 мин")],
            [KeyboardButton(text="17 мин"), KeyboardButton(text="18 мин"), KeyboardButton(text="19 мин")],
            [KeyboardButton(text="20 мин"), KeyboardButton(text="21 мина"), KeyboardButton(text="22 мины")],
            [KeyboardButton(text="23 мины"), KeyboardButton(text="24 мины")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_tower_mines_keyboard():
    """Возвращает клавиатуру для выбора количества бомб в башне."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="1 бомба"), KeyboardButton(text="2 бомбы")],
            [KeyboardButton(text="3 бомбы"), KeyboardButton(text="4 бомбы")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_combination_keyboard():
    """Возвращает клавиатуру для игры комбинация."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Изменить сумму")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def add_to_bet_history(user_id, game_type, bet_amount, choice):
    """Добавляет ставку в историю пользователя."""
    if user_id not in user_bet_history:
        user_bet_history[user_id] = []

    # Добавляем новую ставку в начало (не удаляем дубликаты)
    user_bet_history[user_id].insert(0, {
        'game_type': game_type,
        'bet_amount': bet_amount,
        'choice': choice
    })

    # Оставляем только последние 5 ставок
    user_bet_history[user_id] = user_bet_history[user_id][:5]

def add_bet_amount_to_history(user_id, amount):
    """Добавляет сумму ставки в историю для быстрого доступа."""
    # Получаем историю ставок из базы данных
    history = get_user_bet_history(user_id, 20) # Увеличим количество для получения более релевантных сумм

    # Создаем временную запись для суммы
    temp_bet = {
        'game_type': 'amount_only',
        'bet_amount': amount,
        'choice': 'amount'
    }

    # Проверяем, нет ли уже такой суммы в начале списка
    if not user_bet_history.get(user_id) or user_bet_history[user_id][0]['bet_amount'] != amount:
        if user_id not in user_bet_history:
            user_bet_history[user_id] = []
        user_bet_history[user_id].insert(0, temp_bet)
        # Оставляем только последние 5 записей
        user_bet_history[user_id] = user_bet_history[user_id][:5]

def get_bet_amounts_keyboard(user_id):
    """Создает инлайн клавиатуру с последними суммами денежных ставок."""
    # Получаем последние денежные ставки из базы данных
    history = get_user_bet_history(user_id, 20)

    if not history:
        return InlineKeyboardMarkup(inline_keyboard=[])

    # Собираем уникальные суммы ставок (максимум 3)
    amounts = []
    seen_amounts = set()

    for game_type, bet_amount, choice, result, win_amount, timestamp in history:
        if bet_amount not in seen_amounts and len(amounts) < 3:
            amounts.append(bet_amount)
            seen_amounts.add(bet_amount)

    if not amounts:
        return InlineKeyboardMarkup(inline_keyboard=[])

    keyboard = []
    for amount in amounts:
        keyboard.append([InlineKeyboardButton(
            text=f"💰 {amount} $",
            callback_data=f"quick_amount_{amount}"
        )])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_leaderboard_keyboard():
    """Создает клавиатуру для лидерборда."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏆 Топ по выигрышам", callback_data="leaderboard_winnings_all")],
            [InlineKeyboardButton(text="💰 Топ по балансу", callback_data="leaderboard_balance")],
            [
                InlineKeyboardButton(text="📅 День", callback_data="leaderboard_winnings_day"),
                InlineKeyboardButton(text="📅 Неделя", callback_data="leaderboard_winnings_week"),
                InlineKeyboardButton(text="📅 Месяц", callback_data="leaderboard_winnings_month")
            ]
        ]
    )
    return keyboard

def get_quick_bet_keyboard(user_id, current_game_type=None):
    """Создает инлайн клавиатуру с быстрыми ставками."""
    if user_id not in user_bet_history or not user_bet_history[user_id]:
        return InlineKeyboardMarkup(inline_keyboard=[])

    keyboard = []

    # Фильтруем по типу игры если указан, иначе показываем все
    history = user_bet_history[user_id]
    if current_game_type:
        # Для канальных игр показываем все канальные игры
        channel_games = ['bowling', 'dice_duel', 'basketball', 'dice_higher', 'dice_even', 'triada', 'darts']
        if current_game_type in channel_games:
            history = [bet for bet in history if bet['game_type'] in channel_games]
        else:
            # Для ботовых игр показываем только ботовые игры
            history = [bet for bet in history if bet['game_type'] == current_game_type]

    if not history:
        return InlineKeyboardMarkup(inline_keyboard=[])

    game_names = {
        'bowling': '🎳',
        'dice_duel': '🎲',
        'basketball': '🏀',
        'dice_higher': '🎲⬆️',
        'dice_even': '🎲⚪',
        'triada': '🎲💎',
        'darts': '🎯',
        'mines': '💣',
        'tower': '🏗'
    }

    choice_texts = {
        ('bowling', 'win'): 'Победа',
        ('bowling', 'loss'): 'Поражение',
        ('dice_duel', 'win'): 'Победа',
        ('dice_duel', 'loss'): 'Поражение',
        ('basketball', 'hit'): 'Попадание',
        ('basketball', 'miss'): 'Мимо',
        ('dice_higher', 'higher'): 'Больше 3',
        ('dice_higher', 'lower'): 'Меньше 4',
        ('dice_even', 'even'): 'Четное',
        ('dice_even', 'odd'): 'Нечетное',
        ('darts', 'red'): 'Красное',
        ('darts', 'white'): 'Белое'
    }

    # Показываем последние 3 уникальные ставки
    seen = set()
    unique_history = []
    for bet in history:
        # Делаем более строгий ключ для дубликатов
        bet_key = (bet['game_type'], bet['bet_amount'], bet['choice'])
        if bet_key not in seen:
            seen.add(bet_key)
            unique_history.append(bet)
        if len(unique_history) >= 3:
            break

    for i, bet in enumerate(unique_history):
        game_icon = game_names.get(bet['game_type'], '🎮')

        if bet['game_type'] in ['mines', 'tower']:
            if bet['game_type'] == 'mines':
                text = f"{game_icon} {bet['bet_amount']}$ | {bet['choice']} мин"
            else:
                text = f"{game_icon} {bet['bet_amount']}$ | {bet['choice']} бомб"
        elif bet['game_type'] == 'triada':
            text = f"{game_icon} {bet['bet_amount']}$ | число {bet['choice']}"
        else:
            choice_text = choice_texts.get((bet['game_type'], bet['choice']), str(bet['choice']))
            text = f"{game_icon} {bet['bet_amount']}$ | {choice_text}"

        callback_data = f"quick_bet_{i}"
        keyboard.append([InlineKeyboardButton(text=text, callback_data=callback_data)])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_mines_field(mines_count):
    """Создает поле для игры в мины."""
    field = [[0 for _ in range(5)] for _ in range(5)]

    # Размещаем мины случайным образом
    mine_positions = set()
    while len(mine_positions) < mines_count:
        row = random.randint(0, 4)
        col = random.randint(0, 4)
        mine_positions.add((row, col))

    for row, col in mine_positions:
        field[row][col] = 1  # 1 = мина

    return field

def create_tower_keyboard(level, bombs_count):
    """Создает клавиатуру для башни."""
    if level >= 6:
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="💰 Забрать выигрыш")]],
            resize_keyboard=True
        )

    total_cells = 4 - bombs_count
    keyboard_rows = []

    for i in range(total_cells + bombs_count):
        cell_text = f"🎁 Сейф {i+1}"
        keyboard_rows.append([KeyboardButton(text=cell_text)])

    keyboard_rows.append([KeyboardButton(text="💰 Забрать выигрыш")])
    keyboard_rows.append([KeyboardButton(text="⬅️ Назад")])

    return ReplyKeyboardMarkup(
        keyboard=keyboard_rows,
        resize_keyboard=True
    )

def create_mines_inline_keyboard(mines_count, opened_cells, current_coeff, clicks_count=0):
    """Создает инлайн клавиатуру для игры в мины."""
    keyboard = []
    field = create_mines_field(mines_count)

    # Отображаем поле снизу вверх (с 4 ряда до 0)
    for i in range(4, -1, -1):
        row_buttons = []
        for j in range(5):
            if (i, j) in opened_cells:
                # Проверяем, есть ли мина в этой клетке
                is_mine = False
                for mine_row, mine_col in data.get('mines_positions', []):
                    if i == mine_row and j == mine_col:
                        is_mine = True
                        break

                if is_mine:
                    row_buttons.append(InlineKeyboardButton(text="💣", callback_data=f"mine_{i}_{j}"))
                else:
                    row_buttons.append(InlineKeyboardButton(text="💎", callback_data=f"mine_{i}_{j}"))
            else:
                row_buttons.append(InlineKeyboardButton(text="⬜", callback_data=f"mine_{i}_{j}"))
        keyboard.append(row_buttons)

    # Кнопка "Забрать" появляется только после первого хода
    if clicks_count > 0:
        keyboard.append([
            InlineKeyboardButton(text=f"💰 Забрать {current_coeff}x", callback_data="mines_cash_out")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(text="❌ Выйти x0", callback_data="mines_exit")
        ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_twist_keyboard():
    """Создает клавиатуру для игры Твист."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎰 Крутить", callback_data="twist_spin")],
            [InlineKeyboardButton(text="💰 Забрать банк", callback_data="twist_cashout")],
            [InlineKeyboardButton(text="❌ Выйти", callback_data="twist_exit")]
        ]
    )
    return keyboard

def create_tower_inline_keyboard(tower_mines, opened_levels, current_level):
    """Создает инлайн клавиатуру для игры Башня."""
    keyboard = []

    # Отображаем башню снизу вверх (с 5 уровня до 0) - 6 уровней всего
    for level in range(5, -1, -1):
        row = []
        for cell in range(5):
            if level < current_level:
                # Уровень уже пройден - показываем результат
                if any(ol[0] == level for ol in opened_levels):
                    # Нашли безопасную ячейку на этом уровне
                    safe_cell = next(ol[1] for ol in opened_levels if ol[0] == level)
                    if cell == safe_cell:
                        row.append(InlineKeyboardButton(text="💎", callback_data=f"tower_passed_{level}_{cell}"))
                    else:
                        row.append(InlineKeyboardButton(text="⬜", callback_data=f"tower_passed_{level}_{cell}"))
                else:
                    row.append(InlineKeyboardButton(text="⬜", callback_data=f"tower_passed_{level}_{cell}"))
            elif level == current_level:
                # Текущий уровень - можно кликать
                row.append(InlineKeyboardButton(text="⬜", callback_data=f"tower_{level}_{cell}"))
            else:
                # Будущие уровни - заблокированы
                row.append(InlineKeyboardButton(text="⬛", callback_data=f"tower_disabled_{level}_{cell}"))
        keyboard.append(row)

    if current_level > 0:
        coeffs = TOWER_COEFFICIENTS[tower_mines]
        current_coeff = coeffs[current_level - 1] if current_level - 1 < len(coeffs) else coeffs[-1]
        keyboard.append([
            InlineKeyboardButton(text=f"💰 Забрать {current_coeff}x", callback_data="tower_cash_out")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(text="❌ Выйти x0", callback_data="tower_exit")
        ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_profile_keyboard():
    """Возвращает клавиатуру профиля."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏆 Топ игроков"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="👥 Рефералы"), KeyboardButton(text="📜 История")],
            [KeyboardButton(text="💸 Кэш-бек"), KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

@router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    is_subscribed = await check_subscription(message.from_user.id)

    if not is_subscribed:
        await message.answer(
            f"🔒 <b>Для использования бота необходимо подписаться на наш канал!</b>\n\n"
            f"📢 Канал: {SUBSCRIPTION_CHANNEL}\n"
            f"🎰 После подписки нажмите 'Проверить подписку'",
            reply_markup=get_subscription_keyboard()
        )
        return

    # Обработка реферальной ссылки
    referrer_id = None
    if len(message.text.split()) > 1:
        start_param = message.text.split()[1]
        if start_param.startswith("ref"):
            try:
                referrer_id = int(start_param[3:])
                if referrer_id == message.from_user.id:
                    referrer_id = None  # Нельзя быть рефералом самого себя
            except ValueError:
                pass

    # Создаем пользователя с рефералом если есть
    from db import create_user_with_referrer, get_user_by_id

    # Проверяем, не зарегистрирован ли уже пользователь
    existing_user = get_user_by_id(message.from_user.id)

    if not existing_user and referrer_id:
        # Проверяем, что реферер существует
        referrer_exists = get_user_by_id(referrer_id)
        if referrer_exists:
            create_user_with_referrer(message.from_user.id, referrer_id)
            # Уведомляем реферера
            try:
                await bot.send_message(
                    referrer_id,
                    f"🎉 <b>Новый реферал!</b>\n"
                    f"👤 Пользователь {message.from_user.first_name} зарегистрировался по вашей ссылке!\n"
                    f"💰 Теперь вы будете получать 5% с его выигрышей!"
                )
            except:
                pass
        else:
            create_user(message.from_user.id)
    elif not existing_user:
        create_user(message.from_user.id)

    balance = get_balance(message.from_user.id)
    await state.set_state(GameState.main_menu)

    welcome_text = f"🎰 <b>Добро пожаловать в NN | DICE WIN!</b>\n💰 Ваш баланс: <b>${balance:.2f}</b>"
    if referrer_id:
        welcome_text += f"\n\n🎁 Вы зарегистрировались по реферальной ссылке!"

    has_bets = message.from_user.id in user_active_bets and user_active_bets[message.from_user.id]
    await message.answer(welcome_text, reply_markup=get_start_keyboard(has_bets))

@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, state: FSMContext):
    is_subscribed = await check_subscription(callback.from_user.id)

    if is_subscribed:
        create_user(callback.from_user.id)
        balance = get_balance(callback.from_user.id)
        await state.set_state(GameState.main_menu)
        await callback.message.edit_text(
            f"✅ <b>Подписка подтверждена!</b>\n\n"
            f"🎰 <b>Добро пожаловать в NN | DICE WIN!</b>\n"
            f"💰 Ваш баланс: <b>${balance:.2f}</b>",
            reply_markup=None
        )
        await callback.message.answer(
            "🎮 Выберите действие:",
            reply_markup=get_start_keyboard()
        )
        await callback.answer("✅ Подписка подтверждена!")
    else:
        await callback.answer("❌ Вы не подписаны на канал! Подпишитесь и нажмите 'Проверить подписку'", show_alert=True)

@router.message(F.text == "🎮 Играть")
async def play_menu_handler(message: Message, state: FSMContext):
    is_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer(
            f"🔒 <b>Для игры необходимо подписаться на наш канал!</b>\n\n"
            f"📢 Канал: {SUBSCRIPTION_CHANNEL}",
            reply_markup=get_subscription_keyboard()
        )
        return

    await state.set_state(GameState.play_menu)
    await message.answer(
        "🎮 <b>Выберите режим игры:</b>",
        reply_markup=get_play_menu_keyboard()
    )

@router.message(F.text == "🤖 Играть в боте")
async def bot_games_handler(message: Message, state: FSMContext):
    is_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer(
            f"🔒 <b>Для игры необходимо подписаться на наш канал!</b>\n\n"
            f"📢 Канал: {SUBSCRIPTION_CHANNEL}",
            reply_markup=get_subscription_keyboard()
        )
        return

    await state.set_state(GameState.bot_games)
    await message.answer(
        "🤖 <b>Игры в боте:</b>\n\n"
        "💣 <b>Мины</b> - найдите алмазы, избегая мин\n"
        "🏗 <b>Башня</b> - поднимайтесь выше по уровням\n"
        "🌪 <b>Твист</b> - игра на сбор символов\n"
        "🎯 <b>Комбинация</b> - угадайте цифры в трёхзначном числе",
        reply_markup=get_bot_games_keyboard()
    )

@router.message(F.text == "💬 Играть в канале")
async def channel_games_handler(message: Message, state: FSMContext):
    is_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer(
            f"🔒 <b>Для игры необходимо подписаться на наш канал!</b>\n\n"
            f"📢 Канал: {SUBSCRIPTION_CHANNEL}",
            reply_markup=get_subscription_keyboard()
        )
        return

    await state.set_state(GameState.channel_games)
    await message.answer(
        "💬 <b>Игры в канале:</b>\n\n"
        "🎳 <b>Боулинг</b> - дуэль x1.8\n"
        "🏀 <b>Баскетбол</b> - попадание x1.8, мимо x1.3\n"
        "🎲 <b>Кубы (дуэль)</b> - x1.8\n"
        "🎲 <b>Больше/меньше</b> - x1.8\n"
        "🎲 <b>Чет/нечет</b> - x1.8\n"
        "🎲 <b>Триада</b> - 1 совп. x1.8, 2 совп. x2.4, 3 совп. x3.1\n"
        "🎯 <b>Дартс</b> - x1.8\n"
        "🎰 <b>Слоты</b> - 3 одинаковых x3.5",
        reply_markup=get_channel_games_keyboard()
    )

@router.message(F.text == "💳 Кошелек")
async def wallet_handler(message: Message, state: FSMContext):
    is_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer(
            f"🔒 <b>Для доступа к кошельку необходимо подписаться на наш канал!</b>\n\n"
            f"📢 Канал: {SUBSCRIPTION_CHANNEL}",
            reply_markup=get_subscription_keyboard()
        )
        return

    balance = get_balance(message.from_user.id)

    wallet_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Пополнить"), KeyboardButton(text="💸 Вывести")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

    await message.answer(
        f"💳 <b>Кошелек</b>\n\n"
        f"💰 Ваш баланс: <b>${balance:.2f}</b>\n\n"
        f"💡 Выберите действие:",
        reply_markup=wallet_keyboard
    )

@router.message(F.text == "👤 Профиль")
async def profile_handler(message: Message, state: FSMContext):
    is_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer(
            f"🔒 <b>Для доступа к профилю необходимо подписаться на наш канал!</b>\n\n"
            f"📢 Канал: {SUBSCRIPTION_CHANNEL}",
            reply_markup=get_subscription_keyboard()
        )
        return

    await state.set_state(GameState.profile)
    balance = get_balance(message.from_user.id)
    username = message.from_user.username or "Без ника"
    first_name = message.from_user.first_name or "Игрок"

    # Специальная админ панель для администратора
    if message.from_user.id == 1597157163:
        profile_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🏆 Топ игроков"), KeyboardButton(text="📊 Статистика")],
                [KeyboardButton(text="👥 Рефералы"), KeyboardButton(text="📜 История")],
                [KeyboardButton(text="💸 Кэш-бек"), KeyboardButton(text="💰 +$1")],
                [KeyboardButton(text="💰 Начислить по ID"), KeyboardButton(text="👁 Баланс по ID")],
                [KeyboardButton(text="🗑 Удалить пользователя"), KeyboardButton(text="⬅️ Назад")]
            ],
            resize_keyboard=True,
            one_time_keyboard=False
        )
    else:
        profile_keyboard = get_profile_keyboard()

    # Получаем статистику пользователя
    stats = get_user_stats(message.from_user.id)
    if stats:
        favorite_game = f"{stats['favorite_game']} [{stats['favorite_game_count']}]"
        total_games = stats['total_games']
        biggest_win = stats['biggest_win']
        registration_date = stats['registration_date'][:10] if stats['registration_date'] else "20.10.2024"
    else:
        favorite_game = "Триада [74]"
        total_games = 206
        biggest_win = 9
        registration_date = "20.10.2024"

    await message.answer(
        f"👤 <b>Профиль</b>\n\n"
        f"🆔 ID: {message.from_user.id}\n"
        f"👤 Имя: {first_name}\n"
        f"📱 Ник: @{username}\n"
        f"💰 Баланс: <b>${balance:.2f}</b>\n\n"
        f"📊 Статистика\n"
        f"┣ Любимая игра: {favorite_game}\n"
        f"┣ Сыгранные игры: {total_games}\n"
        f"┗ Самый большой выигрыш: ${biggest_win:.2f}\n\n"
        f"📆 Дата регистрации: {registration_date}",
        reply_markup=profile_keyboard
    )

@router.message(F.text == "💰 +$1")
async def add_dollar_handler(message: Message, state: FSMContext):
    # Проверяем, что это нужный пользователь
    if message.from_user.id == 1597157163:
        # Создаем пользователя если его нет
        create_user(message.from_user.id)
        update_balance(message.from_user.id, 1.0)
        new_balance = get_balance(message.from_user.id)
        await message.answer(
            f"✅ <b>Баланс пополнен!</b>\n\n"
            f"💰 Добавлено: $1.00\n"
            f"💳 Текущий баланс: ${new_balance:.2f}"
        )
    else:
        await message.answer("❌ У вас нет доступа к этой функции")

@router.message(F.text == "💰 Начислить по ID")
async def admin_add_money_handler(message: Message, state: FSMContext):
    # Проверяем, что это админ
    if message.from_user.id == 1597157163:
        await state.set_state(GameState.admin_add_money)
        await message.answer(
            "💰 <b>Начисление средств по ID</b>\n\n"
            "📝 Введите данные в формате:\n"
            "<code>ID СУММА</code>\n\n"
            "Пример: <code>123456789 50.00</code>",
            reply_markup=get_bet_input_keyboard()
        )
    else:
        await message.answer("❌ У вас нет доступа к этой функции")

@router.message(F.text == "👁 Баланс по ID")
async def admin_check_balance_handler(message: Message, state: FSMContext):
    # Проверяем, что это админ
    if message.from_user.id == 1597157163:
        await state.set_state(GameState.admin_check_balance)
        await message.answer(
            "👁 <b>Проверка баланса по ID</b>\n\n"
            "📝 Введите ID пользователя для проверки баланса:",
            reply_markup=get_bet_input_keyboard()
        )
    else:
        await message.answer("❌ У вас нет доступа к этой функции")

@router.message(F.text == "🗑 Удалить пользователя")
async def admin_delete_user_handler(message: Message, state: FSMContext):
    # Проверяем, что это админ
    if message.from_user.id == 1597157163:
        await state.set_state(GameState.admin_delete_user)
        await message.answer(
            "🗑 <b>Удаление пользователя</b>\n\n"
            "⚠️ <b>ВНИМАНИЕ!</b> Это действие удалит все данные пользователя:\n"
            "• Баланс\n"
            "• Статистику игр\n"
            "• Историю ставок\n"
            "• Реферальные связи\n\n"
            "📝 Введите ID пользователя для удаления:",
            reply_markup=get_bet_input_keyboard()
        )
    else:
        await message.answer("❌ У вас нет доступа к этой функции")

@router.message(GameState.admin_add_money)
async def process_admin_add_money(message: Message, state: FSMContext):
    if message.from_user.id != 1597157163:
        await message.answer("❌ У вас нет доступа к этой функции")
        return

    # Обработка кнопки "Назад"
    if message.text == "⬅️ Назад":
        await back_handler(message, state)
        return

    try:
        parts = message.text.split()
        if len(parts) != 2:
            await message.answer("❌ Неверный формат! Используйте: ID СУММА")
            return

        user_id = int(parts[0])
        amount = float(parts[1])

        if amount <= 0:
            await message.answer("❌ Сумма должна быть положительной!")
            return

        # Создаем пользователя если его нет и начисляем деньги
        create_user(user_id)
        update_balance(user_id, amount)
        new_balance = get_balance(user_id)

        await message.answer(
            f"✅ <b>Средства начислены!</b>\n\n"
            f"👤 ID получателя: {user_id}\n"
            f"💰 Начислено: ${amount:.2f}\n"
            f"💳 Новый баланс: ${new_balance:.2f}"
        )

        # Уведомляем получателя
        try:
            await bot.send_message(
                user_id,
                f"🎁 <b>Вам начислены средства!</b>\n\n"
                f"💰 Начислено: ${amount:.2f}\n"
                f"💳 Ваш баланс: ${new_balance:.2f}\n\n"
                f"🎰 Удачной игры!"
            )
        except:
            await message.answer("⚠️ Не удалось уведомить получателя (возможно, заблокировал бота)")

        await state.set_state(GameState.profile)

    except ValueError:
        await message.answer("❌ Неверный формат! ID должен быть числом, сумма - числом с точкой")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@router.message(GameState.admin_check_balance)
async def process_admin_check_balance(message: Message, state: FSMContext):
    if message.from_user.id != 1597157163:
        await message.answer("❌ У вас нет доступа к этой функции")
        return

    # Обработка кнопки "Назад"
    if message.text == "⬅️ Назад":
        await back_handler(message, state)
        return

    try:
        user_id = int(message.text.strip())

        # Получаем баланс пользователя
        balance = get_balance(user_id)

        # Получаем дополнительную информацию о пользователе
        user_stats = get_user_stats(user_id)

        if user_stats:
            await message.answer(
                f"👁 <b>Информация о пользователе</b>\n\n"
                f"🆔 ID: {user_id}\n"
                f"💰 Баланс: ${balance:.2f}\n\n"
                f"📊 <b>Статистика:</b>\n"
                f"🎮 Всего игр: {user_stats['total_games']}\n"
                f"💎 Общие выигрыши: ${user_stats['total_winnings']:.2f}\n"
                f"🏆 Самый большой выигрыш: ${user_stats['biggest_win']:.2f}\n"
                f"🎯 Любимая игра: {user_stats['favorite_game']}\n"
                f"📅 Дата регистрации: {user_stats['registration_date'] or 'Неизвестно'}"
            )
        else:
            await message.answer(
                f"👁 <b>Информация о пользователе</b>\n\n"
                f"🆔 ID: {user_id}\n"
                f"💰 Баланс: ${balance:.2f}\n\n"
                f"ℹ️ Пользователь не найден в базе или не имеет статистики"
            )

        await state.set_state(GameState.profile)

    except ValueError:
        await message.answer("❌ Введите корректный числовой ID пользователя!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@router.message(GameState.admin_delete_user)
async def process_admin_delete_user(message: Message, state: FSMContext):
    if message.from_user.id != 1597157163:
        await message.answer("❌ У вас нет доступа к этой функции")
        return

    # Обработка кнопки "Назад"
    if message.text == "⬅️ Назад":
        await back_handler(message, state)
        return

    try:
        user_id = int(message.text.strip())

        if user_id == message.from_user.id:
            await message.answer("❌ Нельзя удалить самого себя!")
            return

        # Проверяем, существует ли пользователь
        balance = get_balance(user_id)

        if balance == 0:
            # Возможно пользователь не существует, но попробуем удалить
            pass

        # Получаем информацию о пользователе для подтверждения
        from db import delete_user
        success = delete_user(user_id)

        if success:
            await message.answer(
                f"✅ <b>Пользователь удален!</b>\n\n"
                f"👤 ID: {user_id}\n"
                f"💰 Баланс был: ${balance:.2f}\n\n"
                f"🗑 Удалены:\n"
                f"• Все данные пользователя\n"
                f"• История игр и ставок\n"
                f"• Реферальные связи\n\n"
                f"ℹ️ Пользователь теперь считается новым"
            )

            # Попытаемся уведомить пользователя (если он не заблокировал бота)
            try:
                await bot.send_message(
                    user_id,
                    f"🔄 <b>Ваш аккаунт был сброшен администратором</b>\n\n"
                    f"Вы можете начать заново с командой /start"
                )
            except:
                pass  # Игнорируем ошибки отправки

        else:
            await message.answer("❌ Ошибка при удалении пользователя")

        await state.set_state(GameState.profile)

    except ValueError:
        await message.answer("❌ Введите корректный числовой ID пользователя!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@router.message(F.text == "💸 Кэш-бек")
async def cashback_handler(message: Message, state: FSMContext):
    is_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer(
            f"🔒 <b>Для доступа к кешбеку необходимо подписаться на наш канал!</b>\n\n"
            f"📢 Канал: {SUBSCRIPTION_CHANNEL}",
            reply_markup=get_subscription_keyboard()
        )
        return

    cashback_info = get_cashback_info(message.from_user.id)

    await message.answer(
        f"💸 <b>Кэш-бек система</b>\n\n"
        f"💰 Накоплено кешбека: <b>${cashback_info['available_cashback']:.2f}</b>\n\n"
        f"📊 <b>Как работает кэш-бек программа:</b>\n"
        f"• Вы получаете 6% с каждого проигрыша\n"
        f"• Кешбек начисляется автоматически при достижении $5.00\n"
        f"• Автоматическое зачисление на баланс\n\n"
        f"📈 Общие проигрыши: ${cashback_info['total_losses']:.2f}\n\n"
        f"💡 При достижении $5.00 кешбек автоматически зачислится на баланс!"
    )



@router.message(F.text == "📈 История ставок")
async def my_bets_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id

    if user_id not in user_active_bets or not user_active_bets[user_id]:
        await message.answer(
            "📊 <b>Мои ставки</b>\n\n"
            "❌ У вас нет активных ставок"
        )
        return

    bets_text = "📊 <b>Ваши активные ставки:</b>\n\n"

    for i, bet in enumerate(user_active_bets[user_id], 1):
        game_names = {
            'bowling': '🎳 Боулинг',
            'dice_duel': '🎲 Кубы (дуэль)',
            'basketball': '🏀 Баскетбол',
            'dice_higher': '🎲 Больше/меньше',
            'dice_even': '🎲 Чет/нечет',
            'triada': '🎲 Триада',
            'darts': '🎯 Дартс'
        }

        choice_texts = {
            ('bowling', 'win'): '🏆 Победа',
            ('bowling', 'loss'): '💀 Поражение',
            ('dice_duel', 'win'): '🏆 Победа',
            ('dice_duel', 'loss'): '💀 Поражение',
            ('basketball', 'hit'): '🎯 Попадание',
            ('basketball', 'miss'): '❌ Мимо',
            ('dice_higher', 'higher'): '⬆️ Больше 3',
            ('dice_higher', 'lower'): '⬇️ Меньше 4',
            ('dice_even', 'even'): '2️⃣ Четное',
            ('dice_even', 'odd'): '1️⃣ Нечетное',
            ('darts', 'red'): '🔴 Красное',
            ('darts', 'white'): '⚪ Белое'
        }

        game_name = game_names.get(bet['game_type'], 'Неизвестная игра')
        choice_text = choice_texts.get((bet['game_type'], bet['choice']), str(bet['choice']))

        bets_text += f"{i}. {game_name}\n"
        bets_text += f"   💰 Ставка: ${bet['bet_amount']:.2f}\n"
        bets_text += f"   🎲 Выбор: {choice_text}\n"
        bets_text += f"   📊 Позиция в очереди: {bet['position']}\n\n"

    await message.answer(bets_text)

@router.message(F.text == "🏆 Лидерборд")
async def leaderboard_handler(message: Message, state: FSMContext):
    await state.set_state(GameState.leaderboard)
    await message.answer(
        "🏆 <b>Лидерборд</b>\n\n"
        "Выберите категорию для просмотра:",
        reply_markup=get_leaderboard_keyboard()
    )

@router.message(F.text == "👥 Рефералы")
async def referral_handler(message: Message, state: FSMContext):
    from db import get_referral_info

    referrals_count = get_referral_info(message.from_user.id)
    bot_username = (await bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start=ref{message.from_user.id}"

    await message.answer(
        f"👥 <b>Реферальная система</b>\n\n💰 Вы получаете 5% с каждого выигрыша ваших рефералов!\n\n"
        f"📊 Ваша статистика:\n"
        f"└ Приглашено друзей: {referrals_count}\n\n"
        f"🔗 Ваша реферальная ссылка:\n"
        f"`{referral_link}`\n\n"
        f"📤 Поделитесь этой ссылкой с друзьями!"
    )

@router.message(F.text == "🏆 Топ игроков")
async def top_players_handler(message: Message, state: FSMContext):
    await state.set_state(GameState.leaderboard)
    await message.answer(
        "🏆 <b>Топ игроков</b>\n\n"
        "Выберите категорию для просмотра:",
        reply_markup=get_leaderboard_keyboard()
    )

@router.message(F.text == "📊 Статистика")
async def statistics_handler(message: Message, state: FSMContext):
    stats = get_user_stats(message.from_user.id)
    balance = get_balance(message.from_user.id)

    if stats:
        favorite_game = f"{stats['favorite_game']} [{stats['favorite_game_count']}]"
        total_games = stats['total_games']
        total_winnings = stats['total_winnings']
        biggest_win = stats['biggest_win']
        registration_date = stats['registration_date'][:10] if stats['registration_date'] else "20.10.2024"
    else:
        favorite_game = "Нет данных"
        total_games = 0
        total_winnings = 0
        biggest_win = 0
        registration_date = "20.10.2024"

    await message.answer(
        f"📊 <b>Детальная статистика</b>\n\n"
        f"💰 Текущий баланс: ${balance:.2f}\n"
        f"🎮 Всего игр: {total_games}\n"
        f"💎 Общие выигрыши: ${total_winnings:.2f}\n"
        f"🏆 Самый большой выигрыш: ${biggest_win:.2f}\n"
        f"🎯 Любимая игра: {favorite_game}\n"
        f"📅 Дата регистрации: {registration_date}\n\n"
        f"💡 Продолжайте играть для улучшения статистики!"
    )

@router.message(F.text == "📜 История")
async def history_handler(message: Message, state: FSMContext):
    await state.set_state(GameState.viewing_history)

    history = get_user_bet_history(message.from_user.id, 10)

    if not history:
        await message.answer(
            "📜 <b>История ставок</b>\n\n"
            "❌ У вас пока нет истории ставок.\n"
            "Сделайте первую ставку, чтобы увидеть историю!"
        )
        return

    history_text = "📜 <b>История ваших ставок</b>\n\n"

    game_names = {
        'bowling': '🎳 Боулинг',
        'dice_duel': '🎲 Кубы (дуэль)',
        'basketball': '🏀 Баскетбол',
        'dice_higher': '🎲 Больше/меньше',
        'dice_even': '🎲 Чет/нечет',
        'triada': '🎲 Триада',
        'darts': '🎯 Дартс',
        'slots': '🎰 Слоты',
        'mines': '💣 Мины',
        'tower': '🏗 Башня',
        'twist': '🌪 Твист',
        'combination': '🎯 Комбинация'
    }

    for i, (game_type, bet_amount, choice, result, win_amount, timestamp) in enumerate(history, 1):
        game_name = game_names.get(game_type, 'Неизвестная игра')

        if result == "win":
            result_emoji = "✅"
            result_text = f"Выигрыш: ${win_amount:.2f}"
        else:
            result_emoji = "❌"
            result_text = f"Проигрыш: ${bet_amount:.2f}"

        history_text += f"{i}. {game_name}\n"
        history_text += f"   💰 Ставка: ${bet_amount:.2f}\n"
        history_text += f"   {result_emoji} {result_text}\n"
        history_text += f"   📅 {timestamp[:16]}\n\n"

    await message.answer(history_text)

@router.message(F.text == "💰 Пополнить")
async def deposit_handler(message: Message, state: FSMContext):
    is_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer(
            f"🔒 <b>Для пополнения необходимо подписаться на наш канал!</b>\n\n"
            f"📢 Канал: {SUBSCRIPTION_CHANNEL}",
            reply_markup=get_subscription_keyboard()
        )
        return

    await state.set_state(GameState.crypto_deposit)
    await message.answer(
        "💳 <b>Пополнение баланса</b>\n\n"
        "💰 Введите сумму для пополнения в долларах (от $0.20 до $500.00):",
        reply_markup=get_bet_input_keyboard()
    )

@router.message(F.text == "💸 Вывести")
async def withdraw_handler(message: Message, state: FSMContext):
    balance = get_balance(message.from_user.id)

    if balance < 1.1:
        await message.answer(
            f"❌ <b>Недостаточно средств для вывода</b>\n\n"
            f"💰 Ваш баланс: ${balance:.2f}\n"
            f"📝 Минимальная сумма вывода: $1.10"
        )
        return

    await state.set_state(GameState.crypto_withdraw)
    await message.answer(
        f"💸 <b>Вывод средств</b>\n\n"
        f"💰 Доступно для вывода: ${balance:.2f}\n"
        f"📝 Минимальная сумма: $1.10\n\n"
        f"💰 Введите сумму для вывода в долларах:",
        reply_markup=get_bet_input_keyboard()
    )

@router.message(GameState.crypto_deposit)
async def process_deposit(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace("$", "").replace(",", "."))
        user_id = message.from_user.id

        if amount < 0.2 or amount > 500:
            await message.answer("❌ Сумма пополнения должна быть от $0.20 до $500.00")
            return

        await message.answer("⏳ Создаем счет для оплаты...")

        # Генерируем ссылку на оплату через CryptoBot
        try:
            invoice_result = await crypto_bot.create_invoice(amount, f"Пополнение NN | DICE WIN ${amount:.2f}", "USDT")

            if invoice_result:
                # Успешная генерация инвойса - отправляем ссылку
                invoice_url = invoice_result.get('pay_url')
                invoice_id = str(invoice_result.get('invoice_id'))

                # Сохраняем депозит в базу данных
                add_deposit(user_id, amount, invoice_id)

                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="💳 Оплатить", url=invoice_url)],
                        [InlineKeyboardButton(text="✅ Проверить платеж", callback_data=f"check_payment_{invoice_id}")]
                    ]
                )
                await message.answer(
                    f"✅ <b>Счет на пополнение создан!</b>\n\n"
                    f"💰 Сумма: ${amount:.2f} USDT\n"
                    f"🔗 Нажмите 'Оплатить' для перехода к оплате\n"
                    f"✅ После оплаты нажмите 'Проверить платеж'",
                    reply_markup=keyboard
                )

            else:
                # Ошибка генерации инвойса
                await message.answer(
                    f"❌ <b>Ошибка создания счета</b>\n\n"
                    f"Возможные причины:\n"
                    f"• Проблемы с CryptoBot API\n"
                    f"• Временные технические работы\n\n"
                    f"📞 Попробуйте позже или обратитесь к администратору"
                )

        except Exception as e:
            print(f"Error creating invoice: {e}")
            await message.answer(
                f"❌ <b>Техническая ошибка</b>\n\n"
                f"Не удалось создать счет для оплаты.\n"
                f"📞 Обратитесь к администратору"
            )

        await state.set_state(GameState.main_menu)

    except ValueError:
        await message.answer("❌ Введите корректную сумму для пополнения! Пример: 10 или 10.50")

@router.message(GameState.crypto_withdraw)
async def process_withdraw(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace("$", ""))
        user_id = message.from_user.id
        balance = get_balance(user_id)

        if amount < 1.1:
            await message.answer("❌ Минимальная сумма вывода: $1.10")
            return

        if amount > balance:
            await message.answer(f"❌ Недостаточно средств! Ваш баланс: ${balance:.2f}")
            return

        # Сначала проверяем подключение к CryptoBot
        await message.answer("⏳ Обрабатываем запрос на вывод...")

        # Пытаемся сделать автоматический вывод через CryptoBot
        result = await crypto_bot.transfer(user_id, amount, "USDT", f"Вывод из MoonCasino: ${amount:.2f}")

        if result:
            # Успешный автоматический вывод - списываем средства
            update_balance(user_id, -amount)
            await message.answer(
                f"✅ <b>Вывод успешно выполнен!</b>\n\n"
                f"💰 Сумма: ${amount:.2f}\n"
                f"🔗 Переведено на ваш CryptoBot кошелек\n"
                f"💳 Ваш баланс: ${get_balance(user_id):.2f}",
                reply_markup=get_start_keyboard()
            )
            add_withdrawal(user_id, amount)
        else:
            # Ошибка автоматического вывода - НЕ списываем деньги, уведомляем администратора
            # Уведомляем администратора о необходимости ручного вывода
            admin_id = 6774136020
            try:
                await bot.send_message(
                    admin_id,
                    f"💸 <b>Запрос на ручной вывод</b>\n\n"
                    f"👤 Пользователь: {message.from_user.first_name} (@{message.from_user.username or 'без_ника'})\n"
                    f"🆔 ID: <code>{user_id}</code>\n"
                    f"💰 Сумма: ${amount:.2f}\n\n"
                    f"❌ Автоматический вывод не удался (недостаточно средств в CryptoBot)\n"
                    f"💳 Баланс пользователя: ${balance:.2f}"
                )
            except:
                pass

            await message.answer(
                f"⚠️ <b>Временные технические проблемы</b>\n\n"
                f"💰 Запрошенная сумма: ${amount:.2f}\n"
                f"📞 Администратор обработает ваш запрос в ближайшее время\n"
                f"💳 Ваш баланс: ${balance:.2f} (средства НЕ списаны)\n\n"
                f"ℹ️ <b>Причина:</b> В кассе казино временно недостаточно средств для автоматического вывода",
                reply_markup=get_start_keyboard()
            )

        await state.set_state(GameState.main_menu)

    except ValueError:
        await message.answer("❌ Введите корректную сумму для вывода!")

@router.callback_query(F.data.startswith("check_payment_"))
async def check_payment_callback(callback: CallbackQuery):
    """Ручная проверка платежа пользователем"""
    invoice_id = callback.data.split("_")[2]

    await callback.answer("⏳ Проверяем платеж...")

    # Получаем информацию об инвойсе из CryptoBot
    invoice_data = await crypto_bot.get_invoice(invoice_id)

    if invoice_data and invoice_data.get('status') == 'paid':
        # Платеж подтвержден - зачисляем средства
        deposit_info = get_deposit_by_invoice(invoice_id)

        if deposit_info:
            user_id, amount = deposit_info
            update_balance(user_id, amount)
            update_deposit_status(invoice_id, 'completed')

            await callback.message.edit_text(
                f"✅ <b>Платеж подтвержден!</b>\n\n"
                f"💰 Зачислено: ${amount:.2f}\n"
                f"💳 Ваш баланс: ${get_balance(user_id):.2f}",
                reply_markup=None
            )
        else:
            await callback.message.edit_text(
                "❌ Ошибка: Депозит не найден",
                reply_markup=None
            )
    else:
        await callback.message.edit_text(
            f"⚠️ <b>Платеж еще не подтвержден</b>\n\n"
            f"Пожалуйста, завершите оплату и попробуйте снова.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Проверить снова", callback_data=f"check_payment_{invoice_id}")]
                ]
            )
        )

# Обработчики для игр
@router.message(F.text == "💣 Мины")
async def mines_handler(message: Message, state: FSMContext):
    is_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer(
            f"🔒 <b>Для игры необходимо подписаться на наш канал!</b>\n\n"
            f"📢 Канал: {SUBSCRIPTION_CHANNEL}",
            reply_markup=get_subscription_keyboard()
        )
        return

    balance = get_balance(message.from_user.id)
    if balance < 0.2:
        await message.answer("❌ Недостаточно средств для игры! Минимум $0.20")
        return

    await state.set_state(GameState.waiting_bet)
    await state.update_data(game_type='mines')

    quick_keyboard = get_bet_amounts_keyboard(message.from_user.id)

    await message.answer(
        f"💣 <b>Мины</b>\n\n"
        f"💰 Ваш баланс: ${balance:.2f}\n"
        f"📝 Введите сумму ставки (от $0.20 до $500.00):",
        reply_markup=get_bet_input_keyboard()
    )

    if quick_keyboard.inline_keyboard:
        await message.answer("⚡ <b>Быстрые ставки:</b>", reply_markup=quick_keyboard)

@router.message(F.text == "🏗 Башня")
async def tower_handler(message: Message, state: FSMContext):
    is_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer(
            f"🔒 <b>Для игры необходимо подписаться на наш канал!</b>\n\n"
            f"📢 Канал: {SUBSCRIPTION_CHANNEL}",
            reply_markup=get_subscription_keyboard()
        )
        return

    balance = get_balance(message.from_user.id)
    if balance < 0.2:
        await message.answer("❌ Недостаточно средств для игры! Минимум $0.20")
        return

    await state.set_state(GameState.waiting_bet)
    await state.update_data(game_type='tower')

    quick_keyboard = get_bet_amounts_keyboard(message.from_user.id)

    await message.answer(
        f"🏗 <b>Башня</b>\n\n"
        f"💰 Ваш баланс: ${balance:.2f}\n"
        f"📝 Введите сумму ставки (от $0.20 до $500.00):",
        reply_markup=get_bet_input_keyboard()
    )

    if quick_keyboard.inline_keyboard:
        await message.answer("⚡ <b>Быстрые ставки:</b>", reply_markup=quick_keyboard)

@router.message(F.text == "🌪 Твист")
async def twist_handler(message: Message, state: FSMContext):
    is_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer(
            f"🔒 <b>Для игры необходимо подписаться на наш канал!</b>\n\n"
            f"📢 Канал: {SUBSCRIPTION_CHANNEL}",
            reply_markup=get_subscription_keyboard()
        )
        return

    balance = get_balance(message.from_user.id)
    if balance < 0.2:
        await message.answer("❌ Недостаточно средств для игры! Минимум $0.20")
        return

    await state.set_state(GameState.waiting_bet)
    await state.update_data(game_type='twist')

    quick_keyboard = get_bet_amounts_keyboard(message.from_user.id)

    await message.answer(
        f"🌪 <b>Твист</b>\n\n"
        f"📖 <b>Правила игры:</b>\n"
        f"🔄 Крутите барабан и собирайте символы в любом порядке\n"
        f"💎 Денежные символы: ⭐️(звезда), ⚓️(якорь), 🐚(ракушка)\n"
        f"💸 Денежный смайлик - для максимальных коэффициентов\n"
        f"💀 Череп - откидывает на 1 шаг назад в каждой секции\n"
        f"💩 Какашка - самый частый символ, ничего не дает\n\n"
        f"🎰 <b>Коэффициенты (нужен 💸 для максимума):</b>\n"
        f"🐚🐚🐚🐚🐚🐚🐚💸\n"
        f"x4 · x13 · x28.5 · x53 · x88 · x137.5 · x205\n\n"
        f"⭐️⭐️⭐️⭐️⭐️💸\n"
        f"x2.5 · x8 · x16.5 · x28.5 · x45\n\n"
        f"⚓️⚓️⚓️💸\n"
        f"x1.6 · x5 · x10.5\n\n"
        f"💰 Ваш баланс: ${balance:.2f}\n"
        f"📝 Введите сумму ставки (от $0.20 до $500.00):",
        reply_markup=get_bet_input_keyboard()
    )

    if quick_keyboard.inline_keyboard:
        await message.answer("⚡ <b>Быстрые ставки:</b>", reply_markup=quick_keyboard)

@router.message(F.text == "🎯 Комбинация")
async def combination_handler(message: Message, state: FSMContext):
    is_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer(
            f"🔒 <b>Для игры необходимо подписаться на наш канал!</b>\n\n"
            f"📢 Канал: {SUBSCRIPTION_CHANNEL}",
            reply_markup=get_subscription_keyboard()
        )
        return

    balance = get_balance(message.from_user.id)
    if balance < 0.2:
        await message.answer("❌ Недостаточно средств для игры! Минимум $0.20")
        return

    await state.set_state(GameState.waiting_bet)
    await state.update_data(game_type='combination')

    quick_keyboard = get_bet_amounts_keyboard(message.from_user.id)

    await message.answer(
        f"🎯 <b>Комбинация</b>\n\n"
        f"💰 Ваш баланс: ${balance:.2f}\n"
        f"📝 Введите сумму ставки (от $0.20 до $500.00):",
        reply_markup=get_bet_input_keyboard()
    )

    if quick_keyboard.inline_keyboard:
        await message.answer("⚡ <b>Быстрые ставки:</b>", reply_markup=quick_keyboard)

# Обработчики канальных игр
@router.message(F.text.in_(["🎳 Боулинг", "🏀 Баскетбол", "🎲 Кубы (дуэль)", "🎲 Больше/меньше", "🎲 Чет/нечет", "🎲 Триада", "🎯 Дартс", "🎰 Слоты"]))
async def channel_games_start_handler(message: Message, state: FSMContext):
    balance = get_balance(message.from_user.id)
    if balance < 0.2:
        await message.answer("❌ Недостаточно средств для игры! Минимум $0.20")
        return

    # Определяем тип игры
    game_types = {
        "🎳 Боулинг": 'bowling',
        "🏀 Баскетбол": 'basketball',
        "🎲 Кубы (дуэль)": 'dice_duel',
        "🎲 Больше/меньше": 'dice_higher',
        "🎲 Чет/нечет": 'dice_even',
        "🎲 Триада": 'triada',
        "🎯 Дартс": 'darts',
        "🎰 Слоты": 'slots'
    }

    game_type = game_types.get(message.text)
    if not game_type:
        return

    await state.set_state(GameState.waiting_bet)
    await state.update_data(game_type=game_type)

    quick_keyboard = get_bet_amounts_keyboard(message.from_user.id)

    await message.answer(
        f"{message.text}\n\n"
        f"💰 Ваш баланс: ${balance:.2f}\n"
        f"📝 Введите сумму ставки (от $0.20 до $500.00):",
        reply_markup=get_bet_input_keyboard()
    )

    if quick_keyboard.inline_keyboard:
        await message.answer("⚡ <b>Быстрые ставки:</b>", reply_markup=quick_keyboard)

@router.message(GameState.waiting_bet)
async def process_bet_amount(message: Message, state: FSMContext):
    # Проверяем кнопку "Назад"
    if message.text == "⬅️ Назад":
        await back_handler(message, state)
        return

    try:
        bet_amount = float(message.text.replace("$", ""))
        data = await state.get_data()
        game_type = data.get('game_type')

        balance = get_balance(message.from_user.id)

        if bet_amount < 0.2:
            await message.answer("❌ Минимальная ставка $0.20")
            return

        if bet_amount > 500:
            await message.answer("❌ Максимальная ставка $500.00")
            return

        # Округляем баланс и ставку до 2 знаков для корректного сравнения
        balance_rounded = round(balance, 2)
        bet_rounded = round(bet_amount, 2)

        if bet_rounded > balance_rounded:
            await message.answer(f"❌ Недостаточно средств! Ваш баланс: ${balance_rounded:.2f}")
            return

        await state.update_data(bet_amount=bet_amount) # Сохраняем ставку как bet_amount
        add_bet_amount_to_history(message.from_user.id, bet_amount)

        # Переходим к выбору исхода в зависимости от игры
        if game_type == 'bowling':
            await state.set_state(GameState.channel_bowling)
            await message.answer(
                f"🎳 <b>Боулинг (дуэль)</b>\n"
                f"💰 Ставка: ${bet_amount:.2f}\n"
                f"💳 Баланс: ${balance:.2f}\n\n"
                f"Выберите исход:",
                reply_markup=get_bowling_choice_keyboard()
            )
        elif game_type == 'basketball':
            await state.set_state(GameState.channel_basketball)
            await message.answer(
                f"🏀 <b>Баскетбол</b>\n"
                f"💰 Ставка: ${bet_amount:.2f}\n"
                f"💳 Баланс: ${balance:.2f}\n\n"
                f"Выберите исход:",
                reply_markup=get_basketball_keyboard()
            )
        elif game_type == 'dice_duel':
            await state.set_state(GameState.channel_dice_duel)
            await message.answer(
                f"🎲 <b>Кубы (дуэль)</b>\n"
                f"💰 Ставка: ${bet_amount:.2f}\n"
                f"💳 Баланс: ${balance:.2f}\n\n"
                f"Выберите исход:",
                reply_markup=get_dice_duel_choice_keyboard()
            )
        elif game_type == 'dice_higher':
            await state.set_state(GameState.channel_dice_higher)
            await message.answer(
                f"🎲 <b>Больше/меньше</b>\n"
                f"💰 Ставка: ${bet_amount:.2f}\n"
                f"💳 Баланс: ${balance:.2f}\n\n"
                f"Выберите исход:",
                reply_markup=get_dice_higher_lower_keyboard()
            )
        elif game_type == 'dice_even':
            await state.set_state(GameState.channel_dice_even)
            await message.answer(
                f"🎲 <b>Чет/нечет</b>\n"
                f"💰 Ставка: ${bet_amount:.2f}\n"
                f"💳 Баланс: ${balance:.2f}\n\n"
                f"Выберите исход:",
                reply_markup=get_dice_even_odd_keyboard()
            )
        elif game_type == 'triada':
            await state.set_state(GameState.channel_triada)
            await message.answer(
                f"🎲 <b>Триада</b>\n"
                f"💰 Ставка: ${bet_amount:.2f}\n"
                f"💳 Баланс: ${balance:.2f}\n\n"
                f"Выберите число:",
                reply_markup=get_triada_keyboard()
            )
        elif game_type == 'darts':
            await state.set_state(GameState.channel_darts)
            await message.answer(
                f"🎯 <b>Дартс</b>\n"
                f"💰 Ставка: ${bet_amount:.2f}\n"
                f"💳 Баланс: ${balance:.2f}\n\n"
                f"Выберите исход:",
                reply_markup=get_darts_keyboard()
            )
        elif game_type == 'slots':
            # Для слотов сразу запускаем игру
            update_balance(message.from_user.id, -bet_amount)
            await message.answer(
                f"🎰 <b>Слоты</b>\n"
                f"💰 Ставка: ${bet_amount:.2f}\n"
                f"🎮 Запускаем игру в канале...\n\n"
                f"📺 Следите за результатом в канале!"
            )

            # Добавляем в очередь
            from games import game_queue, is_game_running, process_game_queue, play_slots_direct
            game_queue.append({
                'game_type': 'slots',
                'user': message.from_user,
                'bet_amount': bet_amount,
                'choice': 'spin',
                'game_function': play_slots_direct
            })

            if not is_game_running:
                asyncio.create_task(process_game_queue(bot))

            await state.set_state(GameState.main_menu)
        elif game_type == 'combination':
            await state.set_state(GameState.combination_game)
            await message.answer(
                f"🎯 <b>Комбинация</b>\n"
                f"💰 Ставка: ${bet_amount:.2f}\n\n"
                f"🎮 Введите трёхзначное число (100-999):\nПример: 123, 456, 789",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                    resize_keyboard=True,
                    one_time_keyboard=False
                )
            )
        elif game_type == 'twist':
            await state.set_state(GameState.twist_game)

            # Инициализируем игровое состояние
            twist_state = {
                'anchor_count': 0,      # ⚓️ счетчик
                'star_count': 0,        # ⭐️ счетчик
                'shell_count': 0,       # 🐚 счетчик
                'bet_amount': bet_amount,
                'game_bank': 0,         # банк игры
                'spins_made': 0
            }
            await state.update_data(twist_state=twist_state)

            keyboard = create_twist_keyboard()
            await message.answer(
                f"🌪 <b>Твист - Игра началась!</b>\n\n"
                f"💳 Ваш баланс: ${get_balance(message.from_user.id):.2f}\n"
                f"🏦 Банк игры: $0.00\n\n"
                f"📊 <b>Коэффициенты:</b>\n"
                f"🐚 Ракушка: x3.0\n"
                f"⭐️ Звезда: x2.0\n"
                f"⚓️ Якорь: x1.8\n"
                f"💀 Череп: банк сгорает!\n"
                f"💩 Какашка: ничего\n\n"
                f"📊 <b>Прогресс секций:</b>\n"
                f"🐚: 0/7\n"
                f"⭐️: 0/5\n"
                f"⚓️: 0/3\n\n"
                f"⚠️ Каждый спин стоит: ${bet_amount:.2f}\n"
                f"💰 При попадании символа деньги по коэффициенту идут в банк!",
                reply_markup=keyboard
            )
        elif game_type == 'mines':
            await state.set_state(GameState.mines_setup)
            await message.answer(
                f"💣 <b>Мины</b>\n"
                f"💰 Ставка: ${bet_amount:.2f}\n\n"
                f"Выберите количество мин:",
                reply_markup=get_mines_count_keyboard()
            )
        elif game_type == 'tower':
            await state.set_state(GameState.tower_setup)
            await message.answer(
                f"🏗 <b>Башня</b>\n"
                f"💰 Ставка: ${bet_amount:.2f}\n\n"
                f"Выберите количество бомб на уровне:",
                reply_markup=get_tower_mines_keyboard()
            )

    except ValueError:
        await message.answer("❌ Введите корректную сумму ставки!")

# Обработчики выбора исхода для канальных игр
@router.message(F.text.in_(["🏆 Победа (x1.8)", "💀 Поражение (x1.8)"]))
async def handle_choice_buttons(message: Message, state: FSMContext):
    current_state = await state.get_state()
    data = await state.get_data()
    bet_amount = data.get('bet_amount', 0)

    if current_state == GameState.channel_bowling:
        choice = "win" if "Победа" in message.text else "loss"
        await process_channel_game(message, state, 'bowling', bet_amount, choice)
    elif current_state == GameState.channel_dice_duel:
        choice = "win" if "Победа" in message.text else "loss"
        await process_channel_game(message, state, 'dice_duel', bet_amount, choice)

@router.message(F.text.in_(["🎯 Попадание (x1.8)", "❌ Мимо (x1.3)"]))
async def handle_basketball_choice(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == GameState.channel_basketball:
        data = await state.get_data()
        bet_amount = data.get('bet_amount', 0)
        choice = "hit" if "Попадание" in message.text else "miss"
        await process_channel_game(message, state, 'basketball', bet_amount, choice)

@router.message(F.text.in_(["⬆️ Больше", "⬇️ Меньше"]))
async def handle_dice_higher_choice(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == GameState.channel_dice_higher:
        data = await state.get_data()
        bet_amount = data.get('bet_amount', 0)
        choice = "higher" if "Больше" in message.text else "lower"
        await process_channel_game(message, state, 'dice_higher', bet_amount, choice)

@router.message(F.text.in_(["2️⃣ Четное", "1️⃣ Нечетное"]))
async def handle_dice_even_choice(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == GameState.channel_dice_even:
        data = await state.get_data()
        bet_amount = data.get('bet_amount', 0)
        choice = "even" if "Четное" in message.text else "odd"
        await process_channel_game(message, state, 'dice_even', bet_amount, choice)

@router.message(F.text.in_(["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"]))
async def handle_triada_choice(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == GameState.channel_triada:
        data = await state.get_data()
        bet_amount = data.get('bet_amount', 0)
        choice = message.text[0]  # Получаем цифру из эмодзи
        await process_channel_game(message, state, 'triada', bet_amount, choice)

@router.message(F.text.in_(["🔴 Красное (x1.8)", "⚪ Белое (x1.8)"]))
async def handle_darts_choice(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == GameState.channel_darts:
        data = await state.get_data()
        bet_amount = data.get('bet_amount', 0)
        choice = "red" if "Красное" in message.text else "white"
        await process_channel_game(message, state, 'darts', bet_amount, choice)

@router.message(F.text == "💰 Изменить сумму")
async def change_bet_amount_handler(message: Message, state: FSMContext):
    """Обработчик для кнопки изменения суммы ставки"""
    current_state = await state.get_state()
    data = await state.get_data()
    game_type = data.get('game_type')

    if current_state in [GameState.channel_bowling, GameState.channel_basketball,
                          GameState.channel_dice_duel, GameState.channel_dice_higher,
                          GameState.channel_dice_even, GameState.channel_triada,
                          GameState.channel_darts, GameState.combination_game]:

        await state.set_state(GameState.waiting_bet)
        balance = get_balance(message.from_user.id)

        quick_keyboard = get_bet_amounts_keyboard(message.from_user.id)

        await message.answer(
            f"💰 <b>Изменить сумму ставки</b>\n\n"
            f"💳 Ваш баланс: ${balance:.2f}\n"
            f"📝 Введите новую сумму ставки (от $0.20 до $500.00):",
            reply_markup=get_bet_input_keyboard()
        )

        if quick_keyboard.inline_keyboard:
            await message.answer("⚡ <b>Быстрые ставки:</b>", reply_markup=quick_keyboard)



@router.message(GameState.combination_game)
async def combination_number_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    bet_amount = data.get('bet_amount', 0)

    # Проверяем, что введено корректное число
    try:
        user_number = int(message.text)
        if 100 <= user_number <= 999:
            # Списываем деньги
            update_balance(message.from_user.id, -bet_amount)

            # Генерируем случайное число
            winning_number = random.randint(100, 999)

            # Проверяем совпадения
            user_digits = str(user_number)
            winning_digits = str(winning_number)

            exact_matches = sum(1 for i in range(3) if user_digits[i] == winning_digits[i])
            digit_matches = len(set(user_digits) & set(winning_digits))

            # Определяем выигрыш
            if exact_matches == 3:
                # Точное совпадение
                win_amount = bet_amount * 2.15
                result_text = f"🎉 <b>ДЖЕКПОТ!</b>\n💰 Выигрыш: ${win_amount:.2f} (x2.15)"
                update_balance(message.from_user.id, win_amount)
                update_game_stats(message.from_user.id, "Комбинация", win_amount)
            elif exact_matches == 2:
                # 2 цифры на правильных позициях
                win_amount = bet_amount * 1.75
                result_text = f"🎉 <b>Отлично!</b>\n💰 Выигрыш: ${win_amount:.2f} (x1.75)"
                update_balance(message.from_user.id, win_amount)
                update_game_stats(message.from_user.id, "Комбинация", win_amount)
            elif exact_matches == 1:
                # 1 цифра на правильной позиции
                win_amount = bet_amount * 1.35
                result_text = f"🎉 <b>Неплохо!</b>\n💰 Выигрыш: ${win_amount:.2f} (x1.35)"
                update_balance(message.from_user.id, win_amount)
                update_game_stats(message.from_user.id, "Комбинация", win_amount)
            else:
                # Проигрыш
                result_text = f"😢 <b>Не угадали</b>\n💸 Проигрыш: ${bet_amount:.2f}"
                update_game_stats(message.from_user.id, "Комбинация", 0)

            await message.answer(
                f"🎯 <b>Результат игры Комбинация</b>\n\n"
                f"🎲 Ваше число: {user_number}\n"
                f"🎯 Выигрышное число: {winning_number}\n"
                f"📊 Точных совпадений: {exact_matches}\n"
                f"📈 Цифр угадано: {digit_matches}\n\n"
                f"{result_text}\n\n"
                f"💳 Ваш баланс: ${get_balance(message.from_user.id):.2f}",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                    resize_keyboard=True,
                    one_time_keyboard=False
                )
            )

            await state.set_state(GameState.bot_games)
        else:
            await message.answer("❌ Введите трёхзначное число от 100 до 999!")
    except ValueError:
        await message.answer("❌ Введите корректное трёхзначное число!")

async def process_channel_game(message: Message, state: FSMContext, game_type: str, bet_amount: float, choice: str):
    """Обрабатывает канальную игру."""
    from games import game_queue, is_game_running, process_game_queue
    from games import (play_bowling_direct, play_dice_duel_direct, play_basketball_direct,
                       play_dice_higher_direct, play_dice_even_direct, play_triada_direct,
                       play_darts_direct)

    # Проверяем баланс перед списанием
    balance = get_balance(message.from_user.id)
    balance_rounded = round(balance, 2)
    bet_rounded = round(bet_amount, 2)

    if bet_rounded > balance_rounded:
        await message.answer(f"❌ Недостаточно средств! Ваш баланс: ${balance_rounded:.2f}")
        await state.set_state(GameState.main_menu)
        return

    # Списываем деньги
    update_balance(message.from_user.id, -bet_amount)

    # Показываем подтверждение и убираем панель
    game_names = {
        'bowling': '🎳 Боулинг',
        'dice_duel': '🎲 Кубы (дуэль)',
        'basketball': '🏀 Баскетбол',
        'dice_higher': '🎲 Больше/меньше',
        'dice_even': '🎲 Чет/нечет',
        'triada': '🎲 Триада',
        'darts': '🎯 Дартс'
    }

    # Кнопка перехода в канал в сообщении о принятой ставке
    channel_button_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="📺 Смотреть в канале", url="https://t.me/NNDICEWIN")
        ]]
    )

    await message.answer(
        f"✅ <b>Ставка принята!</b>\n\n"
        f"🎮 Игра: {game_names[game_type]}\n"
        f"💰 Ставка: ${bet_amount:.2f}\n"
        f"🎲 Ваш выбор: {choice}\n\n"
        f"📺 Следите за результатом в канале!",
        reply_markup=channel_button_keyboard
    )

    await message.answer(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⬅️ Назад")]],
            resize_keyboard=True,
            one_time_keyboard=False
        )
    )

    # Определяем функцию игры
    game_functions = {
        'bowling': play_bowling_direct,
        'dice_duel': play_dice_duel_direct,
        'basketball': play_basketball_direct,
        'dice_higher': play_dice_higher_direct,
        'dice_even': play_dice_even_direct,
        'triada': play_triada_direct,
        'darts': play_darts_direct
    }

    # Добавляем в очередь
    game_queue.append({
        'game_type': game_type,
        'user': message.from_user,
        'bet_amount': bet_amount,
        'choice': choice,
        'game_function': game_functions[game_type]
    })

    # Запускаем обработку очереди если не запущена
    if not is_game_running:
        asyncio.create_task(process_game_queue(bot))

    await state.set_state(GameState.main_menu)

# Обработчики выбора количества мин
@router.message(F.text.in_(["2 мины", "3 мины", "4 мины", "5 мин", "6 мин", "7 мин", "8 мин", "9 мин", "10 мин", "11 мин", "12 мин", "13 мин", "14 мин", "15 мин", "16 мин", "17 мин", "18 мин", "19 мин", "20 мин", "21 мина", "22 мины", "23 мины", "24 мины"]))
async def mines_count_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    bet_amount = data.get('bet_amount', 0) # Получаем ставку

    mines_count = int(message.text.split()[0])

    await state.update_data(mines_count=mines_count)
    await state.set_state(GameState.mines_playing)

    # Создаем поле мин 5x5
    mines_field = create_mines_field(mines_count)
    await state.update_data(mines_field=mines_field, opened_cells=[], current_coefficient=1.0, clicks_count=0)

    keyboard = create_mines_inline_keyboard(mines_count, [], MINES_COEFFICIENTS[mines_count][0], 0) # Передаем начальный коэффициент

    # Убираем обычную клавиатуру во время игры
    await message.answer(
        f"💣 <b>Мины</b>\n\n"
        f"💰 Ставка: ${bet_amount:.2f}\n"
        f"💣 Количество мин: {mines_count}\n"
        f"💎 Открыто клеток: 0\n"
        f"🎯 Текущий коэффициент: x1.00\n\n"
        f"Выберите клетку:",
        reply_markup=keyboard
    )

    # Отправляем сообщение без клавиатуры для скрытия панели
    await message.answer(
        "🎮 <b>Игра началась!</b>\n"
        "Используйте кнопки выше для игры",
        reply_markup=types.ReplyKeyboardRemove()
    )

# Обработчики выбора количества бомб для башни
@router.message(F.text.in_(["1 бомба", "2 бомбы", "3 бомбы", "4 бомбы"]))
async def tower_bombs_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    bet_amount = data.get('bet_amount', 0) # Получаем ставку

    bombs_count = int(message.text.split()[0])

    await state.set_state(GameState.tower_playing)
    await state.update_data(
        bombs_count=bombs_count,
        tower_level=0,
        opened_levels=[],
        game_over=False
    )

    keyboard = create_tower_inline_keyboard(bombs_count, [], 0) # Начальный уровень 0

    # Убираем обычную клавиатуру во время игры
    await message.answer(
        f"🏗 <b>Башня</b>\n\n"
        f"💰 Ставка: ${bet_amount:.2f}\n"
        f"💣 Бомб на уровне: {bombs_count}\n"
        f"🎯 Текущий уровень: 1/6\n"
        f"📈 Коэффициент: x1.00\n\n"
        f"Выберите сейф на уровне 1:",
        reply_markup=keyboard
    )

    # Отправляем сообщение без клавиатуры для скрытия панели
    await message.answer(
        "🎮 <b>Игра началась!</b>\n"
        "Используйте кнопки выше для игры",
        reply_markup=types.ReplyKeyboardRemove()
    )

# Обработчики callback для быстрых ставок
@router.callback_query(F.data.startswith("quick_amount_"))
async def quick_amount_callback(callback: CallbackQuery, state: FSMContext):
    try:
        amount = float(callback.data.split("_")[2])
        data = await state.get_data()
        game_type = data.get('game_type')

        # Проверяем баланс перед применением ставки
        balance = get_balance(callback.from_user.id)
        balance_rounded = round(balance, 2)
        amount_rounded = round(amount, 2)

        if amount_rounded > balance_rounded:
            await callback.answer(f"❌ Недостаточно средств! Баланс: ${balance_rounded:.2f}", show_alert=True)
            return

        await callback.answer(f"Выбрана сумма: ${amount}")

        # Обновляем сумму ставки и переходим к выбору исхода
        await state.update_data(bet_amount=amount) # Сохраняем ставку как bet_amount
        add_bet_amount_to_history(callback.from_user.id, amount)

        # Переходим к соответствующему состоянию игры
        if game_type == 'bowling':
            await state.set_state(GameState.channel_bowling)
            await callback.message.edit_text(
                f"🎳 <b>Боулинг (дуэль)</b>\n"
                f"💰 Ставка: ${amount:.2f}\n\n"
                f"Выберите исход:",
                reply_markup=None
            )
            await callback.message.answer(
                "Выберите ваш прогноз:",
                reply_markup=get_bowling_choice_keyboard()
            )
        elif game_type == 'basketball':
            await state.set_state(GameState.channel_basketball)
            await callback.message.edit_text(
                f"🏀 <b>Баскетбол</b>\n"
                f"💰 Ставка: ${amount:.2f}\n\n"
                f"Выберите исход:",
                reply_markup=None
            )
            await callback.message.answer(
                "Выберите ваш прогноз:",
                reply_markup=get_basketball_keyboard()
            )
        elif game_type == 'dice_duel':
            await state.set_state(GameState.channel_dice_duel)
            await callback.message.edit_text(
                f"🎲 <b>Кубы (дуэль)</b>\n"
                f"💰 Ставка: ${amount:.2f}\n\n"
                f"Выберите исход:",
                reply_markup=None
            )
            await callback.message.answer(
                "Выберите ваш прогноз:",
                reply_markup=get_dice_duel_choice_keyboard()
            )
        elif game_type == 'dice_higher':
            await state.set_state(GameState.channel_dice_higher)
            await callback.message.edit_text(
                f"🎲 <b>Больше/меньше</b>\n"
                f"💰 Ставка: ${amount:.2f}\n\n"
                f"Выберите исход:",
                reply_markup=None
            )
            await callback.message.answer(
                "Выберите ваш прогноз:",
                reply_markup=get_dice_higher_lower_keyboard()
            )
        elif game_type == 'dice_even':
            await state.set_state(GameState.channel_dice_even)
            await callback.message.edit_text(
                f"🎲 <b>Чет/нечет</b>\n"
                f"💰 Ставка: ${amount:.2f}\n\n"
                f"Выберите исход:",
                reply_markup=None
            )
            await callback.message.answer(
                "Выберите ваш прогноз:",
                reply_markup=get_dice_even_odd_keyboard()
            )
        elif game_type == 'triada':
            await state.set_state(GameState.channel_triada)
            await callback.message.edit_text(
                f"🎲 <b>Триада</b>\n"
                f"💰 Ставка: ${amount:.2f}\n\n"
                f"Выберите число:",
                reply_markup=None
            )
            await callback.message.answer(
                "Выберите число:",
                reply_markup=get_triada_keyboard()
            )
        elif game_type == 'darts':
            await state.set_state(GameState.channel_darts)
            await callback.message.edit_text(
                f"🎯 <b>Дартс</b>\n"
                f"💰 Ставка: ${amount:.2f}\n\n"
                f"Выберите исход:",
                reply_markup=None
            )
            await callback.message.answer(
                "Выберите ваш прогноз:",
                reply_markup=get_darts_keyboard()
            )
        elif game_type == 'slots':
            # Для слотов сразу запускаем игру
            # Дополнительная проверка баланса для слотов
            current_balance = get_balance(callback.from_user.id)
            if amount > current_balance:
                await callback.answer(f"❌ Недостаточно средств! Баланс: ${current_balance:.2f}", show_alert=True)
                return

            update_balance(callback.from_user.id, -amount)
            await callback.message.edit_text(
                f"🎰 <b>Слоты</b>\n"
                f"💰 Ставка: ${amount:.2f}\n"
                f"🎮 Запускаем игру в канале...\n\n"
                f"📺 Следите за результатом в канале!",
                reply_markup=None
            )

            # Добавляем в очередь
            from games import game_queue, is_game_running, process_game_queue, play_slots_direct
            game_queue.append({
                'game_type': 'slots',
                'user': callback.from_user,
                'bet_amount': amount,
                'choice': 'spin',
                'game_function': play_slots_direct
            })

            if not is_game_running:
                asyncio.create_task(process_game_queue(bot))

            await state.set_state(GameState.main_menu)

        # Добавим поддержку ботовых игр
        elif game_type == 'mines':
            await state.set_state(GameState.mines_setup)
            await callback.message.edit_text(
                f"💣 <b>Мины</b>\n"
                f"💰 Ставка: ${amount:.2f}\n\n"
                f"Выберите количество мин:",
                reply_markup=None
            )
            await callback.message.answer(
                "Выберите количество мин:",
                reply_markup=get_mines_count_keyboard()
            )
        elif game_type == 'tower':
            await state.set_state(GameState.tower_setup)
            await callback.message.edit_text(
                f"🏗 <b>Башня</b>\n"
                f"💰 Ставка: ${amount:.2f}\n\n"
                f"Выберите количество бомб:",
                reply_markup=None
            )
            await callback.message.answer(
                "Выберите количество бомб на уровне:",
                reply_markup=get_tower_mines_keyboard()
            )
        elif game_type == 'combination':
            await state.set_state(GameState.combination_game)
            await callback.message.edit_text(
                f"🎯 <b>Комбинация</b>\n"
                f"💰 Ставка: ${amount:.2f}\n\n"
                f"Введите трёхзначное число (100-999):",
                reply_markup=None
            )
            await callback.message.answer(
                "🎮 Введите трёхзначное число!\nПример: 123, 456, 789",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                    resize_keyboard=True,
                    one_time_keyboard=False
                )
            )
        elif game_type == 'twist':
            await state.set_state(GameState.twist_game)

            # Инициализируем игровое состояние
            twist_state = {
                'anchor_count': 0,      # ⚓️ счетчик
                'star_count': 0,        # ⭐️ счетчик
                'shell_count': 0,       # 🐚 счетчик
                'bet_amount': amount,
                'game_bank': 0,         # банк игры
                'spins_made': 0
            }
            await state.update_data(twist_state=twist_state)

            keyboard = create_twist_keyboard()
            await callback.message.edit_text(
                f"🌪 <b>Твист - Игра началась!</b>\n\n"
                f"💳 Ваш баланс: ${get_balance(callback.from_user.id):.2f}\n"
                f"🏦 Банк игры: $0.00\n\n"
                f"📊 <b>Коэффициенты:</b>\n"
                f"🐚 Ракушка: x3.0\n"
                f"⭐️ Звезда: x2.0\n"
                f"⚓️ Якорь: x1.8\n"
                f"💀 Череп: банк сгорает!\n"
                f"💩 Какашка: ничего\n\n"
                f"📊 <b>Прогресс секций:</b>\n"
                f"🐚: 0/7\n"
                f"⭐️: 0/5\n"
                f"⚓️: 0/3\n\n"
                f"⚠️ Каждый спин стоит: ${amount:.2f}",
                reply_markup=keyboard
            )
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {str(e)}")

# Обработчики callback для игр Мины и Башня
@router.callback_query(F.data.startswith("mine_"))
async def mines_callback_handler(callback: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        mines_positions = data.get('mines_positions', [])
        opened_cells = data.get('opened_cells', [])
        mines_count = data.get('mines_count', 2)
        bet_amount = data.get('bet_amount', 0)
        clicks_count = data.get('clicks_count', 0)

        if callback.data == "mines_cash_out":
            # Забираем выигрыш
            current_coeff = MINES_COEFFICIENTS[mines_count][clicks_count - 1] if clicks_count > 0 else 1
            win_amount = bet_amount * current_coeff

            # Возвращаем ставку + выигрыш (деньги уже были списаны при начале игры)
            update_balance(callback.from_user.id, win_amount)
            update_game_stats(callback.from_user.id, "Мины", win_amount)

            play_again_keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🎮 Играть снова", callback_data="play_mines_again")],
                    [InlineKeyboardButton(text="🎰 Главное меню", callback_data="main_menu")]
                ]
            )

            await callback.message.edit_text(
                f"💰 <b>Выигрыш забран!</b>\n\n"
                f"💣 Мины: {mines_count}\n"
                f"💎 Открыто клеток: {clicks_count}\n"
                f"💰 Выигрыш: ${win_amount:.2f} (x{current_coeff})\n"
                f"💳 Ваш баланс: ${get_balance(callback.from_user.id):.2f}",
                reply_markup=play_again_keyboard
            )
            return

        elif callback.data == "mines_exit":
            await callback.message.edit_text(
                f"❌ <b>Игра завершена</b>\n\n"
                f"💸 Проигрыш: ${bet_amount:.2f}",
                reply_markup=None
            )

            # Возвращаем клавиатуру и переходим к играм в боте
            await state.set_state(GameState.bot_games)
            await callback.message.answer(
                "🤖 <b>Игры в боте:</b>\n\nВыберите игру:",
                reply_markup=get_bot_games_keyboard()
            )
            return

        # Обработка клика по клетке
        parts = callback.data.split("_")
        if len(parts) == 3:
            row, col = int(parts[1]), int(parts[2])
            cell_index = row * 5 + col

            if (row, col) in opened_cells:
                await callback.answer("Эта клетка уже открыта!")
                return

            # Подкрут казино: после 5 кликов увеличиваем шанс попадания на мину
            is_mine = cell_index in mines_positions
            if clicks_count >= 5 and not is_mine and random.random() < 0.25:  # 25% шанс "создать" мину
                is_mine = True

            if is_mine:
                # Попали на мину - игра окончена
                update_game_stats(callback.from_user.id, "Мины", 0)

                play_again_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="🎮 Играть снова", callback_data="play_mines_again")],
                        [InlineKeyboardButton(text="🎰 Главное меню", callback_data="main_menu")]
                    ]
                )

                await callback.message.edit_text(
                    f"💥 <b>ВЗРЫВ!</b>\n\n"
                    f"💣 Вы попали на мину!\n"
                    f"💸 Проигрыш: ${bet_amount:.2f}",
                    reply_markup=play_again_keyboard
                )
            else:
                # Открыли безопасную клетку
                opened_cells.append((row, col))
                clicks_count += 1

                current_coeff = MINES_COEFFICIENTS[mines_count][clicks_count - 1] if clicks_count <= len(MINES_COEFFICIENTS[mines_count]) else MINES_COEFFICIENTS[mines_count][-1]

                await state.update_data(opened_cells=opened_cells, clicks_count=clicks_count)

                keyboard = create_mines_inline_keyboard(mines_count, opened_cells, current_coeff, clicks_count)

                await callback.message.edit_text(
                    f"💣 <b>Мины</b>\n\n"
                    f"💰 Ставка: ${bet_amount:.2f}\n"
                    f"💣 Количество мин: {mines_count}\n"
                    f"💎 Открыто клеток: {clicks_count}\n"
                    f"🎯 Текущий коэффициент: x{current_coeff}",
                    reply_markup=keyboard
                )

        await callback.answer()
    except Exception as e:
        await callback.answer(f"Ошибка: {str(e)}")

@router.callback_query(F.data.startswith("tower_"))
async def tower_callback_handler(callback: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        tower_mines = data.get('bombs_count', 1) # Используем bombs_count из данных состояния
        opened_levels = data.get('opened_levels', [])
        current_level = data.get('current_level', 0)
        bet_amount = data.get('bet_amount', 0)

        if callback.data == "tower_cash_out":
            # Забираем выигрыш
            coeffs = TOWER_COEFFICIENTS[tower_mines]
            current_coeff = coeffs[current_level - 1] if current_level > 0 and current_level - 1 < len(coeffs) else 1
            win_amount = bet_amount * current_coeff

            update_balance(callback.from_user.id, win_amount)
            update_game_stats(callback.from_user.id, "Башня", win_amount)

            await callback.message.edit_text(
                f"💰 <b>Выигрыш забран!</b>\n\n"
                f"🏗 Башня: {tower_mines} бомб\n"
                f"📈 Пройдено уровней: {current_level}\n"
                f"💰 Выигрыш: ${win_amount:.2f} (x{current_coeff})\n"
                f"💳 Ваш баланс: ${get_balance(callback.from_user.id):.2f}",
                reply_markup=None
            )

            # Возвращаем клавиатуру и переходим к играм в боте
            await state.set_state(GameState.bot_games)
            await callback.message.answer(
                "🤖 <b>Игры в боте:</b>\n\nВыберите игру:",
                reply_markup=get_bot_games_keyboard()
            )
            return

        elif callback.data == "tower_exit":
            await callback.message.edit_text(
                f"❌ <b>Игра завершена</b>\n\n"
                f"💸 Проигрыш: ${bet_amount:.2f}",
                reply_markup=None
            )

            # Возвращаем клавиатуру и переходим к играм в боте
            await state.set_state(GameState.bot_games)
            await callback.message.answer(
                "🤖 <b>Игры в боте:</b>\n\nВыберите игру:",
                reply_markup=get_bot_games_keyboard()
            )
            return

        # Обработка клика по клетке башни
        parts = callback.data.split("_")
        if len(parts) >= 3:
            level = int(parts[1])
            cell = int(parts[2])

            if level != current_level:
                await callback.answer("Можно кликать только на текущий уровень!")
                return

            # Генерируем бомбы для текущего уровня
            bomb_positions = random.sample(range(5), tower_mines)

            # Подкрут казино: на уровнях 3+ увеличиваем шанс попадания на бомбу
            is_bomb = cell in bomb_positions
            if level >= 2 and not is_bomb and random.random() < (0.15 * level):  # Прогрессивный шанс "создания" бомбы
                is_bomb = True

            # На уровнях 4-6 (индексы 3-5) НЕ перемещаем мины - убираем защиту игрока

            if is_bomb:
                # Попали на бомбу - игра окончена
                update_game_stats(callback.from_user.id, "Башня", 0)

                play_again_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="🎮 Играть снова", callback_data="play_tower_again")],
                        [InlineKeyboardButton(text="🎰 Главное меню", callback_data="main_menu")]
                    ]
                )

                await callback.message.edit_text(
                    f"💥 <b>ВЗРЫВ!</b>\n\n"
                    f"💣 Вы попали на бомбу на уровне {level + 1}!\n"
                    f"💸 Проигрыш: ${bet_amount:.2f}",
                    reply_markup=play_again_keyboard
                )
            else:
                # Прошли уровень успешно
                opened_levels.append((level, cell))
                current_level += 1

                await state.update_data(opened_levels=opened_levels, current_level=current_level)

                if current_level >= 6:
                    # Прошли всю башню
                    coeffs = TOWER_COEFFICIENTS[tower_mines]
                    final_coeff = coeffs[-1]
                    win_amount = bet_amount * final_coeff

                    update_balance(callback.from_user.id, win_amount)
                    update_game_stats(callback.from_user.id, "Башня", win_amount)

                    play_again_keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="🎮 Играть снова", callback_data="play_tower_again")],
                            [InlineKeyboardButton(text="🎰 Главное меню", callback_data="main_menu")]
                        ]
                    )

                    await callback.message.edit_text(
                        f"🎉 <b>ПОБЕДА!</b>\n\n"
                        f"🏗 Вы прошли всю башню!\n"
                        f"💰 Выигрыш: ${win_amount:.2f} (x{final_coeff})\n"
                        f"💳 Ваш баланс: ${get_balance(callback.from_user.id):.2f}",
                        reply_markup=play_again_keyboard
                    )
                else:
                    # Продолжаем игру
                    keyboard = create_tower_inline_keyboard(tower_mines, opened_levels, current_level)

                    coeffs = TOWER_COEFFICIENTS[tower_mines]
                    current_coeff = coeffs[current_level - 1] if current_level - 1 < len(coeffs) else coeffs[-1]

                    await callback.message.edit_text(
                        f"🏗 <b>Башня</b>\n\n"
                        f"💰 Ставка: ${bet_amount:.2f}\n"
                        f"💣 Бомб на уровне: {tower_mines}\n"
                        f"📈 Текущий уровень: {current_level + 1}\n"
                        f"🎯 Текущий коэффициент: x{current_coeff}\n\n"
                        f"✅ Уровень {current_level} пройден!\n"
                        f"Выберите сейф на уровне {current_level + 1}:",
                        reply_markup=keyboard
                    )

        await callback.answer()
    except Exception as e:
        await callback.answer(f"Ошибка: {str(e)}")

@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
        await state.set_state(GameState.main_menu)

        has_bets = callback.from_user.id in user_active_bets and user_active_bets[callback.from_user.id]

        await callback.message.edit_text(
            "🎰 <b>Главное меню</b>",
            reply_markup=None
        )
        await callback.message.answer(
            "🎮 Выберите действие:",
            reply_markup=get_start_keyboard(has_bets)
        )
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {str(e)}")

@router.callback_query(F.data == "play_mines_again")
async def play_mines_again_callback(callback: CallbackQuery, state: FSMContext):
    balance = get_balance(callback.from_user.id)
    if balance < 0.2:
        await callback.answer("❌ Недостаточно средств для игры! Минимум $0.20", show_alert=True)
        return

    await callback.answer()
    await state.set_state(GameState.waiting_bet)
    await state.update_data(game_type='mines')

    quick_keyboard = get_bet_amounts_keyboard(callback.from_user.id)

    await callback.message.edit_text(
        f"💣 <b>Мины</b>\n\n"
        f"💰 Ваш баланс: ${balance:.2f}\n"
        f"📝 Введите сумму ставки (от $0.20 до $500.00):",
        reply_markup=None
    )

    await callback.message.answer(
        "Введите сумму ставки:",
        reply_markup=get_bet_input_keyboard()
    )

    if quick_keyboard.inline_keyboard:
        await callback.message.answer("⚡ <b>Быстрые ставки:</b>", reply_markup=quick_keyboard)

@router.callback_query(F.data == "play_tower_again")
async def play_tower_again_callback(callback: CallbackQuery, state: FSMContext):
    balance = get_balance(callback.from_user.id)
    if balance < 0.2:
        await callback.answer("❌ Недостаточно средств для игры! Минимум $0.20", show_alert=True)
        return

    await callback.answer()
    await state.set_state(GameState.waiting_bet)
    await state.update_data(game_type='tower')

    quick_keyboard = get_bet_amounts_keyboard(callback.from_user.id)

    await callback.message.edit_text(
        f"🏗 <b>Башня</b>\n\n"
        f"💰 Ваш баланс: ${balance:.2f}\n"
        f"📝 Введите сумму ставки (от $0.20 до $500.00):",
        reply_markup=None
    )

    await callback.message.answer(
        "Введите сумму ставки:",
        reply_markup=get_bet_input_keyboard()
    )

    if quick_keyboard.inline_keyboard:
        await callback.message.answer("⚡ <b>Быстрые ставки:</b>", reply_markup=quick_keyboard)

@router.callback_query(F.data.startswith("twist_"))
async def twist_callback_handler(callback: CallbackQuery, state: FSMContext):
    # Перенаправляем обработку в games.py
    from games import twist_callback_handler as games_twist_handler
    return await games_twist_handler(callback, state)

@router.callback_query(F.data == "play_twist_again")
async def play_twist_again_callback(callback: CallbackQuery, state: FSMContext):
    balance = get_balance(callback.from_user.id)
    if balance < 0.2:
        await callback.answer("❌ Недостаточно средств для игры! Минимум $0.20", show_alert=True)
        return

    await callback.answer()
    await state.set_state(GameState.waiting_bet)
    await state.update_data(game_type='twist')

    quick_keyboard = get_bet_amounts_keyboard(callback.from_user.id)

    await callback.message.edit_text(
        f"🌪 <b>Твист</b>\n\n"
        f"💰 Ваш баланс: ${balance:.2f}\n"
        f"📝 Введите сумму ставки (от $0.20 до $500.00):",
        reply_markup=None
    )

    await callback.message.answer(
        "Введите сумму ставки:",
        reply_markup=get_bet_input_keyboard()
    )

    if quick_keyboard.inline_keyboard:
        await callback.message.answer("⚡ <b>Быстрые ставки:</b>", reply_markup=quick_keyboard)

@router.callback_query(F.data.startswith("leaderboard_"))
async def leaderboard_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    if callback.data == "leaderboard_balance":
        # Топ по балансу
        leaderboard = get_leaderboard_by_balance(10)
        text = "💰 <b>Топ игроков по балансу</b>\n\n"

        if not leaderboard:
            text += "❌ Пока нет данных"
        else:
            for i, (user_id, balance) in enumerate(leaderboard, 1):
                try:
                    user_info = await bot.get_chat(user_id)
                    username = f"@{user_info.username}" if user_info.username else user_info.first_name
                except:
                    username = f"ID: {user_id}"

                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                text += f"{medal} {username}: ${balance:.2f}\n"

    elif callback.data.startswith("leaderboard_winnings_"):
        # Топ по выигрышам
        period = callback.data.split("_")[2]
        period_names = {
            'day': 'за день',
            'week': 'за неделю',
            'month': 'за месяц',
            'all': 'за все время'
        }

        leaderboard = get_leaderboard_by_winnings(period, 10)
        text = f"🏆 <b>Топ игроков по выигрышам {period_names.get(period, '')}</b>\n\n"

        if not leaderboard:
            text += "❌ Пока нет данных"
        else:
            for i, (user_id, total_winnings) in enumerate(leaderboard, 1):
                try:
                    user_info = await bot.get_chat(user_id)
                    username = f"@{user_info.username}" if user_info.username else user_info.first_name
                except:
                    username = f"ID: {user_id}"

                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                text += f"{medal} {username}: ${total_winnings:.2f}\n"

    await callback.message.edit_text(text, reply_markup=get_leaderboard_keyboard())

@router.message(F.text == "⬅️ Назад")
async def back_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    data = await state.get_data()

    # Главное меню
    if current_state == GameState.play_menu:
        await state.set_state(GameState.main_menu)
        has_bets = message.from_user.id in user_active_bets and user_active_bets[message.from_user.id]
        await message.answer("🎰 Главное меню", reply_markup=get_start_keyboard(has_bets))

    elif current_state == GameState.profile:
        await state.set_state(GameState.main_menu)
        has_bets = message.from_user.id in user_active_bets and user_active_bets[message.from_user.id]
        await message.answer("🎰 Главное меню", reply_markup=get_start_keyboard(has_bets))

    # Меню игр
    elif current_state in [GameState.bot_games, GameState.channel_games]:
        await state.set_state(GameState.play_menu)
        await message.answer("🎮 Выберите режим игры:", reply_markup=get_play_menu_keyboard())

    # Настройка игр в боте
    elif current_state in [GameState.mines_setup, GameState.tower_setup]:
        await state.set_state(GameState.bot_games)
        await message.answer("🤖 Игры в боте:", reply_markup=get_bot_games_keyboard())

    # Активные игры в боте - возврат к выбору игры
    elif current_state in [GameState.mines_playing, GameState.tower_playing]:
        # Завершаем активную игру и возвращаемся к выбору игр в боте
        await state.set_state(GameState.bot_games)
        await message.answer(
            "❌ <b>Игра прервана</b>\n\n"
            "Вы вышли из игры. Выберите другую игру:",
            reply_markup=get_bot_games_keyboard()
        )

    # Ввод ставки - возврат к соответствующему меню
    elif current_state == GameState.waiting_bet:
        game_type = data.get('game_type')
        if game_type in ['mines', 'tower', 'combination', 'twist']:
            await state.set_state(GameState.bot_games)
            await message.answer("🤖 Игры в боте:", reply_markup=get_bot_games_keyboard())
        else:
            await state.set_state(GameState.channel_games)
            await message.answer("💬 Игры в канале:", reply_markup=get_channel_games_keyboard())

    # Канальные игры - возврат к ожиданию ставки
    elif current_state in [GameState.channel_bowling, GameState.channel_basketball,
                          GameState.channel_dice_duel, GameState.channel_dice_higher,
                          GameState.channel_dice_even, GameState.channel_triada,
                          GameState.channel_darts]:
        game_type = data.get('game_type')
        await state.set_state(GameState.waiting_bet)
        balance = get_balance(message.from_user.id)

        game_names = {
            'bowling': '🎳 Боулинг',
            'basketball': '🏀 Баскетбол',
            'dice_duel': '🎲 Кубы (дуэль)',
            'dice_higher': '🎲 Больше/меньше',
            'dice_even': '🎲 Чет/нечет',
            'triada': '🎲 Триада',
            'darts': '🎯 Дартс'
        }

        await message.answer(
            f"{game_names.get(game_type, 'Игра')}\n\n"
            f"💰 Ваш баланс: ${balance:.2f}\n"
            f"📝 Введите сумму ставки (от $0.20 до $500.00):",
            reply_markup=get_bet_input_keyboard()
        )

    # Комбинация - возврат к ожиданию ставки
    elif current_state == GameState.combination_game:
        await state.set_state(GameState.waiting_bet)
        balance = get_balance(message.from_user.id)
        await message.answer(
            f"🎯 Комбинация\n\n"
            f"💰 Ваш баланс: ${balance:.2f}\n"
            f"📝 Введите сумму ставки (от $0.20 до $500.00):",
            reply_markup=get_bet_input_keyboard()
        )

    # Пополнение/вывод - возврат в кошелек
    elif current_state in [GameState.crypto_deposit, GameState.crypto_withdraw]:
        balance = get_balance(message.from_user.id)

        wallet_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="💰 Пополнить"), KeyboardButton(text="💸 Вывести")],
                [KeyboardButton(text="⬅️ Назад")]
            ],
            resize_keyboard=True,
            one_time_keyboard=False
        )

        await message.answer(
            f"💳 <b>Кошелек</b>\n\n"
            f"💰 Ваш баланс: <b>${balance:.2f}</b>\n\n"
            f"💡 Выберите действие:",
            reply_markup=wallet_keyboard
        )
        return

    elif current_state in [GameState.admin_add_money, GameState.admin_delete_user, GameState.admin_check_balance, GameState.leaderboard]:
        await state.set_state(GameState.profile)
        balance = get_balance(message.from_user.id)
        username = message.from_user.username or "Без ника"
        first_name = message.from_user.first_name or "Игрок"

        if message.from_user.id == 1597157163:
            profile_keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="🏆 Топ игроков"), KeyboardButton(text="📊 Статистика")],
                    [KeyboardButton(text="👥 Рефералы"), KeyboardButton(text="📜 История")],
                    [KeyboardButton(text="💸 Кэш-бек"), KeyboardButton(text="💰 +$1")],
                    [KeyboardButton(text="💰 Начислить по ID"), KeyboardButton(text="👁 Баланс по ID")],
                    [KeyboardButton(text="🗑 Удалить пользователя"), KeyboardButton(text="⬅️ Назад")]
                ],
                resize_keyboard=True,
                one_time_keyboard=False
            )
        else:
            profile_keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="🏆 Топ игроков"), KeyboardButton(text="📊 Статистика")],
                    [KeyboardButton(text="👥 Рефералы"), KeyboardButton(text="📜 История")],
                    [KeyboardButton(text="💸 Кэш-бек"), KeyboardButton(text="⬅️ Назад")]
                ],
                resize_keyboard=True,
                one_time_keyboard=False
            )

        stats = get_user_stats(message.from_user.id)
        if stats:
            favorite_game = f"{stats['favorite_game']} [{stats['favorite_game_count']}]"
            total_games = stats['total_games']
            biggest_win = stats['biggest_win']
            registration_date = stats['registration_date'][:10] if stats['registration_date'] else "20.10.2024"
        else:
            favorite_game = "Триада [74]"
            total_games = 206
            biggest_win = 9
            registration_date = "20.10.2024"

        await message.answer(
            f"👤 <b>Профиль</b>\n\n"
            f"🆔 ID: {message.from_user.id}\n"
            f"👤 Имя: {first_name}\n"
            f"📱 Ник: @{username}\n"
            f"💰 Баланс: <b>${balance:.2f}</b>\n\n"
            f"📊 Статистика\n"
            f"┣ Любимая игра: {favorite_game}\n"
            f"┣ Сыгранные игры: {total_games}\n"
            f"┗ Самый большой выигрыш: ${biggest_win:.2f}\n\n"
            f"📆 Дата регистрации: {registration_date}",
            reply_markup=profile_keyboard
        )

    # Если состояние неизвестно - возврат в главное меню
    else:
        await state.set_state(GameState.main_menu)
        has_bets = message.from_user.id in user_active_bets and user_active_bets[message.from_user.id]
        await message.answer("🎰 Главное меню", reply_markup=get_start_keyboard(has_bets))

async def check_pending_payments():
    """Автоматическая проверка ожидающих платежей и кешбека"""
    while True:
        try:
            conn = sqlite3.connect("casino.db")
            c = conn.cursor()

            # Получаем все ожидающие депозиты
            c.execute("SELECT user_id, amount, invoice_id FROM deposits WHERE status = 'pending'")
            pending_deposits = c.fetchall()
            conn.close()

            for user_id, amount, invoice_id in pending_deposits:
                # Проверяем статус каждого инвойса
                invoice_data = await crypto_bot.get_invoice(invoice_id)

                if invoice_data and invoice_data.get('status') == 'paid':
                    # Платеж подтвержден - зачисляем средства
                    update_balance(user_id, amount)
                    update_deposit_status(invoice_id, 'completed')

                    # Отправляем уведомление пользователю
                    try:
                        await bot.send_message(
                            user_id,
                            f"🎉 <b>Пополнение подтверждено!</b>\n\n"
                            f"💰 Зачислено: ${amount:.2f}\n"
                            f"💳 Текущий баланс: ${get_balance(user_id):.2f}",
                            reply_markup=get_start_keyboard()
                        )
                    except:
                        pass  # Игнорируем ошибки отправки (пользователь заблокировал бота и т.д.)

            # Проверяем и автоматически начисляем кешбек при достижении $5
            conn = sqlite3.connect("casino.db")
            c = conn.cursor()
            c.execute("SELECT user_id, available_cashback FROM cashback WHERE available_cashback >= 5.0")
            cashback_users = c.fetchall()
            conn.close()

            for user_id, available_cashback in cashback_users:
                # Автоматически начисляем кешбек
                cashback_amount = claim_cashback(user_id)
                if cashback_amount > 0:
                    try:
                        await bot.send_message(
                            user_id,
                            f"🎁 <b>Автоматическое начисление кешбека!</b>\n\n"
                            f"💰 Начислено: ${cashback_amount:.2f}\n"
                            f"💳 Ваш баланс: ${get_balance(user_id):.2f}\n\n"
                            f"🎮 Кешбек автоматически начисляется при достижении $5.00"
                        )
                    except:
                        pass

        except Exception as e:
            print(f"Ошибка проверки платежей и кешбека: {e}")

        # Проверяем каждые 5 секунд для быстрого зачисления
        await asyncio.sleep(5)

async def main():
    # Запускаем фоновую задачу проверки платежей
    asyncio.create_task(check_pending_payments())

    # Добавляем обработку сетевых ошибок
    retry_count = 0
    max_retries = 5

    while retry_count < max_retries:
        try:
            print(f"🚀 Запуск бота (попытка {retry_count + 1})")
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                timeout=20,
                relax=0.1,
                fast=True
            )
            # Если дошли сюда, значит бот работал и остановился штатно
            print("✅ Бот остановлен штатно")
            break

        except Exception as e:
            retry_count += 1
            print(f"❌ Ошибка бота (попытка {retry_count}/{max_retries}): {e}")

            if retry_count < max_retries:
                wait_time = min(5 * retry_count, 30)  # Экспоненциальная задержка
                print(f"⏳ Перезапуск через {wait_time} секунд...")
                await asyncio.sleep(wait_time)
            else:
                print("💥 Превышено максимальное количество попыток перезапуска")
                break

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 Бот остановлен пользователем")
    except Exception as e:
        print(f"💥 Критическая ошибка: {e}")