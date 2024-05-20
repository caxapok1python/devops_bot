CREATE USER repl_user WITH PASSWORD 'eve@123' REPLICATION;

CREATE TABLE IF NOT EXISTS hba ( lines text );
COPY hba FROM '/var/lib/postgresql/data/pg_hba.conf';
INSERT INTO hba (lines) VALUES ('host replication all 0.0.0.0/0 scram-sha-256');
COPY hba TO '/var/lib/postgresql/data/pg_hba.conf';
SELECT pg_reload_conf();

CREATE TABLE IF NOT EXISTS emails (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS phone_numbers (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(30) NOT NULL
);

INSERT INTO emails (email) VALUES
('test1@example.com'),
('test2@example.com');

INSERT INTO phone_numbers (phone_number) VALUES
('1234567890'),
('0987654321');