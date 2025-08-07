import sqlite3

def init_db():
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()

    # Проверяем существующие столбцы
    c.execute("PRAGMA table_info(users)")
    existing_columns = [column[1] for column in c.fetchall()]

    # Создаем таблицу с базовой структурой если её нет
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance REAL DEFAULT 0.0
    )''')

    # Добавляем недостающие столбцы
    columns_to_add = [
        ('referrer_id', 'INTEGER DEFAULT NULL'),
        ('registration_date', 'TEXT DEFAULT CURRENT_TIMESTAMP'),
        ('total_games', 'INTEGER DEFAULT 0'),
        ('total_winnings', 'REAL DEFAULT 0'),
        ('biggest_win', 'REAL DEFAULT 0'),
        ('favorite_game', 'TEXT DEFAULT ""'),
        ('favorite_game_count', 'INTEGER DEFAULT 0')
    ]

    for column_name, column_def in columns_to_add:
        if column_name not in existing_columns:
            try:
                c.execute(f'ALTER TABLE users ADD COLUMN {column_name} {column_def}')
                print(f"Added column: {column_name}")
            except Exception as e:
                print(f"Error adding column {column_name}: {e}")

    # Создаем таблицу для подсчета игр
    c.execute('''CREATE TABLE IF NOT EXISTS game_stats (
        user_id INTEGER,
        game_name TEXT,
        games_count INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, game_name)
    )''')

    # Создаем таблицу истории ставок
    c.execute("""
        CREATE TABLE IF NOT EXISTS bet_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            game_type TEXT NOT NULL,
            bet_amount REAL NOT NULL,
            choice TEXT NOT NULL,
            result TEXT,
            win_amount REAL DEFAULT 0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Создаем таблицу выводов
    c.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending'
        )
    """)

    # Создаем таблицу для пополнений
    c.execute('''CREATE TABLE IF NOT EXISTS deposits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        invoice_id TEXT UNIQUE,
        status TEXT DEFAULT 'pending',
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.commit()
    conn.close()

def create_user(user_id):
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def get_balance(user_id):
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def update_balance(user_id, amount):
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def create_user_with_referrer(user_id, referrer_id=None):
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    try:
        c.execute("INSERT OR IGNORE INTO users (user_id, referrer_id, registration_date) VALUES (?, ?, datetime('now'))", (user_id, referrer_id))
    except sqlite3.OperationalError:
        # Если столбец registration_date не существует, создаем пользователя без него
        c.execute("INSERT OR IGNORE INTO users (user_id, referrer_id) VALUES (?, ?)", (user_id, referrer_id))
        # Затем пытаемся обновить дату регистрации если столбец есть
        try:
            c.execute("UPDATE users SET registration_date = datetime('now') WHERE user_id = ? AND registration_date IS NULL", (user_id,))
        except:
            pass
    conn.commit()
    conn.close()

def get_user_stats(user_id):
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    try:
        c.execute("""SELECT total_games, total_winnings, biggest_win, favorite_game, 
                            favorite_game_count, registration_date, referrer_id 
                     FROM users WHERE user_id = ?""", (user_id,))
        row = c.fetchone()
        if row:
            return {
                'total_games': row[0] or 0,
                'total_winnings': row[1] or 0,
                'biggest_win': row[2] or 0,
                'favorite_game': row[3] or 'Триада',
                'favorite_game_count': row[4] or 74,
                'registration_date': row[5] or '2024-10-20',
                'referrer_id': row[6]
            }
    except sqlite3.OperationalError:
        # Если столбец registration_date не существует, используем старый запрос
        c.execute("""SELECT total_games, total_winnings, biggest_win, favorite_game, 
                            favorite_game_count, referrer_id 
                     FROM users WHERE user_id = ?""", (user_id,))
        row = c.fetchone()
        if row:
            return {
                'total_games': row[0] or 0,
                'total_winnings': row[1] or 0,
                'biggest_win': row[2] or 0,
                'favorite_game': row[3] or 'Триада',
                'favorite_game_count': row[4] or 74,
                'registration_date': '2024-10-20',
                'referrer_id': row[5]
            }
    finally:
        conn.close()
    return None

def update_game_stats(user_id, game_name, win_amount=0):
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()

    # Обновляем общую статистику
    c.execute("UPDATE users SET total_games = total_games + 1 WHERE user_id = ?", (user_id,))

    if win_amount > 0:
        c.execute("UPDATE users SET total_winnings = total_winnings + ? WHERE user_id = ?", (win_amount, user_id))
        # Проверяем и обновляем самый большой выигрыш
        c.execute("UPDATE users SET biggest_win = ? WHERE user_id = ? AND ? > biggest_win", (win_amount, user_id, win_amount))

    # Обновляем статистику по играм
    c.execute("INSERT OR REPLACE INTO game_stats (user_id, game_name, games_count) VALUES (?, ?, COALESCE((SELECT games_count FROM game_stats WHERE user_id = ? AND game_name = ?), 0) + 1)", (user_id, game_name, user_id, game_name))

    # Получаем самую играемую игру
    c.execute("SELECT game_name, games_count FROM game_stats WHERE user_id = ? ORDER BY games_count DESC LIMIT 1", (user_id,))
    fav_game = c.fetchone()
    if fav_game:
        c.execute("UPDATE users SET favorite_game = ?, favorite_game_count = ? WHERE user_id = ?", (fav_game[0], fav_game[1], user_id))

    conn.commit()
    conn.close()

def get_referral_info(user_id):
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    # Считаем количество рефералов
    c.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))
    referrals_count = c.fetchone()[0]
    conn.close()
    return referrals_count

def add_referral_bonus(referrer_id, bonus_amount):
    """Добавляет бонус рефереру (5% от выигрыша реферала)"""
    update_balance(referrer_id, bonus_amount)

def delete_user(user_id):
    """Удаляет пользователя из базы данных"""
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()

    # Удаляем из основной таблицы
    c.execute("DELETE FROM users WHERE user_id = ?", (user_id,))

    # Удаляем статистику игр
    c.execute("DELETE FROM game_stats WHERE user_id = ?", (user_id,))

    # Удаляем историю ставок
    c.execute("DELETE FROM bet_history WHERE user_id = ?", (user_id,))

    # Обнуляем реферера у тех, кто был приглашен этим пользователем
    c.execute("UPDATE users SET referrer_id = NULL WHERE referrer_id = ?", (user_id,))

    conn.commit()
    conn.close()

    return True

def add_withdrawal(user_id, amount):
    """Добавляет запись о выводе средств"""
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO withdrawals (user_id, amount, timestamp, status)
        VALUES (?, ?, CURRENT_TIMESTAMP, 'completed')
    """, (user_id, amount))

    conn.commit()
    conn.close()

def add_bet_to_history(user_id, game_type, bet_amount, choice, result="pending", win_amount=0):
    """Добавляет ставку в историю"""
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    c.execute("""INSERT INTO bet_history (user_id, game_type, bet_amount, choice, result, win_amount) 
                 VALUES (?, ?, ?, ?, ?, ?)""", 
              (user_id, game_type, bet_amount, choice, result, win_amount))
    bet_id = c.lastrowid
    conn.commit()
    conn.close()
    return bet_id

def update_bet_result(bet_id, result, win_amount=0):
    """Обновляет результат ставки"""
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    c.execute("UPDATE bet_history SET result = ?, win_amount = ? WHERE id = ?", 
              (result, float(win_amount), bet_id))
    conn.commit()
    conn.close()

def add_deposit(user_id, amount, invoice_id):
    """Добавляет депозит в базу данных"""
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    c.execute("INSERT INTO deposits (user_id, amount, invoice_id) VALUES (?, ?, ?)", 
              (user_id, float(amount), invoice_id))
    conn.commit()
    conn.close()

def update_deposit_status(invoice_id, status):
    """Обновляет статус депозита"""
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    c.execute("UPDATE deposits SET status = ? WHERE invoice_id = ?", (status, invoice_id))
    conn.commit()
    conn.close()

def get_deposit_by_invoice(invoice_id):
    """Получает депозит по invoice_id"""
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    c.execute("SELECT user_id, amount FROM deposits WHERE invoice_id = ? AND status = 'pending'", (invoice_id,))
    result = c.fetchone()
    conn.close()
    return result

def get_user_bet_history(user_id, limit=10):
    """Получает историю ставок пользователя"""
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    c.execute("""SELECT game_type, bet_amount, choice, result, win_amount, timestamp 
                 FROM bet_history WHERE user_id = ? 
                 ORDER BY timestamp DESC LIMIT ?""", (user_id, limit))
    history = c.fetchall()
    conn.close()
    return history

def get_user_by_id(user_id):
    """Получает пользователя по ID"""
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    c.execute("SELECT user_id, balance, referrer_id FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result

def get_leaderboard_by_winnings(period='all', limit=10):
    """Получает топ игроков по выигрышам за период"""
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    
    if period == 'day':
        time_filter = "AND timestamp >= datetime('now', '-1 day')"
    elif period == 'week':
        time_filter = "AND timestamp >= datetime('now', '-7 days')"
    elif period == 'month':
        time_filter = "AND timestamp >= datetime('now', '-30 days')"
    else:
        time_filter = ""
    
    query = f"""
        SELECT u.user_id, SUM(bh.win_amount) as total_winnings
        FROM users u
        JOIN bet_history bh ON u.user_id = bh.user_id
        WHERE bh.win_amount > 0 {time_filter}
        GROUP BY u.user_id
        ORDER BY total_winnings DESC
        LIMIT ?
    """
    
    c.execute(query, (limit,))
    results = c.fetchall()
    conn.close()
    return results

def get_leaderboard_by_balance(limit=10):
    """Получает топ игроков по балансу"""
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    c.execute("SELECT user_id, balance FROM users WHERE balance > 0 ORDER BY balance DESC LIMIT ?", (limit,))
    results = c.fetchall()
    conn.close()
    return results

def init_cashback_table():
    """Инициализация таблицы кешбека"""
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS cashback (
        user_id INTEGER PRIMARY KEY,
        total_losses REAL DEFAULT 0,
        available_cashback REAL DEFAULT 0,
        last_claimed DATETIME DEFAULT NULL
    )''')
    conn.commit()
    conn.close()

def add_loss_to_cashback(user_id, loss_amount):
    """Добавляет проигрыш в кешбек (6%)"""
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    
    cashback_amount = loss_amount * 0.06  # 6% кешбек
    
    c.execute('''INSERT OR REPLACE INTO cashback (user_id, total_losses, available_cashback)
                 VALUES (?, 
                         COALESCE((SELECT total_losses FROM cashback WHERE user_id = ?), 0) + ?,
                         COALESCE((SELECT available_cashback FROM cashback WHERE user_id = ?), 0) + ?)''',
              (user_id, user_id, loss_amount, user_id, cashback_amount))
    
    conn.commit()
    conn.close()

def get_cashback_info(user_id):
    """Получает информацию о кешбеке пользователя"""
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    c.execute("SELECT total_losses, available_cashback, last_claimed FROM cashback WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    
    if result:
        return {
            'total_losses': result[0],
            'available_cashback': result[1],
            'last_claimed': result[2]
        }
    return {'total_losses': 0, 'available_cashback': 0, 'last_claimed': None}

def claim_cashback(user_id):
    """Забирает доступный кешбек"""
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    
    c.execute("SELECT available_cashback FROM cashback WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    
    if result and result[0] > 0:
        cashback_amount = result[0]
        
        # Обновляем баланс пользователя
        c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (cashback_amount, user_id))
        
        # Обнуляем доступный кешбек и обновляем дату
        c.execute("UPDATE cashback SET available_cashback = 0, last_claimed = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,))
        
        conn.commit()
        conn.close()
        return cashback_amount
    
    conn.close()
    return 0