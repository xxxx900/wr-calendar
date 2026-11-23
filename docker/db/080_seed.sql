-- Fictional local data. Dev users match scripts/dev_token.py.
INSERT INTO auth.users (id, email, raw_user_meta_data) VALUES
    ('11111111-1111-1111-1111-111111111111', 'admin@example.test', '{"full_name": "Local Admin"}'),
    ('22222222-2222-2222-2222-222222222222', 'resident@example.test', '{"full_name": "Local Resident"}'),
    ('33333333-3333-3333-3333-333333333333', 'calendar.admin@example.test', '{"full_name": "Local Calendar Admin"}');

INSERT INTO users (id, email, role) VALUES
    ('11111111-1111-1111-1111-111111111111', 'admin@example.test', 'admin'),
    ('22222222-2222-2222-2222-222222222222', 'resident@example.test', 'user'),
    ('33333333-3333-3333-3333-333333333333', 'calendar.admin@example.test', 'calendar_admin');

-- first_day is an offset from the first of this month; each template repeats 3 times, every_days apart.
WITH templates (title, description, location, host, start_hour, hours, all_day, fee, rsvp, audience, kids, adult, first_day, every_days) AS (
    VALUES
    ('Sunrise Yoga on the Lawn',   'Gentle flow for all levels. Bring a mat.',          'Willow Creek Lawn',      'paid_fitness',     7,  1,    false, true,  true,  'adult_friendly', false, true,  3,  14),
    ('Pinecrest Farmers Market',   'Local produce, baked goods and live music.',        'Pinecrest Pavilion',     'community',        9,  4,    false, false, false, 'all_ages',       true,  true,  5,  14),
    ('Taco Truck Tuesday',         'Rotating food trucks in the clubhouse lot.',        'Clubhouse Lot',          'food_truck',       17, 3,    false, true,  false, 'all_ages',       true,  true,  1,  14),
    ('Neighborhood Trivia Night',  'Teams of up to six. Prizes for the top three.',     'Willow Creek Clubhouse', 'hoa_event',        19, 2,    false, false, true,  'adult_friendly', false, true,  9,  14),
    ('Splash Pad Opening Day',     'Ribbon cutting and free popsicles.',                'Fairview Splash Pad',    'hoa_announcement', NULL, NULL, true, false, false, 'kids_friendly',   true,  false, 11, 14),
    ('Kids Craft Hour',            'Paper lanterns and friendship bracelets.',          'Willow Creek Library',   'community',        15, 1,    false, false, true,  'kids_friendly',  true,  false, 4,  10),
    ('Movie Night Under the Stars','Family film on the big inflatable screen.',         'Pinecrest Pavilion',     'hoa_event',        20, 2,    false, false, false, 'all_ages',       true,  true,  12, 14),
    ('Homeowner Garden Swap',      'Trade seedlings, cuttings and tools.',              '14 Example Lane',        'homeowner_hosted', 10, 2,    false, false, false, 'adult_friendly', false, true,  6,  14),
    ('HOA Board Meeting',          'Open session. Agenda posted a week ahead.',         'Willow Creek Clubhouse', 'hoa_announcement', 18, 1,    false, false, false, 'unspecified',    false, false, 14, 14),
    ('Pickleball Social',          'Casual doubles. Paddles available to borrow.',      'Fairview Courts',        'community',        8,  2,    false, false, false, 'adult_friendly', false, true,  2,  10)
)
INSERT INTO events (
    community_id, event_date, day_of_week, start_time_utc, end_time_utc, is_all_day, title, description,
    location, host_type, fee_required, rsvp_required, audience_tag, is_kids_friendly, is_adult_friendly
)
SELECT
    'wolf_ranch',
    d.event_date,
    trim(to_char(d.event_date, 'FMDay')),
    CASE WHEN t.all_day THEN NULL ELSE (d.event_date + make_time(t.start_hour, 0, 0)) AT TIME ZONE 'America/Chicago' END,
    CASE WHEN t.all_day THEN NULL ELSE (d.event_date + make_time(t.start_hour, 0, 0) + make_interval(hours => t.hours)) AT TIME ZONE 'America/Chicago' END,
    t.all_day, t.title, t.description, t.location,
    t.host::host_type, t.fee, t.rsvp, t.audience::audience_tag, t.kids, t.adult
FROM templates t
CROSS JOIN generate_series(0, 2) AS k
CROSS JOIN LATERAL (
    SELECT (date_trunc('month', current_date)::date + t.first_day + k * t.every_days) AS event_date
) d;

INSERT INTO events (community_id, event_date, day_of_week, is_all_day, title, description, location, host_type, is_deleted)
VALUES ('wolf_ranch', date_trunc('month', current_date)::date + 7, trim(to_char(date_trunc('month', current_date)::date + 7, 'FMDay')),
        true, 'Cancelled Bake Sale', 'Soft-deleted sample row.', 'Pinecrest Pavilion', 'community', true);

INSERT INTO event_reviews (event_id, user_id, rating, comment, attended_event, is_anonymous, is_deleted, deleted_at)
SELECT (SELECT id FROM events WHERE title = v.title AND NOT is_deleted ORDER BY event_date LIMIT 1),
       v.user_id::uuid, v.rating, v.comment, v.attended, v.anon, v.deleted, CASE WHEN v.deleted THEN now() END
FROM (VALUES
    ('Pinecrest Farmers Market',    '22222222-2222-2222-2222-222222222222', 5::smallint, 'Great variety and friendly vendors.', true,  false, false),
    ('Pinecrest Farmers Market',    '11111111-1111-1111-1111-111111111111', 4::smallint, 'Parking fills up early.',             true,  false, false),
    ('Neighborhood Trivia Night',   '22222222-2222-2222-2222-222222222222', 4::smallint, 'Fun, but the questions ran long.',    true,  true,  false),
    ('Neighborhood Trivia Night',   '33333333-3333-3333-3333-333333333333', 5::smallint, 'Won a gift card.',                    true,  false, false),
    ('Sunrise Yoga on the Lawn',    '11111111-1111-1111-1111-111111111111', 3::smallint, 'A bit crowded.',                      true,  false, false),
    ('Movie Night Under the Stars', '22222222-2222-2222-2222-222222222222', 5::smallint, 'Kids loved it.',                      true,  false, false),
    ('Movie Night Under the Stars', '33333333-3333-3333-3333-333333333333', 4::smallint, NULL,                                  false, false, false),
    ('Sunrise Yoga on the Lawn',    '22222222-2222-2222-2222-222222222222', 2::smallint, 'Removed by the author.',              false, false, true)
) AS v(title, user_id, rating, comment, attended, anon, deleted);

INSERT INTO event_reactions (event_id, user_id, reaction_type)
SELECT (SELECT id FROM events WHERE title = v.title AND NOT is_deleted ORDER BY event_date LIMIT 1), u.id, v.reaction
FROM (VALUES
    ('Pinecrest Farmers Market',    'going'),
    ('Taco Truck Tuesday',          'love'),
    ('Movie Night Under the Stars', 'helpful'),
    ('Neighborhood Trivia Night',   'going'),
    ('Pickleball Social',           'love')
) AS v(title, reaction)
CROSS JOIN (VALUES
    ('11111111-1111-1111-1111-111111111111'::uuid),
    ('22222222-2222-2222-2222-222222222222'::uuid),
    ('33333333-3333-3333-3333-333333333333'::uuid)
) AS u(id);
