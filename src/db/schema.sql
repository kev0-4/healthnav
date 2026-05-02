-- HBP Healthcare Navigator — Azure SQL Schema
-- Run via init_db.py, not directly.

IF OBJECT_ID('dbo.specialty_priority',       'U') IS NOT NULL DROP TABLE dbo.specialty_priority;
IF OBJECT_ID('dbo.clinical_pathways',        'U') IS NOT NULL DROP TABLE dbo.clinical_pathways;
IF OBJECT_ID('dbo.hospitals',                'U') IS NOT NULL DROP TABLE dbo.hospitals;
IF OBJECT_ID('dbo.procedures',               'U') IS NOT NULL DROP TABLE dbo.procedures;
IF OBJECT_ID('dbo.packages',                 'U') IS NOT NULL DROP TABLE dbo.packages;
IF OBJECT_ID('dbo.specialties',              'U') IS NOT NULL DROP TABLE dbo.specialties;
IF OBJECT_ID('dbo.bed_day_rates',            'U') IS NOT NULL DROP TABLE dbo.bed_day_rates;
IF OBJECT_ID('dbo.city_tier_map',            'U') IS NOT NULL DROP TABLE dbo.city_tier_map;
IF OBJECT_ID('dbo.hospital_type_multipliers','U') IS NOT NULL DROP TABLE dbo.hospital_type_multipliers;

-- ── Core HBP procedure hierarchy ──────────────────────────────────────────────

CREATE TABLE dbo.specialties (
    specialty_code  NVARCHAR(10)  NOT NULL PRIMARY KEY,
    specialty_name  NVARCHAR(255) NOT NULL
);

CREATE TABLE dbo.packages (
    package_code   NVARCHAR(20)  NOT NULL PRIMARY KEY,
    package_name   NVARCHAR(500) NOT NULL,
    specialty_code NVARCHAR(10)  NOT NULL REFERENCES dbo.specialties(specialty_code)
);

CREATE TABLE dbo.procedures (
    procedure_code     NVARCHAR(20)   NOT NULL PRIMARY KEY,
    procedure_name     NVARCHAR(500)  NULL,
    package_code       NVARCHAR(20)   NOT NULL REFERENCES dbo.packages(package_code),
    tier1_inr          INT            NULL,
    tier2_inr          INT            NULL,
    tier3_inr          INT            NULL,
    implant_mapped     BIT            NOT NULL DEFAULT 0,
    implant_cost_inr   INT            NULL,
    stratification_text NVARCHAR(MAX) NULL
);

-- ── Static reference / config tables ──────────────────────────────────────────

CREATE TABLE dbo.bed_day_rates (
    bed_category  NVARCHAR(50) NOT NULL PRIMARY KEY,
    rate_per_day  INT          NOT NULL,
    hbp_version   NVARCHAR(20) NOT NULL DEFAULT 'HBP_2022'
);

CREATE TABLE dbo.city_tier_map (
    city_name NVARCHAR(100) NOT NULL PRIMARY KEY,
    state     NVARCHAR(100) NOT NULL,
    tier      INT           NOT NULL,
    is_metro  BIT           NOT NULL DEFAULT 0,
    CONSTRAINT chk_tier CHECK (tier IN (1, 2, 3))
);

CREATE TABLE dbo.hospital_type_multipliers (
    hospital_type    NVARCHAR(50) NOT NULL PRIMARY KEY,
    multiplier_low   FLOAT        NOT NULL,
    multiplier_high  FLOAT        NOT NULL,
    notes            NVARCHAR(500) NULL
);

-- ── Clinical logic tables ──────────────────────────────────────────────────────

CREATE TABLE dbo.clinical_pathways (
    id               INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    condition_name   NVARCHAR(255)     NOT NULL,
    specialty_code   NVARCHAR(10)      NULL REFERENCES dbo.specialties(specialty_code),
    severity         NVARCHAR(20)      NOT NULL,
    step_order       INT               NOT NULL,
    step_type        NVARCHAR(50)      NULL,
    step_description NVARCHAR(MAX)     NOT NULL,
    procedure_code   NVARCHAR(20)      NULL REFERENCES dbo.procedures(procedure_code),
    bed_category     NVARCHAR(50)      NULL,
    los_days_low     INT               NULL,
    los_days_high    INT               NULL,
    hbp_covered      BIT               NOT NULL DEFAULT 1,
    notes            NVARCHAR(MAX)     NULL
);

-- ── Hospital directory (NHP / data.gov.in — 30k records) ─────────────────────

CREATE TABLE dbo.hospitals (
    hospital_id         INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    source_id           INT            NULL,          -- Sr_No from NHP directory
    hospital_name       NVARCHAR(500)  NOT NULL,
    hospital_category   NVARCHAR(100)  NULL,          -- raw: "Public/ Government", "Private", etc.
    hospital_type       NVARCHAR(50)   NULL,          -- derived: government | mid_private | corporate
    care_type           NVARCHAR(100)  NULL,          -- Hospital, Clinic, Dispensary, etc.
    discipline          NVARCHAR(100)  NULL,          -- Allopathic, Ayush, etc.
    address             NVARCHAR(500)  NULL,
    location            NVARCHAR(500)  NULL,          -- area/locality description
    state               NVARCHAR(100)  NULL,
    district            NVARCHAR(100)  NULL,
    pincode             NVARCHAR(10)   NULL,
    latitude            FLOAT          NULL,
    longitude           FLOAT          NULL,
    telephone           NVARCHAR(200)  NULL,
    mobile              NVARCHAR(100)  NULL,
    website             NVARCHAR(500)  NULL,
    specialties         NVARCHAR(MAX)  NULL,          -- comma-separated from source
    accreditation       NVARCHAR(500)  NULL,
    nabh_accredited     BIT            NOT NULL DEFAULT 0,
    total_beds          INT            NULL,
    emergency_services  BIT            NOT NULL DEFAULT 0,
    tariff_range        NVARCHAR(100)  NULL,
    state_id            INT            NULL,
    district_id         INT            NULL,
    google_rating       FLOAT          NULL,          -- populated later via Google Places API
    practo_rating       FLOAT          NULL           -- populated later via Practo scraper
);

-- ── Utilisation metadata ───────────────────────────────────────────────────────

CREATE TABLE dbo.specialty_priority (
    specialty_code NVARCHAR(10) NOT NULL PRIMARY KEY REFERENCES dbo.specialties(specialty_code),
    volume_rank    INT          NULL,
    cost_rank      INT          NULL,
    volume_pct     FLOAT        NULL,
    source         NVARCHAR(100) NULL
);
