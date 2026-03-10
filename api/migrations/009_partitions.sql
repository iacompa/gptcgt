-- Generate monthly partitions for usage_events and audit_log up to 2030

DO $$
DECLARE
    start_date DATE := '2026-05-01';
    end_date DATE := '2031-01-01';
    partition_date DATE := start_date;
    next_date DATE;
    partition_name TEXT;
    table_names TEXT[] := ARRAY['usage_events', 'audit_log'];
    tbl TEXT;
BEGIN
    WHILE partition_date < end_date LOOP
        next_date := partition_date + INTERVAL '1 month';
        
        FOREACH tbl IN ARRAY table_names LOOP
            -- Format partition name, e.g., usage_events_2026_05
            partition_name := format('%I_%s_%s', 
                                     tbl, 
                                     to_char(partition_date, 'YYYY'), 
                                     to_char(partition_date, 'MM'));
            
            -- Only attempt creation if it doesn't already exist
            -- (IF NOT EXISTS is supported natively in CREATE TABLE ... PARTITION OF)
            EXECUTE format(
                'CREATE TABLE IF NOT EXISTS %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L);',
                partition_name, tbl, partition_date, next_date
            );
        END LOOP;
        
        partition_date := next_date;
    END LOOP;
    
    -- Explicitly backfill the missing audit_log partition for 2026-04 to match usage_events
    CREATE TABLE IF NOT EXISTS audit_log_2026_04 PARTITION OF audit_log
        FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
END $$;
