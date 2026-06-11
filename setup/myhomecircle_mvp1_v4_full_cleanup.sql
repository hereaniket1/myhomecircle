-- =====================================================
-- MyHomeCircle MVP 1 - V4 Full Cleanup Script
-- =====================================================
-- WARNING:
-- This deletes all MyHomeCircle schema objects.
-- Use only in development/test unless you know exactly what you are doing.
-- =====================================================

DROP TABLE IF EXISTS user_badges CASCADE;
DROP TABLE IF EXISTS badges CASCADE;
DROP TABLE IF EXISTS points_ledger CASCADE;

DROP TABLE IF EXISTS vendor_group_buy_proposals CASCADE;
DROP TABLE IF EXISTS group_buy_participants CASCADE;
DROP TABLE IF EXISTS group_buys CASCADE;

DROP TABLE IF EXISTS vendor_reviews CASCADE;
DROP TABLE IF EXISTS quotes CASCADE;
DROP TABLE IF EXISTS vendors CASCADE;
DROP TABLE IF EXISTS vendor_categories CASCADE;

DROP TABLE IF EXISTS community_join_requests CASCADE;
DROP TABLE IF EXISTS community_members CASCADE;
DROP TABLE IF EXISTS community_settings CASCADE;
DROP TABLE IF EXISTS communities CASCADE;
DROP TABLE IF EXISTS addresses CASCADE;

DROP TABLE IF EXISTS email_otp_codes CASCADE;
DROP TABLE IF EXISTS auth_identities CASCADE;
DROP TABLE IF EXISTS app_users CASCADE;

DROP FUNCTION IF EXISTS set_updated_at() CASCADE;

-- Extensions are intentionally not dropped because other objects may use them.
-- DROP EXTENSION IF EXISTS citext;
-- DROP EXTENSION IF EXISTS pgcrypto;
