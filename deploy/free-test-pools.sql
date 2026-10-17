-- Pinned Sub2API v0.2.16: standard mode preserves group isolation.
-- Its admin API rejects zero multipliers; billing accepts zero correctly.
-- Run ONLY on this private pilot after backup, with the three group IDs.
\set ON_ERROR_STOP on
BEGIN;
CREATE TEMP TABLE free_pool_ids AS
SELECT DISTINCT unnest(ARRAY[:plus_group_id, :pro_group_id, :auto_group_id]::bigint[]) AS id;
DO $$ BEGIN
  IF (SELECT count(*) FROM free_pool_ids) <> 3 OR
     (SELECT count(*) FROM groups g JOIN free_pool_ids p USING (id)
      WHERE g.platform = 'openai' AND g.status = 'active' AND g.deleted_at IS NULL) <> 3 THEN
    RAISE EXCEPTION 'Expected three distinct active OpenAI pilot groups';
  END IF;
END $$;
UPDATE groups SET rate_multiplier = 0, updated_at = now()
WHERE id IN (SELECT id FROM free_pool_ids);
COMMIT;
