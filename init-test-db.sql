-- Create a separate test database for pytest.
-- This runs on first PostgreSQL container startup only.
CREATE DATABASE noteme_test
    OWNER noteme
    ENCODING 'UTF8'
    LC_COLLATE = 'en_US.utf8'
    LC_CTYPE = 'en_US.utf8';
