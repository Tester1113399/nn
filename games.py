import asyncio
import random
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.markdown import hbold
from aiogram import Router

# Инициализация роутера
router = Router()

from db import (
    update_balance, update_game_stats, add_referral_bonus, add_bet_to_history, get_balance, add_loss_to_cashback, get_user_stats
)

# Класс для состояний игры
class GameState(StatesGroup):
    main_menu = State()
    bet_amount = State()
    twist_game = State()

# Глобальные переменные
CHANNEL_ID = "-1002816845887"
user_active_bets = {}
game_queue = []
is_game_running = False

# Коэффициенты для мин (расширенные до 24 мин)
MINES_COEFFICIENTS = {
    2: [1.02, 1.11, 1.22, 1.34, 1.48, 1.65, 1.84, 2.07, 2.35, 2.69, 3.1, 3.62, 4.27, 5.13, 6.27, 7.83, 10.07, 13.43, 18.8, 27.56, 42.21, 68.0, 117.5, 226.9],
    3: [1.07, 1.22, 1.4, 1.63, 1.9, 2.23, 2.65, 3.18, 3.86, 4.75, 5.94, 7.56, 9.83, 13.1, 18.02, 25.74, 38.61, 61.77, 108.0, 207.4, 434.03, 1014.3, 2710.8, 8547.0],
    4: [1.12, 1.34, 1.62, 1.97, 2.43, 3.02, 3.82, 4.89, 6.35, 8.37, 11.21, 15.29, 21.29, 30.27, 43.97, 65.52, 100.4, 159.84, 264.4, 456.7, 834.9, 1659.8, 3652.6, 9130.2],
    5: [1.18, 1.48, 1.87, 2.39, 3.09, 4.04, 5.37, 7.27, 10.02, 14.05, 20.06, 29.26, 43.89, 67.58, 107.3, 175.4, 295.7, 514.4, 929.6, 1764.0, 3528.0, 7409.9, 16923.0, 42307.5],
    6: [1.24, 1.64, 2.17, 2.93, 4.01, 5.56, 7.85, 11.24, 16.49, 24.74, 37.86, 59.28, 94.85, 155.4, 261.9, 454.4, 815.9, 1509.4, 2887.9, 5775.8, 12103.7, 26628.1, 63507.0, 170685.3],
    7: [1.31, 1.81, 2.54, 3.62, 5.25, 7.72, 11.61, 17.94, 28.37, 46.3, 77.17, 131.4, 229.9, 413.8, 765.6, 1454.3, 2827.2, 5654.4, 11742.5, 25232.7, 56773.5, 134257.9, 344669.5, 980476.9],
    8: [1.39, 2.0, 2.97, 4.47, 6.88, 10.78, 17.24, 28.26, 47.4, 81.33, 142.3, 255.6, 471.2, 892.7, 1742.4, 3484.8, 7162.9, 15335.4, 34504.6, 80844.1, 196840.7, 508985.8, 1399718.0, 4199154.0],
    9: [1.48, 2.22, 3.49, 5.58, 9.09, 15.15, 25.95, 45.4, 81.73, 149.5, 281.1, 542.1, 1084.2, 2223.8, 4725.4, 10350.8, 23289.3, 54008.5, 129620.4, 324051.0, 842533.0, 2317841.3, 6953524.0, 22778773.0],
    10: [1.58, 2.47, 4.12, 7.07, 12.36, 22.25, 40.86, 76.6, 147.9, 294.4, 596.9, 1253.3, 2696.4, 5978.6, 13759.0, 32622.6, 80056.5, 202641.3, 533703.5, 1468245.6, 4172130.2, 12516390.6, 39427469.7, 131424899.0],
    11: [1.69, 2.76, 4.86, 9.01, 17.02, 33.29, 66.58, 136.2, 287.0, 626.5, 1409.6, 3276.1, 7690.2, 18616.0, 46540.0, 119804.0, 318411.0, 875131.0, 2450366.0, 7126061.0, 21378183.0, 67434322.0, 223447740.0, 781667090.0],
    12: [1.81, 3.09, 5.75, 11.5, 23.86, 51.45, 113.2, 258.2, 600.8, 1442.0, 3564.9, 9053.8, 23639.9, 63573.0, 176090.0, 501686.0, 1471010.0, 4413030.0, 13776843.0, 44409499.0, 148031663.0, 518610822.0, 1888772008.0, 7264147693.0],
    13: [1.94, 3.48, 6.83, 14.77, 33.48, 78.78, 190.3, 472.5, 1201.3, 3154.4, 8411.8, 23138.0, 65186.4, 189042.2, 567126.6, 1757892.0, 5537654.4, 17984630.0, 60548220.0, 212719768.0, 771998228.0, 2893324354.0, 11397165380.0, 46563778061.0],
    14: [2.08, 3.92, 8.17, 18.95, 46.67, 119.8, 315.4, 861.8, 2413.1, 6896.0, 20171.5, 60514.5, 186593.0, 592698.6, 1927077.0, 6423590.0, 22082565.0, 77288776.0, 278740794.0, 1037776285.0, 3946048280.0, 15627393120.0, 64780804667.0, 280061448727.0],
    15: [2.24, 4.42, 9.8, 23.04, 64.59, 188.3, 566.8, 1747.5, 5511.9, 17859.7, 59532.0, 202609.0, 706130.0, 2542068.0, 9323850.0, 34995936.0, 134596103.0, 525846402.0, 2103385608.0, 8617727532.0, 36474867387.0, 158952290883.0, 711885208973.0, 3291951441235.0],
    16: [2.42, 4.99, 11.84, 29.6, 77.69, 209.8, 580.5, 1654.2, 4861.1, 14583.2, 44844.7, 140640.9, 451051.0, 1486418.4, 5049663.0, 17673821.0, 63465123.6, 233407453.2, 875277199.0, 3326540256.0, 12885662997.6, 51542651990.4, 212424992959.6, 896344969170.3],
    17: [2.62, 5.63, 14.32, 38.19, 107.7, 314.6, 954.7, 2954.7, 9467.1, 31223.7, 106359.5, 370259.3, 1334133.5, 4891822.9, 18567336.0, 71973162.5, 284892650.0, 1139570600.0, 4618574400.0, 18918554440.0, 78827729840.0, 334398987600.0, 1449137305420.0, 6421041263848.0],
    18: [2.84, 6.35, 17.43, 49.8, 149.4, 463.3, 1480.7, 4923.6, 16798.2, 58693.1, 211730.0, 784112.5, 2940421.9, 11387078.1, 44634062.5, 179861250.0, 742970125.0, 3127134525.0, 13409075256.3, 58896781125.0, 262935514062.5, 1197610313281.3, 5586480956093.8, 26378438408437.5],
    19: [3.08, 7.18, 21.34, 65.29, 208.9, 697.0, 2439.5, 8738.2, 32017.5, 119315.6, 460606.0, 1842424.0, 7601996.0, 32208583.2, 139465642.4, 614828906.5, 2767530079.3, 12653888361.5, 58782277618.0, 277721300684.0, 1333422432832.0, 6555441700536.0, 32777208502680.0, 166460602763816.0],
    20: [3.35, 8.17, 26.41, 86.36, 296.2, 1066.3, 3965.1, 15244.9, 60979.6, 249480.7, 1047001.4, 4516606.0, 20024664.3, 91111896.4, 421848779.5, 1967428637.8, 9245801509.7, 44459847246.7, 217253011829.0, 1077266259145.0, 5420831295725.0, 27652640243475.0, 142817808625987.5, 743332564935593.8],
    21: [3.64, 9.32, 32.92, 115.2, 424.4, 1616.6, 6414.4, 26393.5, 111656.9, 489690.3, 2202406.4, 10112881.9, 47529451.0, 230145805.0, 1150729025.0, 5848076328.1, 30329596703.1, 159630506796.2, 855563386578.3, 4659798426180.6, 25828892043893.1, 145162276246440.6, 823874986983229.4, 4743171354192169.0],
    22: [3.96, 10.7, 41.28, 154.8, 615.2, 2513.8, 10555.8, 45390.0, 202755.0, 929472.3, 4415945.1, 21582718.0, 109913590.0, 574543068.0, 3072730231.0, 16889116271.3, 94700410000.0, 540001771428.6, 3132010285714.3, 18520060000000.0, 111120360000000.0, 678323769230769.2, 4186546153846153.8, 26166032307692307.7],
    23: [4.32, 12.35, 52.14, 210.6, 896.7, 3946.7, 17823.0, 82106.3, 388497.5, 1864034.0, 9321170.0, 47988928.0, 254415572.7, 1398485900.0, 7891683055.6, 45809618888.9, 271758113333.3, 1629348800000.0, 9977732571428.6, 61835203428571.4, 388345021714285.7, 2466208138857142.9, 15825052850285714.3, 102862843726857142.9],
    24: [4.72, 14.32, 66.82, 288.5, 1325.6, 6286.9, 30436.9, 151184.3, 766871.5, 3971230.8, 21042162.1, 113158734.0, 625322537.0, 3563557357.1, 20648616000.0, 123891696000.0, 765571360000.0, 4895457142857.1, 31771542857142.9, 210143785714285.7, 1400958571428571.4, 9539729142857142.9, 65812200000000000.0, 460885400000000000.0]
}

# Коэффициенты для башни
TOWER_COEFFICIENTS = {
    1: [1.17, 1.47, 1.84, 2.29, 2.87, 3.59],
    2: [1.57, 2.61, 4.35, 7.25, 12.09, 20.15],
    3: [2.35, 5.87, 14.69, 36.72, 91.80, 229.49],
    4: [4.70, 23.50, 117.50, 587.50, 2937.50, 14687.50]
}

# Функции для создания клавиатур
def create_twist_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔄 Спин", callback_data="twist_spin"))
    builder.row(InlineKeyboardButton(text="💸 Забрать банк", callback_data="twist_cashout"))
    builder.row(InlineKeyboardButton(text="❌ Выйти", callback_data="twist_exit"))
    return builder.as_markup()

def create_main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎰 Слоты", callback_data="play_slots"))
    builder.row(InlineKeyboardButton(text="🎲 Кубы", callback_data="play_dice_menu"))
    builder.row(InlineKeyboardButton(text="🎳 Боулинг", callback_data="play_bowling"))
    builder.row(InlineKeyboardButton(text="🎯 Дартс", callback_data="play_darts"))
    builder.row(InlineKeyboardButton(text="🏀 Баскетбол", callback_data="play_basketball"))
    builder.row(InlineKeyboardButton(text="💰 Пополнить", callback_data="deposit"))
    builder.row(InlineKeyboardButton(text="💳 Баланс", callback_data="show_balance"))
    builder.row(InlineKeyboardButton(text="❓ Правила", callback_data="rules"))
    builder.row(InlineKeyboardButton(text="🤝 Партнерка", callback_data="referral"))
    builder.row(InlineKeyboardButton(text="🎮 Твист", callback_data="play_twist"))
    return builder.as_markup()

# Обработчик команды /start
@router.message(CommandStart())
async def start_handler(message: Message):
    user_id = message.from_user.id
    # Проверяем, есть ли пользователь в базе данных, если нет - регистрируем
    # (предполагается, что эта логика есть в db.py или в другом месте)
    # register_user_if_not_exists(user_id) # Пример

    await message.answer(
        f"👋 <b>Привет, {message.from_user.first_name}!</b>\n\n"
        f"Добро пожаловать в наше казино!\n"
        f"Здесь вы можете испытать удачу в различных играх.\n\n"
        f"✨ Используйте меню ниже для навигации.",
        reply_markup=create_main_menu_keyboard()
    )
    await message.bot.send_message(CHANNEL_ID, f"👤 Новый игрок: {message.from_user.first_name} (ID: {user_id})")
    await GameState.main_menu.set()

# Обработчик для игры "Твист"
@router.callback_query(lambda c: c.data == "play_twist")
async def play_twist_handler(callback: CallbackQuery, state: FSMContext):
    await state.set_state(GameState.bet_amount)
    await callback.message.edit_text(
        "🌪 <b>Твист</b>\n\n"
        "Цель игры - собрать комбинации символов.\n"
        "Каждый спин стоит 10% от вашей первоначальной ставки.\n"
        "Вы можете забрать накопленный банк в любой момент или попытаться собрать комбинации.\n\n"
        "💰 <b>Введите вашу ставку:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu")]]))
    await callback.answer()

@router.message(GameState.bet_amount)
async def process_twist_bet(message: Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        bet_amount = float(message.text)
        current_balance = get_balance(user_id)

        if bet_amount <= 0:
            await message.answer("❌ Ставка должна быть больше нуля.")
            return
        if bet_amount > current_balance:
            await message.answer(f"❌ Недостаточно средств. Ваш баланс: ${current_balance:.2f}")
            return

        # Инициализируем состояние игры
        twist_state = {
            'bet_amount': bet_amount,
            'game_bank': 0,
            'spins_made': 0,
            'anchor_count': 0,
            'star_count': 0,
            'shell_count': 0,
            'last_symbol': None,
            'result_text': ""
        }

        await state.update_data(twist_state=twist_state)
        await state.set_state(GameState.twist_game)

        await message.answer(
            f"🌪 <b>Твист</b>\n\n"
            f"💰 Ваша ставка: ${bet_amount:.2f}\n"
            f"🏦 Банк игры: ${twist_state['game_bank']:.2f}\n\n"
            f"📊 <b>Прогресс:</b>\n"
            f"🐚: {twist_state['shell_count']}/7\n"
            f"⭐️: {twist_state['star_count']}/5\n"
            f"⚓️: {twist_state['anchor_count']}/3\n\n"
            f"🔄 <b>Нажмите 'Спин', чтобы начать!</b>\n"
            f"💰 Спин стоит: ${bet_amount * 0.1:.2f}",
            reply_markup=create_twist_keyboard()
        )

    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректное число для ставки.")
    except Exception as e:
        print(f"Ошибка при обработке ставки для Твиста: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")

@router.callback_query(lambda c: c.data == "play_twist_again")
async def play_twist_again_handler(callback: CallbackQuery, state: FSMContext):
    await state.set_state(GameState.bet_amount)
    await callback.message.edit_text(
        "🌪 <b>Твист</b>\n\n"
        "Цель игры - собрать комбинации символов.\n"
        "Каждый спин стоит 10% от вашей первоначальной ставки.\n"
        "Вы можете забрать накопленный банк в любой момент или попытаться собрать комбинации.\n\n"
        "💰 <b>Введите вашу ставку:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu")]]))
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("twist_"))
async def twist_callback_handler(callback: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        twist_state = data.get('twist_state', {})

        if callback.data == "twist_spin":
            bet_amount = twist_state.get('bet_amount', 0)
            current_balance = get_balance(callback.from_user.id)

            # Проверяем баланс перед спином
            if current_balance < bet_amount:
                await callback.answer("❌ Недостаточно средств для продолжения игры!", show_alert=True)
                return

            # Списываем полную ставку с баланса
            update_balance(callback.from_user.id, -bet_amount)
            twist_state['spins_made'] = twist_state.get('spins_made', 0) + 1

            # Проверяем, завершен ли какой-либо ряд
            anchors = twist_state.get('anchor_count', 0)
            stars = twist_state.get('star_count', 0)
            shells = twist_state.get('shell_count', 0)

            completed_rows = []
            if anchors >= 3:
                completed_rows.append('anchor')
            if stars >= 5:
                completed_rows.append('star')
            if shells >= 7:
                completed_rows.append('shell')

            # Генерируем символы с адаптивными весами
            if completed_rows:
                # Если есть завершенные ряды, смайлик может выпасть
                symbols = ['⚓️', '⭐️', '🐚', '💀', '💩', '💸']
                weights = [10, 10, 10, 40, 50, 15]  # Увеличиваем шанс смайлика
            else:
                # Если нет завершенных рядов, смайлик НЕ может выпасть
                symbols = ['⚓️', '⭐️', '🐚', '💀', '💩']

                # Считаем общее количество собранных символов
                total_symbols = anchors + stars + shells

                if total_symbols >= 3:
                    weights = [8, 8, 8, 50, 60]  # После 3 символов - больше негатива
                elif total_symbols >= 1:
                    weights = [15, 15, 15, 35, 45]  # После 1 символа - умеренный подкрут
                else:
                    weights = [25, 25, 25, 25, 30]  # Начальные веса

            symbol = random.choices(symbols, weights=weights)[0]

            result = ""
            bank_change = 0

            # Обработка символов
            if symbol == '⚓️':
                twist_state['anchor_count'] = twist_state.get('anchor_count', 0) + 1
                # Коэффициент зависит от количества якорей
                anchor_coeffs = [1.6, 5, 10.5]  # 1, 2, 3 якоря
                current_anchors = twist_state['anchor_count']

                # Проверяем, нужен ли денежный смайлик для множителя
                if current_anchors <= len(anchor_coeffs):
                    if current_anchors < 3:
                        coeff = anchor_coeffs[current_anchors - 1]
                        bank_add = bet_amount * coeff
                        twist_state['game_bank'] = twist_state.get('game_bank', 0) + bank_add
                        bank_change = bank_add
                        result = f"⚓️ Якорь! x{coeff} = +${bank_add:.2f} в банк ({current_anchors}/3)"
                    else:
                        result = f"⚓️ Якорь! 3 якоря собраны! Нужен 💸 для получения x10.5"
                else:
                    result = f"⚓️ Якорь! ({current_anchors}/3)"

            elif symbol == '⭐️':
                twist_state['star_count'] = twist_state.get('star_count', 0) + 1
                # Коэффициенты для звезд
                star_coeffs = [2.5, 8, 16.5, 28.5, 45]  # 1, 2, 3, 4, 5 звезд
                current_stars = twist_state['star_count']

                if current_stars <= len(star_coeffs):
                    if current_stars < 5:
                        coeff = star_coeffs[current_stars - 1]
                        bank_add = bet_amount * coeff
                        twist_state['game_bank'] = twist_state.get('game_bank', 0) + bank_add
                        bank_change = bank_add
                        result = f"⭐️ Звезда! x{coeff} = +${bank_add:.2f} в банк ({current_stars}/5)"
                    else:
                        result = f"⭐️ Звезда! 5 звезд собраны! Нужен 💸 для получения x45"
                else:
                    result = f"⭐️ Звезда! ({current_stars}/5)"

            elif symbol == '🐚':
                twist_state['shell_count'] = twist_state.get('shell_count', 0) + 1
                # Коэффициенты для ракушек
                shell_coeffs = [4, 13, 28.5, 53, 88, 137.5, 205]  # 1, 2, 3, 4, 5, 6, 7 ракушек
                current_shells = twist_state['shell_count']

                if current_shells <= len(shell_coeffs):
                    if current_shells < 7:
                        coeff = shell_coeffs[current_shells - 1]
                        bank_add = bet_amount * coeff
                        twist_state['game_bank'] = twist_state.get('game_bank', 0) + bank_add
                        bank_change = bank_add
                        result = f"🐚 Ракушка! x{coeff} = +${bank_add:.2f} в банк ({current_shells}/7)"
                    else:
                        result = f"🐚 Ракушка! 7 ракушек собраны! Нужен 💸 для получения x205"
                else:
                    result = f"🐚 Ракушка! ({current_shells}/7)"

            elif symbol == '💸':
                # Денежный смайлик - активирует максимальные коэффициенты только для завершенных рядов
                total_multiplier = 1
                bonus_details = []

                # Проверяем каждую секцию
                anchors = twist_state.get('anchor_count', 0)
                if anchors >= 3:
                    total_multiplier *= 10.5
                    bonus_details.append(f"⚓️x3 = x10.5")

                stars = twist_state.get('star_count', 0)
                if stars >= 5:
                    total_multiplier *= 45
                    bonus_details.append(f"⭐️x5 = x45")

                shells = twist_state.get('shell_count', 0)
                if shells >= 7:
                    total_multiplier *= 205
                    bonus_details.append(f"🐚x7 = x205")

                if bonus_details:
                    mega_win = bet_amount * total_multiplier
                    twist_state['game_bank'] = twist_state.get('game_bank', 0) + mega_win
                    bank_change = mega_win
                    result = f"💸 МЕГА ВЫИГРЫШ! {' + '.join(bonus_details)} = x{total_multiplier}! +${mega_win:.2f}"
                else:
                    # Этого не должно происходить, так как смайлик выпадает только при завершенных рядах
                    result = f"💸 Денежный смайлик! Ошибка: нет завершенных рядов"

            elif symbol == '💀':
                # Череп - откидывает назад на один шаг в каждой секции и удаляет соответствующие деньги из банка
                bank_loss = 0

                # Якоря - убираем деньги за последний шаг
                if twist_state.get('anchor_count', 0) > 0:
                    current_anchors = twist_state['anchor_count']
                    twist_state['anchor_count'] -= 1

                    # Если был на уровне с коэффициентом, вычитаем его из банка
                    anchor_coeffs = [1.6, 5, 10.5]
                    if current_anchors <= len(anchor_coeffs):
                        lost_coeff = anchor_coeffs[current_anchors - 1]
                        bank_loss += bet_amount * lost_coeff

                # Звезды - убираем деньги за последний шаг
                if twist_state.get('star_count', 0) > 0:
                    current_stars = twist_state['star_count']
                    twist_state['star_count'] -= 1

                    # Если был на уровне с коэффициентом, вычитаем его из банка
                    star_coeffs = [2.5, 8, 16.5, 28.5, 45]
                    if current_stars <= len(star_coeffs):
                        lost_coeff = star_coeffs[current_stars - 1]
                        bank_loss += bet_amount * lost_coeff

                # Ракушки - убираем деньги за последний шаг
                if twist_state.get('shell_count', 0) > 0:
                    current_shells = twist_state['shell_count']
                    twist_state['shell_count'] -= 1

                    # Если был на уровне с коэффициентом, вычитаем его из банка
                    shell_coeffs = [4, 13, 28.5, 53, 88, 137.5, 205]
                    if current_shells <= len(shell_coeffs):
                        lost_coeff = shell_coeffs[current_shells - 1]
                        bank_loss += bet_amount * lost_coeff

                # Вычитаем потерянные деньги из банка
                twist_state['game_bank'] = max(0, twist_state.get('game_bank', 0) - bank_loss)
                bank_change = -bank_loss

                if bank_loss > 0:
                    result = f"💀 Череп! Все счетчики откинуты на 1 шаг назад. Потеряно ${bank_loss:.2f} из банка!"
                else:
                    result = f"💀 Череп! Все счетчики откинуты на 1 шаг назад"

            elif symbol == '💩':
                # Какашка - ничего не происходит
                result = f"💩 Какашка! Ничего не происходит"

            await state.update_data(twist_state=twist_state)

            # Обновляем сообщение с актуальными данными
            current_balance_after = get_balance(callback.from_user.id)
            game_bank = twist_state.get('game_bank', 0)

            bank_info = ""
            if bank_change > 0:
                bank_info = f"💰 В банк добавлено: ${bank_change:.2f}\n"
            elif bank_change < 0:
                bank_info = f"💸 Из банка потеряно: ${abs(bank_change):.2f}\n"

            keyboard = create_twist_keyboard()

            # Создаем рамку снизу с отображением выпавшего символа
            frame_top = "┌─────────────────────┐"
            frame_middle = f"│    🎰 ВЫПАЛ: {symbol}    │"
            frame_bottom = "└─────────────────────┘"

            symbol_frame = f"```\n{frame_top}\n{frame_middle}\n{frame_bottom}\n```"

            new_text = (
                f"🌪 <b>Твист</b>\n\n"
                f"{result}\n\n"
                f"💳 Ваш баланс: ${current_balance_after:.2f}\n"
                f"🏦 Банк игры: ${game_bank:.2f}\n"
                f"{bank_info}\n"
                f"📊 <b>Текущие коэффициенты:</b>\n"
                f"🐚🐚🐚🐚🐚🐚🐚💸 = x4·x13·x28.5·x53·x88·x137.5·x205\n"
                f"⭐️⭐️⭐️⭐️⭐️💸 = x2.5·x8·x16.5·x28.5·x45\n"
                f"⚓️⚓️⚓️💸 = x1.6·x5·x10.5\n"
                f"💀 Череп: -1 шаг в каждой секции\n"
                f"💩 Какашка: ничего\n\n"
                f"📊 <b>Прогресс секций:</b>\n"
                f"🐚: {twist_state.get('shell_count', 0)}/7\n"
                f"⭐️: {twist_state.get('star_count', 0)}/5\n"
                f"⚓️: {twist_state.get('anchor_count', 0)}/3\n\n"
                f"🔄 Следующий спин: ${bet_amount:.2f}\n\n"
                f"{symbol_frame}"
            )

            try:
                await callback.message.edit_text(new_text, reply_markup=keyboard)
            except Exception as e:
                if "message is not modified" in str(e):
                    # Если сообщение одинаковое, просто отвечаем на callback
                    await callback.answer()
                else:
                    raise e

        elif callback.data == "twist_cashout":
            game_bank = twist_state.get('game_bank', 0)

            if game_bank > 0:
                update_balance(callback.from_user.id, game_bank)
                update_game_stats(callback.from_user.id, "Твист", game_bank)

                await callback.message.edit_text(
                    f"💰 <b>Банк забран!</b>\n\n"
                    f"🏦 Забрано из банка: ${game_bank:.2f}\n"
                    f"💳 Ваш баланс: ${get_balance(callback.from_user.id):.2f}",
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="🎮 Играть снова", callback_data="play_twist_again")],
                            [InlineKeyboardButton(text="🎰 Главное меню", callback_data="main_menu")]
                        ]
                    )
                )
            else:
                bet_amount = twist_state.get('bet_amount', 0)
                update_game_stats(callback.from_user.id, "Твист", 0)

                await callback.message.edit_text(
                    f"❌ <b>Банк пуст!</b>\n\n"
                    f"🏦 В банке нет денег для вывода\n"
                    f"💸 Проигрыш: ${bet_amount:.2f}\n"
                    f"💳 Ваш баланс: ${get_balance(callback.from_user.id):.2f}",
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="🎮 Играть снова", callback_data="play_twist_again")],
                            [InlineKeyboardButton(text="🎰 Главное меню", callback_data="main_menu")]
                        ]
                    )
                )

            await state.set_state(GameState.main_menu)

        elif callback.data == "twist_exit":
            game_bank = twist_state.get('game_bank', 0)
            bet_amount = twist_state.get('bet_amount', 0)

            update_game_stats(callback.from_user.id, "Твист", 0)

            await callback.message.edit_text(
                f"❌ <b>Игра прервана</b>\n\n"
                f"🏦 Банк игры сгорел: ${game_bank:.2f}\n"
                f"💸 Проигрыш: ${bet_amount:.2f}\n"
                f"💳 Ваш баланс: ${get_balance(callback.from_user.id):.2f}",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="🎮 Играть снова", callback_data="play_twist_again")],
                        [InlineKeyboardButton(text="🎰 Главное меню", callback_data="main_menu")]
                    ]
                )
            )
            await state.set_state(GameState.main_menu)

        await callback.answer()

    except Exception as e:
        print(f"Ошибка в твисте: {e}")
        if "message is not modified" not in str(e):
            await callback.answer(f"❌ Ошибка: {str(e)}")
        else:
            await callback.answer()

async def play_bowling_direct(bot: Bot, message, bet_amount: float, choice: str):
    user = message.from_user

    try:
        while True:  # Переигрываем при ничьей
            # Кидаем кегли игрока
            user_bowling = await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎳")
            await asyncio.sleep(4)
            user_pins = user_bowling.dice.value

            # Кидаем кегли бота
            await bot.send_message(CHANNEL_ID, "🤖 Бот кидает...")
            bot_bowling = await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎳")
            await asyncio.sleep(4)
            bot_pins = bot_bowling.dice.value

            # Проверяем на ничью
            if user_pins == bot_pins:
                await bot.send_message(CHANNEL_ID, "🤝 Ничья! Переигрываем...")
                await asyncio.sleep(2)
                continue

            # Определяем результат
            actual_result = "win" if user_pins > bot_pins else "loss"
            win = choice == actual_result
            break

        if win:
            win_amount = bet_amount * 1.8
            update_balance(user.id, win_amount)
            update_game_stats(user.id, "Боулинг", win_amount)

            # Реферальный бонус
            try:
                stats = get_user_stats(user.id)
                if stats and stats.get('referrer_id'):
                    bonus = win_amount * 0.05  # 5%
                    if bonus >= 0.01:  # Минимальный бонус $0.01
                        add_referral_bonus(stats['referrer_id'], bonus)
                        try:
                            await bot.send_message(
                                stats['referrer_id'],
                                f"💰 <b>Реферальный бонус!</b>\n"
                                f"👤 Ваш реферал выиграл в боулинг\n"
                                f"🎁 Ваш бонус: ${bonus:.2f} (5%)"
                            )
                        except:
                            pass
            except Exception as e:
                print(f"Error processing referral bonus: {e}")

            result_text = f"🎉 <b>ПОБЕДА!</b>\n💰 Выигрыш: ${win_amount:.2f}"
        else:
            update_game_stats(user.id, "Боулинг", 0)
            cashback_amount = bet_amount * 0.06
            add_loss_to_cashback(user.id, bet_amount)  # Добавляем в кешбек
            result_text = f"😢 <b>Поражение</b>\n💸 Проигрыш: ${bet_amount:.2f}\n💰 Кешбек +6%: +${cashback_amount:.2f}"

            # Сохраняем результат в базу данных
        bet_id = add_bet_to_history(user.id, 'bowling', bet_amount, choice, "win" if win else "loss", win_amount if win else 0)

        # Инлайн-кнопка для канала
        channel_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Сделать ставку", url=f"https://t.me/{(await bot.get_me()).username}?start=game")
            ]]
        )

        # Отправляем изображение с результатом
        try:
            if win:
                image_path = "attached_assets/win_image.png"  # Победа
            else:
                image_path = "attached_assets/loss_image.png"  # Поражение

            await bot.send_photo(
                CHANNEL_ID,
                photo=FSInputFile(image_path),
                caption=f"🎳 <b>Результат игры</b>\n\n"
                        f"👤 Игрок: {user.first_name}\n"
                        f"🎯 Игрок: {user_pins} кеглей | 🤖 Бот: {bot_pins} кеглей\n"
                        f"🎲 Выбор: {'🏆 Победа' if choice == 'win' else '💀 Поражение'}\n\n"
                        f"{'🎉' if win else '😔'} {result_text}",
                reply_markup=channel_keyboard,
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"Error sending photo: {e}")
            # Fallback to text message
            await bot.send_message(
                CHANNEL_ID,
                f"🎳 <b>Результат игры</b>\n\n"
                f"👤 Игрок: {user.first_name}\n"
                f"🎯 Игрок: {user_pins} кеглей | 🤖 Бот: {bot_pins} кеглей\n"
                f"🎲 Выбор: {'🏆 Победа' if choice == 'win' else '💀 Поражение'}\n\n"
                f"{'🎉' if win else '😔'} {result_text}",
                reply_markup=channel_keyboard,
                parse_mode='HTML'
            )

        # Удаляем ставку из активных
        user_id = user.id
        if user_id in user_active_bets:
            for i, bet in enumerate(user_active_bets[user_id]):
                if (bet['game_type'] == 'bowling' and 
                    bet['bet_amount'] == bet_amount and 
                    bet['choice'] == choice):
                    user_active_bets[user_id].pop(i)
                    break

            if not user_active_bets[user_id]:
                del user_active_bets[user_id]

        # Уведомление в боте с кнопкой главного меню
        bot_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Главное меню", callback_data="main_menu")
            ]]
        )

        if win:
            await bot.send_message(
                user.id,
                f"🎉 <b>Поздравляем с победой!</b>\n\n"
                f"🎳 Игра: Боулинг\n"
                f"💰 Выигрыш: ${win_amount:.2f}\n"
                f"💳 Ваш баланс: ${get_balance(user.id):.2f}",
                reply_markup=bot_keyboard
            )
        else:
            await bot.send_message(
                user.id,
                f"😔 <b>Повезет в другой раз :)</b>\n\n"
                f"🎳 Игра: Боулинг\n"
                f"💸 Проигрыш: ${bet_amount:.2f}\n"
                f"💳 Текущий баланс: ${get_balance(user.id):.2f}",
                reply_markup=bot_keyboard
            )

    except Exception as e:
        print(f"Ошибка в боулинге: {e}")
        await asyncio.sleep(5)  # Увеличиваем задержку
        try:
            # Повторная попытка с другим подходом
            await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎳")
        except Exception as retry_error:
            print(f"Повторная ошибка в боулинге: {retry_error}")
            # Если все еще ошибка, пропускаем игру и возвращаем деньги
            update_balance(user.id, bet_amount)
            await bot.send_message(user.id, 
                f"❌ Техническая ошибка в игре Боулинг\n"
                f"💰 Ставка ${bet_amount:.2f} возвращена на ваш счет")
            return

async def play_dice_duel_direct(bot: Bot, message, bet_amount: float, choice: str):
    user = message.from_user

    try:
        while True:  # Переигрываем при ничьей
            user_dice = await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎲")
            await asyncio.sleep(4)
            user_roll = user_dice.dice.value

            await bot.send_message(CHANNEL_ID, "🤖 Бот кидает...")
            bot_dice = await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎲")
            await asyncio.sleep(4)
            bot_roll = bot_dice.dice.value

            # Проверяем на ничью
            if user_roll == bot_roll:
                await bot.send_message(CHANNEL_ID, "🤝 Ничья! Переигрываем...")
                await asyncio.sleep(2)
                continue

            actual_result = "win" if user_roll > bot_roll else "loss"
            win = choice == actual_result
            break

        if win:
            win_amount = bet_amount * 1.8
            update_balance(user.id, win_amount)
            update_game_stats(user.id, "Кубы (дуэль)", win_amount)

            # Реферальный бонус
            try:
                stats = get_user_stats(user.id)
                if stats and stats.get('referrer_id'):
                    bonus = win_amount * 0.05  # 5%
                    if bonus >= 0.01:  # Минимальный бонус $0.01
                        add_referral_bonus(stats['referrer_id'], bonus)
                        try:
                            await bot.send_message(
                                stats['referrer_id'],
                                f"💰 <b>Реферальный бонус!</b>\n"
                                f"👤 Ваш реферал выиграл в кубы (дуэль)\n"
                                f"🎁 Ваш бонус: ${bonus:.2f} (5%)"
                            )
                        except:
                            pass
            except Exception as e:
                print(f"Error processing referral bonus: {e}")

            result_text = f"🎉 <b>ПОБЕДА!</b>\n💰 Выигрыш: ${win_amount:.2f}"

            # Сохраняем результат в базу данных
        else:
            update_game_stats(user.id, "Кубы (дуэль)", 0)
            cashback_amount = bet_amount * 0.06
            add_loss_to_cashback(user.id, bet_amount) # Добавляем в кешбек
            result_text = f"😢 <b>Поражение</b>\n💸 Проигрыш: ${bet_amount:.2f}\n💰 Кешбек +6%: +${cashback_amount:.2f}"

        bet_id = add_bet_to_history(user.id, 'dice_duel', bet_amount, choice, "win" if win else "loss", win_amount if win else 0)

        # Инлайн-кнопка для канала
        channel_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Сделать ставку", url=f"https://t.me/{(await bot.get_me()).username}?start=game")
            ]]
        )

        # Отправляем изображение с результатом
        try:
            if win:
                image_path = "attached_assets/win_image.png"  # Победа
            else:
                image_path = "attached_assets/loss_image.png"  # Поражение

            await bot.send_photo(
                CHANNEL_ID,
                photo=FSInputFile(image_path),
                caption=f"🎲 <b>Результат игры</b>\n\n"
                        f"👤 Игрок: {user.first_name}\n"
                        f"🎯 Игрок: {user_roll} | 🤖 Бот: {bot_roll}\n"
                        f"🎲 Выбор: {'🏆 Победа' if choice == 'win' else '💀 Поражение'}\n\n"
                        f"{'🎉' if win else '😔'} {result_text}",
                reply_markup=channel_keyboard,
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"Error sending dice duel photo: {e}")
            # Fallback to text message
            await bot.send_message(
                CHANNEL_ID,
                f"🎲 <b>Результат игры</b>\n\n"
                f"👤 Игрок: {user.first_name}\n"
                f"🎯 Игрок: {user_roll} | 🤖 Бот: {bot_roll}\n"
                f"🎲 Выбор: {'🏆 Победа' if choice == 'win' else '💀 Поражение'}\n\n"
                f"{'🎉' if win else '😔'} {result_text}",
                reply_markup=channel_keyboard,
                parse_mode='HTML'
            )

        # Удаляем ставку из активных
        user_id = user.id
        if user_id in user_active_bets:
            for i, bet in enumerate(user_active_bets[user_id]):
                if (bet['game_type'] == 'dice_duel' and 
                    bet['bet_amount'] == bet_amount and 
                    bet['choice'] == choice):
                    user_active_bets[user_id].pop(i)
                    break

            if not user_active_bets[user_id]:
                del user_active_bets[user_id]

        # Уведомление в боте с кнопкой главного меню
        bot_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Главное меню", callback_data="main_menu")
            ]]
        )

        if win:
            await bot.send_message(
                user.id,
                f"🎉 <b>Поздравляем с победой!</b>\n\n"
                f"🎲 Игра: Кубы (дуэль)\n"
                f"💰 Выигрыш: ${win_amount:.2f}\n"
                f"💳 Ваш баланс: ${get_balance(user.id):.2f}",
                reply_markup=bot_keyboard
            )
        else:
            await bot.send_message(
                user.id,
                f"😔 <b>Повезет в другой раз :)</b>\n\n"
                f"🎲 Игра: Кубы (дуэль)\n"
                f"💸 Проигрыш: ${bet_amount:.2f}\n"
                f"💳 Текущий баланс: ${get_balance(user.id):.2f}",
                reply_markup=bot_keyboard
            )

    except Exception as e:
        print(f"Ошибка в кубах (дуэль): {e}")
        await asyncio.sleep(5)  # Увеличиваем задержку
        try:
            # Повторная попытка с другим подходом
            await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎲")
        except Exception as retry_error:
            print(f"Повторная ошибка в кубах (дуэль): {retry_error}")
            # Если все еще ошибка, пропускаем игру и возвращаем деньги
            update_balance(user.id, bet_amount)
            await bot.send_message(user.id, 
                f"❌ Техническая ошибка в игре Кубы (дуэль)\n"
                f"💰 Ставка ${bet_amount:.2f} возвращена на ваш счет")
            return

async def play_basketball_direct(bot: Bot, message, bet_amount: float, choice: str):
    user = message.from_user

    try:
        basketball = await bot.send_dice(chat_id=CHANNEL_ID, emoji="🏀")
        await asyncio.sleep(4)
        basketball_value = basketball.dice.value

        # Логика определения цвета для дартс (адаптируйте под реальные значения)
        actual_result = "hit" if basketball_value >= 4 else "miss"
        win = choice == actual_result

        if win:
            coeff = 1.8 if choice == 'hit' else 1.3
            win_amount = bet_amount * coeff
            update_balance(user.id, win_amount)
            update_game_stats(user.id, "Баскетбол", win_amount)

            # Реферальный бонус
            try:
                stats = get_user_stats(user.id)
                if stats and stats.get('referrer_id'):
                    bonus = win_amount * 0.05  # 5%
                    if bonus >= 0.01:  # Минимальный бонус $0.01
                        add_referral_bonus(stats['referrer_id'], bonus)
                        try:
                            await bot.send_message(
                                stats['referrer_id'],
                                f"💰 <b>Реферальный бонус!</b>\n"
                                f"👤 Ваш реферал выиграл в баскетбол\n"
                                f"🎁 Ваш бонус: ${bonus:.2f} (5%)"
                            )
                        except:
                            pass
            except Exception as e:
                print(f"Error processing referral bonus: {e}")
            result_text = f"🎉 <b>ПОБЕДА!</b>\n💰 Выигрыш: ${win_amount:.2f} (x{coeff})"

            # Сохраняем результат в базу данных
        else:
            update_game_stats(user.id, "Баскетбол", 0)
            cashback_amount = bet_amount * 0.06
            add_loss_to_cashback(user.id, bet_amount) # Добавляем в кешбек
            result_text = f"😔 <b>Поражение</b>\n💸 Проигрыш: ${bet_amount:.2f}\n💰 Кешбек +6%: +${cashback_amount:.2f}"

        bet_id = add_bet_to_history(user.id, 'basketball', bet_amount, choice, "win" if win else "loss", win_amount if win else 0)

        # Инлайн-кнопка для канала
        channel_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Сделать ставку", url=f"https://t.me/{(await bot.get_me()).username}?start=game")
            ]]
        )

        # Отправляем изображение с результатом
        try:
            if win:
                image_path = "attached_assets/win_image.png"  # Победа
            else:
                image_path = "attached_assets/loss_image.png"  # Поражение

            await bot.send_photo(
                CHANNEL_ID,
                photo=FSInputFile(image_path),
                caption=f"🏀 <b>Результат игры</b>\n\n"
                        f"👤 Игрок: {user.first_name}\n"
                        f"🎯 Результат: {'🎯 Попадание' if actual_result == 'hit' else '❌ Мимо'} ({basketball_value})\n"
                        f"🎲 Выбор: {'🎯 Попадание' if choice == 'hit' else '❌ Мимо'}\n\n"
                        f"{'🎉' if win else '😔'} {result_text}",
                reply_markup=channel_keyboard,
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"Error sending basketball photo: {e}")
            # Fallback to text message
            await bot.send_message(
                CHANNEL_ID,
                f"🏀 <b>Результат игры</b>\n\n"
                f"👤 Игрок: {user.first_name}\n"
                f"🎯 Результат: {'🎯 Попадание' if actual_result == 'hit' else '❌ Мимо'} ({basketball_value})\n"
                f"🎲 Выбор: {'🎯 Попадание' if choice == 'hit' else '❌ Мимо'}\n\n"
                f"{'🎉' if win else '😔'} {result_text}",
                reply_markup=channel_keyboard,
                parse_mode='HTML'
            )

        # Удаляем ставку из активных
        user_id = user.id
        if user_id in user_active_bets:
            for i, bet in enumerate(user_active_bets[user_id]):
                if (bet['game_type'] == 'basketball' and 
                    bet['bet_amount'] == bet_amount and 
                    bet['choice'] == choice):
                    user_active_bets[user_id].pop(i)
                    break

            if not user_active_bets[user_id]:
                del user_active_bets[user_id]

        # Уведомление в боте с кнопкой главного меню
        bot_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Главное меню", callback_data="main_menu")
            ]]
        )

        if win:
            await bot.send_message(
                user.id,
                f"🎉 <b>Поздравляем с победой!</b>\n\n"
                f"🏀 Игра: Баскетбол\n"
                f"💰 Выигрыш: ${win_amount:.2f} (x{coeff})\n"
                f"💳 Ваш баланс: ${get_balance(user.id):.2f}",
                reply_markup=bot_keyboard
            )
        else:
            await bot.send_message(
                user.id,
                f"😔 <b>Повезет в другой раз :)</b>\n\n"
                f"🏀 Игра: Баскетбол\n"
                f"💸 Проигрыш: ${bet_amount:.2f}\n"
                f"💳 Текущий баланс: ${get_balance(user.id):.2f}",
                reply_markup=bot_keyboard
            )

    except Exception as e:
        print(f"Ошибка в баскетболе: {e}")
        await asyncio.sleep(5)  # Увеличиваем задержку
        try:
            # Повторная попытка с другим подходом
            await bot.send_dice(chat_id=CHANNEL_ID, emoji="🏀")
        except Exception as retry_error:
            print(f"Повторная ошибка в баскетболе: {retry_error}")
            # Если все еще ошибка, пропускаем игру и возвращаем деньги
            update_balance(user.id, bet_amount)
            await bot.send_message(user.id, 
                f"❌ Техническая ошибка в игре Баскетбол\n"
                f"💰 Ставка ${bet_amount:.2f} возвращена на ваш счет")
            return

async def play_dice_higher_direct(bot: Bot, message, bet_amount: float, choice: str):
    user = message.from_user

    try:
        dice = await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎲")
        await asyncio.sleep(4)
        dice_value = dice.dice.value

        actual_result = "higher" if dice_value > 3 else "lower"
        win = choice == actual_result

        if win:
            win_amount = bet_amount * 1.8
            update_balance(user.id, win_amount)
            update_game_stats(user.id, "Кубы больше/меньше", win_amount)

            # Реферальный бонус
            try:
                stats = get_user_stats(user.id)
                if stats and stats.get('referrer_id'):
                    bonus = win_amount * 0.05  # 5%
                    if bonus >= 0.01:  # Минимальный бонус $0.01
                        add_referral_bonus(stats['referrer_id'], bonus)
                        try:
                            await bot.send_message(
                                stats['referrer_id'],
                                f"💰 <b>Реферальный бонус!</b>\n"
                                f"👤 Ваш реферал выиграл в кубы больше/меньше\n"
                                f"🎁 Ваш бонус: ${bonus:.2f} (5%)"
                            )
                        except:
                            pass
            except Exception as e:
                print(f"Error processing referral bonus: {e}")
            result_text = f"🏆 Угадали! Выигрыш: ${win_amount:.2f}"
        else:
            update_game_stats(user.id, "Кубы больше/меньше", 0)
            cashback_amount = bet_amount * 0.06
            add_loss_to_cashback(user.id, bet_amount) # Добавляем в кешбек
            result_text = f"💀 Не угадали! Проигрыш: ${bet_amount:.2f}\n💰 Кешбек +6%: +${cashback_amount:.2f}"

        # Сохраняем результат в базу данных
        bet_id = add_bet_to_history(user.id, 'dice_higher', bet_amount, choice, "win" if win else "loss", win_amount if win else 0)

        # Инлайн-кнопка для канала
        channel_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Сделать ставку", url=f"https://t.me/{(await bot.get_me()).username}?start=game")
            ]]
        )

        # Отправляем изображение с результатом
        try:
            if win:
                image_path = "attached_assets/win_image.png"  # Победа
            else:
                image_path = "attached_assets/loss_image.png"  # Поражение

            await bot.send_photo(
                CHANNEL_ID,
                photo=FSInputFile(image_path),
                caption=f"🎲 <b>Результат игры</b>\n\n"
                        f"👤 Игрок: {user.first_name}\n"
                        f"🎯 Результат: {dice_value}\n"
                        f"🎲 Выбор: {'⬆️ Больше 3' if choice == 'higher' else '⬇️ Меньше 4'}\n\n"
                        f"{'🎉' if win else '😔'} {result_text}",
                reply_markup=channel_keyboard,
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"Error sending dice higher photo: {e}")
            # Fallback to text message
            await bot.send_message(
                CHANNEL_ID,
                f"🎲 <b>Результат игры</b>\n\n"
                f"👤 Игрок: {user.first_name}\n"
                f"🎯 Результат: {dice_value}\n"
                f"🎲 Выбор: {'⬆️ Больше 3' if choice == 'higher' else '⬇️ Меньше 4'}\n\n"
                f"{'🎉' if win else '😔'} {result_text}",
                reply_markup=channel_keyboard,
                parse_mode='HTML'
            )

        # Удаляем ставку из активных
        user_id = user.id
        if user_id in user_active_bets:
            for i, bet in enumerate(user_active_bets[user_id]):
                if (bet['game_type'] == 'dice_higher' and 
                    bet['bet_amount'] == bet_amount and 
                    bet['choice'] == choice):
                    user_active_bets[user_id].pop(i)
                    break

            if not user_active_bets[user_id]:
                del user_active_bets[user_id]

        # Уведомление в боте с кнопкой главного меню
        bot_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Главное меню", callback_data="main_menu")
            ]]
        )

        if win:
            await bot.send_message(
                user.id,
                f"🎉 <b>Поздравляем с победой!</b>\n\n"
                f"🎲 Игра: Кубы больше/меньше\n"
                f"💰 Выигрыш: ${win_amount:.2f}\n"
                f"💳 Ваш баланс: ${get_balance(user.id):.2f}",
                reply_markup=bot_keyboard
            )
        else:
            await bot.send_message(
                user.id,
                f"😔 <b>Повезет в другой раз :)</b>\n\n"
                f"🎲 Игра: Кубы больше/меньше\n"
                f"💸 Проигрыш: ${bet_amount:.2f}\n"
                f"💳 Текущий баланс: ${get_balance(user.id):.2f}",
                reply_markup=bot_keyboard
            )

    except Exception as e:
        print(f"Ошибка в кубах больше/меньше: {e}")
        await asyncio.sleep(5)  # Увеличиваем задержку
        try:
            # Повторная попытка с другим подходом
            await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎲")
        except Exception as retry_error:
            print(f"Повторная ошибка в кубах больше/меньше: {retry_error}")
            # Если все еще ошибка, пропускаем игру и возвращаем деньги
            update_balance(user.id, bet_amount)
            await bot.send_message(user.id, 
                f"❌ Техническая ошибка в игре Кубы больше/меньше\n"
                f"💰 Ставка ${bet_amount:.2f} возвращена на ваш счет")
            return

async def play_dice_even_direct(bot: Bot, message, bet_amount: float, choice: str):
    user = message.from_user

    try:
        dice = await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎲")
        await asyncio.sleep(4)
        dice_value = dice.dice.value

        actual_result = "even" if dice_value % 2 == 0 else "odd"
        win = choice == actual_result

        if win:
            win_amount = bet_amount * 1.8

            update_balance(user.id, win_amount)
            update_game_stats(user.id, "Кубы чет/нечет", win_amount)

            # Реферальный бонус
            try:
                stats = get_user_stats(user.id)
                if stats and stats.get('referrer_id'):
                    bonus = win_amount * 0.05  # 5%
                    if bonus >= 0.01:  # Минимальный бонус $0.01
                        add_referral_bonus(stats['referrer_id'], bonus)
                        try:
                            await bot.send_message(
                                stats['referrer_id'],
                                f"💰 <b>Реферальный бонус!</b>\n"
                                f"👤 Ваш реферал выиграл в кубы чет/нечет\n"
                                f"🎁 Ваш бонус: ${bonus:.2f} (5%)"
                            )
                        except:
                            pass
            except Exception as e:
                print(f"Error processing referral bonus: {e}")

            result_text = f"🏆 Угадали! Выигрыш: ${win_amount:.2f}"
        else:
            update_game_stats(user.id, "Кубы чет/нечет", 0)
            cashback_amount = bet_amount * 0.06
            add_loss_to_cashback(user.id, bet_amount) # Добавляем в кешбек
            result_text = f"💀 Не угадали! Проигрыш: ${bet_amount:.2f}\n💰 Кешбек +6%: +${cashback_amount:.2f}"

        # Сохраняем результат в базу данных
        bet_id = add_bet_to_history(user.id, 'dice_even', bet_amount, choice, "win" if win else "loss", win_amount if win else 0)

        # Инлайн-кнопка для канала
        channel_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Сделать ставку", url=f"https://t.me/{(await bot.get_me()).username}?start=game")
            ]]
        )

        # Отправляем изображение с результатом
        try:
            if win:
                image_path = "attached_assets/win_image.png"  # Победа
            else:
                image_path = "attached_assets/loss_image.png"  # Поражение

            await bot.send_photo(
                CHANNEL_ID,
                photo=FSInputFile(image_path),
                caption=f"🎲 <b>Результат игры</b>\n\n"
                        f"👤 Игрок: {user.first_name}\n"
                        f"🎯 Результат: {dice_value}\n"
                        f"🎲 Выбор: {'2️⃣ Четное' if choice == 'even' else '1️⃣ Нечетное'}\n\n"
                        f"{'🎉' if win else '😔'} {result_text}",
                reply_markup=channel_keyboard,
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"Error sending dice even photo: {e}")
            # Fallback to text message
            await bot.send_message(
                CHANNEL_ID,
                f"🎲 <b>Результат игры</b>\n\n"
                f"👤 Игрок: {user.first_name}\n"
                f"🎯 Результат: {dice_value}\n"
                f"🎲 Выбор: {'2️⃣ Четное' if choice == 'even' else '1️⃣ Нечетное'}\n\n"
                f"{'🎉' if win else '😔'} {result_text}",
                reply_markup=channel_keyboard,
                parse_mode='HTML'
            )

        # Удаляем ставку из активных
        user_id = user.id
        if user_id in user_active_bets:
            for i, bet in enumerate(user_active_bets[user_id]):
                if (bet['game_type'] == 'dice_even' and 
                    bet['bet_amount'] == bet_amount and 
                    bet['choice'] == choice):
                    user_active_bets[user_id].pop(i)
                    break

            if not user_active_bets[user_id]:
                del user_active_bets[user_id]

        # Уведомление в боте с кнопкой главного меню
        bot_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Главное меню", callback_data="main_menu")
            ]]
        )

        if win:
            await bot.send_message(
                user.id,
                f"🎉 <b>Поздравляем с победой!</b>\n\n"
                f"🎲 Игра: Кубы чет/нечет\n"
                f"💰 Выигрыш: ${win_amount:.2f}\n"
                f"💳 Ваш баланс: ${get_balance(user.id):.2f}",
                reply_markup=bot_keyboard
            )
        else:
            await bot.send_message(
                user.id,
                f"😔 <b>Повезет в другой раз :)</b>\n\n"
                f"🎲 Игра: Кубы чет/нечет\n"
                f"💸 Проигрыш: ${bet_amount:.2f}\n"
                f"💳 Текущий баланс: ${get_balance(user.id):.2f}",
                reply_markup=bot_keyboard
            )

    except Exception as e:
        print(f"Ошибка в кубах чет/нечет: {e}")
        await asyncio.sleep(5)  # Увеличиваем задержку
        try:
            # Повторная попытка с другим подходом
            await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎲")
        except Exception as retry_error:
            print(f"Повторная ошибка в кубах чет/нечет: {retry_error}")
            # Если все еще ошибка, пропускаем игру и возвращаем деньги
            update_balance(user.id, bet_amount)
            await bot.send_message(user.id, 
                f"❌ Техническая ошибка в игре Кубы чет/нечет\n"
                f"💰 Ставка ${bet_amount:.2f} возвращена на ваш счет")
            return

async def play_triada_direct(bot: Bot, message, bet_amount: float, choice: str):
    user = message.from_user

    try:
        await bot.send_message(CHANNEL_ID, "🎲 Кидаем 3 кубика...")
        dice1 = await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎲")
        await asyncio.sleep(2)
        dice2 = await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎲")
        await asyncio.sleep(2)
        dice3 = await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎲")
        await asyncio.sleep(2)

        dice_values = [dice1.dice.value, dice2.dice.value, dice3.dice.value]
        choice_num = int(choice)

        matches = dice_values.count(choice_num)
        coeff = 1.8 if matches == 1 else 2.4 if matches == 2 else 3.1 if matches == 3 else 0

        if coeff > 0:
            win_amount = bet_amount * coeff

            update_balance(user.id, win_amount)
            update_game_stats(user.id, "Триада", win_amount)

            # Реферальный бонус
            try:
                stats = get_user_stats(user.id)
                if stats and stats.get('referrer_id'):
                    bonus = win_amount * 0.05  # 5%
                    if bonus >= 0.01:  # Минимальный бонус $0.01
                        add_referral_bonus(stats['referrer_id'], bonus)
                        try:
                            await bot.send_message(
                                stats['referrer_id'],
                                f"💰 <b>Реферальный бонус!</b>\n"
                                f"👤 Ваш реферал выиграл в триаду\n"
                                f"🎁 Ваш бонус: ${bonus:.2f} (5%)"
                            )
                        except:
                            pass
            except Exception as e:
                print(f"Error processing referral bonus: {e}")

            result_text = f"🎉 <b>ПОБЕДА!</b>\n💰 Выигрыш: ${win_amount:.2f} (x{coeff})"
        else:
            update_game_stats(user.id, "Триада", 0)
            cashback_amount = bet_amount * 0.06
            add_loss_to_cashback(user.id, bet_amount) # Добавляем в кешбек
            result_text = f"💀 <b>Поражение</b>\n💸 Проигрыш: ${bet_amount:.2f}\n💰 Кешбек +6%: +${cashback_amount:.2f}"

        # Сохраняем результат в базу данных
        bet_id = add_bet_to_history(user.id, 'triada', bet_amount, choice, "win" if coeff > 0 else "loss", win_amount if coeff > 0 else 0)

        # Инлайн-кнопка для канала
        channel_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Сделать ставку", url=f"https://t.me/{(await bot.get_me()).username}?start=game")
            ]]
        )

        # Отправляем изображение с результатом
        try:
            if coeff > 0:
                image_path = "attached_assets/win_image.png"  # Победа
            else:
                image_path = "attached_assets/loss_image.png"  # Поражение

            await bot.send_photo(
                CHANNEL_ID,
                photo=FSInputFile(image_path),
                caption=f"🎲 <b>Результат игры</b>\n\n"
                        f"👤 Игрок: {user.first_name}\n"
                        f"🎯 Кубики: {dice1.dice.value}, {dice2.dice.value}, {dice3.dice.value}\n"
                        f"🎲 Выбор: {choice}\n"
                        f"✨ Совпадений: {matches}\n\n"
                        f"{'🎉' if coeff > 0 else '😔'} {result_text}",
                reply_markup=channel_keyboard,
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"Error sending triada photo: {e}")
            # Fallback to text message
            await bot.send_message(
                CHANNEL_ID,
                f"🎲 <b>Результат игры</b>\n\n"
                f"👤 Игрок: {user.first_name}\n"
                f"🎯 Кубики: {dice1.dice.value}, {dice2.dice.value}, {dice3.dice.value}\n"
                f"🎲 Выбор: {choice}\n"
                f"✨ Совпадений: {matches}\n\n"
                f"{'🎉' if coeff > 0 else '😔'} {result_text}",
                reply_markup=channel_keyboard,
                parse_mode='HTML'
            )

        # Удаляем ставку из активных
        user_id = user.id
        if user_id in user_active_bets:
            for i, bet in enumerate(user_active_bets[user_id]):
                if (bet['game_type'] == 'triada' and 
                    bet['bet_amount'] == bet_amount and 
                    bet['choice'] == choice):
                    user_active_bets[user_id].pop(i)
                    break

            if not user_active_bets[user_id]:
                del user_active_bets[user_id]

        # Уведомление в боте с кнопкой главного меню
        bot_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Главное меню", callback_data="main_menu")
            ]]
        )

        if coeff > 0:
            await bot.send_message(
                user.id,
                f"🎉 <b>Поздравляем с победой!</b>\n\n"
                f"🎲 Игра: Триада\n"
                f"✨ Совпадений: {matches}\n"
                f"💰 Выигрыш: ${win_amount:.2f} (x{coeff})\n"
                f"💳 Ваш баланс: ${get_balance(user.id):.2f}",
                reply_markup=bot_keyboard
            )
        else:
            await bot.send_message(
                user.id,
                f"😔 <b>Повезет в другой раз :)</b>\n\n"
                f"🎲 Игра: Триада\n"
                f"✨ Совпадений: {matches}\n"
                f"💸 Проигрыш: ${bet_amount:.2f}\n"
                f"💳 Текущий баланс: ${get_balance(user.id):.2f}",
                reply_markup=bot_keyboard
            )

    except Exception as e:
        print(f"Ошибка в триаде: {e}")
        await asyncio.sleep(5)  # Увеличиваем задержку
        try:
            # Повторная попытка с другим подходом
            for _ in range(3): # Попытка 3 раза
                await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎲")
        except Exception as retry_error:
            print(f"Повторная ошибка в триаде: {retry_error}")
            # Если все еще ошибка, пропускаем игру и возвращаем деньги
            update_balance(user.id, bet_amount)
            await bot.send_message(user.id, 
                f"❌ Техническая ошибка в игре Триада\n"
                f"💰 Ставка ${bet_amount:.2f} возвращена на ваш счет")
            return


async def play_darts_direct(bot: Bot, message, bet_amount: float, choice: str):
    user = message.from_user

    try:
        darts = await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎯")
        await asyncio.sleep(4)
        darts_value = darts.dice.value

        # Логика определения цвета для дартс (адаптируйте под реальные значения)
        actual_result = "red" if darts_value in [2, 4, 6] else "white"
        win = choice == actual_result

        if win:
            win_amount = bet_amount * 1.8

            update_balance(user.id, win_amount)
            update_game_stats(user.id, "Дартс", win_amount)

            # Реферальный бонус
            try:
                stats = get_user_stats(user.id)
                if stats and stats.get('referrer_id'):
                    bonus = win_amount * 0.05  # 5%
                    if bonus >= 0.01:  # Минимальный бонус $0.01
                        add_referral_bonus(stats['referrer_id'], bonus)
                        try:
                            await bot.send_message(
                                stats['referrer_id'],
                                f"💰 <b>Реферальный бонус!</b>\n"
                                f"👤 Ваш реферал выиграл в дартс\n"
                                f"🎁 Ваш бонус: ${bonus:.2f} (5%)"
                            )
                        except:
                            pass
            except Exception as e:
                print(f"Error processing referral bonus: {e}")

            result_text = f"🏆 Угадали! Выигрыш: ${win_amount:.2f}"
        else:
            update_game_stats(user.id, "Дартс", 0)
            cashback_amount = bet_amount * 0.06
            add_loss_to_cashback(user.id, bet_amount) # Добавляем в кешбек
            result_text = f"💀 Не угадали! Проигрыш: ${bet_amount:.2f}\n💰 Кешбек +6%: +${cashback_amount:.2f}"

        # Сохраняем результат в базу данных
        bet_id = add_bet_to_history(user.id, 'darts', bet_amount, choice, "win" if win else "loss", win_amount if win else 0)

        # Инлайн-кнопка для канала
        channel_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Сделать ставку", url=f"https://t.me/{(await bot.get_me()).username}?start=game")
            ]]
        )

        # Отправляем изображение с результатом
        try:
            if win:
                image_path = "attached_assets/win_image.png"  # Победа
            else:
                image_path = "attached_assets/loss_image.png"  # Поражение

            await bot.send_photo(
                CHANNEL_ID,
                photo=FSInputFile(image_path),
                caption=f"🎯 <b>Результат игры</b>\n\n"
                        f"👤 Игрок: {user.first_name}\n"
                        f"🎯 Результат: {'🔴 Красное' if actual_result == 'red' else '⚪ Белое'} ({darts_value})\n"
                        f"🎲 Выбор: {'🔴 Красное' if choice == 'red' else '⚪ Белое'}\n\n"
                        f"{'🎉' if win else '😔'} {result_text}",
                reply_markup=channel_keyboard,
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"Error sending darts photo: {e}")
            # Fallback to text message
            await bot.send_message(
                CHANNEL_ID,
                f"🎯 <b>Результат игры</b>\n\n"
                f"👤 Игрок: {user.first_name}\n"
                f"🎯 Результат: {'🔴 Красное' if actual_result == 'red' else '⚪ Белое'} ({darts_value})\n"
                f"🎲 Выбор: {'🔴 Красное' if choice == 'red' else '⚪ Белое'}\n\n"
                f"{'🎉' if win else '😔'} {result_text}",
                reply_markup=channel_keyboard,
                parse_mode='HTML'
            )

        # Удаляем ставку из активных
        user_id = user.id
        if user_id in user_active_bets:
            for i, bet in enumerate(user_active_bets[user_id]):
                if (bet['game_type'] == 'darts' and 
                    bet['bet_amount'] == bet_amount and 
                    bet['choice'] == choice):
                    user_active_bets[user_id].pop(i)
                    break

            if not user_active_bets[user_id]:
                del user_active_bets[user_id]

        # Уведомление в боте с кнопкой главного меню
        bot_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Главное меню", callback_data="main_menu")
            ]]
        )

        if win:
            await bot.send_message(
                user.id,
                f"🎉 <b>Поздравляем с победой!</b>\n\n"
                f"🎯 Игра: Дартс\n"
                f"💰 Выигрыш: ${win_amount:.2f}\n"
                f"💳 Ваш баланс: ${get_balance(user.id):.2f}",
                reply_markup=bot_keyboard
            )
        else:
            await bot.send_message(
                user.id,
                f"😔 <b>Повезет в другой раз :)</b>\n\n"
                f"🎯 Игра: Дартс\n"
                f"💸 Проигрыш: ${bet_amount:.2f}\n"
                f"💳 Текущий баланс: ${get_balance(user.id):.2f}",
                reply_markup=bot_keyboard
            )

    except Exception as e:
        print(f"Ошибка в дартс: {e}")
        await asyncio.sleep(5)  # Увеличиваем задержку
        try:
            # Повторная попытка с другим подходом
            await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎯")
        except Exception as retry_error:
            print(f"Повторная ошибка в дартс: {retry_error}")
            # Если все еще ошибка, пропускаем игру и возвращаем деньги
            update_balance(user.id, bet_amount)
            await bot.send_message(user.id, 
                f"❌ Техническая ошибка в игре Дартс\n"
                f"💰 Ставка ${bet_amount:.2f} возвращена на ваш счет")
            return

async def play_slots_direct(bot: Bot, message, bet_amount: float, choice: str):
    user = message.from_user

    try:
        # Отправляем сообщение о новой игре только для слотов
        await bot.send_message(
            CHANNEL_ID,
            f"🎮 <b>Новая игра!</b>\n\n"
            f"👤 Игрок: {user.first_name}\n"
            f"🎯 Игра: 🎰 Слоты\n"
            f"💰 Ставка: ${bet_amount:.2f}\n"
            f"🎲 Крутим барабан!\n\n"
            f"🎮 Начинаем игру..."
        )

        await asyncio.sleep(1)

        # Отправляем 1 слот с правильным эмодзи
        await bot.send_message(CHANNEL_ID, "🎰 Крутим барабан...")
        slot = await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎰")
        await asyncio.sleep(3)

        # Получаем значение слота
        slot_value = slot.dice.value

        # Проверяем выигрыш - значения 22, 43, 64 (тройки)
        win = slot_value in [22, 43, 64]

        if win:
            win_amount = bet_amount * 3.5

            update_balance(user.id, win_amount)
            update_game_stats(user.id, "Слоты", win_amount)

            # Сохраняем результат в базу данных при выигрыше
            bet_id = add_bet_to_history(user.id, 'slots', bet_amount, 'spin', "win", win_amount)
            # Реферальный бонус
            try:
                stats = get_user_stats(user.id)
                if stats and stats.get('referrer_id'):
                    bonus = win_amount * 0.05  # 5%
                    if bonus >= 0.01:  # Минимальный бонус $0.01
                        add_referral_bonus(stats['referrer_id'], bonus)
                        try:
                            await bot.send_message(
                                stats['referrer_id'],
                                f"💰 <b>Реферальный бонус!</b>\n"
                                f"👤 Ваш реферал выиграл в слоты\n"
                                f"🎁 Ваш бонус: ${bonus:.2f} (5%)"
                            )
                        except:
                            pass
            except Exception as e:
                print(f"Error processing referral bonus: {e}")

            result_text = f"🎉 <b>ДЖЕКПОТ!</b>\n💰 Выигрыш: ${win_amount:.2f} (x3.5)"
        else:
            update_game_stats(user.id, "Слоты", 0)
            cashback_amount = bet_amount * 0.06
            add_loss_to_cashback(user.id, bet_amount) # Добавляем в кешбек
            result_text = f"💀 <b>Проигрыш</b>\n💸 Проигрыш: ${bet_amount:.2f}\n💰 Кешбек +6%: +${cashback_amount:.2f}"

        # Сохраняем результат в базу данных при проигрыше
        bet_id = add_bet_to_history(user.id, 'slots', bet_amount, 'spin', "loss", 0)

        # Инлайн-кнопка для канала
        channel_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Сделать ставку", url=f"https://t.me/{(await bot.get_me()).username}?start=game")
            ]]
        )

        # Отправляем изображение с результатом
        try:
            if win:
                image_path = "attached_assets/win_image.png"  # Победа
            else:
                image_path = "attached_assets/loss_image.png"  # Поражение

            await bot.send_photo(
                CHANNEL_ID,
                photo=FSInputFile(image_path),
                caption=f"🎰 <b>Результат игры</b>\n\n"
                        f"👤 Игрок: {user.first_name}\n"
                        f"🎯 Результат: {slot_value}\n"
                        f"{'🎲 Комбинация: ✅ Джекпот!' if win else ''}\n\n"
                        f"{'🎉' if win else '😔'} {result_text}",
                reply_markup=channel_keyboard,
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"Error sending slots photo: {e}")
            # Fallback to text message
            await bot.send_message(
                CHANNEL_ID,
                f"🎰 <b>Результат игры</b>\n\n"
                f"👤 Игрок: {user.first_name}\n"
                f"🎯 Результат: {slot_value}\n"
                f"{'🎲 Комбинация: ✅ Джекпот!' if win else ''}\n\n"
                f"{'🎉' if win else '😔'} {result_text}",
                reply_markup=channel_keyboard,
                parse_mode='HTML'
            )

        # Удаляем ставку из активных
        user_id = user.id
        if user_id in user_active_bets:
            for i, bet in enumerate(user_active_bets[user_id]):
                if (bet['game_type'] == 'slots' and 
                    bet['bet_amount'] == bet_amount and 
                    bet['choice'] == 'spin'):
                    user_active_bets[user_id].pop(i)
                    break

            if not user_active_bets[user_id]:
                del user_active_bets[user_id]

        # Уведомление в боте с кнопкой главного меню
        bot_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Главное меню", callback_data="main_menu")
            ]]
        )

        if win:
            await bot.send_message(
                user.id,
                f"🎉 <b>Поздравляем с джекпотом!</b>\n\n"
                f"🎰 Игра: Слоты\n"
                f"🎯 Результат: {slot_value}\n"
                f"💰 Выигрыш: ${win_amount:.2f} (x3.5)\n"
                f"💳 Ваш баланс: ${get_balance(user.id):.2f}",
                reply_markup=bot_keyboard
            )
        else:
            await bot.send_message(
                user.id,
                f"😔 <b>Повезет в другой раз :)</b>\n\n"
                f"🎰 Игра: Слоты\n"
                f"🎯 Результат: {slot_value}\n"
                f"💸 Проигрыш: ${bet_amount:.2f}\n"
                f"💳 Текущий баланс: ${get_balance(user.id):.2f}",
                reply_markup=bot_keyboard
            )

    except Exception as e:
        print(f"Ошибка в слотах: {e}")
        await asyncio.sleep(5)  # Увеличиваем задержку
        try:
            # Повторная попытка с другим подходом
            await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎰")
        except Exception as retry_error:
            print(f"Повторная ошибка в слотах: {retry_error}")
            # Если все еще ошибка, пропускаем игру и возвращаем деньги
            update_balance(user.id, bet_amount)
            await bot.send_message(user.id, 
                f"❌ Техническая ошибка в игре Слоты\n"
                f"💰 Ставка ${bet_amount:.2f} возвращена на ваш счет")
            return

# Функция для обработки очереди игр
async def process_game_queue(bot: Bot):
    global is_game_running

    is_game_running = True

    while game_queue:
        bet_info = game_queue.pop(0)

        try:
            # Отправляем сообщение о начале игры
            if bet_info['game_type'] != 'slots':
                game_names = {
                    'bowling': '🎳 Боулинг',
                    'dice_duel': '🎲 Кубы (дуэль)',
                    'basketball': '🏀 Баскетбол',
                    'dice_higher': '🎲 Кубы больше/меньше',
                    'dice_even': '🎲 Кубы чет/нечет',
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

                game_name = game_names.get(bet_info['game_type'], 'Неизвестная игра')
                choice_text = choice_texts.get((bet_info['game_type'], bet_info['choice']), str(bet_info['choice']))

                await bot.send_message(
                    CHANNEL_ID,
                    f"🎮 <b>Новая игра!</b>\n\n"
                    f"👤 Игрок: {bet_info['user'].first_name}\n"
                    f"🎯 Игра: {game_name}\n"
                    f"💰 Ставка: ${bet_info['bet_amount']:.2f}\n"
                    f"🎲 Выбор: {choice_text}\n\n"
                    f"🎮 Начинаем игру..."
                )

                await asyncio.sleep(1)

            # Создаем mock message объект
            class MockMessage:
                def __init__(self, user):
                    self.from_user = user

            mock_message = MockMessage(bet_info['user'])

            # Вызываем соответствующую функцию игры
            await bet_info['game_function'](bot, mock_message, bet_info['bet_amount'], bet_info['choice'])

            # Пауза между играми
            await asyncio.sleep(3)

        except Exception as e:
            print(f"Ошибка в обработке игры: {e}")
            # При ошибке возвращаем деньги
            update_balance(bet_info['user'].id, bet_info['bet_amount'])
            await bot.send_message(
                bet_info['user'].id,
                "❌ Произошла ошибка в игре! Ваши деньги возвращены."
            )

    is_game_running = False