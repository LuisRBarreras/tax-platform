-- Runs only the first time the MySQL volume is created.
-- The application database is created by MYSQL_DATABASE; this adds the schema used
-- by the test suite and grants the application user access to both.
CREATE DATABASE IF NOT EXISTS tax_platform_test
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

GRANT ALL PRIVILEGES ON tax_platform.* TO 'tax'@'%';
GRANT ALL PRIVILEGES ON tax_platform_test.* TO 'tax'@'%';
FLUSH PRIVILEGES;
