-- Upgraded Produce & History Batches Table
CREATE TABLE IF NOT EXISTS produce_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farmer_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    farmer_phone TEXT NOT NULL DEFAULT '9876543210',
    crop_name TEXT NOT NULL,
    crop_status TEXT NOT NULL DEFAULT 'harvested',
    variety TEXT DEFAULT 'Desi / Local',
    field_name TEXT DEFAULT 'Field 1 (North Acre)',
    quantity_kg NUMERIC NOT NULL,
    input_unit TEXT DEFAULT 'kg',
    harvest_date DATE NOT NULL,
    planting_date DATE,
    suggested_harvest_date DATE,
    storage_type TEXT DEFAULT 'Ventilated Godown',
    quality_grade TEXT DEFAULT 'A',
    spoilage_risk TEXT DEFAULT 'Low',
    shelf_life_days INT DEFAULT 14,
    defect_summary TEXT,
    recommendation TEXT,
    processing_idea TEXT,
    
    -- Pre-Harvest / Production Costs
    production_cost NUMERIC DEFAULT 0,
    cost_breakdown JSONB DEFAULT '{}'::jsonb,
    
    -- Status Lifecycle: 'active' or 'sold'
    status TEXT DEFAULT 'active',
    
    -- Post-Harvest & Settlement Fields (Populated when Sold)
    sold_quantity_kg NUMERIC DEFAULT 0,
    selling_price_per_kg NUMERIC DEFAULT 0,
    selling_date DATE,
    selling_costs_breakdown JSONB DEFAULT '{}'::jsonb,
    total_selling_cost NUMERIC DEFAULT 0,
    total_combined_cost NUMERIC DEFAULT 0,
    total_revenue NUMERIC DEFAULT 0,
    net_profit_loss NUMERIC DEFAULT 0,
    next_crop_recommendation JSONB DEFAULT '[]'::jsonb,
    
    image_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE produce_batches ADD COLUMN IF NOT EXISTS farmer_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;
ALTER TABLE produce_batches ADD COLUMN IF NOT EXISTS crop_status TEXT NOT NULL DEFAULT 'harvested';
ALTER TABLE produce_batches ADD COLUMN IF NOT EXISTS planting_date DATE;
ALTER TABLE produce_batches ADD COLUMN IF NOT EXISTS suggested_harvest_date DATE;
CREATE INDEX IF NOT EXISTS produce_batches_farmer_id_idx ON produce_batches (farmer_id);

CREATE TABLE IF NOT EXISTS farmer_profiles (
    farmer_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL DEFAULT '',
    latitude NUMERIC,
    longitude NUMERIC,
    location_name TEXT DEFAULT '',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS farmer_profiles_farmer_id_idx ON farmer_profiles (farmer_id);

CREATE TABLE IF NOT EXISTS storage_facilities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    facility_type TEXT NOT NULL,
    available_capacity TEXT DEFAULT 'Contact facility',
    contact_number TEXT DEFAULT 'Not listed',
    latitude NUMERIC NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude NUMERIC NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    address TEXT DEFAULT '',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS storage_facilities_location_idx ON storage_facilities (latitude, longitude);

CREATE OR REPLACE FUNCTION find_nearest_facilities(
    user_lat NUMERIC,
    user_lng NUMERIC,
    max_distance_meters NUMERIC DEFAULT 50000
)
RETURNS TABLE (
    id UUID,
    name TEXT,
    facility_type TEXT,
    available_capacity TEXT,
    contact_number TEXT,
    latitude NUMERIC,
    longitude NUMERIC,
    address TEXT,
    distance_meters NUMERIC
)
LANGUAGE SQL
STABLE
AS $$
    WITH distances AS (
        SELECT
            sf.*,
            6371000 * 2 * ASIN(SQRT(
            POWER(SIN(RADIANS(sf.latitude - user_lat) / 2), 2) +
            COS(RADIANS(user_lat)) * COS(RADIANS(sf.latitude)) *
            POWER(SIN(RADIANS(sf.longitude - user_lng) / 2), 2)
            )) AS distance_meters
        FROM storage_facilities sf
        WHERE sf.is_active = TRUE
    )
    SELECT
        distances.id,
        distances.name,
        distances.facility_type,
        distances.available_capacity,
        distances.contact_number,
        distances.latitude,
        distances.longitude,
        distances.address,
        distances.distance_meters
    FROM distances
    WHERE distances.distance_meters <= max_distance_meters
    ORDER BY distance_meters
    LIMIT 100;
$$;