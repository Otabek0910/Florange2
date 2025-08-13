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