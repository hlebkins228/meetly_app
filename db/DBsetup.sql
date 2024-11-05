CREATE TABLE IF NOT EXISTS users(
    user_id SERIAL,
    login text,
    email text,
    password text,
    reg_date TIMESTAMP
);