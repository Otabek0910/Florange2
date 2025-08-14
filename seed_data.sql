-- Категории
INSERT INTO categories (name_ru, name_uz, sort) VALUES 
('Букеты', 'Gulchambalar', 1),
('Композиции', 'Kompozitsiyalar', 2),
('Горшечные', 'Gorshokli gullar', 3)
ON CONFLICT DO NOTHING;

-- Товары
INSERT INTO products (category_id, name_ru, name_uz, desc_ru, desc_uz, price, stock_qty, is_active) VALUES 
(1, 'Букет роз', 'Atirgul guldastasi', 'Красивый букет из 15 красных роз', '15 ta qizil atirguldan gulchamba', 150000, 10, true),
(1, 'Букет тюльпанов', 'Lola guldastasi', 'Весенний букет из 21 тюльпана', '21 ta loladan bahorgi gulchamba', 120000, 8, true),
(2, 'Композиция в корзине', 'Savatchada kompozitsiya', 'Микс цветов в плетеной корзине', 'Orilgan savatchada gullar aralashmasi', 200000, 5, true)
ON CONFLICT DO NOTHING;

-- Базовые цветы
INSERT INTO flowers (name_ru, name_uz, unit_type, min_stock, max_stock, shelf_life_days) VALUES 
('Роза красная', 'Qizil atirgul', 'piece', 50, 200, 7),
('Роза белая', 'Oq atirgul', 'piece', 30, 150, 7),
('Роза розовая', 'Pushti atirgul', 'piece', 30, 150, 7),
('Тюльпан красный', 'Qizil lola', 'piece', 100, 300, 5),
('Тюльпан жёлтый', 'Sariq lola', 'piece', 100, 300, 5),
('Хризантема', 'Xrizantema', 'piece', 20, 100, 10),
('Гипсофила', 'Gipsofila', 'bundle', 10, 50, 14),
('Эвкалипт', 'Evkalipt', 'bundle', 15, 60, 21),
('Лента атласная', 'Atlas lenta', 'piece', 20, 100, 365),
('Упаковочная бумага', 'O\'rash qog\'ozi', 'sheet', 50, 200, 365)
ON CONFLICT DO NOTHING;

-- Поставщики
INSERT INTO suppliers (name, contact_person, phone, email, rating) VALUES 
('ЦветТорг', 'Александр Иванов', '+998901234567', 'info@cvettorg.uz', 4.5),
('Флора Плюс', 'Мария Петрова', '+998901234568', 'orders@floraplus.uz', 4.2),
('Узбек Гуль', 'Дилшод Каримов', '+998901234569', 'dilshod@uzbekgul.uz', 4.8),
('Импорт Флауэрс', 'Анна Смирнова', '+998901234570', 'import@flowers.uz', 3.9)
ON CONFLICT DO NOTHING;

-- Состав продуктов (рецепты букетов)
INSERT INTO product_compositions (product_id, flower_id, quantity, is_required) VALUES 
-- Букет роз (ID=1): 15 красных роз + гипсофила + лента
(1, 1, 15, true),   -- 15 красных роз
(1, 7, 3, false),   -- 3 веточки гипсофилы (опционально)
(1, 9, 1, true),    -- 1 лента

-- Букет тюльпанов (ID=2): 21 тюльпан + упаковка
(2, 4, 15, true),   -- 15 красных тюльпанов
(2, 5, 6, true),    -- 6 жёлтых тюльпанов
(2, 10, 1, true),   -- 1 лист упаковочной бумаги

-- Композиция в корзине (ID=3): микс цветов
(3, 1, 7, true),    -- 7 красных роз
(3, 2, 5, true),    -- 5 белых роз  
(3, 6, 10, true),   -- 10 хризантем
(3, 7, 5, false),   -- 5 веточек гипсофилы
(3, 8, 3, false)    -- 3 веточки эвкалипта
ON CONFLICT DO NOTHING;

-- Начальные остатки (создаём партии)
INSERT INTO inventory_batches (flower_id, supplier_id, quantity, purchase_price, batch_date, expire_date) VALUES 
-- Розы от ЦветТорг
(1, 1, 150, 2500, CURRENT_DATE, CURRENT_DATE + INTERVAL '7 days'),   -- Красные розы
(2, 1, 100, 2300, CURRENT_DATE, CURRENT_DATE + INTERVAL '7 days'),   -- Белые розы
(3, 1, 80, 2400, CURRENT_DATE, CURRENT_DATE + INTERVAL '7 days'),    -- Розовые розы

-- Тюльпаны от Флора Плюс
(4, 2, 200, 1500, CURRENT_DATE, CURRENT_DATE + INTERVAL '5 days'),   -- Красные тюльпаны
(5, 2, 180, 1400, CURRENT_DATE, CURRENT_DATE + INTERVAL '5 days'),   -- Жёлтые тюльпаны

-- Дополнительные материалы от Узбек Гуль
(6, 3, 60, 1800, CURRENT_DATE, CURRENT_DATE + INTERVAL '10 days'),   -- Хризантемы
(7, 3, 40, 3000, CURRENT_DATE, CURRENT_DATE + INTERVAL '14 days'),   -- Гипсофила
(8, 3, 50, 2000, CURRENT_DATE, CURRENT_DATE + INTERVAL '21 days'),   -- Эвкалипт

-- Упаковочные материалы (долгого хранения)
(9, 4, 80, 500, CURRENT_DATE, CURRENT_DATE + INTERVAL '365 days'),   -- Ленты
(10, 4, 150, 300, CURRENT_DATE, CURRENT_DATE + INTERVAL '365 days')  -- Упаковочная бумага
ON CONFLICT DO NOTHING;

-- Движения склада (приходы от поставок)
INSERT INTO inventory_movements (flower_id, batch_id, movement_type, quantity, reason, performed_by, created_at) VALUES 
(1, 1, 'purchase', 150, 'Поступление от ЦветТорг', 1, CURRENT_TIMESTAMP),
(2, 2, 'purchase', 100, 'Поступление от ЦветТорг', 1, CURRENT_TIMESTAMP),
(3, 3, 'purchase', 80, 'Поступление от ЦветТорг', 1, CURRENT_TIMESTAMP),
(4, 4, 'purchase', 200, 'Поступление от Флора Плюс', 1, CURRENT_TIMESTAMP),
(5, 5, 'purchase', 180, 'Поступление от Флора Плюс', 1, CURRENT_TIMESTAMP),
(6, 6, 'purchase', 60, 'Поступление от Узбек Гуль', 1, CURRENT_TIMESTAMP),
(7, 7, 'purchase', 40, 'Поступление от Узбек Гуль', 1, CURRENT_TIMESTAMP),
(8, 8, 'purchase', 50, 'Поступление от Узбек Гуль', 1, CURRENT_TIMESTAMP),
(9, 9, 'purchase', 80, 'Поступление от Импорт Флауэрс', 1, CURRENT_TIMESTAMP),
(10, 10, 'purchase', 150, 'Поступление от Импорт Флауэрс', 1, CURRENT_TIMESTAMP)
ON CONFLICT DO NOTHING;