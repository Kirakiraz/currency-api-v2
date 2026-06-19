INSERT INTO mart.dim_currency (currency_code, currency_name) VALUES
('USD', 'US Dollar'),
('THB', 'Thai Baht'),
('JPY', 'Japanese Yen'),
('EUR', 'Euro'),
('GBP', 'British Pound Sterling'),
('SGD', 'Singapore Dollar')
ON CONFLICT (currency_code) DO NOTHING;
