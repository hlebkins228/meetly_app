ALTER TABLE IF EXISTS users
    ADD PRIMARY KEY (user_id),
    ALTER COLUMN login SET NOT NULL,
    ALTER COLUMN email SET NOT NULL,
    ALTER COLUMN password SET NOT NULL,
    ALTER COLUMN reg_date SET NOT NULL;
