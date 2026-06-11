-- =====================================================
-- MyHomeCircle MVP 1 - V4 Full PostgreSQL Schema
-- =====================================================
-- Final design includes:
-- - app_users
-- - auth_identities
-- - email_otp_codes
-- - addresses
-- - communities
-- - community_settings
-- - community_members
-- - community_join_requests
-- - vendors / quotes / reviews
-- - group buys / vendor proposals
-- - points / badges
-- =====================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 1. AUTH / USER TABLES
-- =====================================================

CREATE TABLE app_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    email CITEXT NOT NULL UNIQUE,
    full_name VARCHAR(150),
    avatar_url TEXT,

    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    last_login_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_app_users_status
        CHECK (status IN ('ACTIVE', 'PENDING', 'SUSPENDED', 'INACTIVE'))
);

CREATE TABLE auth_identities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    app_user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,

    provider VARCHAR(30) NOT NULL,
    provider_user_id TEXT NOT NULL,
    provider_email CITEXT,

    password_hash TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_auth_provider_identity UNIQUE (provider, provider_user_id),

    CONSTRAINT chk_auth_provider
        CHECK (provider IN ('GOOGLE', 'EMAIL_OTP', 'LOCAL_PASSWORD', 'AMAZON', 'APPLE')),

    CONSTRAINT chk_auth_identity_password
        CHECK (
            provider <> 'LOCAL_PASSWORD'
            OR password_hash IS NOT NULL
        )
);

CREATE TABLE email_otp_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    email CITEXT NOT NULL,
    otp_code VARCHAR(10) NOT NULL,

    purpose VARCHAR(30) NOT NULL DEFAULT 'LOGIN',
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,

    attempt_count INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 5,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_email_otp_purpose
        CHECK (purpose IN ('LOGIN', 'EMAIL_VERIFY')),

    CONSTRAINT chk_email_otp_attempts
        CHECK (attempt_count >= 0 AND max_attempts > 0)
);

-- =====================================================
-- 2. ADDRESS / COMMUNITY TABLES
-- =====================================================

CREATE TABLE addresses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    address_line_1 VARCHAR(255) NOT NULL,
    address_line_2 VARCHAR(255),

    locality VARCHAR(150),
    city VARCHAR(100),
    state VARCHAR(100),

    postal_code VARCHAR(20),
    country VARCHAR(100) NOT NULL DEFAULT 'India',

    latitude NUMERIC(10,7),
    longitude NUMERIC(10,7),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE communities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    name VARCHAR(150) NOT NULL,
    address_id UUID REFERENCES addresses(id) ON DELETE SET NULL,

    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_communities_status
        CHECK (status IN ('ACTIVE', 'INACTIVE'))
);

CREATE TABLE community_settings (
    community_id UUID PRIMARY KEY REFERENCES communities(id) ON DELETE CASCADE,

    require_admin_approval BOOLEAN NOT NULL DEFAULT TRUE,
    allow_anonymous_reviews BOOLEAN NOT NULL DEFAULT TRUE,
    allow_vendor_visibility BOOLEAN NOT NULL DEFAULT TRUE,
    points_enabled BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE community_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    app_user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    community_id UUID NOT NULL REFERENCES communities(id) ON DELETE CASCADE,

    villa_number VARCHAR(50),
    role VARCHAR(30) NOT NULL DEFAULT 'RESIDENT',
    total_points INT NOT NULL DEFAULT 0,
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING',

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_member_per_community UNIQUE (app_user_id, community_id),

    CONSTRAINT chk_community_members_role
        CHECK (role IN ('RESIDENT', 'MODERATOR', 'ADMIN')),

    CONSTRAINT chk_community_members_status
        CHECK (status IN ('PENDING', 'ACTIVE', 'REJECTED', 'SUSPENDED', 'INACTIVE')),

    CONSTRAINT chk_community_members_points_nonnegative
        CHECK (total_points >= 0)
);

CREATE TABLE community_join_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    app_user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    community_id UUID NOT NULL REFERENCES communities(id) ON DELETE CASCADE,

    villa_number VARCHAR(50),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    approved_by_member_id UUID REFERENCES community_members(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,

    status VARCHAR(30) NOT NULL DEFAULT 'PENDING',

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_join_request UNIQUE (app_user_id, community_id),

    CONSTRAINT chk_join_request_status
        CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED'))
);

-- =====================================================
-- 3. VENDOR / QUOTE TABLES
-- =====================================================

CREATE TABLE vendor_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    name VARCHAR(100) NOT NULL UNIQUE,
    display_order INT NOT NULL DEFAULT 0,
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_vendor_categories_status
        CHECK (status IN ('ACTIVE', 'INACTIVE'))
);

CREATE TABLE vendors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    community_id UUID NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
    category_id UUID NOT NULL REFERENCES vendor_categories(id),
    created_by_member_id UUID REFERENCES community_members(id) ON DELETE SET NULL,

    name VARCHAR(150) NOT NULL,
    contact_name VARCHAR(150),
    phone VARCHAR(20),
    email CITEXT,
    service_area TEXT,
    description TEXT,

    average_rating NUMERIC(3,2) NOT NULL DEFAULT 0,
    used_by_count INT NOT NULL DEFAULT 0,
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_vendor_per_community_category UNIQUE (community_id, category_id, name),

    CONSTRAINT chk_vendors_status
        CHECK (status IN ('ACTIVE', 'PENDING', 'SUSPENDED', 'INACTIVE')),

    CONSTRAINT chk_vendors_rating
        CHECK (average_rating >= 0 AND average_rating <= 5),

    CONSTRAINT chk_vendors_used_by
        CHECK (used_by_count >= 0)
);

CREATE TABLE quotes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    community_id UUID NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
    vendor_id UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    category_id UUID NOT NULL REFERENCES vendor_categories(id),
    uploaded_by_member_id UUID NOT NULL REFERENCES community_members(id) ON DELETE CASCADE,

    title VARCHAR(200) NOT NULL,
    quote_amount NUMERIC(12,2),
    currency VARCHAR(10) NOT NULL DEFAULT 'INR',
    quote_date DATE,

    warranty_details TEXT,
    notes TEXT,
    file_url TEXT,

    visibility VARCHAR(30) NOT NULL DEFAULT 'COMMUNITY',
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,

    extracted_json JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_quotes_amount
        CHECK (quote_amount IS NULL OR quote_amount >= 0),

    CONSTRAINT chk_quotes_visibility
        CHECK (visibility IN ('PRIVATE', 'COMMUNITY', 'ANONYMOUS_COMMUNITY'))
);

CREATE TABLE vendor_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    vendor_id UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    member_id UUID NOT NULL REFERENCES community_members(id) ON DELETE CASCADE,

    rating INT NOT NULL,
    review_text TEXT,
    project_amount NUMERIC(12,2),
    project_completed_on DATE,

    is_anonymous BOOLEAN NOT NULL DEFAULT FALSE,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_member_vendor_review UNIQUE (vendor_id, member_id),

    CONSTRAINT chk_vendor_reviews_rating
        CHECK (rating BETWEEN 1 AND 5),

    CONSTRAINT chk_vendor_reviews_amount
        CHECK (project_amount IS NULL OR project_amount >= 0)
);

-- =====================================================
-- 4. GROUP BUY TABLES
-- =====================================================

CREATE TABLE group_buys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    community_id UUID NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
    category_id UUID NOT NULL REFERENCES vendor_categories(id),
    created_by_member_id UUID NOT NULL REFERENCES community_members(id) ON DELETE CASCADE,
    selected_vendor_id UUID REFERENCES vendors(id) ON DELETE SET NULL,

    title VARCHAR(200) NOT NULL,
    description TEXT,

    target_participants INT,
    current_participants INT NOT NULL DEFAULT 0,
    expected_budget NUMERIC(12,2),
    closing_date DATE,

    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_group_buys_status
        CHECK (status IN ('DRAFT', 'ACTIVE', 'CLOSED', 'CANCELLED', 'COMPLETED')),

    CONSTRAINT chk_group_buys_target
        CHECK (target_participants IS NULL OR target_participants > 0),

    CONSTRAINT chk_group_buys_current
        CHECK (current_participants >= 0),

    CONSTRAINT chk_group_buys_budget
        CHECK (expected_budget IS NULL OR expected_budget >= 0)
);

CREATE TABLE group_buy_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    group_buy_id UUID NOT NULL REFERENCES group_buys(id) ON DELETE CASCADE,
    member_id UUID NOT NULL REFERENCES community_members(id) ON DELETE CASCADE,

    status VARCHAR(30) NOT NULL DEFAULT 'JOINED',
    joined_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_group_buy_member UNIQUE (group_buy_id, member_id),

    CONSTRAINT chk_group_buy_participant_status
        CHECK (status IN ('JOINED', 'LEFT', 'CONFIRMED'))
);

CREATE TABLE vendor_group_buy_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    group_buy_id UUID NOT NULL REFERENCES group_buys(id) ON DELETE CASCADE,
    vendor_id UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,

    proposal_amount NUMERIC(12,2),
    warranty_details TEXT,
    timeline_days INT,
    proposal_notes TEXT,

    status VARCHAR(30) NOT NULL DEFAULT 'SUBMITTED',

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_vendor_group_buy_proposal UNIQUE (group_buy_id, vendor_id),

    CONSTRAINT chk_vendor_group_buy_proposal_amount
        CHECK (proposal_amount IS NULL OR proposal_amount >= 0),

    CONSTRAINT chk_vendor_group_buy_timeline
        CHECK (timeline_days IS NULL OR timeline_days > 0),

    CONSTRAINT chk_vendor_group_buy_status
        CHECK (status IN ('SUBMITTED', 'SHORTLISTED', 'REJECTED', 'SELECTED', 'WITHDRAWN'))
);

-- =====================================================
-- 5. POINTS / BADGES TABLES
-- =====================================================

CREATE TABLE points_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    member_id UUID NOT NULL REFERENCES community_members(id) ON DELETE CASCADE,
    community_id UUID NOT NULL REFERENCES communities(id) ON DELETE CASCADE,

    event_type VARCHAR(50) NOT NULL,
    reference_type VARCHAR(50),
    reference_id UUID,

    points INT NOT NULL,
    description TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_points_nonzero
        CHECK (points <> 0),

    CONSTRAINT chk_points_event_type
        CHECK (
            event_type IN (
                'QUOTE_UPLOADED',
                'REVIEW_CREATED',
                'GROUP_BUY_CREATED',
                'GROUP_BUY_JOINED',
                'GROUP_BUY_SUCCESSFUL',
                'VENDOR_VERIFIED',
                'ADMIN_ADJUSTMENT'
            )
        )
);

CREATE TABLE badges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    name VARCHAR(50) NOT NULL UNIQUE,
    min_points INT NOT NULL,
    description TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_badges_min_points
        CHECK (min_points >= 0)
);

CREATE TABLE user_badges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    member_id UUID NOT NULL REFERENCES community_members(id) ON DELETE CASCADE,
    badge_id UUID NOT NULL REFERENCES badges(id) ON DELETE CASCADE,

    awarded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_member_badge UNIQUE (member_id, badge_id)
);

-- =====================================================
-- 6. TRIGGERS
-- =====================================================

CREATE TRIGGER trg_app_users_updated_at
BEFORE UPDATE ON app_users
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_auth_identities_updated_at
BEFORE UPDATE ON auth_identities
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_addresses_updated_at
BEFORE UPDATE ON addresses
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_communities_updated_at
BEFORE UPDATE ON communities
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_community_settings_updated_at
BEFORE UPDATE ON community_settings
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_community_members_updated_at
BEFORE UPDATE ON community_members
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_community_join_requests_updated_at
BEFORE UPDATE ON community_join_requests
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_vendor_categories_updated_at
BEFORE UPDATE ON vendor_categories
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_vendors_updated_at
BEFORE UPDATE ON vendors
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_quotes_updated_at
BEFORE UPDATE ON quotes
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_vendor_reviews_updated_at
BEFORE UPDATE ON vendor_reviews
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_group_buys_updated_at
BEFORE UPDATE ON group_buys
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_group_buy_participants_updated_at
BEFORE UPDATE ON group_buy_participants
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_vendor_group_buy_proposals_updated_at
BEFORE UPDATE ON vendor_group_buy_proposals
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_badges_updated_at
BEFORE UPDATE ON badges
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =====================================================
-- 7. INDEXES
-- =====================================================

CREATE INDEX idx_app_users_email ON app_users(email);

CREATE INDEX idx_auth_identities_app_user ON auth_identities(app_user_id);
CREATE INDEX idx_auth_identities_provider_email ON auth_identities(provider, provider_email);

CREATE INDEX idx_email_otp_email_created ON email_otp_codes(email, created_at DESC);
CREATE INDEX idx_email_otp_email_used_expires ON email_otp_codes(email, used_at, expires_at);

CREATE INDEX idx_addresses_city_state ON addresses(city, state);
CREATE INDEX idx_addresses_postal_code ON addresses(postal_code);
CREATE INDEX idx_addresses_lat_long ON addresses(latitude, longitude);

CREATE INDEX idx_communities_address ON communities(address_id);

CREATE INDEX idx_community_members_app_user ON community_members(app_user_id);
CREATE INDEX idx_community_members_community ON community_members(community_id);
CREATE INDEX idx_community_members_community_points ON community_members(community_id, total_points DESC);
CREATE INDEX idx_community_members_community_villa ON community_members(community_id, villa_number);

CREATE INDEX idx_join_requests_community_status ON community_join_requests(community_id, status);
CREATE INDEX idx_join_requests_app_user ON community_join_requests(app_user_id);

CREATE INDEX idx_vendors_community_category ON vendors(community_id, category_id);
CREATE INDEX idx_vendors_rating_used ON vendors(community_id, used_by_count DESC, average_rating DESC);

CREATE INDEX idx_quotes_community_category ON quotes(community_id, category_id);
CREATE INDEX idx_quotes_vendor ON quotes(vendor_id);
CREATE INDEX idx_quotes_uploaded_by_member ON quotes(uploaded_by_member_id);
CREATE INDEX idx_quotes_extracted_json_gin ON quotes USING GIN (extracted_json);

CREATE INDEX idx_vendor_reviews_vendor ON vendor_reviews(vendor_id);
CREATE INDEX idx_vendor_reviews_member ON vendor_reviews(member_id);

CREATE INDEX idx_group_buys_community_status ON group_buys(community_id, status, closing_date);
CREATE INDEX idx_group_buys_created_by_member ON group_buys(created_by_member_id);

CREATE INDEX idx_group_buy_participants_group ON group_buy_participants(group_buy_id);
CREATE INDEX idx_group_buy_participants_member ON group_buy_participants(member_id);

CREATE INDEX idx_vendor_group_buy_proposals_group ON vendor_group_buy_proposals(group_buy_id);
CREATE INDEX idx_vendor_group_buy_proposals_vendor ON vendor_group_buy_proposals(vendor_id);

CREATE INDEX idx_points_ledger_member_created ON points_ledger(member_id, created_at DESC);
CREATE INDEX idx_points_ledger_community_event ON points_ledger(community_id, event_type);

-- =====================================================
-- 8. SEED DATA
-- =====================================================

INSERT INTO vendor_categories(name, display_order) VALUES
('Solar', 1),
('Interior', 2),
('Water Softener', 3),
('Pest Control', 4),
('CCTV', 5),
('EV Charger', 6),
('Broadband', 7),
('Home Automation', 8)
ON CONFLICT (name) DO NOTHING;

INSERT INTO badges(name, min_points, description) VALUES
('Bronze', 0, 'New contributor'),
('Silver', 500, 'Helpful contributor'),
('Gold', 1500, 'Trusted community contributor'),
('Platinum', 5000, 'Top community contributor')
ON CONFLICT (name) DO NOTHING;
