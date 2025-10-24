-- Fix the properties table insert with proper syntax

DELETE FROM properties;

INSERT INTO properties (price, location, property_type, amenities, details, created_at, company_id) VALUES
(250000, 'Miami Beach', 'Condo', '{"pool": true, "parking": true, "gym": true, "view": "ocean", "floor": "1"}', '{"view": "ocean", "floor": "1"}', '2023-10-22T08:53:00.000Z', 'd984203d-91a2-42d3-b9a4-cd138ed08541'),

(350000, 'Miami', 'Condo', '{"pool": true, "parking": true, "gym": true, "concierge": true}', '{"view": "city", "floor": "12"}', '2023-10-22T08:53:00.000Z', 'd984203d-91a2-42d3-b9a4-cd138ed08541'),

(500000, 'Coral Gables', 'House', '{"pool": true, "parking": true, "garden": true, "balcony": true}', '{"lot_size": "5000 sq ft", "garage": "2 car"}', '2023-10-22T08:53:00.000Z', 'd984203d-91a2-42d3-b9a4-cd138ed08541'),

(300000, 'Orlando', 'Condo', '{"parking": true, "gym": false}', '{"view": "park", "floor": "5"}', '2023-10-22T08:53:00.000Z', 'd984203d-91a2-42d3-b9a4-cd138ed08541'),

(450000, 'Tampa', 'Condo', '{"pool": true, "parking": true, "gym": true, "beach_access": true}', '{"view": "gulf", "floor": "2"}', '2023-10-22T08:53:00.000Z', 'd984203d-91a2-42d3-b9a4-cd138ed08541'),

(750000, 'Miami', 'House', '{"pool": true, "parking": true, "garden": true, "outdoor_kitchen": true}', '{"lot_size": "8000 sq ft", "garage": "3 car"}', '2023-10-22T08:53:00.000Z', 'd984203d-91a2-42d3-b9a4-cd138ed08541'),

(425000, 'Fort Lauderdale', 'Condo', '{"pool": true, "parking": true, "gym": true, "waterfront": true}', '{"view": "intracoastal", "floor": "8"}', '2023-10-22T08:53:00.000Z', 'd984203d-91a2-42d3-b9a4-cd138ed08541'),

(375000, 'West Palm Beach', 'House', '{"pool": false, "parking": true, "garden": true}', '{"lot_size": "6000 sq ft", "garage": "2 car"}', '2023-10-22T08:53:00.000Z', 'd984203d-91a2-42d3-b9a4-cd138ed08541');

SELECT 'Properties loaded successfully!' as status, COUNT(*) as property_count FROM properties;