-- seed_inventory_data.sql - новый файл с данными склада

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
('Упаковочная бумага', 'O''rash qog''ozi', 'sheet', 50, 200, 365)
ON CONFLICT DO NOTHING;

-- Поставщики
INSERT INTO suppliers (name, contact_person, phone, email, rating) VALUES 
('ЦветТорг', 'Александр Иванов', '+998901234567', 'info@cvettorg.uz', 4.5),
('Флора Плюс', 'Мария Петрова', '+998901234568', 'orders@floraplus.uz', 4.2),
('Узбек Гуль', 'Дилшод Каримов', '+998901234569', 'dilshod@uzbekgul.uz', 4.8),
('Импорт Флауэрс', 'Анна Смирнова', '+998901234570', 'import@flowers.uz', 3.9)
ON CONFLICT DO NOTHING;

-- Начальные остатки (создаём партии)
INSERT INTO inventory_batches (flower_id, supplier_id, quantity, purchase_price, batch_date, expire_date) VALUES 
-- Розы от ЦветТорг (ID supplier = 1)
(1, 1, 150, 2500, CURRENT_DATE, CURRENT_DATE + INTERVAL '7 days'),   -- Красные розы
(2, 1, 100, 2300, CURRENT_DATE, CURRENT_DATE + INTERVAL '7 days'),   -- Белые розы
(3, 1, 80, 2400, CURRENT_DATE, CURRENT_DATE + INTERVAL '7 days'),    -- Розовые розы

-- Тюльпаны от Флора Плюс (ID supplier = 2)
(4, 2, 200, 1500, CURRENT_DATE, CURRENT_DATE + INTERVAL '5 days'),   -- Красные тюльпаны
(5, 2, 180, 1400, CURRENT_DATE, CURRENT_DATE + INTERVAL '5 days'),   -- Жёлтые тюльпаны

-- Дополнительные материалы от Узбек Гуль (ID supplier = 3)
(6, 3, 60, 1800, CURRENT_DATE, CURRENT_DATE + INTERVAL '10 days'),   -- Хризантемы
(7, 3, 40, 3000, CURRENT_DATE, CURRENT_DATE + INTERVAL '14 days'),   -- Гипсофила
(8, 3, 50, 2000, CURRENT_DATE, CURRENT_DATE + INTERVAL '21 days'),   -- Эвкалипт

-- Упаковочные материалы (долгого хранения) от Импорт Флауэрс (ID supplier = 4)
(9, 4, 80, 500, CURRENT_DATE, CURRENT_DATE + INTERVAL '365 days'),   -- Ленты
(10, 4, 150, 300, CURRENT_DATE, CURRENT_DATE + INTERVAL '365 days')  -- Упаковочная бумага
ON CONFLICT DO NOTHING;

-- Движения склада (приходы от поставок)
INSERT INTO inventory_movements (flower_id, batch_id, movement_type, quantity, reason, performed_by, created_at) 
SELECT 
    b.flower_id,
    b.id,
    'purchase',
    b.quantity,
    'Начальные остатки',
    1,  -- ID админа
    CURRENT_TIMESTAMP
FROM inventory_batches b
WHERE NOT EXISTS (
    SELECT 1 FROM inventory_movements im 
    WHERE im.batch_id = b.id AND im.movement_type = 'purchase'
);