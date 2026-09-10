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

