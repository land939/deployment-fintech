-- Initialize PostgreSQL database for GTA Fintech

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create schemas
CREATE SCHEMA IF NOT EXISTS public;

-- Set timezone
SET timezone = 'UTC';

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_email ON public.user (email) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON public.transaction (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fraud_alerts_address ON public.fraudalert (suspect_address);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON public.auditlog (timestamp DESC);

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE gta_fintech TO gta_user;
GRANT ALL PRIVILEGES ON SCHEMA public TO gta_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO gta_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO gta_user;

-- Set default privileges
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO gta_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO gta_user;

-- Log initialization
SELECT 'GTA Fintech database initialized successfully' as status;
